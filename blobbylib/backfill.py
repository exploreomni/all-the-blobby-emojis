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
        Raw image bytes to send to the model.
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
# Real `ask` implementation using the Anthropic SDK
# ---------------------------------------------------------------------------

def _make_ask():
    """Return the real `ask` function that calls the Claude API.

    The ANTHROPIC_API_KEY is read at call time (not at module import time) so
    that tests that inject a fake `ask` are never blocked by a missing key.
    """
    import base64
    import anthropic  # type: ignore[import]

    def ask(prompt: str, image_bytes: bytes, media_type: str) -> str:
        """Call claude-haiku-5-5 with the prompt and image; return raw JSON text."""
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
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
