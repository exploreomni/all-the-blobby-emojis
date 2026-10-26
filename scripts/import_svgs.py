"""CLI: plan or execute an SVG import from a source directory into svg/.

Usage:
    python3 scripts/import_svgs.py SOURCE_DIR [--renames PATH] [--dest PATH] [--apply]

Without --apply: prints the mapping and problems, exits 1 if there are problems.
With --apply: copies files to dest/<slug>.svg and writes svg-import-log.csv.
"""

import argparse
import csv
import os
import shutil
import sys

import yaml

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.naming import plan_imports


def collect_svg_basenames(source_dir: str) -> list[str]:
    """Walk source_dir recursively and return all *.svg basenames."""
    basenames: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(source_dir):
        for fn in filenames:
            if fn.lower().endswith(".svg"):
                basenames.append(fn)
    return basenames


def load_renames(path: str) -> dict[str, str]:
    """Load a YAML file that maps raw basename to slug. Returns {} if missing."""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def find_svg_path(source_dir: str, basename: str) -> str | None:
    """Return the full path for a basename found anywhere under source_dir."""
    for dirpath, _dirnames, filenames in os.walk(source_dir):
        if basename in filenames:
            return os.path.join(dirpath, basename)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan or execute SVG imports into the svg/ destination directory."
    )
    parser.add_argument("source", help="Source directory containing SVG files.")
    parser.add_argument(
        "--renames",
        default="svg-renames.yaml",
        help="YAML file mapping raw basenames to slugs (default: svg-renames.yaml).",
    )
    parser.add_argument(
        "--dest",
        default="svg",
        help="Destination directory for imported SVGs (default: svg).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy files and write svg-import-log.csv; without this flag the run is a dry run.",
    )
    args = parser.parse_args()

    basenames = collect_svg_basenames(args.source)
    renames = load_renames(args.renames)
    mapping, problems = plan_imports(basenames, renames)

    # Print the mapping
    print(f"Mapping ({len(mapping)} files):")
    for raw, slug in sorted(mapping.items()):
        print(f"  {raw!r:60s} -> {slug}")

    # Print problems
    if problems:
        print(f"\nProblems ({len(problems)}):")
        for p in problems:
            print(f"  {p}")

    if not args.apply:
        sys.exit(1 if problems else 0)

    # Apply: copy files
    os.makedirs(args.dest, exist_ok=True)
    log_rows: list[tuple[str, str]] = []

    for raw, slug in sorted(mapping.items()):
        src_path = find_svg_path(args.source, raw)
        if src_path is None:
            print(f"WARNING: could not find source file for {raw!r}, skipping.")
            continue
        dest_path = os.path.join(args.dest, f"{slug}.svg")
        shutil.copy2(src_path, dest_path)
        log_rows.append((raw, slug))

    # Write csv log at repo root
    log_path = "svg-import-log.csv"
    with open(log_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["raw", "slug"])
        writer.writerows(log_rows)

    print(f"\nCopied {len(log_rows)} files to {args.dest}/")
    print(f"Log written to {log_path}")

    if problems:
        sys.exit(1)


if __name__ == "__main__":
    main()
