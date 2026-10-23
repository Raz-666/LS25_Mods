#!/usr/bin/env python3
"""What crop circles look like when you simply drive them (FS25_UFO2500).

The stamps are computed exactly like WheelDestruction does it (see
brush_test.py), the shapes come from the driving path - there is no script in
the mod that knows about patterns.

    python tools/ufo/brush_patterns.py  ->  docs/renders/ufo2500_patterns.png
"""

import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import brush_test as bt  # noqa: E402

TILE = 300          # pixels per tile
PAD = 18
GRID = 0.20         # coarser raster for the picture (2 dm)
bt.GRID = GRID


def font(size):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


F_LABEL = font(15)
F_HEAD = font(19)
F_SMALL = font(13)


def circle(radius, cx=0.0, cz=0.0, cw=1):
    length = 2 * math.pi * radius
    n = max(int(length / bt.STEP), 16)
    return [(cx + radius * math.cos(2 * math.pi * i / n * cw),
             cz + radius * math.sin(2 * math.pi * i / n * cw),
             2 * math.pi * i / n) for i in range(n)]


def line(x0, z0, x1, z1):
    n = max(int(math.hypot(x1 - x0, z1 - z0) / bt.STEP), 2)
    heading = math.atan2(x1 - x0, z1 - z0)
    return [(x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n, heading)
            for i in range(n + 1)]


def polyline(waypoints, close=False):
    """Drive through waypoints, one frame every STEP metres."""
    points = list(waypoints) + ([waypoints[0]] if close else [])
    path = []
    for (x0, z0), (x1, z1) in zip(points, points[1:]):
        heading = math.atan2(x1 - x0, z1 - z0)
        n = max(int(math.hypot(x1 - x0, z1 - z0) / bt.STEP), 1)
        for i in range(n):
            path.append((x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n, heading))
    path.append((points[-1][0], points[-1][1], path[-1][2] if path else 0.0))
    return path


def star(points, r_out, r_in):
    way = []
    for k in range(points * 2):
        a = math.pi * k / points
        r = r_out if k % 2 == 0 else r_in
        way.append((r * math.sin(a), r * math.cos(a)))
    return polyline(way, close=True)


def squiggle():
    """a freehand pen line, the way it comes out of a 0.5 m brush"""
    return [(0.62 * math.sin(t * 0.9) * (0.3 + t / 9.0),
             -6.0 + t, math.atan(0.62 * 0.9 * math.cos(t * 0.9)) + math.pi)
            for t in np.linspace(0.0, 12.0, 400)]


def tile_image(veh_cfg, path, half, title, subtitle):
    lo = -half
    size = int(2 * half / GRID) + 1
    rects = bt.drive(veh_cfg, path)
    grid = bt.grid_of(rects, lo, size)

    rng = np.random.default_rng(7)
    img = np.zeros((size, size, 3), dtype=np.float32)
    noise = rng.normal(scale=0.035, size=(size, size))
    img[..., 0] = 0.78 + noise
    img[..., 1] = 0.66 + noise
    img[..., 2] = 0.29 + noise * 0.6
    # pressed crop: flat, dull and noticeably darker than standing wheat
    img[grid] = img[grid] * 0.55 + np.array([0.34, 0.31, 0.18]) * 0.45
    img[grid] *= 0.92
    # a bright rim where the stalks are bent over
    edge = np.zeros_like(grid)
    edge[1:, :] |= grid[1:, :] & ~grid[:-1, :]
    edge[:-1, :] |= grid[:-1, :] & ~grid[1:, :]
    edge[:, 1:] |= grid[:, 1:] & ~grid[:, :-1]
    edge[:, :-1] |= grid[:, :-1] & ~grid[:, 1:]
    img[edge] = np.clip(img[edge] * 1.35 + 0.08, 0, 1)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
    im = im.resize((TILE, TILE), Image.LANCZOS)

    label = Image.new("RGB", (TILE, TILE + 42), (18, 28, 24))
    label.paste(im, (0, 0))
    d = ImageDraw.Draw(label)
    d.text((2, TILE + 4), title, fill=(215, 240, 225), font=F_LABEL)
    d.text((2, TILE + 23), subtitle, fill=(130, 172, 152), font=F_SMALL)
    return label


def main():
    veh, nodes = bt.load()
    cfgs = {save_id: wheels for _n, save_id, wheels in bt.configs(veh, nodes)}

    tiles = [
        tile_image(cfgs["PEN"], squiggle(), 3.2, "PEN · 0,5 m",
                   "frei gemalt, wie mit einem dicken Stift"),
        tile_image(cfgs["RING"], circle(4.0), 5.6,
                   "RING · 1,5 m", "ein Kreis, eine Runde fahren"),
        tile_image(cfgs["STANDARD"],
                   circle(9.0) + line(9.0, 0.0, 4.0, 0.0) + circle(4.0),
                   11.0, "STANDARD · 3,5 m", "Doppelring mit Verbindung"),
        tile_image(cfgs["HARVESTER"], star(4, 8.0, 3.6), 9.5,
                   "HARVESTER · 7,5 m", "ein Stern aus geraden Bahnen"),
    ]

    cols = 2
    rows = 2
    w = cols * TILE + (cols + 1) * PAD
    h = 96 + rows * (TILE + 42) + (rows + 1) * PAD
    out = Image.new("RGB", (w, h), (14, 22, 18))
    d = ImageDraw.Draw(out)
    d.text((PAD, 22), "FS25_UFO2500 – Kornkreise, einfach gefahren", fill=(235, 245, 240), font=F_HEAD)
    d.text((PAD, 52),
           "Kein Skript, keine Mustertaste: der Pinsel drückt genau die Spur platt, die du fährst.",
           fill=(140, 180, 160), font=F_SMALL)

    for i, tile in enumerate(tiles):
        x = PAD + (i % cols) * (TILE + PAD)
        y = 92 + (i // cols) * (TILE + 42 + PAD)
        out.paste(tile, (x, y))

    path = os.path.join(REPO, "docs", "renders", "ufo2500_patterns.png")
    out.save(path)
    print("wrote", path)


if __name__ == "__main__":
    sys.exit(main())
