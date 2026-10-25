"""Manifest builder: produces the generated source-of-truth manifest records."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from typing import Any

from blobbylib.imageinfo import image_info
from blobbylib.items import Item
from blobbylib.urls import build_github_blob_url, build_jsdelivr_url, run_git

_RASTER_EXTS = ("png", "gif", "jpg", "jpeg", "webp")


def added_date(root: Path, rel_path: str, today: date) -> str:
    """Return the ISO date of the first commit touching *rel_path*, or today.

    Uses ``git log --diff-filter=A --follow --format=%as`` and takes the last
    line (chronologically first commit) of the output.  If the path has no
    commits yet, returns *today* formatted as an ISO date string.
    """
    try:
        output = run_git(
            "log",
            "--diff-filter=A",
            "--follow",
            "--format=%as",
            "--",
            rel_path,
            cwd=root,
        )
    except subprocess.CalledProcessError:
        return today.isoformat()

    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    if not lines:
        return today.isoformat()
    # git log lists newest first; last line is the oldest (first) commit.
    return lines[-1]


def build_manifest(
    root: Path,
    items: dict[str, Item],
    owner: str,
    repo: str,
    ref: str,
    pinned_ref: str | None,
    today: date,
) -> list[dict[str, Any]]:
    """Build and return manifest records sorted by slug.

    Each record contains the full set of keys described in the task brief.
    """
    records: list[dict[str, Any]] = []

    for slug in sorted(items):
        item = items[slug]

        # Resolve raster path.
        raster_path: str | None = None
        for ext in _RASTER_EXTS:
            candidate = root / "all-the-slack-blobbies" / f"{slug}.{ext}"
            if candidate.exists():
                raster_path = f"all-the-slack-blobbies/{slug}.{ext}"
                break

        # Resolve SVG path.
        svg_path: str | None = None
        if item.svg is not None:
            # Explicit override from items.yaml (relative to repo root).
            candidate_svg = root / item.svg
            if candidate_svg.exists():
                svg_path = item.svg
        else:
            candidate_svg = root / "svg" / f"{slug}.svg"
            if candidate_svg.exists():
                svg_path = f"svg/{slug}.svg"

        # Determine image info source: raster preferred, fall back to svg.
        if raster_path is not None:
            info = image_info(root / raster_path)
        elif svg_path is not None:
            info = image_info(root / svg_path)
        else:
            # No image found; emit nulls for image fields.
            info = None

        # Determine path used for added_date and github URL.
        primary_path = raster_path if raster_path is not None else svg_path

        added = (
            added_date(root, primary_path, today)
            if primary_path is not None
            else today.isoformat()
        )

        # Build CDN and GitHub URLs.
        cdn_main: str | None = None
        cdn_pinned: str | None = None
        github_url: str | None = None

        if primary_path is not None:
            cdn_main = build_jsdelivr_url(owner, repo, ref, primary_path)
            if pinned_ref is not None:
                cdn_pinned = build_jsdelivr_url(owner, repo, pinned_ref, primary_path)
            github_url = build_github_blob_url(owner, repo, ref, primary_path)

        record: dict[str, Any] = {
            "slug": item.slug,
            "display_name": item.display_name,
            "slack_name": item.slack_name,
            "generation": item.generation,
            "kind": item.kind,
            "collection": item.collection,
            "tags": item.tags,
            "author": item.author,
            "source": item.source,
            "note": item.note,
            "file": raster_path,
            "svg": svg_path,
            "bytes": info.bytes if info is not None else None,
            "width": info.width if info is not None else None,
            "height": info.height if info is not None else None,
            "frames": info.frames if info is not None else None,
            "added": added,
            "cdn_main": cdn_main,
            "cdn_pinned": cdn_pinned,
            "github": github_url,
        }
        records.append(record)

    return records
