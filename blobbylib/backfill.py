"""Vision-assisted tag backfill for Blobby emoji items."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Callable

import yaml

from blobbylib.vocab import Vocab


@dataclass
class Proposal:
    """A proposed update for one Blobby item."""

    slug: str
    display_name: str
    collection: str
    tags: list[str]
    generation: str
    confidence: float
    free_tags: list[str] = field(default_factory=list)
    description: str = ""


def _build_prompt(record: dict, vocab: Vocab) -> str:
    """Build the tagging prompt for the Claude API call."""
    slug = record.get("slug", "unknown")

    # Exclude curator-only collections: classic, animated, and unsorted are
    # assigned by humans, not the model.
    _CURATOR_ONLY = {"classic", "animated", "unsorted"}
    collections_text = "\n".join(
        f"  - {slug_}: {desc}"
        for slug_, desc in vocab.collections.items()
        if slug_ not in _CURATOR_ONLY
    )
    tags_text = ", ".join(sorted(vocab.tags))

    examples = (
        '{"slug":"blobby-paris-2","display_name":"Paris Blobby","collection":"cities",'
        '"tags":["city","hat"],"free_tags":["baguette"],'
        '"description":"Blobby wears a beret and holds a baguette.",'
        '"generation":"new","confidence":0.92}\n'
        '{"slug":"blobby-dbt","display_name":"dbt Blobby","collection":"partners",'
        '"tags":["dbt","data"],"free_tags":[],'
        '"description":"Blobby dressed in dbt partner branding.",'
        '"generation":"new","confidence":0.95}\n'
        '{"slug":"blobby-gingerbread","display_name":"Gingerbread Blobby","collection":"holidays",'
        '"tags":["christmas","cookie"],"free_tags":[],'
        '"description":"Blobby shaped like a gingerbread cookie.",'
        '"generation":"new","confidence":0.88}\n'
        '{"slug":"blobby-yells-at-jonny","display_name":"Yells at Jonny","collection":"unsorted",'
        '"tags":[],"free_tags":["jonny"],'
        '"description":"Blobby appears to be yelling at someone named Jonny.",'
        '"generation":"new","confidence":0.3}'
    )

    return f"""You are tagging a Slack emoji image. The subject is Blobby, Omni Analytics' pink blob mascot.
slug: {slug}

The slug is the strongest clue. Decode it first (people, places, brands, puns, pop culture), then confirm with the image.

Two visual generations:
- classic: gradient fill, dark outline, older style
- new: flat hot-pink fill (#FF3366), clean modern style

Collections (pick the single best fit):
{collections_text}

Collection rules:
- Use `reactions` only for plain expressions or gestures.
- If the slug names a company, product, or sports team: use `partners` only for dbt, Snowflake, Databricks, or MotherDuck; otherwise tag it `brand` and pick the collection by what the picture shows.

Tags:
- Pick 2-6 tags total.
- Prefer words from the vocabulary: {tags_text}
- You may include up to 2 free_tags not in the vocabulary when no vocab word fits.
- Forbidden as tags unless nothing else applies: happy, blobby, pink, emoji, cute

description: One plain sentence, under 15 words, describing what Blobby is doing or dressed as, written so someone could search it.

Worked examples (not real items):
{examples}

Output: one JSON object, no markdown:
{{"display_name": "...", "collection": "...", "tags": [...], "free_tags": [...], "description": "...", "generation": "...", "confidence": 0.0}}"""


def propose(
    record: dict,
    image_bytes: bytes,
    vocab: Vocab,
    ask: Callable[[str, bytes, str], str],
) -> Proposal:
    """Propose display_name, collection, tags, generation, and confidence for one item.

    Parameters
    ----------
    record:
        A manifest record dict (must contain at least 'slug').
    image_bytes:
        Raw PNG bytes to send to the model (always PNG; callers must convert).
    vocab:
        The Vocab instance holding valid tags and collection slugs.
    ask:
        Injected model call: ask(prompt, image_bytes, media_type) -> JSON text.
    """
    prompt = _build_prompt(record, vocab)
    raw = ask(prompt, image_bytes, "image/png")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: decode the first JSON object even if the model added text
        # before or after it (raw_decode stops at the object's closing brace).
        start = raw.find("{")
        try:
            data = json.JSONDecoder().raw_decode(raw[start:])[0] if start != -1 else {}
        except json.JSONDecodeError:
            data = {}

    display_name: str = str(data.get("display_name", record.get("slug", "unknown")))
    raw_collection: str = str(data.get("collection", "unsorted"))
    raw_tags: list = data.get("tags", [])
    raw_free_tags: list = data.get("free_tags", [])
    generation: str = str(data.get("generation", "classic"))
    confidence: float = float(data.get("confidence", 0.0))

    # Validate against vocab; also reject curator-only collections the model
    # should never choose (classic, animated, unsorted).
    _MODEL_FORBIDDEN = {"classic", "animated", "unsorted"}
    if raw_collection in _MODEL_FORBIDDEN:
        collection = "unsorted"
    else:
        collection = vocab.valid_collection(raw_collection)

    # Separate vocab tags from non-vocab tags in the model's `tags` field.
    raw_tags_lower = [str(t).lower() for t in raw_tags]
    tags = vocab.valid_tags(raw_tags_lower)
    non_vocab_from_tags = [t for t in raw_tags_lower if t not in vocab.tags]

    # Build free_tags: non-vocab from `tags` + explicit `free_tags`, lowercased,
    # deduplicated against vocab words and against each other, capped at 2.
    raw_free_lower = [str(t).lower() for t in raw_free_tags]
    combined_candidates = non_vocab_from_tags + raw_free_lower
    free_tags: list[str] = []
    seen_free: set[str] = set()
    for t in combined_candidates:
        if t not in vocab.tags and t not in seen_free:
            free_tags.append(t)
            seen_free.add(t)
            if len(free_tags) == 2:
                break

    # generation must be classic or new; default to classic if invalid.
    if generation not in {"classic", "new"}:
        generation = "classic"

    # description: strip and truncate to 120 chars.
    description = str(data.get("description", "")).strip()[:120]

    return Proposal(
        slug=record.get("slug", ""),
        display_name=display_name,
        collection=collection,
        tags=tags,
        generation=generation,
        confidence=confidence,
        free_tags=free_tags,
        description=description,
    )


def merge_proposals(items_yaml_text: str, proposals: list[Proposal]) -> str:
    """Apply proposals to items YAML text; only updates entries with collection 'unsorted'.

    Returns the updated YAML text. Uses yaml.safe_load / yaml.safe_dump so all
    other fields (including slack_name and note) are preserved exactly.
    """
    data: dict = yaml.safe_load(items_yaml_text) or {}

    by_slug = {p.slug: p for p in proposals}

    for slug, fields in data.items():
        if fields is None:
            continue
        if fields.get("collection") != "unsorted":
            continue
        proposal = by_slug.get(slug)
        if proposal is None:
            continue
        # Replace only the four target fields.
        fields["display_name"] = proposal.display_name
        fields["collection"] = proposal.collection
        fields["tags"] = proposal.tags
        fields["generation"] = proposal.generation
        # Write description into note only when the entry has no note or it is empty.
        if proposal.description and not fields.get("note"):
            fields["note"] = proposal.description

    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


# ---------------------------------------------------------------------------
# Real `ask` implementations
# ---------------------------------------------------------------------------

def _make_ask_urllib(urlopen=None) -> Callable[[str, bytes, str], str]:
    """Build an `ask` function that uses urllib (no third-party SDK required).

    Parameters
    ----------
    urlopen:
        Injectable replacement for ``urllib.request.urlopen`` (for tests).
    """
    import base64
    import urllib.request

    _urlopen = urlopen if urlopen is not None else urllib.request.urlopen

    def ask(prompt: str, image_bytes: bytes, media_type: str) -> str:
        image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
        payload = json.dumps({
            "model": "claude-opus-5-5",
            "max_tokens": 1024,
            "output_config": {"effort": "low"},
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with _urlopen(req) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        for block in body.get("content", []):
            if block.get("type") == "text":
                return block["text"]
        return "{}"

    return ask


def _make_ask() -> Callable[[str, bytes, str], str]:
    """Return the best available `ask` function.

    Tries the ``anthropic`` SDK first; falls back to ``urllib`` if the SDK is
    not installed.  The API key is read from ``ANTHROPIC_API_KEY`` at call
    time, never at import time.
    """
    import base64

    try:
        import anthropic  # type: ignore[import]
    except ImportError:
        return _make_ask_urllib()

    # SDK available: create the client once and close over it.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    def ask(prompt: str, image_bytes: bytes, media_type: str) -> str:
        """Call claude-opus-5-5 with the prompt and image; return raw JSON text."""
        image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
        response = client.messages.create(
            model="claude-opus-5-5",
            max_tokens=1024,
            output_config={"effort": "low"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        return "{}"

    return ask
