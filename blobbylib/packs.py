"""Pack generation: zips, emojipacks.yaml, emojme.json."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import yaml

from blobbylib.items import Collection

_PACK_KINDS = {"emoji", "animation"}


def write_packs(
    records: list[dict[str, Any]],
    collections: dict[str, Collection],
    root: Path,
    out: Path,
) -> list[Path]:
    """Write all packs to out/ and return a sorted list of written paths.

    Outputs:
    - out/all-blobbies.zip          every record with a file or svg
    - out/<collection slug>.zip     per non-empty collection
    - out/emojipacks.yaml           kind emoji/animation with slack_name and cdn url
    - out/emojme.json               same filter, JSON list

    Zips contain files at their repo-relative paths plus LICENSE.md at the zip
    root. Entries are in deterministic (sorted) order. Compression: DEFLATED.

    Raises FileNotFoundError if root/LICENSE.md is absent (checked before any
    zip is written).

    Missing asset files are skipped with a stderr warning. Records with no cdn
    url are skipped from pack lists with a stderr warning.
    """
    license_path = root / "LICENSE.md"
    if not license_path.exists():
        raise FileNotFoundError(f"LICENSE.md not found at {license_path}")

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    # Filter out unlisted records from all generated surfaces.
    records = [r for r in records if r.get("listed", True)]

    def _entries(recs: list[dict[str, Any]]) -> list[tuple[str, Path]]:
        """Return sorted (arcname, disk_path) pairs for records with existing files."""
        seen: dict[str, Path] = {}
        for rec in recs:
            for field in ("file", "svg"):
                rel = rec.get(field)
                if not rel:
                    continue
                disk_path = root / rel
                if not disk_path.exists():
                    print(
                        f"warning: {rec.get('slug', '?')}: missing file {disk_path}, skipped from zips",
                        file=sys.stderr,
                    )
                    continue
                seen[rel] = disk_path
        return sorted(seen.items())

    def _write_zip(zip_path: Path, recs: list[dict[str, Any]]) -> Path:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(license_path, "LICENSE.md")
            for arcname, disk_path in _entries(recs):
                zf.write(disk_path, arcname)
        return zip_path

    # all-blobbies.zip
    all_zip = out / "all-blobbies.zip"
    _write_zip(all_zip, records)
    written.append(all_zip)

    # per-collection zips (skip empty)
    col_records: dict[str, list[dict[str, Any]]] = {slug: [] for slug in collections}
    for rec in records:
        slug = rec.get("collection", "")
        if slug in col_records:
            col_records[slug].append(rec)

    for slug in collections:
        recs = col_records[slug]
        if not recs:
            continue
        col_zip = out / f"{slug}.zip"
        _write_zip(col_zip, recs)
        written.append(col_zip)

    def _cdn_url(rec: dict[str, Any]) -> str | None:
        return rec.get("cdn_pinned") or rec.get("cdn_main") or None

    # pack filter: kind emoji/animation AND slack_name is not None AND cdn url exists
    pack_records: list[dict[str, Any]] = []
    for r in records:
        if r.get("kind") not in _PACK_KINDS:
            continue
        if r.get("slack_name") is None:
            continue
        if _cdn_url(r) is None:
            print(
                f"warning: {r.get('slug', '?')}: no cdn url, skipped from packs",
                file=sys.stderr,
            )
            continue
        pack_records.append(r)

    # emojipacks.yaml
    emojipacks_path = out / "emojipacks.yaml"
    emojis_list = [
        {"name": r["slack_name"], "src": _cdn_url(r)}
        for r in pack_records
    ]
    emojipacks_data: dict[str, Any] = {"title": "Omni Blobby", "emojis": emojis_list}
    emojipacks_path.write_text(
        yaml.dump(emojipacks_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
    )
    written.append(emojipacks_path)

    # emojme.json
    emojme_path = out / "emojme.json"
    emojme_list = [
        {"name": r["slack_name"], "url": _cdn_url(r)}
        for r in pack_records
    ]
    emojme_path.write_text(json.dumps(emojme_list, indent=1) + "\n")
    written.append(emojme_path)

    return sorted(written, key=lambda p: p.name)
