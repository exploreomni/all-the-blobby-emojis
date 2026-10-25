from blobbylib.seed import seed_entries


def test_seed_stub_shapes():
    out = seed_entries(["all-the-slack-blobbies/blobby-dbt.png", "all-the-slack-blobbies/blobby-roll.gif", "svg/blobby-paris.svg"], {})
    assert out["blobby-dbt"] == {"display_name": "Blobby Dbt", "generation": "classic", "kind": "emoji",
                                 "collection": "unsorted", "tags": [], "source": "slack"}
    assert out["blobby-roll"]["kind"] == "animation"
    assert out["blobby-paris"] == {"display_name": "Blobby Paris", "generation": "new", "kind": "illustration",
                                   "collection": "unsorted", "tags": [], "source": "figma-illustrations"}


def test_seed_skips_existing():
    assert seed_entries(["svg/blobby-paris.svg"], {"blobby-paris": object()}) == {}
