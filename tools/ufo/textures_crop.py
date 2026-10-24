# SPDX-License-Identifier: GPL-3.0-or-later
"""Extra textures for FS25_CropHarvester (on top of the UFO 2000 set).

New here are only the three materials the blueprint asked for that the UFO
2000 does not have:

  * `decal`  - the "CROP HARVESTER" and "UFO 01" lettering on the hull,
  * `suit`   - Captain Zorp's flight suit,
  * `goggle` - the goggles and the chest patch.
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import textures as base  # noqa: E402

_noise = base._noise
_to_img = base._to_img
_color = base._color
specular = base.specular

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size):
    try:
        return ImageFont.truetype(FONT_BOLD, size)
    except OSError:
        return ImageFont.load_default()


def decal(size=1024):
    """Two panels side by side: the shoulder lettering (left, uv 0..0.72) and
    the small "UFO 01" plate (right, uv 0.72..1.0)."""
    w, h = size, size // 4  # 4:1 - power of two, DDS mips need that
    img = Image.new("RGB", (w, h), (108, 116, 124))
    # a little brushed metal noise so the panels do not look like stickers
    n = np.asarray(img, dtype=np.float32) / 255.0
    grain = _noise(size, 90, seed=5)[:h, :]
    n *= (0.94 + 0.12 * grain)[..., None]
    img = _to_img(n)
    d = ImageDraw.Draw(img)

    font_big = _font(int(h * 0.30))
    font_small = _font(int(h * 0.18))
    d.text((int(w * 0.02), int(h * 0.10)), "CROP", font=font_big, fill=(24, 30, 36))
    d.text((int(w * 0.02), int(h * 0.46)), "HARVESTER", font=font_small,
           fill=(30, 36, 42))
    d.line([(int(w * 0.02), int(h * 0.86)), (int(w * 0.68), int(h * 0.86))],
           fill=(206, 214, 220), width=max(2, h // 34))

    # right panel: a riveted plate with "UFO 01"
    x0 = int(w * 0.72)
    d.rectangle([x0 + 8, 8, w - 9, h - 9], outline=(58, 64, 70), width=max(2, h // 34))
    font_plate = _font(int(h * 0.26))
    d.text((x0 + int(w * 0.020), int(h * 0.22)), "UFO", font=font_plate,
           fill=(20, 24, 28))
    d.text((x0 + int(w * 0.020), int(h * 0.54)), "01", font=font_plate,
           fill=(20, 24, 28))
    for i in range(5):
        cx = x0 + 22 + i * (w - x0 - 44) // 4
        d.ellipse([cx - 4, h - 24, cx + 4, h - 16], fill=(72, 78, 84))
    return img


def suit(size=256):
    """Dark olive flight suit with seams and a few stitched patches."""
    n = _noise(size, 40, seed=17)
    fine = _noise(size, size // 2, seed=18)
    arr = np.dstack([0.20 + 0.10 * n, 0.28 + 0.12 * n, 0.16 + 0.08 * n])
    arr *= (0.92 + 0.16 * fine)[..., None]
    img = _to_img(np.clip(arr, 0, 1))
    d = ImageDraw.Draw(img)
    for y in range(0, size, size // 4):
        d.line([(0, y), (size, y)], fill=(58, 72, 46), width=2)
    for x in range(0, size, size // 3):
        d.line([(x, 0), (x, size)], fill=(44, 56, 36), width=1)
    return img


def goggle(size=128):
    """Black rubber / brass rim for the goggles."""
    n = _noise(size, 24, seed=23)
    arr = np.dstack([0.14 + 0.10 * n, 0.14 + 0.10 * n, 0.15 + 0.10 * n])
    return _to_img(np.clip(arr, 0, 1))


TEXTURES = {
    "decal_diffuse": (decal, "bc1", True),
    "suit_diffuse": (suit, "bc1", True),
    "suit_specular": (lambda: specular("paint"), "bc1", True),
    "goggle_diffuse": (goggle, "bc1", True),
}


def generate(out_dir, build_dir, png2dds=None, python=sys.executable, verbose=True):
    """Base UFO set plus the three harvester materials."""
    png2dds = png2dds or os.path.join(os.path.dirname(_HERE), "png2dds.py")
    made = base.generate(out_dir, build_dir, png2dds=png2dds, python=python,
                         verbose=verbose)
    for name, (fn, fmt, mips) in TEXTURES.items():
        png = os.path.join(build_dir, name + ".png")
        fn().save(png)
        dds = os.path.join(out_dir, name + ".dds")
        import subprocess
        cmd = [python, os.path.abspath(png2dds), png, dds, "--format", fmt]
        if not mips:
            cmd.append("--no-mips")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        made.append(dds)
        if verbose:
            print("  %-26s %s  %6.1f kB"
                  % (name + ".dds", fmt, os.path.getsize(dds) / 1024.0))
    return made


if __name__ == "__main__":
    repo = os.path.dirname(os.path.dirname(_HERE))
    generate(os.path.join(repo, "FS25_CropHarvester", "textures"),
             os.path.join(repo, "build", "crop_textures"))
