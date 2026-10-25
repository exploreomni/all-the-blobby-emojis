#!/usr/bin/env python3
"""CLI: import emojis from a Slack export into all-the-slack-blobbies/.

Usage:
    python3 scripts/import_slack_export.py EXPORT_DIR [--exclude PATH] [--apply]

EXPORT_DIR must contain:
  - emoji.json   mapping emoji name -> URL or "alias:<name>"
  - images/      directory with downloaded image files

Without --apply: prints counts and the first 20 planned copies, exits 0.
With --apply: copies files, runs seed, prints counts.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.items import load_items  # noqa: E402
from blobbylib.slackimport import ImportPlan, load_exclude_csv, plan_import  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _print_counts(plan: ImportPlan) -> None:
    print(f"  planned copies:    {len(plan.copy)}")
    print(f"  skipped aliases:   {plan.skipped_alias}")
    print(f"  skipped existing:  {plan.skipped_existing}")
    print(f"  skipped excluded:  {plan.skipped_excluded}")
    print(f"  missing image:     {len(plan.missing_image)}")
    if plan.missing_image:
        for m in plan.missing_image:
            print(f"    - {m}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Import emojis from a Slack export.")
    parser.add_argument("export_dir", help="Path to the Slack export directory.")
    parser.add_argument("--exclude", default=None, help="CSV file of names to exclude.")
    parser.add_argument("--apply", action="store_true", help="Copy files and seed items.yaml.")
    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    emoji_json = export_dir / "emoji.json"

    if not emoji_json.exists():
        print(f"ERROR: {emoji_json} not found.", file=sys.stderr)
        sys.exit(1)

    emoji: dict[str, str] = json.loads(emoji_json.read_text(encoding="utf-8"))
    image_dir = export_dir / "images"

    # Load existing slugs
    items_path = REPO_ROOT / "items.yaml"
    existing = load_items(items_path) if items_path.exists() else {}
    existing_slugs: set[str] = set(existing.keys())

    # Load exclude list
    exclude_path = Path(args.exclude) if args.exclude else Path("/dev/null")
    exclude = load_exclude_csv(exclude_path)

    plan = plan_import(emoji, image_dir, existing_slugs, exclude)

    print("Dry run:" if not args.apply else "Import plan:")
    _print_counts(plan)

    if not args.apply:
        if plan.copy:
            print(f"\nFirst {min(20, len(plan.copy))} planned copies:")
            for src, dest in plan.copy[:20]:
                print(f"  {src.name} -> {dest}")
        sys.exit(0)

    # --apply: copy files
    dest_dir = REPO_ROOT / "all-the-slack-blobbies"
    dest_dir.mkdir(exist_ok=True)

    copied = 0
    for src, dest_rel in plan.copy:
        dest = REPO_ROOT / dest_rel
        shutil.copy2(src, dest)
        copied += 1

    print(f"\nCopied {copied} files into all-the-slack-blobbies/.")

    # Run seed_items logic
    try:
        from scripts.seed_items import main as seed_main  # type: ignore[import]
        # seed_main reads sys.argv; call it with no extra args
        old_argv = sys.argv
        sys.argv = [sys.argv[0]]
        seed_main()
        sys.argv = old_argv
    except Exception:
        import subprocess
        subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "seed_items.py")], check=True)

    print("\nPost-apply counts:")
    _print_counts(plan)


if __name__ == "__main__":
    main()
