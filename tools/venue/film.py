# SPDX-License-Identifier: GPL-3.0-or-later
"""Cartoon films for the FS25 Autokino - drawn frame by frame with Pillow.

Three little silent films, each a seamless loop:

  * "Der kleine Traktor" - a red tractor crossing a field at sunset
  * "UFO ueber dem Hof"  - the saucer hovering over a farm at night
  * "Der Alien"          - a green alien waving at the audience

Every frame is a PNG the build step turns into a DDS that the Lua script swaps
onto the screen, so the "movie" needs no video codec at all.
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 320, 180


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def sky(top, bottom, w=W, h=H):
    """Vertical gradient."""
    arr = np.zeros((h, w, 3), dtype=np.float32)
    t = np.linspace(0, 1, h)[:, None]
    arr[:] = np.array(top, dtype=np.float32) * (1 - t)[..., None] + \
        np.array(bottom, dtype=np.float32) * t[..., None]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")


def stars(draw, count=46, seed=1, y_max=110, colour=(235, 235, 255)):
    rng = np.random.default_rng(seed)
    for _ in range(count):
        x = float(rng.uniform(0, W))
        y = float(rng.uniform(0, y_max))
        r = float(rng.uniform(0.5, 1.4))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)


def hills(img, y, colour, amp=8.0, phase=0.0, freq=0.03):
    d = ImageDraw.Draw(img)
    pts = [(0, H)]
    for x in range(0, W + 4, 4):
        pts.append((x, y + amp * math.sin(x * freq + phase)))
    pts.append((W, H))
    d.polygon(pts, fill=colour)
    return img


def glow(img, centre, radius, colour, strength=0.85):
    """Additive soft glow."""
    arr = np.asarray(img, dtype=np.float32) / 255.0
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt((xx - centre[0]) ** 2 + (yy - centre[1]) ** 2) / max(radius, 1e-3)
    a = np.clip(1.0 - d, 0, 1) ** 2 * strength
    arr = np.clip(arr + a[..., None] * np.array(colour, dtype=np.float32), 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8), "RGB")


def label(img, text):
    """Small film title in the bottom left, like an old home movie."""
    d = ImageDraw.Draw(img)
    d.rectangle([6, H - 20, 6 + 6 * len(text), H - 7], fill=(0, 0, 0))
    d.text((10, H - 18), text, fill=(245, 240, 210))
    return img


# --------------------------------------------------------------------------
# film 1: the little tractor
# --------------------------------------------------------------------------
def film_tractor(i, frames):
    p = i / float(frames)
    img = sky((0.99, 0.72, 0.42), (0.55, 0.36, 0.42))
    # low sun
    sun = (250, 150 - 10 * math.sin(p * math.tau))
    img = glow(img, (sun[0], sun[1]), 60, (0.45, 0.25, 0.05))
    d = ImageDraw.Draw(img)
    d.ellipse([sun[0] - 22, sun[1] - 22, sun[0] + 22, sun[1] + 22], fill=(255, 235, 150))
    # two hills behind the field
    hills(img, 108, (92, 74, 60), amp=5, phase=1.0)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 118, W, H], fill=(120, 96, 62))
    # furrows running with the tractor
    for k in range(7):
        y = 124 + k * 8
        d.line([(0, y), (W, y + 12)], fill=(104, 82, 52), width=2)
    # the tractor drives across, with a little bounce
    x = -60 + (W + 120) * ((p * 1.0) % 1.0)
    y = 120 + 2.0 * math.sin(p * math.tau * 8)
    # dust
    for k in range(4):
        dx = x - 34 - k * 12
        r = 5 + k * 2
        d.ellipse([dx - r, y + 16 - r * 0.6, dx + r, y + 16 + r * 0.6],
                  fill=(150, 126, 92))
    # wheels (rotating spokes)
    for wx, wr in ((x - 22, 12), (x + 22, 8)):
        d.ellipse([wx - wr, y + 12 - wr, wx + wr, y + 12 + wr], fill=(38, 34, 32))
        d.ellipse([wx - wr + 2, y + 12 - wr + 2, wx + wr - 2, y + 12 + wr - 2],
                  fill=(120, 108, 88))
        ang = p * math.tau * 4
        for k in range(3):
            a = ang + k * math.tau / 3
            d.line([(wx, y + 12), (wx + math.cos(a) * (wr - 3),
                                   y + 12 + math.sin(a) * (wr - 3))],
                   fill=(60, 54, 48), width=2)
    # body + cabin + chimney
    d.rectangle([x - 26, y - 4, x + 18, y + 14], fill=(178, 42, 34))
    d.rectangle([x - 10, y - 18, x + 12, y + 2], fill=(196, 56, 44))
    d.rectangle([x - 7, y - 15, x + 9, y + 1], fill=(150, 205, 220))
    d.rectangle([x + 2, y - 26, x + 7, y - 4], fill=(70, 66, 62))
    d.ellipse([x + 1, y - 29, x + 9, y - 24], fill=(90, 88, 84))
    # smoke puffs
    for k in range(3):
        t = (p + k / 3.0) % 1.0
        r = 2 + t * 6
        d.ellipse([x + 4 + t * 16 - r, y - 30 - t * 22 - r,
                   x + 4 + t * 16 + r, y - 30 - t * 22 + r],
                  fill=(200, 196, 190))
    # birds
    for k in range(3):
        bx = 40 + k * 26 + 18 * math.sin(p * math.tau + k)
        by = 40 + 8 * math.cos(p * math.tau * 2 + k)
        d.line([(bx - 5, by), (bx, by - 3), (bx + 5, by)], fill=(60, 40, 40), width=1)
    return label(img, "DER KLEINE TRAKTOR")


# --------------------------------------------------------------------------
# film 2: the saucer over the farm
# --------------------------------------------------------------------------
def film_ufo(i, frames):
    p = i / float(frames)
    img = sky((0.05, 0.07, 0.16), (0.10, 0.16, 0.28))
    d = ImageDraw.Draw(img)
    stars(d, 60, seed=4)
    # moon
    d.ellipse([250, 22, 286, 58], fill=(230, 232, 220))
    d.ellipse([258, 26, 276, 42], fill=(206, 210, 198))
    img = glow(img, (268, 40), 60, (0.20, 0.22, 0.18), 0.6)
    d = ImageDraw.Draw(img)
    # farm silhouette
    hills(img, 128, (16, 26, 22), amp=4, phase=2.0)
    d = ImageDraw.Draw(img)
    d.rectangle([30, 96, 96, 132], fill=(24, 32, 30))     # barn
    d.polygon([(26, 96), (63, 78), (100, 96)], fill=(30, 38, 36))
    d.rectangle([110, 108, 150, 132], fill=(22, 30, 28))  # house
    d.polygon([(106, 108), (130, 94), (154, 108)], fill=(28, 36, 34))
    for k in range(4):                                    # silo + fence
        d.line([(160 + k * 12, 132), (160 + k * 12, 120)], fill=(28, 36, 34), width=2)
    for k in range(3):                                    # warm windows
        d.rectangle([40 + k * 18, 108, 48 + k * 18, 116], fill=(250, 205, 120))
    btn = (40 + 18 * int(p * 8) % 54, 108)
    img = glow(img, btn, 18, (0.20, 0.14, 0.05), 0.8)
    d = ImageDraw.Draw(img)
    # the saucer, bobbing
    cx = 168 + 26 * math.sin(p * math.tau)
    cy = 58 + 6 * math.sin(p * math.tau * 2)
    # beam
    beam_r = 16 + 4 * math.sin(p * math.tau * 4)
    d.polygon([(cx - 6, cy + 6), (cx + 6, cy + 6),
               (cx + beam_r, 132), (cx - beam_r, 132)],
              fill=(80, 150, 60))
    img = glow(img, (cx, cy), 60, (0.12, 0.22, 0.10), 0.7)
    d = ImageDraw.Draw(img)
    d.polygon([(cx - 6, cy + 6), (cx + 6, cy + 6),
               (cx + beam_r, 132), (cx - beam_r, 132)],
              fill=(120, 200, 90))
    # hull: a lens shape with a bell jar
    d.ellipse([cx - 34, cy - 4, cx + 34, cy + 14], fill=(150, 170, 172))
    d.ellipse([cx - 34, cy + 2, cx + 34, cy + 12], fill=(96, 112, 116))
    d.ellipse([cx - 20, cy - 6, cx + 20, cy + 4], fill=(178, 198, 200))
    d.arc([cx - 9, cy - 22, cx + 9, cy + 2], 180, 360, fill=(190, 230, 235), width=3)
    d.line([(cx - 9, cy - 10), (cx - 9, cy + 2)], fill=(190, 230, 235), width=2)
    d.line([(cx + 9, cy - 10), (cx + 9, cy + 2)], fill=(190, 230, 235), width=2)
    # lights around the rim blink in sequence
    for k in range(9):
        a = math.tau * k / 9
        lx = cx + 32 * math.cos(a)
        ly = cy + 6 + 4 * math.sin(a)
        on = (k + int(p * 18)) % 9 < 3
        d.ellipse([lx - 1.6, ly - 1.6, lx + 1.6, ly + 1.6],
                  fill=(120, 255, 150) if on else (40, 80, 50))
    # crop circle in the field, growing
    gr = int(6 + 16 * min(1.0, (p % 0.5) * 2.0))
    d.ellipse([cx - gr, 128 - gr * 0.28, cx + gr, 128 + gr * 0.28],
              outline=(150, 190, 120), width=2)
    return label(img, "UFO UEBER DEM HOF")


# --------------------------------------------------------------------------
# film 3: the alien waves
# --------------------------------------------------------------------------
def film_alien(i, frames):
    p = i / float(frames)
    img = sky((0.03, 0.05, 0.12), (0.12, 0.10, 0.22))
    d = ImageDraw.Draw(img)
    stars(d, 70, seed=9)
    # a distant planet
    d.ellipse([24, 20, 70, 66], fill=(120, 90, 150))
    d.ellipse([18, 34, 76, 52], outline=(170, 140, 190), width=1)
    img = glow(img, (46, 42), 46, (0.10, 0.06, 0.12), 0.7)
    d = ImageDraw.Draw(img)
    # ground + a little fence
    d.rectangle([0, 140, W, H], fill=(26, 40, 30))
    for k in range(11):
        d.line([(k * 32, 140), (k * 32, 126)], fill=(40, 58, 44), width=2)
    d.line([(0, 130), (W, 130)], fill=(40, 58, 44), width=1)
    # the alien: big head, huge eyes, antennae
    cx = 160 + 4 * math.sin(p * math.tau)
    head_y = 74 + 3 * math.sin(p * math.tau * 2)
    d.ellipse([cx - 34, head_y - 34, cx + 34, head_y + 30], fill=(96, 190, 96))
    d.ellipse([cx - 30, head_y - 30, cx + 30, head_y + 24], fill=(126, 214, 110))
    # eyes
    blink = (p * 3.0) % 1.0 < 0.08
    for sx in (-1, 1):
        ex = cx + sx * 14
        if blink:
            d.line([(ex - 9, head_y - 2), (ex + 9, head_y - 2)], fill=(20, 40, 20), width=3)
        else:
            d.ellipse([ex - 9, head_y - 16, ex + 9, head_y + 8], fill=(245, 250, 245))
            d.ellipse([ex - 5 + sx * 2, head_y - 9, ex + 4 + sx * 2, head_y + 3],
                      fill=(22, 26, 24))
            d.ellipse([ex - 6 + sx * 2, head_y - 11, ex - 2 + sx * 2, head_y - 7],
                      fill=(255, 255, 255))
    # smile
    d.arc([cx - 14, head_y + 2, cx + 14, head_y + 22], 20, 160, fill=(40, 70, 40), width=2)
    # antennae with glowing tips
    for sx in (-1, 1):
        d.line([(cx + sx * 12, head_y - 32), (cx + sx * 20, head_y - 48)],
               fill=(96, 190, 96), width=3)
        tip = (cx + sx * 20, head_y - 48)
        d.ellipse([tip[0] - 4, tip[1] - 4, tip[0] + 4, tip[1] + 4],
                  fill=(220, 255, 180))
    img = glow(img, (cx, head_y - 48), 26, (0.10, 0.18, 0.05), 0.8)
    d = ImageDraw.Draw(img)
    # body and the waving arm
    d.rounded_rectangle([cx - 18, head_y + 20, cx + 18, 132], radius=10,
                        fill=(110, 200, 104))
    wave = math.sin(p * math.tau * 2) * 0.7
    ax, ay = cx + 16, head_y + 34
    d.line([(ax, ay), (ax + 16 * math.cos(wave), ay - 18 * math.sin(wave) - 6)],
           fill=(110, 200, 104), width=7)
    hx = ax + 16 * math.cos(wave)
    hy = ay - 18 * math.sin(wave) - 6
    d.ellipse([hx - 5, hy - 5, hx + 5, hy + 5], fill=(126, 214, 110))
    # speech bubble on the second half
    if 0.35 < p < 0.95:
        d.rounded_rectangle([cx + 34, head_y - 58, cx + 96, head_y - 22], radius=8,
                            fill=(250, 250, 240))
        d.polygon([(cx + 40, head_y - 24), (cx + 36, head_y - 10), (cx + 52, head_y - 22)],
                  fill=(250, 250, 240))
        d.text((cx + 46, head_y - 48), "HALLO!", fill=(40, 60, 40))
    return label(img, "DER ALIEN")


FILMS = (
    ("tractor", "DER KLEINE TRAKTOR", film_tractor),
    ("ufo", "UFO UEBER DEM HOF", film_ufo),
    ("alien", "DER ALIEN", film_alien),
)

FRAMES = 16
FPS = 6.0


def render_frames(out_dir, frames=FRAMES, size=(W, H)):
    """Write every frame as a PNG; returns {film: [paths]}."""
    os.makedirs(out_dir, exist_ok=True)
    out = {}
    for key, _title, fn in FILMS:
        paths = []
        for i in range(frames):
            img = fn(i, frames)
            if size != (W, H):
                img = img.resize(size, Image.LANCZOS)
            p = os.path.join(out_dir, "%s_%02d.png" % (key, i))
            img.save(p)
            paths.append(p)
        out[key] = paths
    return out


def generate(out_dir, build_dir, python=None, size=(W, H), verbose=True):
    """Render every frame of every film and convert it to a BC1 DDS.

    The Lua swaps these textures on the screen (one material map per frame),
    which needs no video codec and stays in sync through the network time.
    """
    import subprocess
    import sys

    python = python or sys.executable
    png2dds = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "png2dds.py")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(build_dir, exist_ok=True)
    made = []
    for key, _title, fn in FILMS:
        for i in range(FRAMES):
            img = fn(i, FRAMES)
            if size != (W, H):
                img = img.resize(size, Image.LANCZOS)
            png = os.path.join(build_dir, "%s_%02d.png" % (key, i))
            img.save(png)
            dds = os.path.join(out_dir, "%s_%02d.dds" % (key, i))
            # mip chains need power-of-two sizes, so the film frames go
            # without mips - they are seen from far away anyway
            subprocess.run([python, os.path.abspath(png2dds), png, dds,
                            "--format", "bc1", "--no-mips"], check=True,
                           stdout=subprocess.DEVNULL)
            made.append(dds)
        if verbose:
            print("  %-8s %2d frames  %5.1f kB" % (
                key, FRAMES,
                sum(os.path.getsize(f) for f in made[-FRAMES:]) / 1024.0))
    return made
