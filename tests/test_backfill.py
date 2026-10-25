"""Tests for blobbylib.backfill: propose, merge_proposals, Proposal, urllib path."""

import io
import json
import os

from blobbylib.backfill import propose, merge_proposals, Proposal, _make_ask_urllib
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
    assert captured["body"]["model"] == "claude-haiku-5-5"
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
