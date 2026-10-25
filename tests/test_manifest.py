"""Tests for blobbylib.manifest."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from blobbylib.items import Item
from blobbylib.manifest import added_date, build_manifest


def make_repo(tmp_path: Path) -> Path:
    """git init, commit one png, leave a second png uncommitted."""
    root = tmp_path / "repo"
    root.mkdir()

    subdir = root / "all-the-slack-blobbies"
    subdir.mkdir()

    # Create a real PNG using Pillow.
    old_png = subdir / "old.png"
    img = Image.new("RGBA", (64, 64), color=(255, 0, 0, 255))
    img.save(old_png)

    new_png = subdir / "new.png"
    img2 = Image.new("RGBA", (32, 32), color=(0, 255, 0, 255))
    img2.save(new_png)

    # git init and configure local identity.
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=root, check=True, capture_output=True)

    # Commit only old.png.
    subprocess.run(["git", "add", "all-the-slack-blobbies/old.png"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add old emoji"],
        cwd=root,
        check=True,
        capture_output=True,
    )

    return root


def test_added_date_falls_back_to_today_for_uncommitted(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert added_date(root, "all-the-slack-blobbies/new.png", date(2026, 10, 24)) == "2026-10-24"


def test_added_date_uses_first_commit(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    assert added_date(root, "all-the-slack-blobbies/old.png", date(2026, 10, 24)) == date.today().isoformat()


def test_manifest_record_shape(tmp_path: Path) -> None:
    root = make_repo(tmp_path)
    items = {
        "old": Item(
            slug="old",
            display_name="Old",
            slack_name="old",
            generation="classic",
            kind="emoji",
            collection="core",
            tags=["a"],
            author=None,
            source="slack",
            svg=None,
            note=None,
        )
    }
    [rec] = build_manifest(
        root,
        items,
        "exploreomni",
        "all-the-blobby-emojis",
        "main",
        "v2026.11",
        date(2026, 10, 24),
    )
    assert rec["cdn_main"] == (
        "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/all-the-slack-blobbies/old.png"
    )
    assert rec["cdn_pinned"].endswith("@v2026.11/all-the-slack-blobbies/old.png")
    assert rec["file"] == "all-the-slack-blobbies/old.png" and rec["frames"] == 1
    assert set(rec) == {
        "slug",
        "display_name",
        "slack_name",
        "generation",
        "kind",
        "collection",
        "tags",
        "author",
        "source",
        "note",
        "file",
        "svg",
        "bytes",
        "width",
        "height",
        "frames",
        "added",
        "cdn_main",
        "cdn_pinned",
        "github",
    }
