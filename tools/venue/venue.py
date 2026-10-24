# SPDX-License-Identifier: GPL-3.0-or-later
"""Shared building blocks for the venue mods (Disco, Autokino)."""

import math

from meshlib import Mesh, box
from model import Node

def quad(corners, material, mesh, uvs=None):
    """A flat quad from four corner points (counter clockwise, seen from front)."""
    verts = list(corners)
    if uvs is None:
        uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    a, b, c = verts[0], verts[1], verts[2]
    ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    n = (nx / ln, ny / ln, nz / ln)
    mesh.add(material, verts, [n] * 4, uvs, [(0, 1, 2), (0, 2, 3)])


# how many metres one texture tile covers, per material - keeps brick and
# cobbles at a believable size instead of stretching one tile over a wall
TILE = {
    "brick": 2.0, "brickDark": 2.0, "brickGraffiti": 2.0,
    "concrete": 3.0, "concreteDark": 3.0,
    "cobble": 2.0, "gravel": 3.0,
    "steel": 1.2, "woodDark": 1.5, "speaker": 1.2,
    "stage": 2.0, "mirror": 1.0,
    "brickRed": 2.4, "graffitiDense": 5.2, "window": 1.2, "roof": 2.0,
    "lightFlower": 9.0,
}


def slab(mesh, material, centre, size, tile=None):
    if tile is None:
        tile = TILE.get(material)
    m = box(centre, size, tile=tile)
    mesh.add(material, *m)


FONT = {
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    " ": ("00000",) * 7,
}


def sign_mesh(text="DISCO", pixel=0.13, gap=0.30):
    """Chunky pixel letters lying flat on the front gable."""
    m = {}
    cols = 5
    width = len(text) * (cols + 1) * pixel + (len(text) - 1) * gap
    x0 = -width * 0.5
    for i, ch in enumerate(text):
        glyph = FONT[ch]
        ox = x0 + i * (cols * pixel + gap)
        for row in range(7):
            for col in range(cols):
                if glyph[6 - row][col] != "1":
                    continue
                cx = ox + (col + 0.5) * pixel
                cy = (row + 0.5) * pixel
                m[(round(cx, 4), round(cy, 4))] = True
    return m, width


def neon_sign(material_name, text="DISCO", pixel=0.13, gap=0.30, z=0.0, y=0.0):
    """Build the pixel letters as one shape node at the front wall."""
    pts, width = sign_mesh(text, pixel, gap)
    mesh = Mesh()
    depth = 0.24
    for (cx, cy) in pts:
        slab(mesh, material_name,
             (cx, cy + y, z + depth * 0.5),
             (pixel * 1.05, pixel * 1.05, depth))
    return Node("Shape", "neonSign", mesh, translation="0 0 0"), width


def area(name, x, y, z, width, height):
    """Start node plus the width / height vector nodes the game expects."""
    start = Node("TransformGroup", name, translation="%g %g %g" % (x, y, z))
    start.add(Node("TransformGroup", name + "Width", translation="%g 0 0" % width))
    start.add(Node("TransformGroup", name + "Height", translation="0 0 %g" % height))
    return start


def line_area(name, start, end):
    node = Node("TransformGroup", name
                , translation="%g %g %g" % tuple(start))
    node.add(Node("TransformGroup", name + "End",
                  translation="%g 0 %g" % (end[0] - start[0], end[2] - start[2])))
    return node


# --------------------------------------------------------------------------
# preview helpers: paste a film frame onto the rendered screen
# --------------------------------------------------------------------------
def project_points(pts, eye, target, fov, size):
    """Project world points to image pixels with the software renderer camera."""
    import numpy as np
    import render

    view = render.look_at(tuple(eye), tuple(target))
    f = 1.0 / math.tan(math.radians(fov) / 2.0)
    vp = np.array([[f, 0, 0, 0], [0, f, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]) @ view
    out = []
    for (x, y, z) in pts:
        c = vp @ np.array([x, y, z, 1.0])
        w = -c[2] if abs(c[2]) > 1e-9 else 1e-9
        out.append(((c[0] / w * 0.5 + 0.5) * size, (1 - (c[1] / w * 0.5 + 0.5)) * size))
    return out


def paste_quad(base, frame, quad_px):
    """Warp `frame` into the four image points of `quad_px` (TL, TR, BR, BL)."""
    import numpy as np
    from PIL import Image, ImageDraw

    W, H = base.size
    src = [(0, 0), (frame.width, 0), (frame.width, frame.height), (0, frame.height)]
    A, b = [], []
    for (x, y), (u, v) in zip(quad_px, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    coeffs = np.linalg.solve(np.array(A, dtype=np.float64), np.array(b, dtype=np.float64))
    warped = frame.convert("RGB").transform((W, H), Image.PERSPECTIVE,
                                            tuple(coeffs), Image.BICUBIC)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(x, y) for (x, y) in quad_px], fill=255)
    base.paste(warped, (0, 0), mask)
    return base
