#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
from pathlib import Path

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from blobbylib.urls import (  # noqa: E402
    build_github_blob_url,
    build_jsdelivr_url,
    list_tracked_images,
    parse_github_remote,
    run_git,
)

BEGIN_MARKER = "<!-- BEGIN GENERATED EMOJI TABLE -->"
END_MARKER = "<!-- END GENERATED EMOJI TABLE -->"
INSERT_BEFORE_HEADING = "## Internal Instructions"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_README = REPO_ROOT / "README.md"


def render_table(owner: str, repo: str, ref: str, image_paths: list[str]) -> str:
    lines = [
        "## Emoji Hotlinks",
        "",
        "Generated from tracked image files by `scripts/generate_readme.py`.",
        "",
        "To refresh this automatically on commit, enable the checked-in hook with `git config core.hooksPath .githooks`.",
        "",
        "| Preview | jsDelivr URL | Repo file |",
        "| --- | --- | --- |",
    ]

    for path in image_paths:
        file_name = Path(path).name
        cdn_url = build_jsdelivr_url(owner, repo, ref, path)
        blob_url = build_github_blob_url(owner, repo, ref, path)
        preview = f'<img src="{html.escape(cdn_url, quote=True)}" alt="{html.escape(file_name, quote=True)}" width="48">'
        hotlink = f'<a href="{html.escape(cdn_url, quote=True)}"><code>{html.escape(cdn_url)}</code></a>'
        repo_link = f'[`{file_name}`]({blob_url})'
        lines.append(f"| {preview} | {hotlink} | {repo_link} |")

    return "\n".join(lines)


def replace_or_insert_section(readme_text: str, generated_section: str) -> str:
    block = f"{BEGIN_MARKER}\n{generated_section}\n{END_MARKER}"

    if BEGIN_MARKER in readme_text and END_MARKER in readme_text:
        pattern = re.compile(
            rf"{re.escape(BEGIN_MARKER)}.*?{re.escape(END_MARKER)}",
            re.DOTALL,
        )
        return pattern.sub(block, readme_text, count=1)

    if INSERT_BEFORE_HEADING in readme_text:
        return readme_text.replace(
            INSERT_BEFORE_HEADING,
            f"{block}\n\n{INSERT_BEFORE_HEADING}",
            1,
        )

    trimmed = readme_text.rstrip()
    if trimmed:
        return f"{trimmed}\n\n{block}\n"
    return f"{block}\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate README hotlinks for tracked image files.",
    )
    parser.add_argument(
        "--readme",
        default=str(DEFAULT_README),
        help="Path to the README file to update.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Git remote used to derive the GitHub owner and repo.",
    )
    parser.add_argument(
        "--ref",
        default="main",
        help="Git ref used in generated jsDelivr and GitHub URLs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    readme_path = Path(args.readme).resolve()

    try:
        owner, repo = parse_github_remote(run_git("remote", "get-url", args.remote))
        image_paths = list_tracked_images()
    except (subprocess.CalledProcessError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    generated_section = render_table(owner, repo, args.ref, image_paths)

    try:
        existing_readme = readme_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing_readme = ""

    updated_readme = replace_or_insert_section(existing_readme, generated_section)
    readme_path.write_text(f"{updated_readme.rstrip()}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
