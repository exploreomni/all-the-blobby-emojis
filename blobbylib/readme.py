"""README section renderer: produces the generated content block from manifest records."""

from __future__ import annotations

import re
from typing import Any

from blobbylib.items import Collection

_GITHUB_BLOB_BASE_RE = re.compile(
    r"(https://github\.com/[^/]+/[^/]+/blob/[^/]+/)"
)

_ZIP_URL = "https://github.com/exploreomni/all-the-blobby-emojis/releases/latest"


def _svg_blob_url(github_raster_url: str, svg_path: str) -> str:
    """Build a GitHub blob URL for svg_path using the base from github_raster_url."""
    m = _GITHUB_BLOB_BASE_RE.match(github_raster_url)
    if m:
        return m.group(1) + svg_path
    return github_raster_url


def _preview_cell(rec: dict[str, Any]) -> str:
    src = rec.get("cdn_main") or ""
    if not src:
        return ""
    slug = rec.get("slug", "")
    return f'<img src="{src}" alt="{slug}" width="48">'


def _files_cell(rec: dict[str, Any]) -> str:
    parts: list[str] = []
    file_path: str | None = rec.get("file")
    svg_path: str | None = rec.get("svg")
    github: str | None = rec.get("github")

    if file_path is not None and github is not None:
        fname = file_path.rsplit("/", 1)[-1]
        parts.append(f"[{fname}]({github})")
        if svg_path is not None:
            svg_fname = svg_path.rsplit("/", 1)[-1]
            svg_url = _svg_blob_url(github, svg_path)
            parts.append(f"[{svg_fname}]({svg_url})")
    elif svg_path is not None and github is not None:
        # svg-only: record["github"] is already the SVG blob URL
        svg_fname = svg_path.rsplit("/", 1)[-1]
        parts.append(f"[{svg_fname}]({github})")

    return " ".join(parts)


def render_sections(
    records: list[dict[str, Any]],
    collections: dict[str, Collection],
) -> str:
    """Render the generated README block between the BEGIN/END markers.

    Returns a string with one ``## <Collection name>`` section per non-empty
    collection (in collections.yaml order), a description line, and a table of
    items.  A zip-download link and a license pointer appear above the first
    section.
    """
    # Group records by collection slug.
    by_collection: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        col_slug = rec.get("collection") or "unsorted"
        by_collection.setdefault(col_slug, []).append(rec)

    lines: list[str] = []

    # Header lines (above the first collection).
    lines.append(
        f"Download the full pack: [{_ZIP_URL}]({_ZIP_URL})"
    )
    lines.append("")
    lines.append("Usage terms: [LICENSE.md](LICENSE.md)")
    lines.append("")

    for col_slug, col in collections.items():
        items = by_collection.get(col_slug)
        if not items:
            continue

        lines.append(f"## {col.name}")
        lines.append("")
        lines.append(col.description)
        lines.append("")
        lines.append("| Preview | Name | Shortcode | Gen | Files |")
        lines.append("| --- | --- | --- | --- | --- |")

        for rec in sorted(items, key=lambda r: r["slug"]):
            preview = _preview_cell(rec)
            name = rec.get("display_name") or rec["slug"]
            slack_name = rec.get("slack_name")
            shortcode = f"`:{slack_name}:`" if slack_name else ""
            gen = rec.get("generation") or ""
            files = _files_cell(rec)
            lines.append(f"| {preview} | {name} | {shortcode} | {gen} | {files} |")

        lines.append("")

    # Drop trailing blank line if any.
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
