#!/usr/bin/env python3
"""Generate README.md from the manifest and write manifest.json.

Usage:
    python3 scripts/generate_readme.py [--readme README.md] [--ref main]

Builds the manifest from items.yaml and image files, validates records
(non-strict), writes manifest.json, then regenerates the generated section
inside README.md.  Exits 1 if validation errors are found.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.items import load_collections, load_items  # noqa: E402
from blobbylib.manifest import build_manifest  # noqa: E402
from blobbylib.readme import render_sections  # noqa: E402
from blobbylib.urls import parse_github_remote, run_git  # noqa: E402
from blobbylib.validate import validate, warnings as collect_warnings  # noqa: E402

BEGIN_MARKER = "<!-- BEGIN GENERATED EMOJI TABLE -->"
END_MARKER = "<!-- END GENERATED EMOJI TABLE -->"
INSERT_BEFORE_HEADING = "## Maintainer notes"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_README = REPO_ROOT / "README.md"
DEFAULT_MANIFEST = REPO_ROOT / "manifest.json"


def replace_or_insert_section(readme_text: str, generated_section: str) -> str:
    block = f"{BEGIN_MARKER}\n{generated_section}\n{END_MARKER}"

    if BEGIN_MARKER in readme_text and END_MARKER in readme_text:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
            re.DOTALL,
        )
        return pattern.sub(block, readme_text, count=1)

    if INSERT_BEFORE_HEADING in readme_text:
        return readme_text.replace(
            INSERT_BEFORE_HEADING,
            f"{block}\n\n{INSERT_BEFORE_HEADING}",
            1,
        )

    trimmed = readme_text.rstrip()
    if trimmed:
        return f"{trimmed}\n\n{block}\n"
    return f"{block}\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate README from manifest and write manifest.json.",
    )
    parser.add_argument(
        "--readme",
        default=str(DEFAULT_README),
        help="Path to the README file to update.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote used to derive the GitHub owner and repo.",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref used in generated jsDelivr and GitHub URLs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readme_path = Path(args.readme).resolve()

    items_path = REPO_ROOT / "items.yaml"
    collections_path = REPO_ROOT / "collections.yaml"

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
    except (subprocess.CalledProcessError, ValueError):
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

    # Collect files_on_disk for validation (tracked images + untracked in watched dirs).
    from blobbylib.urls import IMAGE_SUFFIXES  # noqa: E402

    _WATCHED_DIRS = ("all-the-slack-blobbies", "svg")
    files_on_disk: set[str] = set()
    try:
        from blobbylib.urls import list_tracked_images  # noqa: E402
        files_on_disk = set(list_tracked_images(cwd=REPO_ROOT))
    except Exception:
        pass
    for dirname in _WATCHED_DIRS:
        folder = REPO_ROOT / dirname
        if folder.is_dir():
            for fpath in folder.rglob("*"):
                if fpath.is_file() and fpath.suffix.lower() in IMAGE_SUFFIXES:
                    files_on_disk.add(fpath.relative_to(REPO_ROOT).as_posix())

    errors = validate(records, items, collections, files_on_disk, strict=False)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    for warn in collect_warnings(records):
        print(f"warning: {warn}", file=sys.stderr)

    # Write manifest.json to the repo root (always, regardless of --readme path).
    DEFAULT_MANIFEST.write_text(
        json.dumps(records, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    generated_section = render_sections(records, collections)

    try:
        existing_readme = readme_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing_readme = ""

    updated_readme = replace_or_insert_section(existing_readme, generated_section)
    readme_path.write_text(f"{updated_readme.rstrip()}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
