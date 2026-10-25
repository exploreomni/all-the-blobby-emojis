"""Vision-assisted tag backfill for Blobby emoji items."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
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


def _build_prompt(record: dict, vocab: Vocab) -> str:
    """Build the tagging prompt for the Claude API call."""
    slug = record.get("slug", "unknown")

    collections_text = "\n".join(
        f"  - {slug_}: {desc}" for slug_, desc in vocab.collections.items()
    )
    tags_text = ", ".join(sorted(vocab.tags))

    return f"""You are tagging an image of Omni's Blobby mascot emoji (slug: {slug}).

Blobby is a simple blob character used as an emoji/reaction pack. Two visual generations exist:
- classic: gradient fill, dark outline, older style
- new: flat hot-pink fill (#FF3366), clean modern style

Your task: return a single JSON object (no markdown, no explanation) with these fields:
{{
  "display_name": "<short human-readable title, 1-4 words, title case>",
  "collection": "<one of the collection slugs below>",
  "tags": ["<tag>", ...],
  "generation": "<classic or new>",
  "confidence": <0.0-1.0>
}}

Available collections (pick the single best fit):
{collections_text}

Available tags (only use words from this list; pick 1-4 that best describe the image):
{tags_text}

Respond with valid JSON only."""


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
        # Fallback: extract JSON substring if the model added text around it.
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end]) if start != -1 else {}

    display_name: str = str(data.get("display_name", record.get("slug", "unknown")))
    raw_collection: str = str(data.get("collection", "unsorted"))
    raw_tags: list = data.get("tags", [])
    generation: str = str(data.get("generation", "classic"))
    confidence: float = float(data.get("confidence", 0.0))

    # Validate against vocab.
    collection = vocab.valid_collection(raw_collection)
    tags = vocab.valid_tags([str(t).lower() for t in raw_tags])

    # generation must be classic or new; default to classic if invalid.
    if generation not in {"classic", "new"}:
        generation = "classic"

    return Proposal(
        slug=record.get("slug", ""),
        display_name=display_name,
        collection=collection,
        tags=tags,
        generation=generation,
        confidence=confidence,
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
            "model": "claude-haiku-5-5",
            "max_tokens": 512,
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
        """Call claude-haiku-5-5 with the prompt and image; return raw JSON text."""
        image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
        response = client.messages.create(
            model="claude-haiku-5-5",
            max_tokens=512,
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
