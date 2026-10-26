#!/usr/bin/env python3
"""Export Blobby download packs to dist/packs (or --out PATH).

Usage:
    python3 scripts/export_packs.py
    python3 scripts/export_packs.py --out dist/packs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from blobbylib.items import load_collections
from blobbylib.packs import write_packs


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Blobby download packs")
    parser.add_argument(
        "--out",
        default="dist/packs",
        help="Output directory (default: dist/packs)",
    )
    args = parser.parse_args()

    manifest_path = REPO_ROOT / "manifest.json"
    if not manifest_path.exists():
        print("Error: manifest.json not found; run build_manifest.py first", file=sys.stderr)
        sys.exit(1)

    with manifest_path.open() as f:
        records = json.load(f)

    collections = load_collections(REPO_ROOT / "collections.yaml")
    out_path = REPO_ROOT / args.out

    try:
        paths = write_packs(records, collections, REPO_ROOT, out_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    for p in paths:
        size_kb = p.stat().st_size / 1024
        print(f"{p}  {size_kb:.1f} KB")


if __name__ == "__main__":
    main()
