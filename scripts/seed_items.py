#!/usr/bin/env python3
"""CLI: append missing stub entries to items.yaml.

Usage:
    python3 scripts/seed_items.py [--items PATH]

Scans all-the-slack-blobbies/ (raster) and svg/ (SVG), then appends stub
entries for any slug not already in items.yaml. Preserves existing content
and key order. Exits 0 always.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.items import load_items  # noqa: E402
from blobbylib.seed import seed_entries  # noqa: E402

# Slugs that originated in the Figma stickers folder.
# These get source=figma-stickers instead of figma-illustrations.
_STICKER_SLUGS: frozenset[str] = frozenset({
    "blobby-bat",
    "blobby-big-eyes",
    "blobby-bumble",
    "blobby-cat",
    "blobby-cold-face",
    "blobby-elf",
    "blobby-frankenstein",
    "blobby-from-the-black-lagoon-2",
    "blobby-ghost",
    "blobby-gingerbread",
    "blobby-imp",
    "blobby-mummy",
    "blobby-nutcracker",
    "blobby-penguin",
    "blobby-polar-bear",
    "blobby-reindeer",
    "blobby-snow-globe",
    "blobby-werewolf-2",
    "blobby-whats-in-the-box",
    "blobby-zombie",
})

REPO_ROOT = Path(__file__).resolve().parents[1]
_RASTER_EXTS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}


def collect_raster_files(root: Path) -> list[str]:
    folder = root / "all-the-slack-blobbies"
    if not folder.is_dir():
        return []
    paths = []
    for p in sorted(folder.iterdir()):
        if p.is_file() and p.suffix.lower() in _RASTER_EXTS:
            paths.append(f"all-the-slack-blobbies/{p.name}")
    return paths


def collect_svg_files(root: Path) -> list[str]:
    folder = root / "svg"
    if not folder.is_dir():
        return []
    return [f"svg/{p.name}" for p in sorted(folder.iterdir()) if p.suffix.lower() == ".svg"]


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Append missing stub entries to items.yaml.")
    parser.add_argument("--items", default="items.yaml", help="Path to items.yaml.")
    args = parser.parse_args()

    items_path = REPO_ROOT / args.items

    # Load existing items (if file exists)
    if items_path.exists():
        existing = load_items(items_path)
        # Also read raw YAML to preserve existing content exactly
        raw_text = items_path.read_text(encoding="utf-8")
        existing_data: dict = yaml.safe_load(raw_text) or {}
    else:
        existing = {}
        existing_data = {}

    raster_files = collect_raster_files(REPO_ROOT)
    svg_files = collect_svg_files(REPO_ROOT)

    # Seed raster first so existing raster slugs block duplicate svg entries.
    raster_entries = seed_entries(raster_files, existing)

    # SVG entries only for slugs not already in items.yaml or covered by a raster entry.
    combined_existing = {**existing, **raster_entries}
    svg_entries = seed_entries(svg_files, combined_existing)

    # Override source for sticker slugs
    for slug, entry in svg_entries.items():
        if slug in _STICKER_SLUGS:
            entry["source"] = "figma-stickers"

    new_entries = {**raster_entries, **svg_entries}

    if not new_entries:
        print("No new entries to add.")
        return

    # Merge new entries into existing data preserving order
    merged = {**existing_data, **new_entries}

    items_path.write_text(
        yaml.safe_dump(merged, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    raster_count = len(raster_entries)
    svg_count = len(svg_entries)
    print(f"Added {len(new_entries)} new entries ({raster_count} raster, {svg_count} svg-only) to {items_path.relative_to(REPO_ROOT)}")
    print(f"Total entries: {len(merged)}")


if __name__ == "__main__":
    main()
