# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural texture set for the venue mods (Autokino, Disco)."""

import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_HERE = os.path.dirname(os.path.abspath(__file__))
_UFO = os.path.join(os.path.dirname(_HERE), "ufo")
sys.path.insert(0, _UFO)

import textures as ufo_textures  # noqa: E402

_noise = ufo_textures._noise
_to_img = ufo_textures._to_img
specular = ufo_textures.specular


def asphalt(size=512):
    base = np.array((0.115, 0.120, 0.125), dtype=np.float32)
    n = _noise(size, 128, seed=31)
    fine = _noise(size, size // 2, seed=32)
    arr = base[None, None, :] * (0.82 + 0.40 * n[..., None])
    arr += (fine[..., None] - 0.5) * 0.05
    return _to_img(np.clip(arr, 0, 1))


def concrete(size=512):
    base = np.array((0.34, 0.33, 0.31), dtype=np.float32)
    n = _noise(size, 64, seed=33)
    arr = base[None, None, :] * (0.86 + 0.28 * n[..., None])
    return _to_img(np.clip(arr, 0, 1))


def gravel(size=512):
    img = Image.new("RGB", (size, size), (70, 66, 60))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(34)
    for _ in range(2600):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        r = rng.uniform(1.0, 3.4)
        v = int(rng.uniform(58, 118))
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=(v, int(v * 0.96), int(v * 0.9)))
    return img.filter(ImageFilter.SMOOTH)


def screen_canvas(size=512):
    """The screen itself: near white with a soft vignette, so the frames pop."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    r = np.sqrt((xx - 0.5) ** 2 + (yy - 0.5) ** 2) * 2.0
    v = 0.93 - 0.10 * np.clip(r, 0, 1) ** 2
    arr = np.dstack([v, v, v * 0.99])
    return _to_img(arr)


def dark_metal(size=256):
    n = _noise(size, 32, seed=36)
    v = 0.09 + 0.05 * n
    return _to_img(np.dstack([v * 1.0, v * 1.02, v * 1.05]))


def plank_wood(size=512):
    img = Image.new("RGB", (size, size), (86, 58, 36))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(37)
    step = size // 6
    for i in range(6):
        y = i * step
        v = int(rng.uniform(-14, 14))
        d.rectangle([0, y, size, y + step - 2], fill=(96 + v, 64 + v // 2, 40 + v // 3))
        for k in range(26):                      # grain
            gy = y + rng.uniform(2, step - 4)
            d.line([(0, gy), (size, gy + rng.uniform(-2, 2))],
                   fill=(74 + v, 48 + v, 30 + v // 2), width=1)
    return img


def stage_floor(size=512):
    """Black and white dance floor tiles with a soft reflection."""
    img = Image.new("RGB", (size, size), (18, 18, 22))
    d = ImageDraw.Draw(img)
    step = size // 8
    for i in range(8):
        for j in range(8):
            if (i + j) % 2 == 0:
                d.rectangle([j * step, i * step, (j + 1) * step - 2, (i + 1) * step - 2],
                            fill=(205, 205, 215))
            else:
                d.rectangle([j * step, i * step, (j + 1) * step - 2, (i + 1) * step - 2],
                            fill=(24, 24, 30))
    return img


def speaker_cloth(size=256):
    img = Image.new("RGB", (size, size), (26, 26, 30))
    d = ImageDraw.Draw(img)
    for i in range(0, size, 4):
        d.line([(i, 0), (i, size)], fill=(34, 34, 40))
        d.line([(0, i), (size, i)], fill=(22, 22, 26))
    return img


def neon(rgb, size=256):
    """A glowing lamp face: bright core, soft falloff."""
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    core = np.clip(1.0 - r, 0, 1) ** 0.5
    base = np.array(rgb, dtype=np.float32)
    arr = np.clip(base[None, None, :] * (0.55 + 0.75 * core[..., None]) +
                  core[..., None] * 0.45, 0, 1)
    return _to_img(arr)


def mirror(size=256):
    """Dance floor / mirror ball face: many small mirrored facets."""
    img = Image.new("RGB", (size, size), (140, 145, 155))
    d = ImageDraw.Draw(img)
    step = size // 8
    rng = np.random.default_rng(41)
    for i in range(8):
        for j in range(8):
            v = int(rng.uniform(120, 240))
            d.rectangle([j * step + 1, i * step + 1,
                         (j + 1) * step - 2, (i + 1) * step - 2],
                        fill=(v, int(v * 0.98), min(255, int(v * 1.06))))
    return img


TEXTURES = {
    "asphalt_diffuse": (asphalt, "bc1", True),
    "asphalt_specular": (lambda: specular("dark"), "bc1", True),
    "concrete_diffuse": (concrete, "bc1", True),
    "concrete_specular": (lambda: specular("paint"), "bc1", True),
    "gravel_diffuse": (gravel, "bc1", True),
    "gravel_specular": (lambda: specular("dark"), "bc1", True),
    "screen_diffuse": (screen_canvas, "bc1", True),
    "darkMetal_diffuse": (dark_metal, "bc1", True),
    "darkMetal_specular": (lambda: specular("metal"), "bc1", True),
    "plank_diffuse": (plank_wood, "bc1", True),
    "plank_specular": (lambda: specular("paint"), "bc1", True),
    "danceFloor_diffuse": (stage_floor, "bc1", True),
    "danceFloor_specular": (lambda: specular("glass"), "bc1", True),
    "speaker_diffuse": (speaker_cloth, "bc1", True),
    "speaker_specular": (lambda: specular("dark"), "bc1", True),
    "neonPink_diffuse": (lambda: neon((1.0, 0.28, 0.62)), "bc1", True),
    "neonCyan_diffuse": (lambda: neon((0.25, 0.92, 1.0)), "bc1", True),
    "neonYellow_diffuse": (lambda: neon((1.0, 0.86, 0.30)), "bc1", True),
    "neonGreen_diffuse": (lambda: neon((0.35, 1.0, 0.45)), "bc1", True),
    "mirror_diffuse": (mirror, "bc1", True),
    "mirror_specular": (lambda: specular("metal"), "bc1", True),
}


def generate(out_dir, build_dir, python=sys.executable, verbose=True, only=None):
    png2dds = os.path.join(os.path.dirname(_HERE), "png2dds.py")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)
    made = []
    for name, (fn, fmt, mips) in TEXTURES.items():
        if only is not None and name not in only:
            continue
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
