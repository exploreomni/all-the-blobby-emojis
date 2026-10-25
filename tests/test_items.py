import pytest

from blobbylib.items import load_items, load_collections, ItemError


def test_loads_item_with_defaults(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "blobby-dbt:\n  display_name: dbt Blobby\n  generation: classic\n  kind: emoji\n  collection: partners\n  tags: [dbt, partner]\n  source: slack\n"
    )
    items = load_items(tmp_path / "items.yaml")
    assert items["blobby-dbt"].slack_name == "blobby-dbt"  # defaults to slug for emoji
    assert items["blobby-dbt"].author is None


def test_rejects_bad_generation(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "x:\n  display_name: X\n  generation: old\n  kind: emoji\n  collection: core\n  tags: []\n  source: slack\n"
    )
    with pytest.raises(ItemError, match="x.*generation"):
        load_items(tmp_path / "items.yaml")


def test_non_emoji_has_no_slack_name_by_default(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "blobby-paris:\n  display_name: Paris\n  generation: new\n  kind: illustration\n  collection: cities\n  tags: []\n  source: figma-illustrations\n"
    )
    assert load_items(tmp_path / "items.yaml")["blobby-paris"].slack_name is None


def test_collections_sorted_by_order(tmp_path):
    (tmp_path / "c.yaml").write_text(
        "- {slug: cities, name: Cities, order: 3, description: d}\n- {slug: core, name: Core, order: 1, description: d}\n"
    )
    cols = load_collections(tmp_path / "c.yaml")
    assert list(cols) == ["core", "cities"]


def test_explicit_null_slack_name_overrides_default(tmp_path):
    """An explicit slack_name: null means the emoji no longer exists in Slack.
    This overrides the kind-based default (which would be the slug for emoji/animation)."""
    (tmp_path / "items.yaml").write_text(
        "blobby-gone:\n  display_name: Gone Blobby\n  generation: classic\n  kind: emoji\n  collection: core\n  tags: []\n  source: slack\n  slack_name: null\n"
    )
    item = load_items(tmp_path / "items.yaml")["blobby-gone"]
    assert item.slack_name is None


def test_animation_defaults_slack_name_to_slug(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "blobby-spin:\n  display_name: Spin\n  generation: new\n  kind: animation\n  collection: animated\n  tags: []\n  source: slack\n"
    )
    item = load_items(tmp_path / "items.yaml")["blobby-spin"]
    assert item.slack_name == "blobby-spin"


def test_tags_lowercased_and_deduplicated(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "blobby-test:\n  display_name: Test\n  generation: new\n  kind: emoji\n  collection: core\n  tags: [DBT, dbt, Partner]\n  source: slack\n"
    )
    item = load_items(tmp_path / "items.yaml")["blobby-test"]
    assert item.tags == ["dbt", "partner"]


def test_rejects_bad_kind(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "x:\n  display_name: X\n  generation: classic\n  kind: meme\n  collection: core\n  tags: []\n  source: slack\n"
    )
    with pytest.raises(ItemError, match="x.*kind"):
        load_items(tmp_path / "items.yaml")


def test_rejects_bad_source(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "x:\n  display_name: X\n  generation: classic\n  kind: emoji\n  collection: core\n  tags: []\n  source: unknown\n"
    )
    with pytest.raises(ItemError, match="x.*source"):
        load_items(tmp_path / "items.yaml")


def test_item_slug_on_dataclass(tmp_path):
    (tmp_path / "items.yaml").write_text(
        "blobby-dbt:\n  display_name: dbt Blobby\n  generation: classic\n  kind: emoji\n  collection: partners\n  tags: []\n  source: slack\n"
    )
    item = load_items(tmp_path / "items.yaml")["blobby-dbt"]
    assert item.slug == "blobby-dbt"


def test_collection_cover_defaults_none(tmp_path):
    (tmp_path / "c.yaml").write_text(
        "- {slug: core, name: Core, order: 1, description: The originals}\n"
    )
    col = load_collections(tmp_path / "c.yaml")["core"]
    assert col.cover is None
    assert col.slug == "core"
    assert col.order == 1
