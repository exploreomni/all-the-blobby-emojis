"""Tests for blobbylib.packs."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import yaml
from PIL import Image

from blobbylib.items import load_collections
from blobbylib.packs import write_packs

COLLECTIONS_YAML = Path(__file__).parent.parent / "collections.yaml"
COLS = load_collections(COLLECTIONS_YAML)

RECORDS = [
    {
        "slug": "blobby",
        "display_name": "Blobby",
        "slack_name": "blobby",
        "generation": "new",
        "kind": "emoji",
        "collection": "core",
        "tags": [],
        "author": None,
        "source": "slack",
        "note": None,
        "file": "all-the-slack-blobbies/blobby.png",
        "svg": None,
        "bytes": 1000,
        "width": 128,
        "height": 128,
        "frames": 1,
        "added": "2026-01-01",
        "cdn_main": "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/all-the-slack-blobbies/blobby.png",
        "cdn_pinned": None,
        "github": None,
    },
    {
        "slug": "blobby-paris",
        "display_name": "Blobby Paris",
        "slack_name": None,
        "generation": "new",
        "kind": "illustration",
        "collection": "cities",
        "tags": [],
        "author": None,
        "source": "figma-illustrations",
        "note": None,
        "file": None,
        "svg": "svg/blobby-paris.svg",
        "bytes": None,
        "width": None,
        "height": None,
        "frames": None,
        "added": "2026-01-01",
        "cdn_main": None,
        "cdn_pinned": None,
        "github": None,
    },
]

STALE_RECORD = {
    "slug": "blobby-stale",
    "display_name": "Blobby Stale",
    "slack_name": None,
    "generation": "classic",
    "kind": "emoji",
    "collection": "core",
    "tags": [],
    "author": None,
    "source": "slack",
    "note": None,
    "file": "all-the-slack-blobbies/blobby-stale.png",
    "svg": None,
    "bytes": 1000,
    "width": 128,
    "height": 128,
    "frames": 1,
    "added": "2026-01-01",
    "cdn_main": "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/all-the-slack-blobbies/blobby-stale.png",
    "cdn_pinned": None,
    "github": None,
}


def make_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "LICENSE.md").write_text("MIT License")
    subdir = root / "all-the-slack-blobbies"
    subdir.mkdir()
    img = Image.new("RGBA", (128, 128), color=(255, 0, 0, 255))
    img.save(subdir / "blobby.png")
    svg_dir = root / "svg"
    svg_dir.mkdir()
    (svg_dir / "blobby-paris.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    return root


def test_packs_written_with_license_and_filters(tmp_path):
    root = make_root(tmp_path)
    paths = write_packs(RECORDS, COLS, root, tmp_path / "out")
    names = {p.name for p in paths}
    assert {"all-blobbies.zip", "core.zip", "cities.zip", "emojipacks.yaml", "emojme.json"} <= names
    with zipfile.ZipFile(tmp_path / "out" / "all-blobbies.zip") as z:
        assert "LICENSE.md" in z.namelist() and "svg/blobby-paris.svg" in z.namelist()
    pack = yaml.safe_load((tmp_path / "out" / "emojipacks.yaml").read_text())
    assert [e["name"] for e in pack["emojis"]] == ["blobby"]      # illustration excluded
    assert json.loads((tmp_path / "out" / "emojme.json").read_text())[0]["url"].startswith("https://cdn.jsdelivr.net/")


def test_stale_emoji_excluded_from_packs_but_in_zips(tmp_path):
    """A stale record (kind emoji, slack_name None) is excluded from pack lists but still in zips."""
    root = make_root(tmp_path)
    # Write the stale png file
    img = Image.new("RGBA", (128, 128), color=(0, 0, 255, 255))
    img.save(root / "all-the-slack-blobbies" / "blobby-stale.png")
    records = RECORDS + [STALE_RECORD]
    paths = write_packs(records, COLS, root, tmp_path / "out")
    # stale must not appear in emojipacks.yaml
    pack = yaml.safe_load((tmp_path / "out" / "emojipacks.yaml").read_text())
    pack_names = [e["name"] for e in pack["emojis"]]
    assert "blobby-stale" not in pack_names
    # stale must not appear in emojme.json
    emojme = json.loads((tmp_path / "out" / "emojme.json").read_text())
    emojme_names = [e["name"] for e in emojme]
    assert "blobby-stale" not in emojme_names
    # stale file still lands in the zip
    with zipfile.ZipFile(tmp_path / "out" / "all-blobbies.zip") as z:
        assert "all-the-slack-blobbies/blobby-stale.png" in z.namelist()


def test_missing_license_raises_before_any_zip(tmp_path):
    """write_packs raises FileNotFoundError before writing anything when LICENSE.md is absent."""
    root = tmp_path / "repo"
    root.mkdir()
    # no LICENSE.md written
    (root / "all-the-slack-blobbies").mkdir()
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    img.save(root / "all-the-slack-blobbies" / "blobby.png")
    out = tmp_path / "out"
    with pytest.raises(FileNotFoundError, match="LICENSE.md"):
        write_packs(RECORDS, COLS, root, out)
    # out directory may be created but no zip file should exist
    assert not any(out.glob("*.zip")) if out.exists() else True


def test_missing_asset_file_skipped_with_warning(tmp_path, capsys):
    """A record whose file does not exist on disk is skipped from zips with a stderr warning."""
    root = make_root(tmp_path)
    # blobby.png exists; blobby-paris.svg exists; introduce a third record with a missing file
    ghost_record = {
        "slug": "blobby-ghost",
        "display_name": "Blobby Ghost",
        "slack_name": "blobby-ghost",
        "generation": "new",
        "kind": "emoji",
        "collection": "core",
        "tags": [],
        "author": None,
        "source": "slack",
        "note": None,
        "file": "all-the-slack-blobbies/blobby-ghost.png",
        "svg": None,
        "bytes": 1000,
        "width": 128,
        "height": 128,
        "frames": 1,
        "added": "2026-01-01",
        "cdn_main": "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/all-the-slack-blobbies/blobby-ghost.png",
        "cdn_pinned": None,
        "github": None,
    }
    records = RECORDS + [ghost_record]
    paths = write_packs(records, COLS, root, tmp_path / "out")
    captured = capsys.readouterr()
    assert "blobby-ghost" in captured.err and "missing file" in captured.err
    with zipfile.ZipFile(tmp_path / "out" / "all-blobbies.zip") as z:
        assert "all-the-slack-blobbies/blobby-ghost.png" not in z.namelist()
        assert "all-the-slack-blobbies/blobby.png" in z.namelist()


def test_null_cdn_url_skipped_from_packs_with_warning(tmp_path, capsys):
    """A record with no cdn url (cdn_main and cdn_pinned both None) is skipped from pack lists."""
    root = make_root(tmp_path)
    no_cdn_record = {
        "slug": "blobby-nocdn",
        "display_name": "Blobby No CDN",
        "slack_name": "blobby-nocdn",
        "generation": "new",
        "kind": "emoji",
        "collection": "core",
        "tags": [],
        "author": None,
        "source": "slack",
        "note": None,
        "file": "all-the-slack-blobbies/blobby.png",
        "svg": None,
        "bytes": 1000,
        "width": 128,
        "height": 128,
        "frames": 1,
        "added": "2026-01-01",
        "cdn_main": None,
        "cdn_pinned": None,
        "github": None,
    }
    records = RECORDS + [no_cdn_record]
    paths = write_packs(records, COLS, root, tmp_path / "out")
    captured = capsys.readouterr()
    assert "blobby-nocdn" in captured.err and "no cdn url" in captured.err
    pack = yaml.safe_load((tmp_path / "out" / "emojipacks.yaml").read_text())
    pack_names = [e["name"] for e in pack["emojis"]]
    assert "blobby-nocdn" not in pack_names
    emojme = json.loads((tmp_path / "out" / "emojme.json").read_text())
    emojme_names = [e["name"] for e in emojme]
    assert "blobby-nocdn" not in emojme_names
