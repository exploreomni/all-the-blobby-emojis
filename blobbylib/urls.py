"""URL helpers for jsDelivr and GitHub blob links, plus git utilities."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".avif"}


def run_git(*args: str, cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_github_remote(remote_url: str) -> tuple[str, str]:
    patterns = (
        r"^https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^git@github\.com:(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, remote_url)
        if match:
            return match.group("owner"), match.group("repo")
    raise ValueError(f"Unsupported GitHub remote URL: {remote_url}")


def list_tracked_images(cwd: Path = REPO_ROOT) -> list[str]:
    image_paths = []
    for path in run_git("ls-files", cwd=cwd).splitlines():
        if Path(path).suffix.lower() in IMAGE_SUFFIXES:
            image_paths.append(path)
    return sorted(image_paths)


def build_jsdelivr_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{quote(ref, safe='-._~')}/{quote(path, safe='/-._~')}"


def build_github_blob_url(owner: str, repo: str, ref: str, path: str) -> str:
    return f"https://github.com/{owner}/{repo}/blob/{quote(ref, safe='-._~')}/{quote(path, safe='/-._~')}"
