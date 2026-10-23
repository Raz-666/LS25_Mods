# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural texture set for the UFO 2000 (PNG -> DDS).

The saucer uses lathe UVs: u runs around the hull (0..1 = full circle) and v
runs along the profile (bottom centre -> rim -> dome base), so panel seams are
drawn as vertical lines and ring bands as horizontal ones.
"""

import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CREAM = (231, 240, 232)
MINT = (150, 219, 190)
DEEP = (38, 58, 54)
GRAPHITE = (74, 82, 86)
GREEN = (86, 255, 150)
RED = (255, 74, 74)
WHITE = (255, 245, 214)
CYAN = (120, 235, 255)
SKIN = (150, 226, 138)


def _noise(size, scale=64, seed=0, octaves=3):
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), dtype=np.float32)
    amp = 1.0
    total = 0.0
    for o in range(octaves):
        s = max(2, scale >> o)
        grid = rng.random((s + 1, s + 1)).astype(np.float32)
        img = np.array(Image.fromarray((grid * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC),
                       dtype=np.float32) / 255.0
        out += img * amp
        total += amp
        amp *= 0.5
    return out / total


def _to_img(arr, alpha=None):
    arr = np.clip(arr, 0, 1)
    if alpha is None:
        return Image.fromarray((arr * 255).astype(np.uint8), "RGB")
    a = np.clip(alpha, 0, 1)
    rgba = np.dstack([arr, a[..., None]])
    return Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")


def _color(rgb):
    return np.array([c / 255.0 for c in rgb], dtype=np.float32)


# --------------------------------------------------------------------------
def hull_paint(size=512):
    base = _color(CREAM)
    n = _noise(size, 48, seed=11)
    grad = np.linspace(0, 1, size)[None, :, None]
    arr = np.ones((size, size, 3), dtype=np.float32) * base
    arr *= (0.9 + 0.16 * n[..., None])
    # soft mint tint towards the rim (v grows towards the rim/lip)
    v = np.linspace(0, 1, size)[:, None, None]
    mint = _color(MINT)
    arr = arr * (1 - 0.35 * v) + mint * (0.35 * v)
    img = _to_img(arr)
    d = ImageDraw.Draw(img)

    # radial panel seams every 30 degrees
    for i in range(12):
        x = int(i * size / 12)
        d.line([(x, 0), (x, size)], fill=tuple(int(c * 255) for c in _color(DEEP) * 0.55), width=2)
        d.line([(x + 3, 0), (x + 3, size)], fill=(250, 252, 248), width=1)

    # horizontal structural bands
    for frac, width in ((0.30, 3), (0.66, 4), (0.80, 2)):
        y = int(frac * size)
        d.line([(0, y), (size, y)], fill=tuple(int(c * 255) for c in _color(DEEP) * 0.7), width=width)
        d.line([(0, y + width), (size, y + width)], fill=(252, 253, 250), width=1)

    # rivets along the seams
    for i in range(12):
        x = i * size / 12
        for yf in (0.13, 0.22, 0.40, 0.52, 0.60, 0.72, 0.86):
            y = yf * size
            for ox in (-7, 7):
                d.ellipse([x + ox - 2, y - 2, x + ox + 2, y + 2], fill=(196, 208, 200))

    # faint warning stripe near the rim
    y0 = int(0.735 * size)
    for i in range(int(size / 16)):
        x = i * 16
        d.polygon([(x, y0), (x + 9, y0), (x + 16, y0 + 10), (x + 7, y0 + 10)],
                  fill=tuple(int(c * 255) for c in _color((214, 168, 74))))
    img = img.filter(ImageFilter.SMOOTH)
    return img


def hull_metal(size=512):
    base = _color(GRAPHITE)
    n = _noise(size, 128, seed=5, octaves=2)
    arr = np.ones((size, size, 3), dtype=np.float32) * base
    arr *= (0.85 + 0.3 * n[..., None])
    img = _to_img(arr)
    d = ImageDraw.Draw(img)
    for y in range(0, size, 4):
        shade = 66 + (y * 7 % 23)
        d.line([(0, y), (size, y)], fill=(shade, shade + 5, shade + 6), width=1)
    for i in range(0, size, 64):
        d.line([(i, 0), (i, size)], fill=(52, 58, 62), width=3)
    for i in range(0, size, 64):
        for j in range(0, size, 64):
            d.ellipse([i + 6, j + 6, i + 14, j + 14], fill=(120, 128, 132))
    return img.filter(ImageFilter.SMOOTH)


def cockpit(size=256):
    base = _color((44, 54, 52))
    n = _noise(size, 24, seed=7)
    arr = np.ones((size, size, 3), dtype=np.float32) * base
    arr *= (0.9 + 0.2 * n[..., None])
    img = _to_img(arr)
    d = ImageDraw.Draw(img)
    for i in range(0, size, 32):
        d.line([(i, 0), (i, size)], fill=(30, 38, 37), width=2)
        d.line([(0, i), (size, i)], fill=(30, 38, 37), width=2)
    for i in range(16):
        x = (i * 37) % size
        y = (i * 61) % size
        d.ellipse([x, y, x + 6, y + 6], fill=(90, 210, 150))
    return img.filter(ImageFilter.SMOOTH)


def glass(size=256):
    yy, xx = np.mgrid[0:size, 0:size] / float(size)
    # a soft diagonal sheen plus a fresnel-like darkening at the edges
    sheen = np.clip(1.0 - np.abs((xx * 0.8 + yy * 0.6) - 0.42) * 3.2, 0, 1) ** 2
    arr = np.ones((size, size, 3), dtype=np.float32) * _color((170, 232, 240))
    arr = arr * (0.85 + 0.25 * sheen[..., None])
    alpha = 0.30 + 0.45 * sheen
    return _to_img(arr, alpha)


def lens(rgb, size=128, glow=1.0):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    core = np.clip(1.0 - r, 0, 1) ** 0.6
    base = _color(rgb)
    arr = base[None, None, :] * (0.35 + 0.85 * core[..., None] * glow)
    arr = np.clip(arr, 0, 1)
    arr = np.clip(arr + (1.0 - r)[..., None] * 0.35, 0, 1)
    return _to_img(arr)


def alien_skin(size=256):
    n = _noise(size, 16, seed=3, octaves=4)
    arr = np.ones((size, size, 3), dtype=np.float32) * _color(SKIN)
    arr *= (0.86 + 0.24 * n[..., None])
    yy = np.linspace(0, 1, size)[:, None, None]
    arr = arr * (1 - 0.25 * yy) + _color((206, 244, 180)) * (0.25 * yy)
    return _to_img(arr)


def eye_black(size=128):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
    arr = np.ones((size, size, 3), dtype=np.float32) * _color((14, 18, 22))
    sheen = np.clip(1.0 - np.abs((xx + yy) - 0.5) * 3.0, 0, 1) ** 2
    arr = arr + sheen[..., None] * _color((60, 90, 120)) * 0.5
    return _to_img(arr)


def beam(size=256):
    yy = np.linspace(0, 1, size)[:, None]
    xx = np.linspace(0, 1, size)[None, :]
    arr = np.ones((size, size, 3), dtype=np.float32) * _color(CYAN)
    alpha = np.clip(0.62 * (1.0 - yy) ** 1.4, 0, 1) * np.ones((1, size))
    streak = 0.75 + 0.25 * np.sin(xx * 40) ** 2
    arr = arr * (0.6 + 0.5 * (1 - yy)[..., None]) * streak[..., None]
    return _to_img(arr, alpha * streak)


def specular(kind, size=256):
    if kind == "paint":
        base = 0.42
        n = _noise(size, 32, seed=21) * 0.10
    elif kind == "metal":
        base = 0.72
        n = _noise(size, 96, seed=22) * 0.12
    elif kind == "glass":
        base = 0.92
        n = _noise(size, 16, seed=23) * 0.05
    else:
        base = 0.22
        n = _noise(size, 32, seed=24) * 0.08
    v = np.clip(base + n - 0.05, 0, 1)
    arr = np.dstack([v, v, v])
    return _to_img(arr)


# --------------------------------------------------------------------------
TEXTURES = {
    "hullPaint_diffuse": (hull_paint, "bc1", True),
    "hullPaint_specular": (lambda: specular("paint"), "bc1", True),
    "hullMetal_diffuse": (hull_metal, "bc1", True),
    "hullMetal_specular": (lambda: specular("metal"), "bc1", True),
    "cockpit_diffuse": (cockpit, "bc1", True),
    "cockpit_specular": (lambda: specular("dark"), "bc1", True),
    "glass_diffuse": (glass, "bc3", True),
    "glass_specular": (lambda: specular("glass"), "bc1", True),
    "lensGreen_diffuse": (lambda: lens(GREEN), "bc1", True),
    "lensRed_diffuse": (lambda: lens(RED), "bc1", True),
    "lensWhite_diffuse": (lambda: lens(WHITE), "bc1", True),
    "alienSkin_diffuse": (alien_skin, "bc1", True),
    "alienSkin_specular": (lambda: specular("dark"), "bc1", True),
    "eyeBlack_diffuse": (eye_black, "bc1", True),
    "beam_diffuse": (beam, "bc3", True),
}


def generate(out_dir, build_dir, png2dds=os.path.join(os.path.dirname(__file__), "..", "png2dds.py"),
             python=sys.executable, verbose=True):
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)
    made = []
    for name, (fn, fmt, mips) in TEXTURES.items():
        png = os.path.join(build_dir, name + ".png")
        img = fn()
        img.save(png)
        dds = os.path.join(out_dir, name + ".dds")
        cmd = [python, os.path.abspath(png2dds), png, dds, "--format", fmt]
        if not mips:
            cmd.append("--no-mips")
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        made.append(dds)
        if verbose:
            print("  %-26s %s  %6.1f kB" % (name + ".dds", fmt, os.path.getsize(dds) / 1024.0))
    return made


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    generate(os.path.join(repo, "FS25_UFO2000", "textures"), os.path.join(repo, "build", "textures"))
