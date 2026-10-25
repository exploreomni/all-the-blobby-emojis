"""Tests for blobbylib.validate."""

from __future__ import annotations

from blobbylib.items import Collection, Item
from blobbylib.validate import validate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COLS: dict[str, Collection] = {
    "core": Collection(slug="core", name="Core", order=1, description="Core emoji", cover=None),
    "unsorted": Collection(
        slug="unsorted", name="Unsorted", order=99, description="Unsorted", cover=None
    ),
}


def base_record(**overrides) -> dict:
    """Return a valid manifest record for slug 'x' with safe defaults."""
    rec: dict = {
        "slug": "x",
        "display_name": "X",
        "slack_name": "x",
        "generation": "classic",
        "kind": "emoji",
        "collection": "core",
        "tags": [],
        "author": None,
        "source": "slack",
        "note": None,
        "file": "all-the-slack-blobbies/x.png",
        "svg": None,
        "bytes": 1000,
        "width": 64,
        "height": 64,
        "frames": 1,
        "added": "2026-01-01",
        "cdn_main": None,
        "cdn_pinned": None,
        "github": None,
    }
    rec.update(overrides)
    return rec


def items_for(*records) -> dict[str, Item]:
    """Build a minimal Item dict keyed by slug from the given records."""
    result: dict[str, Item] = {}
    for rec in records:
        result[rec["slug"]] = Item(
            slug=rec["slug"],
            display_name=rec.get("display_name", rec["slug"]),
            slack_name=rec.get("slack_name"),
            generation=rec.get("generation", "classic"),
            kind=rec.get("kind", "emoji"),
            collection=rec.get("collection", "core"),
            tags=rec.get("tags", []),
            author=rec.get("author"),
            source=rec.get("source", "slack"),
            svg=rec.get("svg"),
            note=rec.get("note"),
        )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_record_passes():
    rec = base_record()
    assert validate([rec], items_for(rec), COLS, {rec["file"]}, False) == []


def test_oversize_emoji_fails():
    rec = base_record(bytes=131073, kind="emoji")
    assert any(
        "131073" in e and "bytes" in e
        for e in validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    )


def test_gif_over_50_frames_fails():
    rec = base_record(frames=51, file="all-the-slack-blobbies/x.gif")
    assert any(
        "frames" in e
        for e in validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    )


def test_uppercase_slack_name_fails():
    rec = base_record(slack_name="Blobby-X")
    assert any(
        "lowercase" in e
        for e in validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    )


def test_duplicate_slack_name_fails():
    a, b = base_record(slug="a", slack_name="same"), base_record(slug="b", slack_name="same")
    assert any(
        "same" in e and "duplicate" in e
        for e in validate([a, b], items_for(a, b), COLS, {a["file"], b["file"]}, False)
    )


def test_file_without_item_and_item_without_file_fail():
    rec = base_record(slug="has-item")
    errs = validate(
        [rec], items_for(rec), COLS, {rec["file"], "all-the-slack-blobbies/orphan.png"}, False
    )
    assert any("orphan" in e for e in errs)
    errs = validate(
        [base_record(slug="ghost", file="all-the-slack-blobbies/ghost.png")],
        items_for(base_record(slug="ghost")),
        COLS,
        set(),
        False,
    )
    assert any("ghost" in e and "missing" in e for e in errs)


def test_unknown_collection_fails_and_unsorted_only_fails_in_strict():
    rec = base_record(collection="nope")
    assert validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    rec = base_record(collection="unsorted")
    assert validate([rec], items_for(rec), COLS, {rec["file"]}, False) == []
    assert validate([rec], items_for(rec), COLS, {rec["file"]}, True)


def test_null_slack_name_skips_lowercase_and_dup_checks():
    """Items with slack_name=None should not raise lowercase or dup errors."""
    a = base_record(slug="a", slack_name=None)
    b = base_record(slug="b", slack_name=None)
    errs = validate([a, b], items_for(a, b), COLS, {a["file"]}, False)
    assert not any("lowercase" in e or "duplicate" in e for e in errs)


def test_animation_oversize_fails():
    rec = base_record(bytes=131073, kind="animation")
    assert any(
        "bytes" in e
        for e in validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    )


def test_sticker_oversize_passes():
    """Stickers and illustrations are not subject to the Slack bytes limit."""
    rec = base_record(bytes=200000, kind="sticker")
    errs = validate([rec], items_for(rec), COLS, {rec["file"]}, False)
    assert not any("bytes" in e for e in errs)


def test_svg_only_record_skips_bytes_and_frames():
    """Records with file=None (svg-only) skip bytes/frames checks."""
    rec = base_record(file=None, svg="svg/x.svg", bytes=200000, frames=100)
    errs = validate([rec], items_for(rec), COLS, {"svg/x.svg"}, False)
    assert not any("bytes" in e or "frames" in e for e in errs)
