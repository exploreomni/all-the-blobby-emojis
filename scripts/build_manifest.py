#!/usr/bin/env python3
"""CLI: build manifest.json from items.yaml, collections.yaml, and the image files.

Usage:
    python3 scripts/build_manifest.py [--ref main] [--pinned-ref <tag>] [--out manifest.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.items import load_collections, load_items  # noqa: E402
from blobbylib.manifest import build_manifest  # noqa: E402
from blobbylib.urls import parse_github_remote, run_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build manifest.json from items.yaml and image files.",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref used in generated jsDelivr and GitHub URLs.",
    )
    parser.add_argument(
        "--pinned-ref",
        default=None,
        help="Pinned git ref (e.g. a tag) for cdn_pinned URLs. Omit to leave cdn_pinned null.",
    )
    parser.add_argument(
        "--out",
        default="manifest.json",
        help="Output path for manifest.json (relative to repo root or absolute).",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote used to derive the GitHub owner and repo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    items_path = REPO_ROOT / "items.yaml"
    collections_path = REPO_ROOT / "collections.yaml"

    try:
        items = load_items(items_path)
        load_collections(collections_path)  # validate collections exist
    except (FileNotFoundError, Exception) as err:
        print(f"error loading data: {err}", file=sys.stderr)
        return 1

    try:
        owner, repo = parse_github_remote(run_git("remote", "get-url", args.remote))
    except Exception:
        # Fall back to repo directory name if remote is unavailable.
        owner = "exploreomni"
        repo = REPO_ROOT.name

    records = build_manifest(
        root=REPO_ROOT,
        items=items,
        owner=owner,
        repo=repo,
        ref=args.ref,
        pinned_ref=args.pinned_ref,
        today=date.today(),
    )

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    out_path.write_text(
        json.dumps(records, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(records)} records to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
