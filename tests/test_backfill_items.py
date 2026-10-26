"""Tests for scripts/backfill_items.py — specifically the SVG image-loading branch."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import the script as a module without running main().
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = REPO_ROOT / "scripts" / "backfill_items.py"


def _load_backfill_items():
    spec = importlib.util.spec_from_file_location("backfill_items", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Load once at module level; tests share the same module object.
backfill_items = _load_backfill_items()
_png_bytes_for_record = backfill_items._png_bytes_for_record

# A real SVG path that exists in the repo — used so svg_path.exists() is True.
_REAL_SVG = "svg/blobby-bat.svg"
assert (REPO_ROOT / _REAL_SVG).exists(), f"test fixture {_REAL_SVG!r} must exist"

_FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16  # PNG magic + padding


def test_svg_branch_returns_rsvg_stdout(monkeypatch):
    """When rsvg-convert succeeds, _png_bytes_for_record returns its stdout bytes."""

    def fake_which(name):
        return "/usr/local/bin/rsvg-convert"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=_FAKE_PNG, stderr=b"")

    monkeypatch.setattr(backfill_items.shutil, "which", fake_which)
    monkeypatch.setattr(backfill_items.subprocess, "run", fake_run)

    result = _png_bytes_for_record("blobby-bat", {"svg": _REAL_SVG})

    assert result == _FAKE_PNG
    assert captured["cmd"][0] == "/usr/local/bin/rsvg-convert"


def test_svg_branch_command_has_no_dash_o(monkeypatch):
    """-o must not appear anywhere in the rsvg-convert command."""

    def fake_which(name):
        return "/usr/local/bin/rsvg-convert"

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, returncode=0, stdout=_FAKE_PNG, stderr=b"")

    monkeypatch.setattr(backfill_items.shutil, "which", fake_which)
    monkeypatch.setattr(backfill_items.subprocess, "run", fake_run)

    _png_bytes_for_record("blobby-bat", {"svg": _REAL_SVG})

    assert "-o" not in captured["cmd"], f"'-o' found in command: {captured['cmd']}"
