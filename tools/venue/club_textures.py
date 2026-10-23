# SPDX-License-Identifier: GPL-3.0-or-later
"""Texture set for FS25_Distillery - the Leipzig techno club.

Brick walls (red and soot-black), graffiti tags for the facade, rough concrete
for the dance floor, cobblestones for the street, rusty steel for stairs and
ducts, PA cabinet cloth, stage wood and the neon tube colours.
"""

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

import signs  # noqa: E402

BRICK = (92, 48, 38)
BRICK_B = (120, 66, 50)
BRICK_C = (74, 40, 33)
MORTAR = (128, 122, 112)


# --------------------------------------------------------------------------
def _bricks(size, rows, cols, palette, mortar=MORTAR, jitter=0.16, seed=1,
            soot=0.0):
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (size, size), mortar)
    d = ImageDraw.Draw(img)
    bh = size // rows
    bw = size // cols
    for r in range(rows):
        for c in range(cols):
            off = (bw // 2) if r % 2 else 0
            x0 = c * bw - off
            y0 = r * bh
            base = palette[int(rng.integers(0, len(palette)))]
            v = rng.uniform(1.0 - jitter, 1.0 + jitter)
            col = tuple(int(min(255, max(0, ch * v))) for ch in base)
            d.rectangle([x0 + 2, y0 + 2, x0 + bw - 3, y0 + bh - 3], fill=col)
            # a little highlight on the top edge
            d.line([(x0 + 2, y0 + 2), (x0 + bw - 3, y0 + 2)],
                   fill=tuple(int(min(255, ch * 1.18)) for ch in col))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    grit = _noise(size, size // 3, seed=seed + 7)
    arr *= (0.94 + 0.12 * grit)[..., None]
    if soot:
        # soot collects from the top and in the joints
        yy = np.linspace(0, 1, size)[:, None, None]
        stain = _noise(size, 24, seed=seed + 3)[..., None]
        arr *= (1.0 - soot * (0.45 + 0.35 * yy) * (0.6 + 0.4 * stain))
    return _to_img(np.clip(arr, 0, 1))


def brick(size=512):
    return _bricks(size, 16, 8, (BRICK, BRICK_B, BRICK_C, (104, 56, 42),
                                 (88, 46, 36)), seed=3)


def brick_dark(size=512):
    return _bricks(size, 16, 8, ((58, 34, 30), (48, 30, 27), (66, 40, 33),
                                 (54, 32, 28)), mortar=(70, 66, 62),
                   seed=5, soot=0.55)


def brick_graffiti(size=512):
    """Facade with tags: the signature look of the entrance."""
    base = brick(size).convert("RGB")
    d = ImageDraw.Draw(base)
    rng = np.random.default_rng(11)
    palette = [(240, 90, 180), (60, 190, 240), (250, 220, 60), (120, 230, 90),
               (250, 130, 40), (170, 110, 240), (250, 250, 250)]
    for _ in range(9):
        col = palette[int(rng.integers(0, len(palette)))]
        x = rng.uniform(-40, size)
        y = rng.uniform(0, size)
        # a fat bubble stroke with a dark outline, like a tag
        pts = [(x, y)]
        for _k in range(5):
            x += rng.uniform(20, 70)
            y += rng.uniform(-45, 45)
            pts.append((x, y))
        d.line(pts, fill=(20, 20, 22), width=int(rng.uniform(18, 34)), joint="curve")
        d.line(pts, fill=col, width=int(rng.uniform(10, 20)), joint="curve")
        for _k in range(3):
            cx, cy = pts[int(rng.integers(0, len(pts)))]
            r = rng.uniform(8, 22)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(22, 22, 24), width=5)
            d.ellipse([cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3], outline=col, width=4)
    # paint drips
    for _ in range(40):
        x = rng.uniform(0, size)
        y = rng.uniform(0, size * 0.9)
        h = rng.uniform(10, 60)
        c = palette[int(rng.integers(0, len(palette)))]
        d.line([(x, y), (x, y + h)], fill=c, width=2)
    return base.filter(ImageFilter.SMOOTH)


def graffiti_overlay(size=512):
    """Transparent-ish graffiti sheet for the inside walls (dark background)."""
    img = Image.new("RGB", (size, size), (30, 26, 26))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(21)
    palette = [(240, 90, 180), (60, 190, 240), (250, 220, 60), (120, 230, 90),
               (250, 130, 40), (200, 200, 200)]
    for _ in range(14):
        col = palette[int(rng.integers(0, len(palette)))]
        pts = [(rng.uniform(0, size), rng.uniform(0, size))]
        for _k in range(4):
            x, y = pts[-1]
            pts.append((x + rng.uniform(-80, 80), y + rng.uniform(-60, 60)))
        d.line(pts, fill=col, width=int(rng.uniform(6, 14)), joint="curve")
    return img.filter(ImageFilter.GaussianBlur(0.6))


def concrete(size=512):
    n = _noise(size, 64, seed=31)
    fine = _noise(size, size // 2, seed=32)
    base = np.array((0.33, 0.32, 0.31), dtype=np.float32)
    arr = base[None, None, :] * (0.82 + 0.34 * n[..., None])
    arr += (fine[..., None] - 0.5) * 0.06
    img = _to_img(np.clip(arr, 0, 1))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(33)
    for _ in range(28):                      # scuffs and stains
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        r = rng.uniform(6, 40)
        v = int(rng.uniform(30, 65))
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=(v, v, v - 2))
    for _ in range(6):                       # painted lines, worn
        d.line([(0, rng.uniform(0, size)), (size, rng.uniform(0, size))],
               fill=(150, 150, 145), width=2)
    return img.filter(ImageFilter.GaussianBlur(0.7))


def concrete_dark(size=512):
    img = concrete(size)
    arr = np.asarray(img, dtype=np.float32) * 0.55
    return _to_img(np.clip(arr / 255.0, 0, 1))


def cobbles(size=512):
    img = Image.new("RGB", (size, size), (52, 50, 48))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(41)
    step = size // 12
    for row in range(12):
        for col in range(13):
            x = col * step + (step // 2 if row % 2 else 0)
            y = row * step
            w = step * rng.uniform(0.78, 0.94)
            h = step * rng.uniform(0.72, 0.9)
            v = int(rng.uniform(78, 128))
            d.rounded_rectangle([x, y, x + w, y + h], radius=4,
                                fill=(v, v - 3, v - 6),
                                outline=(40, 39, 38), width=2)
    return img.filter(ImageFilter.GaussianBlur(0.8))


def gravel(size=512):
    img = Image.new("RGB", (size, size), (66, 62, 57))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(42)
    for _ in range(2800):
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        r = rng.uniform(1.2, 3.6)
        v = int(rng.uniform(56, 116))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(v, int(v * 0.96), int(v * 0.9)))
    return img


def rusty_steel(size=512):
    n = _noise(size, 48, seed=51)
    rust = _noise(size, 16, seed=52)
    base = np.array((0.26, 0.25, 0.25), dtype=np.float32)
    arr = base[None, None, :] * (0.8 + 0.4 * n[..., None])
    r = np.clip((rust - 0.52) * 3.0, 0, 1)[..., None]
    arr = arr * (1 - r) + np.array((0.42, 0.20, 0.09), dtype=np.float32) * r
    # rivet-ish grid
    yy, xx = np.mgrid[0:size, 0:size]
    step = size // 8
    dots = ((xx % step) - step // 2) ** 2 + ((yy % step) - step // 2) ** 2
    arr += (np.clip(1 - dots / 12.0, 0, 1) * 0.10)[..., None]
    return _to_img(np.clip(arr, 0, 1))


def speaker_cloth(size=256):
    img = Image.new("RGB", (size, size), (26, 26, 28))
    d = ImageDraw.Draw(img)
    for i in range(0, size, 4):
        d.line([(i, 0), (i, size)], fill=(36, 36, 40))
        d.line([(0, i), (size, i)], fill=(22, 22, 25))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr *= (0.9 + 0.2 * _noise(size, 64, seed=61))[..., None]
    return _to_img(np.clip(arr, 0, 1))


def wood_dark(size=512):
    img = Image.new("RGB", (size, size), (60, 42, 30))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(71)
    step = size // 7
    for i in range(7):
        v = int(rng.uniform(-14, 14))
        d.rectangle([0, i * step, size, (i + 1) * step - 3],
                    fill=(66 + v, 46 + v // 2, 32 + v // 3))
        for _k in range(30):
            gy = i * step + rng.uniform(3, step - 5)
            d.line([(0, gy), (size, gy + rng.uniform(-2, 2))],
                   fill=(52 + v, 36 + v, 26 + v // 2), width=1)
    return img.filter(ImageFilter.GaussianBlur(0.5))


def neon(rgb, size=128):
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    r = np.sqrt((xx - size / 2) ** 2 + (yy - size / 2) ** 2) / (size / 2)
    core = np.clip(1.0 - r, 0, 1) ** 0.35
    base = np.array(rgb, dtype=np.float32)
    arr = np.clip(base[None, None, :] * (0.7 + 0.5 * core[..., None]) +
                  core[..., None] * 0.35, 0, 1)
    return _to_img(arr)


def stage_light(size=256):
    """The lit floor of the stage: black with a magenta wash."""
    n = _noise(size, 32, seed=81)
    arr = np.dstack([0.10 + 0.25 * n, 0.02 + 0.05 * n, 0.16 + 0.30 * n])
    return _to_img(np.clip(arr, 0, 1))


def mirror_disc(size=256):
    img = Image.new("RGB", (size, size), (150, 155, 165))
    d = ImageDraw.Draw(img)
    step = size // 8
    rng = np.random.default_rng(91)
    for i in range(8):
        for j in range(8):
            v = int(rng.uniform(110, 235))
            d.rectangle([j * step + 1, i * step + 1, (j + 1) * step - 2, (i + 1) * step - 2],
                        fill=(v, int(v * 0.98), min(255, int(v * 1.05))))
    return img


TEXTURES = {
    "brick_diffuse": (brick, "bc1", True),
    "brick_specular": (lambda: specular("dark"), "bc1", True),
    "brickDark_diffuse": (brick_dark, "bc1", True),
    "brickDark_specular": (lambda: specular("dark"), "bc1", True),
    "brickGraffiti_diffuse": (brick_graffiti, "bc1", True),
    "brickGraffiti_specular": (lambda: specular("dark"), "bc1", True),
    "graffiti_diffuse": (graffiti_overlay, "bc1", True),
    "concrete_diffuse": (concrete, "bc1", True),
    "concrete_specular": (lambda: specular("paint"), "bc1", True),
    "concreteDark_diffuse": (concrete_dark, "bc1", True),
    "concreteDark_specular": (lambda: specular("paint"), "bc1", True),
    "cobble_diffuse": (cobbles, "bc1", True),
    "cobble_specular": (lambda: specular("paint"), "bc1", True),
    "gravel_diffuse": (gravel, "bc1", True),
    "gravel_specular": (lambda: specular("dark"), "bc1", True),
    "steel_diffuse": (rusty_steel, "bc1", True),
    "steel_specular": (lambda: specular("metal"), "bc1", True),
    "speaker_diffuse": (speaker_cloth, "bc1", True),
    "speaker_specular": (lambda: specular("dark"), "bc1", True),
    "woodDark_diffuse": (wood_dark, "bc1", True),
    "woodDark_specular": (lambda: specular("paint"), "bc1", True),
    "stage_diffuse": (stage_light, "bc1", True),
    "stage_specular": (lambda: specular("glass"), "bc1", True),
    "mirror_diffuse": (mirror_disc, "bc1", True),
    "mirror_specular": (lambda: specular("metal"), "bc1", True),
    "neonCyan_diffuse": (lambda: neon((0.30, 0.80, 1.0)), "bc1", True),
    "neonPink_diffuse": (lambda: neon((1.0, 0.25, 0.60)), "bc1", True),
    "neonAmber_diffuse": (lambda: neon((1.0, 0.62, 0.20)), "bc1", True),
    "neonWhite_diffuse": (lambda: neon((0.95, 0.95, 1.0)), "bc1", True),
    "signDistillery_diffuse": (lambda: _sign("signDistillery.png"), "bc1", True),
    "signLeipzig_diffuse": (lambda: _sign("signLeipzig.png"), "bc1", True),
    "signBar_diffuse": (lambda: _sign("signBar.png"), "bc1", True),
    "playlist_diffuse": (lambda: _playlist(), "bc1", True),
}

_SIGN_CACHE = {}


def _pot(img, size=(1024, 512)):
    """Fit an image into a power-of-two canvas (black border) - the DDS mip
    generator needs POT sizes and the sign panels are vignetted to black."""
    canvas = Image.new("RGB", size, (0, 0, 0))
    w, h = img.size
    scale = min(size[0] / float(w), size[1] / float(h))
    img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    canvas.paste(img, ((size[0] - img.size[0]) // 2, (size[1] - img.size[1]) // 2))
    return canvas


def _sign(name):
    if name not in _SIGN_CACHE:
        path = os.path.join(_HERE, "..", "..", "build", "club_signs", name)
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            signs.sign_pair(512, os.path.dirname(path))
        img = Image.open(path).convert("RGB")
        _SIGN_CACHE[name] = _pot(img, (1024, 512) if name.startswith("signDistillery")
                                 else (512, 512))
    return _SIGN_CACHE[name]


def _playlist():
    """The set list board - titles come from the club module, so geometry,
    texture, sounds xml and script always agree."""
    import distillery
    path = os.path.abspath(os.path.join(_HERE, "..", "..", "build", "club_signs",
                                        "playlist.png"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    signs.playlist_panel([t[1] for t in distillery.TRACKS], out_path=path)
    return _pot(Image.open(path).convert("RGB"), (1024, 512))


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
            print("  %-28s %s %6.1f kB" % (name + ".dds", fmt,
                                           os.path.getsize(dds) / 1024.0))
    return made


if __name__ == "__main__":
    repo = os.path.dirname(os.path.dirname(_HERE))
    generate(os.path.join(repo, "build", "club_tex"), os.path.join(repo, "build", "club_png"))
