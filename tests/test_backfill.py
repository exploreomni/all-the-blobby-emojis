"""Tests for blobbylib.backfill: propose, merge_proposals, and Proposal."""

from blobbylib.backfill import propose, merge_proposals, Proposal
from blobbylib.vocab import VOCAB


def test_propose_parses_model_json():
    ask = lambda prompt, img, mt: '{"display_name":"Hockey Blobby","collection":"sports","tags":["hockey","helmet"],"generation":"new","confidence":0.9}'
    p = propose({"slug": "hockey-blobby", "file": "x.png"}, b"png", VOCAB, ask)
    assert (p.collection, p.tags, p.generation, p.confidence) == ("sports", ["hockey", "helmet"], "new", 0.9)


def test_propose_drops_tags_outside_vocab_and_bad_collection():
    ask = lambda *a: '{"display_name":"X","collection":"nope","tags":["hockey","zzz"],"generation":"new","confidence":0.5}'
    p = propose({"slug": "x", "file": "x.png"}, b"", VOCAB, ask)
    assert p.collection == "unsorted" and p.tags == ["hockey"]


def test_merge_only_touches_unsorted_entries():
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: unsorted\n"
        "  tags: []\n"
        "  source: slack\n"
        "b:\n"
        "  display_name: B\n"
        "  generation: new\n"
        "  kind: emoji\n"
        "  collection: core\n"
        "  tags: [x]\n"
        "  source: slack\n"
    )
    out = merge_proposals(
        text,
        [
            Proposal("a", "A!", "sports", ["hockey"], "new", 0.9),
            Proposal("b", "B!", "food", ["pizza"], "classic", 0.9),
        ],
    )
    assert "collection: sports" in out and "A!" in out
    assert "collection: core" in out and "B!" not in out


def test_merge_preserves_slack_name_null_and_note():
    """merge_proposals must not touch slack_name or note on an entry it updates."""
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: unsorted\n"
        "  tags: []\n"
        "  source: slack\n"
        "  slack_name: null\n"
        "  note: keep me\n"
    )
    out = merge_proposals(text, [Proposal("a", "A!", "sports", ["hockey"], "new", 0.9)])
    data = __import__("yaml").safe_load(out)
    assert data["a"]["slack_name"] is None
    assert data["a"]["note"] == "keep me"
    assert data["a"]["collection"] == "sports"
    assert data["a"]["display_name"] == "A!"
