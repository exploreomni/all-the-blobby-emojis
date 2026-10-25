"""Tests for blobbylib.slackimport."""

from __future__ import annotations

import csv
from pathlib import Path

from blobbylib.slackimport import plan_import, load_exclude_csv


def test_skips_aliases_existing_and_excluded(tmp_path):
    (tmp_path / "images").mkdir()
    for n in ["new-one", "already", "secret"]:
        (tmp_path / "images" / f"{n}.png").write_bytes(b"x")
    emoji = {"new-one": "https://e/1.png", "already": "https://e/2.png", "secret": "https://e/3.png", "ali": "alias:new-one"}
    plan = plan_import(emoji, tmp_path / "images", {"already"}, {"secret"})
    assert [d for _, d in plan.copy] == ["all-the-slack-blobbies/new-one.png"]
    assert (plan.skipped_alias, plan.skipped_existing, plan.skipped_excluded) == (1, 1, 1)


def test_reports_missing_image(tmp_path):
    (tmp_path / "images").mkdir()
    plan = plan_import({"ghost": "https://e/g.png"}, tmp_path / "images", set(), set())
    assert plan.missing_image == ["ghost"] and plan.copy == []


def test_invalid_name_goes_to_missing_image(tmp_path):
    """Names with characters outside [a-z0-9_-] are rejected with '(invalid name)' note."""
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "Bad Name.png").write_bytes(b"x")
    plan = plan_import({"Bad Name": "https://e/b.png"}, tmp_path / "images", set(), set())
    assert plan.missing_image == ["Bad Name (invalid name)"]
    assert plan.copy == []


def test_load_exclude_csv_absent_file(tmp_path):
    """load_exclude_csv returns empty set when the file does not exist."""
    result = load_exclude_csv(tmp_path / "nonexistent.csv")
    assert result == set()


def test_load_exclude_csv_with_header(tmp_path):
    """load_exclude_csv handles a CSV with a name,reason header row."""
    csv_path = tmp_path / "exclude.csv"
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "reason"])
        writer.writerow(["blobby-wink", "off-brand"])
        writer.writerow(["  blobby-sad  ", "retired"])
    result = load_exclude_csv(csv_path)
    assert result == {"blobby-wink", "blobby-sad"}
