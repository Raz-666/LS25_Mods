# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural texture set for FS25_BabaJaga (PNG -> DDS)."""

import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_HERE = os.path.dirname(os.path.abspath(__file__))
_UFO = os.path.join(os.path.dirname(_HERE), "ufo")
sys.path.insert(0, _UFO)

from textures import _noise, _to_img, specular  # noqa: E402  (ufo texture helpers)

BARK = (92, 62, 38)
BARK_DARK = (58, 38, 24)
WOOD = (120, 84, 50)
ROOF = (74, 58, 52)
SKIN = (206, 172, 92)
SKIN_DARK = (150, 118, 56)
GLOW = (255, 214, 120)


def _bands(size, count, colour, background, jitter=0.0, seed=0):
    rng = np.random.default_rng(seed)
    arr = np.zeros((size, size, 3), dtype=np.float32)
    arr[:] = np.array(background, dtype=np.float32) / 255.0
    img = Image.fromarray((arr * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    step = size // count
    for i in range(count):
        y = i * step
        c = tuple(int(v * (1.0 + rng.uniform(-jitter, jitter))) for v in colour)
        d.rectangle([0, y, size, y + step - max(1, step // 6)], fill=c)
    return img


def bark(size=512):
    """Dark tree bark with long vertical cracks (logs are laid horizontally)."""
    base = _noise(size, 40, seed=7) * 0.30 + 0.55
    lines = _noise(size, 8, seed=8)
    v = np.clip(base - np.abs(lines - 0.5) * 0.35, 0.18, 1.0)
    rgb = np.dstack([v * BARK[0] / 200.0, v * BARK[1] / 200.0, v * BARK[2] / 200.0])
    rgb = np.clip(rgb, 0, 1.4)
    return _to_img(rgb)


def planks(size=512):
    img = _bands(size, 8, WOOD, BARK_DARK, jitter=0.18, seed=3)
    grain = _noise(size, 128, seed=4)[..., None] * 0.12
    arr = np.asarray(img, dtype=np.float32) / 255.0 + grain - 0.06
    return _to_img(np.clip(arr, 0, 1))


def shingles(size=512):
    img = Image.new("RGB", (size, size), ROOF)
    d = ImageDraw.Draw(img)
    rows = 10
    for r in range(rows):
        y = r * size // rows
        for c in range(8):
            x = c * size // 8 + (size // 16 if r % 2 else 0)
            shade = 0.85 + 0.3 * ((r * 7 + c * 3) % 5) / 4.0
            col = tuple(min(255, int(v * shade)) for v in ROOF)
            d.rounded_rectangle([x, y, x + size // 8 - 3, y + size // rows - 2],
                                radius=6, fill=col)
    arr = np.asarray(img.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) / 255.0
    arr += (_noise(size, 96, seed=5)[..., None] - 0.5) * 0.10
    return _to_img(np.clip(arr, 0, 1))


def skin(size=512):
    """Scaly chicken leg: overlapping diamond scales in warm yellow."""
    img = Image.new("RGB", (size, size), SKIN)
    d = ImageDraw.Draw(img)
    step = size // 12
    for row in range(13):
        for col in range(13):
            x = col * step + (step // 2 if row % 2 else 0)
            y = row * step
            shade = 0.82 + 0.34 * ((row * 5 + col * 3) % 4) / 3.0
            col_ = tuple(min(255, int(v * shade)) for v in SKIN)
            d.ellipse([x, y, x + step - 2, y + step - 2], fill=col_,
                      outline=SKIN_DARK)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr += (_noise(size, 128, seed=9)[..., None] - 0.5) * 0.08
    return _to_img(np.clip(arr, 0, 1))


def claw(size=256):
    v = 0.30 + _noise(size, 64, seed=11) * 0.12
    return _to_img(np.dstack([v, v * 0.95, v * 0.88]))


def glow(size=256):
    return _to_img(np.dstack([np.ones((size, size)) * GLOW[0] / 255.0,
                              np.ones((size, size)) * GLOW[1] / 255.0,
                              np.ones((size, size)) * GLOW[2] / 255.0]))


def stone(size=256):
    v = 0.16 + _noise(size, 48, seed=13) * 0.14
    rgb = np.dstack([v * 0.98, v * 0.95, v * 0.88])
    return _to_img(np.clip(rgb, 0, 1))


TEXTURES = {
    "woodLog_diffuse": (bark, "bc1", True),
    "woodLog_specular": (lambda: specular("dark"), "bc1", True),
    "woodDark_diffuse": (planks, "bc1", True),
    "woodDark_specular": (lambda: specular("dark"), "bc1", True),
    "roof_diffuse": (shingles, "bc1", True),
    "roof_specular": (lambda: specular("dark"), "bc1", True),
    "legSkin_diffuse": (skin, "bc1", True),
    "legSkin_specular": (lambda: specular("paint"), "bc1", True),
    "claw_diffuse": (claw, "bc1", True),
    "glow_diffuse": (glow, "bc1", True),
    "stone_diffuse": (stone, "bc1", True),
    "stone_specular": (lambda: specular("dark"), "bc1", True),
}


def generate(out_dir, build_dir, python=sys.executable, verbose=True):
    png2dds = os.path.join(os.path.dirname(_HERE), "png2dds.py")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)
    made = []
    for name, (fn, fmt, mips) in TEXTURES.items():
        png = os.path.join(build_dir, name + ".png")
        fn().save(png)
        dds = os.path.join(out_dir, name + ".dds")
        cmd = [python, os.path.abspath(png2dds), png, dds, "--format", fmt]
        if not mips:
            cmd.append("--no-mips")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        made.append(dds)
        if verbose:
            print("  %-26s %s  %5.1f kB" % (name + ".dds", fmt,
                                            os.path.getsize(dds) / 1024.0))
    return made


if __name__ == "__main__":
    repo = os.path.dirname(os.path.dirname(_HERE))
    generate(os.path.join(repo, "FS25_BabaJaga", "textures"),
             os.path.join(repo, "build", "babajaga_tex"))
