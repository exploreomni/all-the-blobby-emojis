from pathlib import Path

import pytest
from PIL import Image

from blobbylib.imageinfo import image_info


def test_png_info(tmp_path):
    p = tmp_path / "a.png"
    Image.new("RGBA", (64, 32)).save(p)
    i = image_info(p)
    assert (i.width, i.height, i.frames, i.ext) == (64, 32, 1, "png")
    assert i.bytes == p.stat().st_size


def test_gif_counts_frames(tmp_path):
    p = tmp_path / "a.gif"
    # Convert RGBA frames to palette mode so Pillow 12 writes all three frames
    frames = [Image.new("RGBA", (16, 16), (c * 80, c * 80, c * 80, 255)).convert("P") for c in range(3)]
    frames[0].save(p, save_all=True, append_images=frames[1:])
    assert image_info(p).frames == 3


def test_svg_reads_viewbox(tmp_path):
    p = tmp_path / "a.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 207 207"></svg>')
    i = image_info(p)
    assert (i.width, i.height, i.frames, i.ext) == (207, 207, 1, "svg")


def test_svg_reads_width_height(tmp_path):
    p = tmp_path / "b.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100px" height="200px"></svg>')
    i = image_info(p)
    assert (i.width, i.height, i.frames, i.ext) == (100, 200, 1, "svg")


def test_svg_no_dimensions_raises(tmp_path):
    p = tmp_path / "c.svg"
    p.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
    with pytest.raises(ValueError, match=str(p)):
        image_info(p)
