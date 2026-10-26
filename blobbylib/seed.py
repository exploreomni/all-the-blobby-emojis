"""Seed stub entries for items.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def seed_entries(
    files: list[str],
    existing: dict[str, Any],
) -> dict[str, dict]:
    """Return YAML-ready stub entries for files that have no item yet.

    Args:
        files: Repo-relative paths to image files.
               Raster files live under ``all-the-slack-blobbies/``;
               SVG files live under ``svg/``.
        existing: Current slug -> Item mapping (any truthy value is a hit).

    Returns:
        Dict of slug -> stub fields for files with no existing entry.
        The source field is always ``slack`` for raster or
        ``figma-illustrations`` for SVG; callers that need ``figma-stickers``
        should override that field after calling this function.
    """
    entries: dict[str, dict] = {}

    for file_path in files:
        name = os.path.basename(file_path)
        # Strip extension
        stem, ext = os.path.splitext(name)
        ext_lower = ext.lower()

        slug = stem

        if slug in existing:
            continue

        # Determine generation, kind, source from path and extension
        if file_path.startswith("all-the-slack-blobbies/"):
            generation = "classic"
            source = "slack"
            if ext_lower == ".gif":
                kind = "animation"
            else:
                kind = "emoji"
        else:
            # SVG
            generation = "new"
            kind = "illustration"
            source = "figma-illustrations"

        display_name = slug.replace("-", " ").title()

        entries[slug] = {
            "display_name": display_name,
            "generation": generation,
            "kind": kind,
            "collection": "unsorted",
            "tags": [],
            "source": source,
        }

    return entries
