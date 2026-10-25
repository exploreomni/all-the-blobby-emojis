"""SVG name normalization and import planning for the blobbylib pipeline."""

import re


def normalize_svg_name(raw: str) -> str:
    """Return a canonical slug from a raw SVG filename.

    Rules applied in order:
    1. Drop the .svg extension.
    2. Remove trailing ' vs.N' version suffixes (e.g. ' vs.2').
    3. Remove trailing '-vN' version suffixes (e.g. '-v2').
    4. Lowercase.
    5. Replace '=', '_', and whitespace runs with '-'.
    6. Fix leading typos: 'bobbly' and 'bloby' -> 'blobby'.
    7. Collapse repeated hyphens.
    8. Strip leading and trailing hyphens.
    """
    name = raw

    # Drop .svg extension (case-insensitive)
    if name.lower().endswith(".svg"):
        name = name[:-4]

    # Remove trailing ' vs.N' suffix before lowercasing
    name = re.sub(r"\s+vs\.\d+\s*$", "", name, flags=re.IGNORECASE)

    # Remove trailing '-vN' version suffix (not plain numbered variants like '-3')
    name = re.sub(r"-v\d+\s*$", "", name, flags=re.IGNORECASE)

    # Lowercase
    name = name.lower()

    # Replace '=', '_', and whitespace runs with '-'
    name = re.sub(r"[=_\s]+", "-", name)

    # Fix leading typos: bobbly -> blobby, bloby -> blobby
    name = re.sub(r"^bobbly(?=-|$)", "blobby", name)
    name = re.sub(r"^bloby(?=-|$)", "blobby", name)

    # Collapse repeated hyphens
    name = re.sub(r"-{2,}", "-", name)

    # Strip leading and trailing hyphens
    name = name.strip("-")

    return name


def plan_imports(
    source_names: list[str], renames: dict[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Plan how raw SVG basenames map to destination slugs.

    Args:
        source_names: Raw basenames (with extension) from the source directory.
        renames: Explicit override map from raw basename to slug (no extension).

    Returns:
        A tuple of (mapping, problems) where:
        - mapping maps raw basename to slug for all successfully resolved names.
        - problems is a list of human-readable issue strings.

    Rules:
    - renames entries are applied first, before normalization.
    - Any raw name starting with 'Group ' that is not in renames is a problem
      and is excluded from the mapping.
    - If two raw names resolve to the same slug, the first wins in the mapping
      and both are named in a collision problem message.
    """
    mapping: dict[str, str] = {}
    problems: list[str] = []
    slug_to_first: dict[str, str] = {}

    for raw in source_names:
        if raw in renames:
            slug = renames[raw]
        elif raw.startswith("Group "):
            problems.append(f"{raw}: unmapped Group file, needs a rename entry")
            continue
        else:
            slug = normalize_svg_name(raw)

        if slug in slug_to_first:
            first_raw = slug_to_first[slug]
            problems.append(
                f"collision: {first_raw!r} and {raw!r} both map to {slug!r}"
            )
        else:
            slug_to_first[slug] = raw
            mapping[raw] = slug

    return mapping, problems
