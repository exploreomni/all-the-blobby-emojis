#!/usr/bin/env python3
"""CLI: validate the manifest against Slack emoji limits and repo rules.

Usage:
    python3 scripts/validate.py [--strict]

Exits 0 on success, 1 on validation errors or load failures.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.items import load_collections, load_items  # noqa: E402
from blobbylib.manifest import build_manifest  # noqa: E402
from blobbylib.urls import (  # noqa: E402
    IMAGE_SUFFIXES,
    REPO_ROOT,
    list_tracked_images,
    parse_github_remote,
    run_git,
)
from blobbylib.validate import validate, warnings as collect_warnings  # noqa: E402

_WATCHED_DIRS = ("all-the-slack-blobbies", "svg")


def _collect_files_on_disk(root: Path) -> set[str]:
    """Return repo-relative paths (forward slashes) for all tracked images
    plus any untracked image files found by walking the watched directories.
    """
    tracked = set(list_tracked_images(cwd=root))

    for dirname in _WATCHED_DIRS:
        folder = root / dirname
        if not folder.is_dir():
            continue
        for fpath in folder.rglob("*"):
            if fpath.is_file() and fpath.suffix.lower() in IMAGE_SUFFIXES:
                rel = fpath.relative_to(root).as_posix()
                tracked.add(rel)

    return tracked


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate manifest against Slack emoji limits and repo rules.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on collection='unsorted'.",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref used in generated URLs (passed to build_manifest).",
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

    if not items_path.exists():
        print(f"error: items.yaml not found at {items_path}", file=sys.stderr)
        return 1

    try:
        items = load_items(items_path)
    except Exception as err:
        print(f"error loading items.yaml: {err}", file=sys.stderr)
        return 1

    try:
        collections = load_collections(collections_path)
    except Exception as err:
        print(f"error loading collections.yaml: {err}", file=sys.stderr)
        return 1

    try:
        owner, repo = parse_github_remote(run_git("remote", "get-url", args.remote))
    except Exception:
        owner = "exploreomni"
        repo = REPO_ROOT.name

    records = build_manifest(
        root=REPO_ROOT,
        items=items,
        owner=owner,
        repo=repo,
        ref=args.ref,
        pinned_ref=None,
        today=date.today(),
    )

    files_on_disk = _collect_files_on_disk(REPO_ROOT)

    errors = validate(records, items, collections, files_on_disk, args.strict)

    for warn in collect_warnings(records):
        print(f"warning: {warn}", file=sys.stderr)

    if errors:
        for err in errors:
            print(err)
        return 1

    print(f"ok: {len(records)} records, no errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
