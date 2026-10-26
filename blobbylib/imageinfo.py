"""Image metadata extraction for raster and SVG files."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class ImageInfo:
    bytes: int
    width: int
    height: int
    frames: int
    ext: str


def _parse_svg_dimension(value: str) -> int:
    """Strip optional units (px, pt, em, ...) and return nearest int."""
    stripped = re.sub(r"[a-zA-Z%]+$", "", value.strip())
    return round(float(stripped))


def image_info(path: Path) -> ImageInfo:
    """Return ImageInfo for a raster image or SVG file at *path*."""
    path = Path(path)
    ext = path.suffix.lstrip(".").lower()
    file_bytes = path.stat().st_size

    if ext == "svg":
        tree = ET.parse(path)
        root = tree.getroot()
        # viewBox takes priority
        viewbox = root.get("viewBox") or root.get("viewbox")
        if viewbox:
            parts = viewbox.strip().replace(",", " ").split()
            if len(parts) < 4:
                raise ValueError(f"SVG viewBox has fewer than four numbers: {path}")
            width = round(float(parts[2]))
            height = round(float(parts[3]))
        else:
            w_attr = root.get("width")
            h_attr = root.get("height")
            if w_attr is None or h_attr is None:
                raise ValueError(f"SVG has no viewBox or width/height: {path}")
            width = _parse_svg_dimension(w_attr)
            height = _parse_svg_dimension(h_attr)
        return ImageInfo(bytes=file_bytes, width=width, height=height, frames=1, ext=ext)

    with Image.open(path) as im:
        width, height = im.size
        frames = getattr(im, "n_frames", 1)
        return ImageInfo(bytes=file_bytes, width=width, height=height, frames=frames, ext=ext)
