"""Tests for blobbylib.backfill: propose, merge_proposals, Proposal, urllib path."""

import io
import json
import os

from blobbylib.backfill import propose, merge_proposals, Proposal, _make_ask_urllib, _build_prompt
from blobbylib.vocab import VOCAB


def test_propose_parses_model_json():
    ask = lambda prompt, img, mt: '{"display_name":"Hockey Blobby","collection":"sports","tags":["hockey","helmet"],"free_tags":[],"description":"Blobby wears a hockey helmet.","generation":"new","confidence":0.9}'
    p = propose({"slug": "hockey-blobby", "file": "x.png"}, b"png", VOCAB, ask)
    assert (p.collection, p.tags, p.generation, p.confidence) == ("sports", ["hockey", "helmet"], "new", 0.9)
    assert p.free_tags == []
    assert p.description == "Blobby wears a hockey helmet."


def test_propose_drops_tags_outside_vocab_and_bad_collection():
    ask = lambda *a: '{"display_name":"X","collection":"nope","tags":["hockey","zzz"],"generation":"new","confidence":0.5}'
    p = propose({"slug": "x", "file": "x.png"}, b"", VOCAB, ask)
    assert p.collection == "unsorted"
    assert p.tags == ["hockey"]
    assert "zzz" in p.free_tags


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


def test_propose_rejects_curator_only_collection():
    """A model reply with collection 'classic' must fall back to 'unsorted'."""
    ask = lambda *a: '{"display_name":"Old Blobby","collection":"classic","tags":["happy"],"generation":"classic","confidence":0.7}'
    p = propose({"slug": "old-blobby", "file": "x.png"}, b"", VOCAB, ask)
    assert p.collection == "unsorted"


def test_make_ask_urllib_path(monkeypatch):
    """_make_ask_urllib uses a fake urlopen; verify it sends the right shape and returns text."""
    api_json = json.dumps({
        "content": [
            {"type": "text", "text": '{"display_name":"Test","collection":"core","tags":["happy"],"generation":"new","confidence":0.8}'},
        ]
    }).encode("utf-8")

    class FakeResponse:
        def read(self):
            return api_json
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    captured = {}

    def fake_urlopen(req):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    ask = _make_ask_urllib(urlopen=fake_urlopen)
    result = ask("tag this image", b"\x89PNG", "image/png")

    assert result.startswith("{")
    assert captured["url"] == "https://api.anthropic.com/v1/messages"
    # urllib capitalises header keys; check case-insensitively
    headers_lower = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers_lower.get("x-api-key") == "test-key-123"
    assert headers_lower.get("anthropic-version") == "2023-06-01"
    assert captured["body"]["model"] == "claude-opus-5-5"
    assert captured["body"]["max_tokens"] == 1024
    assert captured["body"].get("output_config") == {"effort": "low"}
    content = captured["body"]["messages"][0]["content"]
    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["media_type"] == "image/png"


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


# ---------------------------------------------------------------------------
# New tests for v2 features
# ---------------------------------------------------------------------------

def test_propose_free_tag_capture():
    """Non-vocab tags from the model's `tags` field move to free_tags."""
    ask = lambda *a: '{"display_name":"X","collection":"cities","tags":["city","paris-vibes"],"free_tags":[],"generation":"new","confidence":0.8}'
    p = propose({"slug": "blobby-paris-2"}, b"", VOCAB, ask)
    assert "city" in p.tags
    assert "paris-vibes" not in p.tags
    assert "paris-vibes" in p.free_tags


def test_propose_free_tag_cap():
    """free_tags is capped at 2 items even if more are returned."""
    ask = lambda *a: '{"display_name":"X","collection":"cities","tags":["nontag1","nontag2","nontag3"],"free_tags":["nontag4"],"generation":"new","confidence":0.7}'
    p = propose({"slug": "blobby-test"}, b"", VOCAB, ask)
    assert len(p.free_tags) <= 2


def test_propose_free_tag_dedup_against_vocab():
    """Words from the vocab must not appear in free_tags."""
    ask = lambda *a: '{"display_name":"X","collection":"sports","tags":["hockey"],"free_tags":["hockey","new-word"],"generation":"new","confidence":0.7}'
    p = propose({"slug": "blobby-hockey"}, b"", VOCAB, ask)
    assert "hockey" not in p.free_tags
    assert "new-word" in p.free_tags


def test_propose_description_truncation():
    """Description is truncated to 120 characters."""
    long_desc = "a" * 200
    ask = lambda *a: json.dumps({
        "display_name": "X",
        "collection": "core",
        "tags": ["happy"],
        "free_tags": [],
        "description": long_desc,
        "generation": "new",
        "confidence": 0.5,
    })
    p = propose({"slug": "blobby-test"}, b"", VOCAB, ask)
    assert len(p.description) == 120
    assert p.description == "a" * 120


def test_propose_description_stripped():
    """Description has leading/trailing whitespace stripped before truncation."""
    ask = lambda *a: '{"display_name":"X","collection":"core","tags":[],"free_tags":[],"description":"  hello world  ","generation":"new","confidence":0.5}'
    p = propose({"slug": "blobby-test"}, b"", VOCAB, ask)
    assert p.description == "hello world"


def test_merge_writes_note_when_empty():
    """merge_proposals writes description into note when entry has no note."""
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: unsorted\n"
        "  tags: []\n"
        "  source: slack\n"
    )
    proposal = Proposal("a", "A!", "sports", ["hockey"], "new", 0.9,
                        description="Blobby wearing a hockey helmet.")
    out = merge_proposals(text, [proposal])
    data = __import__("yaml").safe_load(out)
    assert data["a"]["note"] == "Blobby wearing a hockey helmet."


def test_merge_does_not_overwrite_existing_note():
    """merge_proposals leaves an existing note untouched even when description is set."""
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: unsorted\n"
        "  tags: []\n"
        "  source: slack\n"
        "  note: existing note\n"
    )
    proposal = Proposal("a", "A!", "sports", ["hockey"], "new", 0.9,
                        description="New description that should not overwrite.")
    out = merge_proposals(text, [proposal])
    data = __import__("yaml").safe_load(out)
    assert data["a"]["note"] == "existing note"


def test_prompt_contains_slug():
    """_build_prompt includes the slug."""
    prompt = _build_prompt({"slug": "blobby-wizard-test"}, VOCAB)
    assert "blobby-wizard-test" in prompt


def test_prompt_contains_example_slugs():
    """_build_prompt includes all four worked-example slugs (updated for v3)."""
    prompt = _build_prompt({"slug": "blobby-any"}, VOCAB)
    for example_slug in ("blobby-paris-2", "blobby-dbt", "blobby-jack-o-lantern", "blobby-yells-at-jonny"):
        assert example_slug in prompt, f"Example slug {example_slug!r} missing from prompt"


def test_propose_tolerates_trailing_text_after_json():
    ask = lambda *a: '{"display_name":"Bee","collection":"animals","tags":["bee"],"generation":"new","confidence":0.8}\n\nNote: cute.'
    p = propose({"slug": "bumblebee-blobby", "file": "x.png"}, b"", VOCAB, ask)
    assert p.collection == "animals" and p.confidence == 0.8

# ---------------------------------------------------------------------------
# New tests for v3 keep-or-move prompt
# ---------------------------------------------------------------------------

def test_prompt_contains_current_label_block():
    """_build_prompt includes the current label block with collection and display_name."""
    record = {"slug": "blobby-test", "collection": "reactions", "display_name": "Test Blobby", "tags": ["happy"]}
    prompt = _build_prompt(record, VOCAB)
    assert "Current label:" in prompt
    assert "reactions" in prompt
    assert "Test Blobby" in prompt


def test_prompt_contains_precedence_rule():
    """_build_prompt includes the precedence rule text."""
    prompt = _build_prompt({"slug": "blobby-any"}, VOCAB)
    assert "lowest number" in prompt


def test_propose_parses_moved_and_reason():
    """propose() parses moved and reason from the model response."""
    ask = lambda *a: (
        '{"display_name":"Hockey Blobby","collection":"sports","tags":["hockey"],'
        '"free_tags":[],"description":"Blobby wears a hockey helmet.","generation":"new",'
        '"confidence":0.9,"moved":true,"reason":"sports item fits sports collection"}'
    )
    record = {"slug": "hockey-blobby", "collection": "unsorted"}
    p = propose(record, b"", VOCAB, ask)
    assert p.moved is True
    assert p.reason == "sports item fits sports collection"


def test_propose_moved_false_when_collection_unchanged():
    """propose() sets moved=False when the collection does not change."""
    ask = lambda *a: (
        '{"display_name":"Sports Blobby","collection":"sports","tags":["hockey"],'
        '"free_tags":[],"description":"Blobby plays hockey.","generation":"new",'
        '"confidence":0.9,"moved":false,"reason":"already in sports"}'
    )
    record = {"slug": "sports-blobby", "collection": "sports"}
    p = propose(record, b"", VOCAB, ask)
    assert p.moved is False
    assert p.collection == "sports"


def test_propose_core_reply_keeps_current_collection():
    """A model reply with collection 'core' must keep the current collection and moved=False."""
    ask = lambda *a: (
        '{"display_name":"X","collection":"core","tags":["happy"],'
        '"generation":"new","confidence":0.8,"moved":true,"reason":"looks core"}'
    )
    record = {"slug": "blobby-test", "collection": "reactions"}
    p = propose(record, b"", VOCAB, ask)
    assert p.collection == "reactions"
    assert p.moved is False


def test_propose_unsorted_reply_keeps_current_non_unsorted():
    """A 'unsorted' reply must not move a non-unsorted item; current collection is kept."""
    ask = lambda *a: (
        '{"display_name":"X","collection":"unsorted","tags":[],'
        '"generation":"new","confidence":0.3,"moved":true,"reason":"cant figure it out"}'
    )
    record = {"slug": "blobby-pizza", "collection": "food"}
    p = propose(record, b"", VOCAB, ask)
    assert p.collection == "food"
    assert p.moved is False


def test_propose_unsorted_reply_allowed_for_unsorted_item():
    """A 'unsorted' reply is fine when the item is already unsorted."""
    ask = lambda *a: (
        '{"display_name":"Yells at Jonny","collection":"unsorted","tags":[],'
        '"free_tags":["jonny"],"description":"Blobby yells at Jonny.","generation":"new",'
        '"confidence":0.3,"moved":false,"reason":"internal in-joke"}'
    )
    record = {"slug": "blobby-yells-at-jonny", "collection": "unsorted"}
    p = propose(record, b"", VOCAB, ask)
    assert p.collection == "unsorted"
    assert p.moved is False


def test_merge_applies_to_non_core_entries():
    """merge_proposals applies to any non-core entry, not just unsorted."""
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: reactions\n"
        "  tags: []\n"
        "  source: slack\n"
        "b:\n"
        "  display_name: B\n"
        "  generation: new\n"
        "  kind: emoji\n"
        "  collection: core\n"
        "  tags: []\n"
        "  source: slack\n"
    )
    out = merge_proposals(
        text,
        [
            Proposal("a", "A!", "sports", ["hockey"], "new", 0.9),
            Proposal("b", "B!", "food", ["pizza"], "classic", 0.9),
        ],
    )
    data = __import__("yaml").safe_load(out)
    assert data["a"]["collection"] == "sports"
    assert data["b"]["collection"] == "core"  # core entry must not be touched


def test_merge_never_sets_core():
    """merge_proposals must not set collection to core even if a Proposal says so."""
    text = (
        "a:\n"
        "  display_name: A\n"
        "  generation: classic\n"
        "  kind: emoji\n"
        "  collection: unsorted\n"
        "  tags: []\n"
        "  source: slack\n"
    )
    out = merge_proposals(
        text,
        [Proposal("a", "A!", "core", [], "new", 0.9)],
    )
    data = __import__("yaml").safe_load(out)
    assert data["a"]["collection"] == "unsorted"


def test_core_holds_the_master_blobbies():
    """Core must contain the 16 master files Vincent supplied on 2026-10-25."""
    import yaml
    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[1]
    with open(repo_root / "items.yaml") as f:
        data = yaml.safe_load(f)
    core_slugs = {k for k, v in data.items() if v and v.get("collection") == "core"}
    for slug in ("blobby-dynamic", "blobby-classic", "blobby-angry", "blobby-blushed-master", "blobby-cheeky", "blobby-chuffed", "blobby-content", "blobby-cute-yawn", "blobby-dazed", "blobby-displeased", "blobby-ouch", "blobby-puppy-eyes", "blobby-scrunched", "blobby-starstruck", "blobby-teary", "blobby-yawn"):
        assert slug in core_slugs, f"{slug!r} should be in core"
