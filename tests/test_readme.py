"""Tests for blobbylib.readme.render_sections."""

from __future__ import annotations

from pathlib import Path

from blobbylib.items import load_collections
from blobbylib.readme import render_sections

REPO_ROOT = Path(__file__).resolve().parents[1]
COLS = load_collections(REPO_ROOT / "collections.yaml")

REC_CORE: dict = {
    "slug": "blobby",
    "display_name": "Blobby",
    "slack_name": "blobby",
    "generation": "classic",
    "kind": "emoji",
    "collection": "core",
    "tags": [],
    "author": None,
    "source": "slack",
    "note": None,
    "file": "all-the-slack-blobbies/blobby.png",
    "svg": None,
    "bytes": 5000,
    "width": 128,
    "height": 128,
    "frames": 1,
    "added": "2024-01-01",
    "cdn_main": "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/all-the-slack-blobbies/blobby.png",
    "cdn_pinned": None,
    "github": "https://github.com/exploreomni/all-the-blobby-emojis/blob/main/all-the-slack-blobbies/blobby.png",
}

REC_CITY_SVG_ONLY: dict = {
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
    "bytes": 2000,
    "width": 200,
    "height": 200,
    "frames": 1,
    "added": "2025-01-01",
    "cdn_main": "https://cdn.jsdelivr.net/gh/exploreomni/all-the-blobby-emojis@main/svg/blobby-paris.svg",
    "cdn_pinned": None,
    "github": "https://github.com/exploreomni/all-the-blobby-emojis/blob/main/svg/blobby-paris.svg",
}


def test_sections_follow_collection_order_and_show_shortcode():
    out = render_sections([REC_CORE, REC_CITY_SVG_ONLY], COLS)
    assert out.index("## Core") < out.index("## Cities")
    assert "`:blobby:`" in out
    assert "classic" in out.split("## Cities")[0]


def test_svg_only_item_links_svg_not_png():
    out = render_sections([REC_CITY_SVG_ONLY], COLS)
    row = [l for l in out.splitlines() if "blobby-paris" in l][0]
    assert "svg/blobby-paris.svg" in row and ".png" not in row
