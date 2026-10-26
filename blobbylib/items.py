"""Loaders for items.yaml and collections.yaml manifest files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


_VALID_GENERATIONS = {"classic", "new"}
_VALID_KINDS = {"emoji", "sticker", "illustration", "animation"}
_VALID_SOURCES = {"slack", "figma-illustrations", "figma-stickers", "website", "master"}

# Kinds that default slack_name to the slug when no explicit value is given.
_SLACK_NAME_DEFAULT_KINDS = {"emoji", "animation"}


class ItemError(ValueError):
    """Raised when an item in items.yaml fails validation.

    The message includes the offending slug and field name.
    """


@dataclass(frozen=True)
class Item:
    slug: str
    display_name: str
    slack_name: str | None
    generation: str
    kind: str
    collection: str
    tags: list[str]
    author: str | None
    source: str
    svg: str | None
    note: str | None
    listed: bool = True
    unlisted_reason: str | None = None


@dataclass(frozen=True)
class Collection:
    slug: str
    name: str
    order: int
    description: str
    cover: str | None


def _deduplicate(seq: list[str]) -> list[str]:
    """Return seq with duplicates removed, preserving first-occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def load_items(path: Path) -> dict[str, Item]:
    """Load items.yaml and return a dict of slug -> Item.

    Explicit ``slack_name: null`` in YAML means None (item no longer in Slack).
    An absent ``slack_name`` key means the kind-based default: slug for emoji/
    animation, None for all other kinds.

    Raises ItemError when a required field is missing or has an invalid value.
    """
    raw_text = Path(path).read_text()
    data: dict[str, Any] = yaml.safe_load(raw_text) or {}

    items: dict[str, Item] = {}
    for slug, fields in data.items():
        fields = fields or {}

        def _require(field: str) -> Any:
            if field not in fields:
                raise ItemError(f"{slug}: missing required field '{field}'")
            return fields[field]

        display_name: str = _require("display_name")
        generation: str = _require("generation")
        kind: str = _require("kind")
        collection: str = _require("collection")
        source: str = _require("source")

        if generation not in _VALID_GENERATIONS:
            raise ItemError(
                f"{slug}: invalid generation {generation!r}; "
                f"must be one of {sorted(_VALID_GENERATIONS)}"
            )
        if kind not in _VALID_KINDS:
            raise ItemError(
                f"{slug}: invalid kind {kind!r}; "
                f"must be one of {sorted(_VALID_KINDS)}"
            )
        if source not in _VALID_SOURCES:
            raise ItemError(
                f"{slug}: invalid source {source!r}; "
                f"must be one of {sorted(_VALID_SOURCES)}"
            )

        # slack_name: explicit null -> None; absent key -> kind-based default
        if "slack_name" in fields:
            slack_name: str | None = fields["slack_name"]  # may be None
        elif kind in _SLACK_NAME_DEFAULT_KINDS:
            slack_name = slug
        else:
            slack_name = None

        raw_tags: list[Any] = fields.get("tags") or []
        tags = _deduplicate([str(t).lower() for t in raw_tags])

        author: str | None = fields.get("author")
        svg: str | None = fields.get("svg")
        note: str | None = fields.get("note")

        # listed: optional boolean, defaults to True
        if "listed" in fields:
            raw_listed = fields["listed"]
            if not isinstance(raw_listed, bool):
                raise ItemError(
                    f"{slug}: 'listed' must be true or false, got {raw_listed!r}"
                )
            listed: bool = raw_listed
        else:
            listed = True

        unlisted_reason: str | None = fields.get("unlisted_reason")

        items[slug] = Item(
            slug=slug,
            display_name=display_name,
            slack_name=slack_name,
            generation=generation,
            kind=kind,
            collection=collection,
            tags=tags,
            author=author,
            source=source,
            svg=svg,
            note=note,
            listed=listed,
            unlisted_reason=unlisted_reason,
        )

    return items


def load_collections(path: Path) -> dict[str, Collection]:
    """Load collections.yaml and return an ordered dict of slug -> Collection.

    The dict is ordered by ``order`` ascending.
    """
    raw_text = Path(path).read_text()
    data: list[dict[str, Any]] = yaml.safe_load(raw_text) or []

    collections = [
        Collection(
            slug=entry["slug"],
            name=entry["name"],
            order=int(entry["order"]),
            description=entry["description"],
            cover=entry.get("cover"),
        )
        for entry in data
    ]

    collections.sort(key=lambda c: c.order)
    return {c.slug: c for c in collections}
