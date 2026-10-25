"""Plan and apply imports from a Slack emoji export."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

_VALID_NAME_RE = re.compile(r'^[a-z0-9_-]+$')

_RASTER_EXTS = {".png", ".gif", ".jpg", ".jpeg", ".webp"}


@dataclass
class ImportPlan:
    copy: list[tuple[Path, str]] = field(default_factory=list)
    skipped_alias: int = 0
    skipped_existing: int = 0
    skipped_excluded: int = 0
    missing_image: list[str] = field(default_factory=list)


def load_exclude_csv(path: Path) -> set[str]:
    """Return the set of excluded names from a CSV file.

    The CSV may have a header row ``name,reason`` or no header.
    Only the ``name`` column is read; whitespace is stripped.
    Returns an empty set if the file does not exist.
    """
    if not path.exists():
        return set()

    names: set[str] = set()
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            name = row[0].strip()
            # Skip header row
            if name.lower() == "name":
                continue
            if name:
                names.add(name)
    return names


def plan_import(
    emoji: dict[str, str],
    image_dir: Path,
    existing_slugs: set[str],
    exclude: set[str],
) -> ImportPlan:
    """Build an ImportPlan from a Slack emoji export dict.

    Args:
        emoji: Mapping of emoji name to URL or ``alias:<other-name>``.
        image_dir: Directory containing downloaded image files.
        existing_slugs: Slugs already present in items.yaml.
        exclude: Names to exclude from the import.

    Returns:
        An ImportPlan describing what would be copied and what was skipped.
    """
    plan = ImportPlan()

    for name, value in sorted(emoji.items()):
        # Skip aliases
        if value.startswith("alias:"):
            plan.skipped_alias += 1
            continue

        # Validate name characters
        if not _VALID_NAME_RE.match(name):
            plan.missing_image.append(f"{name} (invalid name)")
            continue

        # Skip excluded names
        if name in exclude:
            plan.skipped_excluded += 1
            continue

        # Skip names already in items.yaml
        if name in existing_slugs:
            plan.skipped_existing += 1
            continue

        # Find the image file in image_dir
        found: Path | None = None
        for ext in _RASTER_EXTS:
            candidate = image_dir / f"{name}{ext}"
            if candidate.exists():
                found = candidate
                break

        if found is None:
            plan.missing_image.append(name)
            continue

        dest = f"all-the-slack-blobbies/{name}{found.suffix}"
        plan.copy.append((found, dest))

    return plan
