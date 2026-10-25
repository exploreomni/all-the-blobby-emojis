"""Manifest validator: checks records against Slack emoji limits and repo rules."""

from __future__ import annotations

import re
from typing import Any

from blobbylib.items import Collection, Item

_SLACK_NAME_RE = re.compile(r"^[a-z0-9_-]+$")
_BYTES_LIMIT = 131072
_FRAMES_LIMIT = 50
_RASTER_KINDS = {"emoji", "animation"}
_WATCHED_PREFIXES = ("all-the-slack-blobbies/", "svg/")


def validate(
    records: list[dict[str, Any]],
    items: dict[str, Item],
    collections: dict[str, Collection],
    files_on_disk: set[str],
    strict: bool,
) -> list[str]:
    """Validate manifest records against Slack emoji limits and repo rules.

    Returns a list of error strings (empty when valid).  Each error is
    formatted as ``"<slug>: <message>"``; orphan-file errors use the path
    as the slug part.
    """
    errors: list[str] = []
    seen_slack_names: dict[str, str] = {}  # name -> first slug that claimed it
    claimed_files: set[str] = set()

    for rec in records:
        slug: str = rec["slug"]
        file_path: str | None = rec.get("file")
        svg_path: str | None = rec.get("svg")
        kind: str | None = rec.get("kind")
        slack_name: str | None = rec.get("slack_name")
        collection: str | None = rec.get("collection")

        # --- Bytes limit (raster file present, kind is emoji or animation) ---
        if file_path is not None and kind in _RASTER_KINDS:
            size = rec.get("bytes")
            if size is not None and size > _BYTES_LIMIT:
                errors.append(
                    f"{slug}: {size} bytes exceeds {_BYTES_LIMIT} bytes limit"
                )

        # --- Frames limit (raster file present) ---
        if file_path is not None:
            frames = rec.get("frames")
            if frames is not None and frames > _FRAMES_LIMIT:
                errors.append(
                    f"{slug}: {frames} frames exceeds {_FRAMES_LIMIT} frames limit"
                )

        # --- Slack name: lowercase + charset ---
        if slack_name is not None:
            if not _SLACK_NAME_RE.match(slack_name):
                errors.append(
                    f"{slug}: slack_name {slack_name!r} must be lowercase [a-z0-9_-]"
                )
            # --- Duplicate slack name (only among non-None names) ---
            if slack_name in seen_slack_names:
                errors.append(
                    f"{slug}: duplicate slack_name {slack_name!r}"
                    f" (also used by {seen_slack_names[slack_name]})"
                )
            else:
                seen_slack_names[slack_name] = slug

        # --- File missing from disk ---
        if file_path is not None:
            claimed_files.add(file_path)
            if file_path not in files_on_disk:
                errors.append(f"{slug}: file {file_path!r} is missing from disk")

        # Track SVG paths as claimed too.
        if svg_path is not None:
            claimed_files.add(svg_path)

        # --- Unknown collection ---
        if collection is not None:
            if collection not in collections:
                errors.append(f"{slug}: unknown collection {collection!r}")
            elif strict and collection == "unsorted":
                errors.append(
                    f"{slug}: collection is 'unsorted' (not allowed in strict mode)"
                )

    # --- Orphan files (in watched folders but not claimed by any record) ---
    for path in sorted(files_on_disk):
        if any(path.startswith(prefix) for prefix in _WATCHED_PREFIXES):
            if path not in claimed_files:
                errors.append(f"{path}: orphaned file has no record")

    return errors
