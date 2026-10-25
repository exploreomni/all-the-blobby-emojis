#!/usr/bin/env python3
"""CLI: apply approved backfill proposals to items.yaml.

Usage:
    python3 scripts/apply_proposals.py backfill-proposals.csv

Only applies rows where keep == 'y', and only to entries whose collection
is still 'unsorted' in items.yaml.  Rewrites items.yaml in place.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.backfill import Proposal, merge_proposals  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> tuple[Path]:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <proposals.csv>", file=sys.stderr)
        sys.exit(1)
    p = Path(sys.argv[1])
    if not p.is_absolute():
        p = REPO_ROOT / p
    return (p,)


def main() -> int:
    (csv_path,) = parse_args()

    if not csv_path.exists():
        print(f"error: {csv_path} not found", file=sys.stderr)
        return 1

    proposals: list[Proposal] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("keep", "").strip().lower() != "y":
                continue
            tags_raw = row.get("tags", "")
            tags = [t for t in tags_raw.split("|") if t]
            try:
                confidence = float(row.get("confidence", "0"))
            except ValueError:
                confidence = 0.0
            proposals.append(
                Proposal(
                    slug=row["slug"],
                    display_name=row["display_name"],
                    collection=row["collection"],
                    tags=tags,
                    generation=row["generation"],
                    confidence=confidence,
                )
            )

    if not proposals:
        print("No approved rows found (keep == 'y').")
        return 0

    items_path = REPO_ROOT / "items.yaml"
    original = items_path.read_text(encoding="utf-8")
    updated = merge_proposals(original, proposals)
    items_path.write_text(updated, encoding="utf-8")

    print(f"Applied {len(proposals)} proposals to {items_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
