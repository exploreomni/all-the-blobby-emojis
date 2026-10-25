#!/usr/bin/env python3
"""CLI: vision-assisted tag backfill for unsorted Blobby items.

Usage:
    python3 scripts/backfill_items.py --out backfill-proposals.csv [--limit N]

Reads manifest.json if present, else builds the manifest in memory.
Processes only records whose collection is 'unsorted'.
Appends to the CSV so a partial run can be resumed (skips slugs already present).
All image inputs are normalised to PNG bytes before the API call.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.backfill import Proposal, _make_ask, propose  # noqa: E402
from blobbylib.vocab import VOCAB  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]

CSV_COLUMNS = [
    "slug", "keep", "display_name", "collection", "tags",
    "generation", "confidence", "current_display_name",
]


def _load_records() -> list[dict]:
    """Load manifest records from manifest.json, or build in memory if absent."""
    manifest_path = REPO_ROOT / "manifest.json"
    if manifest_path.exists():
        with manifest_path.open(encoding="utf-8") as f:
            return json.load(f)
    # Build manifest in memory (mirrors scripts/validate.py approach).
    from datetime import date
    from blobbylib.items import load_items, load_collections
    from blobbylib.manifest import build_manifest
    from blobbylib.urls import parse_github_remote, run_git

    items = load_items(REPO_ROOT / "items.yaml")
    load_collections(REPO_ROOT / "collections.yaml")
    try:
        owner, repo = parse_github_remote(run_git("remote", "get-url", "origin"))
    except Exception:
        owner = "exploreomni"
        repo = REPO_ROOT.name
    return build_manifest(
        root=REPO_ROOT,
        items=items,
        owner=owner,
        repo=repo,
        ref="main",
        pinned_ref=None,
        today=date.today(),
    )


def _png_bytes_for_record(slug: str, record: dict) -> bytes:
    """Return PNG bytes for the record's image.

    All input formats are converted to PNG so that ``propose`` always
    receives ``image/png`` bytes.

    - PNG: read bytes directly.
    - JPG/JPEG: open with Pillow, save as PNG.
    - GIF: extract the first frame via Pillow, save as PNG.
    - SVG-only: render to a 256px PNG via rsvg-convert.
    - No image / conversion failure: returns empty bytes.
    """
    from PIL import Image  # type: ignore[import]  # noqa: PLC0415

    file_rel: str | None = record.get("file")
    svg_rel: str | None = record.get("svg")

    if file_rel:
        file_path = REPO_ROOT / file_rel
        if file_path.exists():
            ext = file_path.suffix.lower()
            if ext == ".png":
                return file_path.read_bytes()
            elif ext in (".gif", ".jpg", ".jpeg"):
                try:
                    with Image.open(file_path) as img:
                        if ext == ".gif":
                            img.seek(0)
                        buf = io.BytesIO()
                        img.convert("RGBA").save(buf, format="PNG")
                        return buf.getvalue()
                except Exception as exc:
                    print(f"  WARN {slug}: could not convert {ext} to PNG: {exc}", file=sys.stderr)

    if svg_rel:
        svg_path = REPO_ROOT / svg_rel
        if svg_path.exists():
            rsvg = shutil.which("rsvg-convert")
            if rsvg is None:
                print(
                    f"  WARN {slug}: rsvg-convert not found on PATH; "
                    "install librsvg to convert SVGs",
                    file=sys.stderr,
                )
            else:
                try:
                    result = subprocess.run(
                        [rsvg, "-w", "256", "-h", "256", "-a",
                         str(svg_path)],
                        capture_output=True,
                        timeout=15,
                    )
                    if result.returncode != 0:
                        print(
                            f"  WARN {slug}: rsvg-convert returned {result.returncode}",
                            file=sys.stderr,
                        )
                    elif not result.stdout:
                        print(
                            f"  WARN {slug}: rsvg-convert produced no output",
                            file=sys.stderr,
                        )
                    else:
                        return result.stdout
                except Exception as exc:
                    print(f"  WARN {slug}: rsvg-convert failed: {exc}", file=sys.stderr)

    return b""


def _load_existing_slugs(out_path: Path) -> set[str]:
    """Return the set of slugs already present in the CSV (for resume)."""
    if not out_path.exists():
        return set()
    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return set()
        return {row["slug"] for row in reader if row.get("slug")}


def _append_row(out_path: Path, proposal: Proposal, current_display_name: str) -> None:
    """Append one proposal row to the CSV."""
    write_header = not out_path.exists()
    with out_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "slug": proposal.slug,
            "keep": "",  # Vincent sets this to 'y' to approve
            "display_name": proposal.display_name,
            "collection": proposal.collection,
            "tags": "|".join(proposal.tags),
            "generation": proposal.generation,
            "confidence": f"{proposal.confidence:.3f}",
            "current_display_name": current_display_name,
        })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Vision-assisted tag backfill for unsorted Blobby items.",
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV path.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process at most N unsorted records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    records = _load_records()
    unsorted = [r for r in records if r.get("collection") == "unsorted"]

    existing = _load_existing_slugs(out_path)
    pending = [r for r in unsorted if r["slug"] not in existing]

    if args.limit is not None:
        pending = pending[: args.limit]

    if not pending:
        print("Nothing to process.", file=sys.stderr)
        return 0

    ask = _make_ask()
    processed = 0
    for record in pending:
        slug = record["slug"]
        image_bytes = _png_bytes_for_record(slug, record)
        try:
            proposal = propose(record, image_bytes, VOCAB, ask)
        except Exception as exc:
            print(f"  SKIP {slug}: {exc}", file=sys.stderr)
            continue
        _append_row(out_path, proposal, record.get("display_name", ""))
        processed += 1
        print(
            f"  {slug} -> {proposal.collection} "
            f"[{', '.join(proposal.tags)}] (conf={proposal.confidence:.2f})"
        )

    print(f"\nWrote {processed} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
