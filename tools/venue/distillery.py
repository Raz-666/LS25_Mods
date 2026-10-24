# SPDX-License-Identifier: GPL-3.0-or-later
"""FS25_Distillery - the Leipzig techno club as a placeable.

Layout follows the reference plan:

    street ................. z = -16 .. -12   (cobbles)
    main floor (20 x 15) ... x -10 .. 10, z -12 .. 3, 6.5 m high
    bar wing (15 x 15) ..... x  10 .. 24, z -12 .. 3, 5.2 m high
    garden (15 x 20) ....... x  10 .. 24, z   3 .. 21

Inside the main floor: DJ stage, four big PA stacks, concrete dance floor,
trusses with moving heads, two ventilation ducts, mirror ball, a small
mezzanine with stairs.  The bar wing holds the foyer with the cloakroom and the
18 m main bar.  The garden has the outdoor bar hut, benches and string lights.

Nodes the Lua script uses:
    musicNode         3D audio source in the middle of the dance floor
    djNode            DJ booth position (the "walk up to the mixer" spot)
    mirrorBallPivot   turning mirror ball
    lightPink/Cyan/Amber, signNode, ledNode
"""

import math

from meshlib import Mesh, box, cylinder, disc, lathe, open_cone, place, sphere, torus
from model import Node, write_i3d
from triggers import PLAYER, VEHICLE, trigger_mask, trigger_node
from venue import area, line_area, neon_sign, quad, slab

# --- footprint ------------------------------------------------------------
# The house from the photos: a long, tall brick hall with the square tower at
# the corner, a lower bar wing beside it and the beer garden behind.
MX0, MX1 = -10.0, 10.0          # main floor (20 m wide)
MZ0, MZ1 = -12.0, 3.0           # 15 m deep
MH = 11.5                       # eaves - tall enough for two storeys + trusses
BX0, BX1 = 10.0, 24.0           # bar wing (14 m)
BZ0, BZ1 = -12.0, 3.0
BH = 7.4
GX0, GX1 = 10.0, 24.0           # garden (14 x 18 m, right behind the bar wing)
GZ0, GZ1 = 3.0, 21.0
STREET_Z = -16.0
WALL = 0.40

# the brick tower of the old distillery - the landmark of the house
TOWER_X0, TOWER_X1 = 3.0, 8.4
TOWER_Z0, TOWER_Z1 = MZ0 - 3.2, MZ0 + 2.2
TOWER_H = 18.5

# The set list at the DJ booth. Titles and order are shared by the playlist
# texture, the board geometry, the sounds xml and the script.
TRACKS = [
    ("anthem", "Beton & Bass", 132),
    ("afterdark", "Leipzig After Dark", 126),
    ("kohle", "Kohlekraft", 138),
    ("rohrwerk", "Rohrwerk", 124),
    ("untergrund", "Untergrund", 140),
    ("letzteRunde", "Letzte Runde", 118),
]

PANEL_X, PANEL_Y = -1.6, 3.05
PANEL_W, PANEL_H = 3.20, 2.10
PANEL_Z = MZ0 + 0.06
PANEL_TOP = 0.16        # fraction of the texture above the first row
PANEL_BOTTOM = 0.06     # margin below the last row


def row_uvs(count=len(TRACKS)):
    """UV rectangle (u0, v_top, u1, v_bottom) of every row of the set list.

    FS25 uses DirectX UVs: v = 0 is the top row of the texture, so the v of a
    row grows downwards just like its pixel row.
    """
    step = (1.0 - PANEL_TOP - PANEL_BOTTOM) / float(count)
    out = []
    for i in range(count):
        out.append((0.0, PANEL_TOP + i * step, 1.0, PANEL_TOP + (i + 1) * step))
    return out

MATERIALS = [
    {"name": "collision", "diffuse": None, "color": "0.6 0.1 0.6 1",
     "specular": "0.1 0.1 0.1"},
    {"name": "brick", "diffuse": "brick_diffuse.dds", "gloss": "brick_specular.dds"},
    {"name": "brickRed", "diffuse": "brickRed_diffuse.dds",
     "gloss": "brickRed_specular.dds"},
    {"name": "graffitiDense", "diffuse": "graffitiDense_diffuse.dds",
     "gloss": "graffitiDense_specular.dds"},
    {"name": "window", "diffuse": "windowDiffuse.dds", "gloss": None},
    {"name": "roof", "diffuse": "roofTile_diffuse.dds", "gloss": "roofTile_specular.dds"},
    {"name": "lightFlower", "diffuse": "lightFlower_diffuse.dds", "gloss": None},
    {"name": "brickDark", "diffuse": "brickDark_diffuse.dds",
     "gloss": "brickDark_specular.dds"},
    {"name": "brickGraffiti", "diffuse": "brickGraffiti_diffuse.dds",
     "gloss": "brickGraffiti_specular.dds"},
    {"name": "graffiti", "diffuse": "graffiti_diffuse.dds", "gloss": None},
    {"name": "concrete", "diffuse": "concrete_diffuse.dds",
     "gloss": "concrete_specular.dds"},
    {"name": "concreteDark", "diffuse": "concreteDark_diffuse.dds",
     "gloss": "concreteDark_specular.dds"},
    {"name": "cobble", "diffuse": "cobble_diffuse.dds", "gloss": "cobble_specular.dds"},
    {"name": "gravel", "diffuse": "gravel_diffuse.dds", "gloss": "gravel_specular.dds"},
    {"name": "steel", "diffuse": "steel_diffuse.dds", "gloss": "steel_specular.dds"},
    {"name": "speaker", "diffuse": "speaker_diffuse.dds",
     "gloss": "speaker_specular.dds"},
    {"name": "woodDark", "diffuse": "woodDark_diffuse.dds",
     "gloss": "woodDark_specular.dds"},
    {"name": "stage", "diffuse": "stage_diffuse.dds", "gloss": "stage_specular.dds"},
    {"name": "mirror", "diffuse": "mirror_diffuse.dds", "gloss": "mirror_specular.dds"},
    {"name": "neonCyan", "diffuse": "neonCyan_diffuse.dds", "gloss": None},
    {"name": "neonPink", "diffuse": "neonPink_diffuse.dds", "gloss": None},
    {"name": "neonAmber", "diffuse": "neonAmber_diffuse.dds", "gloss": None},
    {"name": "neonWhite", "diffuse": "neonWhite_diffuse.dds", "gloss": None},
    {"name": "signDistillery", "diffuse": "signDistillery_diffuse.dds", "gloss": None},
    {"name": "signLeipzig", "diffuse": "signLeipzig_diffuse.dds", "gloss": None},
    {"name": "signBar", "diffuse": "signBar_diffuse.dds", "gloss": None},
    {"name": "playlist", "diffuse": "playlist_diffuse.dds", "gloss": None},
    {"name": "leaf", "diffuse": None, "color": "0.16 0.30 0.14 1",
     "specular": "0.05 0.05 0.05"},
    {"name": "bark", "diffuse": None, "color": "0.22 0.17 0.13 1",
     "specular": "0.04 0.04 0.04"},
    {"name": "bottleGreen", "diffuse": None, "color": "0.10 0.30 0.14 1",
     "specular": "0.6 0.7 0.6"},
    {"name": "bottleBrown", "diffuse": None, "color": "0.28 0.14 0.05 1",
     "specular": "0.6 0.6 0.5"},
]

LOOK = {
    "collision": None,
    "brick": ((0.42, 0.22, 0.17), 0.25, 0.0, 1.0),
    "brickDark": ((0.24, 0.15, 0.13), 0.25, 0.0, 1.0),
    "brickGraffiti": ((0.44, 0.23, 0.18), 0.25, 0.05, 1.0),
    "graffiti": ((0.25, 0.20, 0.20), 0.15, 0.10, 1.0),
    "concrete": ((0.40, 0.39, 0.37), 0.30, 0.0, 1.0),
    "concreteDark": ((0.24, 0.24, 0.24), 0.30, 0.0, 1.0),
    "cobble": ((0.30, 0.29, 0.28), 0.35, 0.0, 1.0),
    "gravel": ((0.27, 0.25, 0.22), 0.10, 0.0, 1.0),
    "steel": ((0.25, 0.24, 0.23), 0.60, 0.0, 1.0),
    "speaker": ((0.09, 0.09, 0.10), 0.15, 0.0, 1.0),
    "woodDark": ((0.25, 0.17, 0.12), 0.20, 0.0, 1.0),
    "stage": ((0.09, 0.03, 0.10), 0.55, 0.20, 1.0),
    "brickRed": ((0.62, 0.28, 0.14), 0.25, 0.0, 1.0),
    "graffitiDense": ((0.45, 0.30, 0.26), 0.20, 0.10, 1.0),
    "window": ((0.10, 0.12, 0.16), 0.85, 0.10, 1.0),
    "roof": ((0.16, 0.16, 0.18), 0.30, 0.0, 1.0),
    "lightFlower": ((0.80, 0.74, 0.62), 0.15, 0.75, 1.0),
    "mirror": ((0.62, 0.66, 0.72), 0.95, 0.20, 1.0),
    "neonCyan": ((0.30, 0.80, 1.0), 0.3, 0.95, 1.0),
    "neonPink": ((1.0, 0.25, 0.60), 0.3, 0.95, 1.0),
    "neonAmber": ((1.0, 0.62, 0.20), 0.3, 0.95, 1.0),
    "neonWhite": ((0.95, 0.95, 1.0), 0.3, 0.95, 1.0),
    "signDistillery": ((0.95, 0.62, 0.25), 0.3, 0.95, 1.0),
    "signLeipzig": ((0.35, 0.72, 1.0), 0.3, 0.95, 1.0),
    "signBar": ((1.0, 0.55, 0.20), 0.3, 0.95, 1.0),
    "playlist": ((0.95, 0.88, 0.76), 0.2, 0.85, 1.0),
    "leaf": ((0.16, 0.30, 0.14), 0.05, 0.0, 1.0),
    "bark": ((0.22, 0.17, 0.13), 0.05, 0.0, 1.0),
    "bottleGreen": ((0.10, 0.30, 0.14), 0.8, 0.05, 1.0),
    "bottleBrown": ((0.28, 0.14, 0.05), 0.8, 0.05, 1.0),
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def wall(m, mat, x0, x1, z0, z1, h0, h1):
    """Axis aligned wall block."""
    slab(m, mat, ((x0 + x1) * 0.5, (h0 + h1) * 0.5, (z0 + z1) * 0.5),
         (abs(x1 - x0), abs(h1 - h0), abs(z1 - z0)))


def tri(m, mat, pts, facing="+z", tile=2.0):
    """One flat triangle of wall (used for the gables).

    `pts` are three corner points; they are re-ordered so the face looks
    towards `facing`.
    """
    a, b, c = pts
    ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    n = (nx / ln, ny / ln, nz / ln)
    want = {"+z": (0, 0, 1), "-z": (0, 0, -1), "+x": (1, 0, 0), "-x": (-1, 0, 0)}[facing]
    if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
        b, c = c, b
        n = (-n[0], -n[1], -n[2])
    span = math.sqrt(ux * ux + uy * uy + uz * uz)
    rise = math.sqrt(vx * vx + vy * vy + vz * vz)
    us = max(1.0, span / tile)
    vs = max(1.0, rise / tile)
    uvs = [(0.0, vs), (us * 0.5, 0.0), (us, vs)]
    m.add(mat, [a, b, c], [n] * 3, uvs, [(0, 1, 2)])


def billboard(mesh, mat, centre, width, height, facing="+z", uv=None):
    """A flat quad with a texture, used for signs and posters.

    The corner order follows what a viewer standing *in front of* the quad
    sees (bottom-left, bottom-right, top-right, top-left), so the lettering
    reads correctly - the UVs are always in that same order.
    """
    cx, cy, cz = centre
    hw, hh = width * 0.5, height * 0.5
    corners = {
        "+z": [(cx - hw, cy - hh, cz), (cx + hw, cy - hh, cz),
               (cx + hw, cy + hh, cz), (cx - hw, cy + hh, cz)],
        "-z": [(cx + hw, cy - hh, cz), (cx - hw, cy - hh, cz),
               (cx - hw, cy + hh, cz), (cx + hw, cy + hh, cz)],
        "+x": [(cx, cy - hh, cz + hw), (cx, cy - hh, cz - hw),
               (cx, cy + hh, cz - hw), (cx, cy + hh, cz + hw)],
        "-x": [(cx, cy - hh, cz - hw), (cx, cy - hh, cz + hw),
               (cx, cy + hh, cz + hw), (cx, cy + hh, cz - hw)],
        # lying flat on the floor, readable from the south (the DJ side)
        "+y": [(cx - hw, cy, cz + hh), (cx + hw, cy, cz + hh),
               (cx + hw, cy, cz - hh), (cx - hw, cy, cz - hh)],
    }[facing]
    # FS25 / DirectX UV convention: v = 0 is the TOP row of the texture, and
    # the corners are ordered bottom-left .. top-left, so the v values run the
    # other way round.
    u0, v_top, u1, v_bottom = (0.0, 0.0, 1.0, 1.0) if uv is None else uv
    # corners are bottom-left, bottom-right, top-right, top-left
    quad(corners, mat, mesh,
         [(u0, v_bottom), (u1, v_bottom), (u1, v_top), (u0, v_top)])


def horn(mesh, mat, pos, radius, depth, rot=(90, 0, 0), segments=16):
    """A horn flare: open cone plus a driver can behind it."""
    cone = open_cone(0.0, radius, -depth, radius * 0.22, segments=segments)
    mesh.add(mat, *place(cone, translation=pos, rot=rot))
    mesh.add(mat, *place(cylinder(radius * 0.16, -depth, -depth - 0.16, 10),
                         translation=pos, rot=rot))


def drum(mesh, mat, pos, radius, height, rot=(90, 0, 0), segments=18):
    mesh.add(mat, *place(cylinder(radius, 0.0, height, segments, caps=True),
                         translation=pos, rot=rot))
    mesh.add(mat, *place(disc(radius * 0.92, 0.0, segments=segments),
                         translation=pos, rot=rot))


# --------------------------------------------------------------------------
# exterior shell
# --------------------------------------------------------------------------
def shell_mesh():
    """The house from the photos: long brick hall, square tower, pitched roof,
    tagged facade, and the forecourt where the queue stands."""
    m = Mesh()
    # --- street / forecourt ------------------------------------------------
    wall(m, "cobble", -30.0, 34.0, STREET_Z, -12.6, -0.34, 0.0)
    wall(m, "concrete", -30.0, 34.0, -12.6, -12.0, -0.34, 0.02)
    # ground under the buildings
    wall(m, "concreteDark", MX0 - 1.0, BX1 + 1.0, MZ0 - 0.5, BZ1 + 0.5, -0.38, 0.0)
    # garden
    wall(m, "gravel", GX0, GX1, GZ0, GZ1, -0.36, 0.0)

    # --- main floor -------------------------------------------------------
    wall(m, "concreteDark", MX0, MX1, MZ0, MZ1, 0.0, 0.06)
    # the facade carries the tags, the flanks are plain brick
    wall(m, "graffitiDense", MX0 - WALL, MX1, MZ0 - WALL, MZ0, 0.0, 4.6)
    wall(m, "brickRed", MX0 - WALL, MX1, MZ0 - WALL, MZ0, 4.6, MH)
    wall(m, "brickRed", MX0 - WALL, MX1 + WALL, MZ1, MZ1 + WALL, 0.0, MH)
    wall(m, "brickRed", MX0 - WALL, MX0, MZ0, MZ1, 0.0, MH)
    wall(m, "brickRed", MX1, MX1 + WALL, MZ0, BZ0, 0.0, MH)   # behind the stage wall

    # --- pitched roof (the photo shows a real saddle roof, not a flat deck) --
    ridge_y = MH + 3.6
    mid_z = (MZ0 + MZ1) * 0.5
    half = (MZ1 - MZ0) * 0.5 + WALL
    slope = math.degrees(math.atan2(ridge_y - MH, half))
    length = math.hypot(ridge_y - MH, half)
    for sign in (1, -1):
        m.add("roof", *place(box((0, 0, 0), (MX1 - MX0 + 2 * WALL, 0.22, length)),
                             rot=(sign * slope, 0, 0),
                             translation=((MX0 + MX1) * 0.5,
                                          (MH + ridge_y) * 0.5 - 0.05,
                                          mid_z + sign * half * 0.5)))
    # ridge cap + two chimney stacks
    m.add("roof", *place(box((0, 0, 0), (MX1 - MX0 + 2 * WALL, 0.16, 0.5)),
                         translation=((MX0 + MX1) * 0.5, ridge_y + 0.06, mid_z)))
    for cx in (-8.2, 7.4):
        m.add("brickRed", *place(box((0, 0, 0), (0.9, 2.0, 0.9)),
                                 translation=(cx, ridge_y - 0.7, mid_z - 0.4)))
    # gable ends: a real triangle of brick under each roof slope
    gx0, gx1 = MX0 - WALL, MX1 + WALL
    gmid = (MX0 + MX1) * 0.5
    for zc in (MZ0 - WALL * 0.5, MZ1 + WALL * 0.5):
        tri(m, "brickRed",
            [(gx0, MH, zc), (gmid, ridge_y, zc), (gx1, MH, zc)],
            "+z" if zc < 0 else "-z", tile=2.4)
        # a small round window in the gable, like the photos
        m.add("window", *place(disc(0.55, 0.0, segments=20),
                               rot=(90, 0, 0),
                               translation=(gmid + 3.0, MH + 1.05,
                                            zc + (0.06 if zc < 0 else -0.06))))

    # --- the tower --------------------------------------------------------
    tx0, tx1, tz0, tz1 = TOWER_X0, TOWER_X1, TOWER_Z0, TOWER_Z1
    wall(m, "graffitiDense", tx0, tx1, tz0, tz1, 0.0, 4.6)
    wall(m, "brickRed", tx0, tx1, tz0, tz1, 4.6, TOWER_H)
    # the tower cap: a flat slab and a small parapet
    wall(m, "concreteDark", tx0 - 0.25, tx1 + 0.25, tz0 - 0.25, tz1 + 0.25,
         TOWER_H, TOWER_H + 0.35)
    wall(m, "brickRed", tx0 - 0.25, tx1 + 0.25, tz0 - 0.25, tz1 + 0.25,
         TOWER_H + 0.35, TOWER_H + 0.95)
    # tall narrow windows on the two visible sides
    for y in (6.2, 9.2, 12.2, 15.2):
        for i in range(3):
            x = tx0 + 0.7 + i * 1.6
            wall(m, "window", x, x + 0.75, tz0 - 0.06, tz0 + 0.02, y, y + 1.7)
            wall(m, "steel", x - 0.07, x + 0.82, tz0 - 0.10, tz0 - 0.04, y - 0.07, y)
            wall(m, "steel", x - 0.07, x + 0.82, tz0 - 0.10, tz0 - 0.04, y + 1.7, y + 1.77)
        for i in range(2):
            z = tz0 + 1.4 + i * 3.0
            wall(m, "window", tx1 - 0.02, tx1 + 0.06, z, z + 0.85, y, y + 1.7)
    # the little balcony with the iron railing from the photo
    wall(m, "concreteDark", tx0 - 0.1, tx0 + 2.2, tz0 - 0.75, tz0 - 0.10, 8.4, 8.55)
    for i in range(7):
        x = tx0 - 0.05 + i * 0.35
        wall(m, "steel", x, x + 0.05, tz0 - 0.72, tz0 - 0.66, 8.55, 9.5)
    wall(m, "steel", tx0 - 0.1, tx0 + 2.25, tz0 - 0.74, tz0 - 0.66, 9.45, 9.55)

    # --- facade openings --------------------------------------------------
    # entrance door: x -1.6 .. 1.6, y 0 .. 3.2
    wall(m, "concreteDark", -1.7, 1.7, MZ0 - WALL - 0.02, MZ0 - WALL + 0.06, 0.0, 3.25)
    # two big shop windows at eye height, one tall window band above
    for (x0, x1) in ((-7.8, -4.8), (-3.9, -2.4)):
        wall(m, "window", x0, x1, MZ0 - WALL - 0.02, MZ0 - WALL + 0.06, 1.0, 4.3)
        wall(m, "steel", x0, x1, MZ0 - WALL - 0.10, MZ0 - WALL - 0.02, 1.0, 1.08)
        wall(m, "steel", x0, x1, MZ0 - WALL - 0.10, MZ0 - WALL - 0.02, 4.22, 4.3)
        for k in range(1, 4):
            xx = x0 + (x1 - x0) * k / 4.0
            wall(m, "steel", xx - 0.05, xx + 0.05, MZ0 - WALL - 0.10, MZ0 - WALL - 0.02,
                 1.0, 4.3)
    # upper storey: five tall windows with a steel frame, like the photos
    for i in range(5):
        x = -8.4 + i * 3.3
        wall(m, "window", x, x + 1.5, MZ0 - WALL - 0.02, MZ0 - WALL + 0.06, 6.4, 9.6)
        wall(m, "steel", x - 0.08, x + 1.58, MZ0 - WALL - 0.12, MZ0 - WALL - 0.02,
             6.32, 6.42)
        wall(m, "steel", x - 0.08, x + 1.58, MZ0 - WALL - 0.12, MZ0 - WALL - 0.02,
             9.58, 9.68)
        wall(m, "steel", x + 0.72, x + 0.80, MZ0 - WALL - 0.12, MZ0 - WALL - 0.02,
             6.4, 9.6)
        wall(m, "steel", x - 0.08, x + 0.02, MZ0 - WALL - 0.12, MZ0 - WALL - 0.02,
             6.4, 9.6)
        wall(m, "steel", x + 1.50, x + 1.60, MZ0 - WALL - 0.12, MZ0 - WALL - 0.02,
             6.4, 9.6)
    # door frame + handles
    for sx in (-1, 1):
        wall(m, "steel", sx * 1.7 - 0.06, sx * 1.7 + 0.06, MZ0 - 0.7, MZ0 - 0.6, 0.0, 3.3)
    wall(m, "steel", -1.8, 1.8, MZ0 - 0.7, MZ0 - 0.6, 3.2, 3.35)
    wall(m, "woodDark", -0.06, 0.06, MZ0 - 0.68, MZ0 - 0.62, 0.0, 3.2)  # door gap
    # the yellow cable the crew taped across the yard in the photo
    m.add("neonAmber", *place(cylinder(0.05, 0.0, 0.05, 8, caps=True),
                              translation=(-9.0, 0.02, -13.4), rot=(0, 14, 0)))

    # --- bar wing ---------------------------------------------------------
    wall(m, "concreteDark", BX0, BX1, BZ0, BZ1, 0.0, 0.06)
    wall(m, "graffitiDense", BX0, BX1 + WALL, BZ0 - WALL, BZ0, 0.0, 3.6)
    wall(m, "brickRed", BX0, BX1 + WALL, BZ0 - WALL, BZ0, 3.6, BH)
    wall(m, "brickRed", BX0, BX1 + WALL, BZ1, BZ1 + WALL, 0.0, BH)
    wall(m, "brickRed", BX1, BX1 + WALL, BZ0, BZ1, 0.0, BH)
    # shed roof over the bar wing
    sag = 2.2
    slope2 = math.degrees(math.atan2(sag, (BX1 - BX0) * 0.5))
    m.add("roof", *place(box((0, 0, 0), (math.hypot(sag, (BX1 - BX0) * 0.5), 0.20,
                                             BZ1 - BZ0 + 2 * WALL)),
                         rot=(0, 0, slope2),
                         translation=((BX0 + BX1) * 0.5, BH + sag * 0.5,
                                      (BZ0 + BZ1) * 0.5)))
    # a couple of windows towards the garden and the street
    for z in (-9.0, -5.5, -2.0, 1.0):
        wall(m, "window", BX1 + WALL - 0.02, BX1 + WALL + 0.06, z, z + 1.3, 2.4, 4.2)
    for x in (12.0, 14.4, 16.8, 19.2, 21.6):
        wall(m, "window", x, x + 1.3, BZ1 + WALL - 0.02, BZ1 + WALL + 0.06, 2.4, 4.2)

    # --- fire escape ------------------------------------------------------
    fx = MX0 - 1.15
    for y in (4.6, 8.4):
        wall(m, "steel", fx - 0.7, fx + 0.7, -9.2, -6.4, y, y + 0.10)
        for z in (-9.2, -6.4):
            wall(m, "steel", fx - 0.68, fx + 0.68, z - 0.04, z + 0.04, y + 0.1, y + 1.1)
        wall(m, "steel", fx - 0.7, fx + 0.7, -9.24, -9.16, y + 1.02, y + 1.10)
    m.add("steel", *place(box((0, 0, 0), (1.0, 0.10, 5.2)),
                          translation=(fx, 6.5, -7.8), rot=(-38, 0, 0)))
    for i in range(11):
        t = i / 10.0
        m.add("steel", *place(box((0, 0, 0), (1.0, 0.06, 0.30)),
                              translation=(fx, 4.7 + t * 3.7, -9.0 + t * 2.6)))
    for z in (-6.6, -6.2):
        wall(m, "steel", fx - 0.04, fx + 0.04, z, z + 0.06, 8.4, MH + 0.9)
    for i in range(8):
        wall(m, "steel", fx - 0.04, fx + 0.04, -6.6, -6.14, 8.5 + i * 0.34,
             8.56 + i * 0.34)

    # --- street fittings --------------------------------------------------
    lamp = Mesh()
    lamp.add("steel", *place(cylinder(0.09, 0.0, 8.4, 10, caps=True),
                             translation=(-8.5, 0.0, -13.4)))
    lamp.add("steel", *place(box((0, 0, 0), (0.12, 0.12, 1.7)),
                             translation=(-8.5, 8.2, -12.7)))
    lamp.add("neonWhite", *place(box((0, 0, 0), (0.5, 0.10, 0.8)),
                                 translation=(-8.5, 8.1, -12.0)))
    m.add("steel", *lamp.parts["steel"])
    m.add("neonWhite", *lamp.parts["neonWhite"])
    for x in (-12.0, -10.6, 4.6, 6.0, -2.4):
        m.add("steel", *place(cylinder(0.08, 0.0, 0.95, 8, caps=True),
                              translation=(x, 0.0, -13.1)))
    # barrier rails of the queue in front of the door
    for i in range(4):
        x = -6.6 + i * 2.2
        m.add("steel", *place(cylinder(0.04, 0.0, 1.05, 6, caps=True),
                              translation=(x, 0.0, -13.9)))
        if i < 3:
            m.add("steel", *place(box((0, 0, 0), (2.2, 0.05, 0.05)),
                                  translation=(x + 1.1, 1.0, -13.9)))
    # a couple of bollards at the garden gate
    for z in (4.0, 6.0):
        m.add("steel", *place(cylinder(0.08, 0.0, 1.0, 8, caps=True),
                              translation=(GX0 + 0.4, 0.0, z)))
    return m


# --------------------------------------------------------------------------
# interior
# --------------------------------------------------------------------------
def stage_mesh():
    """DJ stage, booth, turntables and the back wall LED strip."""
    m = Mesh()
    # stage body 8 x 4 m, 0.9 m high
    wall(m, "woodDark", -6.0, 2.0, MZ0 + 0.35, MZ0 + 4.2, 0.0, 0.85)
    wall(m, "stage", -6.0, 2.0, MZ0 + 0.35, MZ0 + 4.2, 0.85, 0.92)
    # steel edge
    wall(m, "steel", -6.0, 2.0, MZ0 + 4.1, MZ0 + 4.2, 0.85, 0.95)
    # booth desk
    wall(m, "woodDark", -3.4, 0.4, MZ0 + 1.2, MZ0 + 2.2, 0.92, 1.98)
    wall(m, "steel", -3.5, 0.5, MZ0 + 1.15, MZ0 + 2.25, 1.95, 2.02)
    wall(m, "steel", -3.5, 0.5, MZ0 + 1.15, MZ0 + 1.35, 0.92, 1.95)
    # two decks + a mixer
    for dx in (-2.4, -0.6):
        m.add("steel", *place(disc(0.30, 0.0, segments=22),
                              translation=(dx, 2.04, MZ0 + 1.7)))
        m.add("mirror", *place(disc(0.22, 0.0, segments=22),
                               translation=(dx, 2.06, MZ0 + 1.7)))
        m.add("steel", *place(cylinder(0.03, 0.0, 0.35, 6),
                              translation=(dx + 0.24, 2.06, MZ0 + 1.95), rot=(90, 0, 0)))
    wall(m, "steel", -1.6, -1.2, MZ0 + 1.45, MZ0 + 2.0, 2.02, 2.16)
    for i in range(6):
        m.add("neonWhite", *place(box((0, 0, 0), (0.05, 0.07, 0.03)),
                                  translation=(-1.52 + i * 0.055, 2.19, MZ0 + 1.55)))
    # laptop
    m.add("steel", *place(box((0, 0, 0), (0.36, 0.02, 0.26)),
                          translation=(0.0, 2.05, MZ0 + 1.75)))
    m.add("neonCyan", *place(box((0, 0, 0), (0.34, 0.22, 0.02)),
                             translation=(0.0, 2.17, MZ0 + 1.62), rot=(-70, 0, 0)))
    # back wall: LED strip and the club logo
    for i in range(3):
        wall(m, "neonPink" if i % 2 == 0 else "neonCyan",
             -6.2, 2.2, MZ0 + 0.3, MZ0 + 0.42, 2.4 + i * 0.5, 2.46 + i * 0.5)
    return m


def dance_floor_mesh():
    m = Mesh()
    # slightly lighter concrete island with steel edging
    wall(m, "concrete", -7.2, 7.2, -3.6, 2.4, 0.06, 0.09)
    # the yellow flower of light on the floor - the gobo from the photo, laid
    # 12 cm over the concrete so it never fights with the floor itself
    billboard(m, "lightFlower", (0.0, 0.12, -0.6), 6.6, 6.6, "+y")
    for (x0, x1, z0, z1) in ((-7.3, 7.3, -3.7, -3.6), (-7.3, 7.3, 2.4, 2.5),
                             (-7.3, -7.2, -3.7, 2.5), (7.2, 7.3, -3.7, 2.5)):
        wall(m, "steel", x0, x1, z0, z1, 0.06, 0.10)
    # floor lights along the edge
    for i in range(10):
        x = -6.6 + i * 1.47
        m.add("neonPink", *place(box((0, 0, 0), (0.5, 0.03, 0.06)),
                                 translation=(x, 0.10, 2.42)))
    return m


def pa_stack(x, z, facing=1):
    """A big horn-loaded PA stack: two subs and a mid/high cabinet on top."""
    m = Mesh()
    y = 0.0
    # two sub bass cabinets
    for i in range(2):
        slab(m, "speaker", (x, y + 0.62, z), (1.30, 1.24, 1.05))
        m.add("steel", *place(disc(0.46, 0.0, segments=20),
                              translation=(x, y + 0.62, z + facing * 0.53),
                              rot=(90 if facing > 0 else -90, 0, 0)))
        m.add("steel", *place(torus(0.46, 0.045, segments=22, sides=8),
                              translation=(x, y + 0.62, z + facing * 0.55),
                              rot=(90 if facing > 0 else -90, 0, 0)))
        m.add("steel", *place(disc(0.20, 0.0, segments=16),
                              translation=(x, y + 0.62, z + facing * 0.57),
                              rot=(90 if facing > 0 else -90, 0, 0)))
        y += 1.30
    # mid/high cabinet with four horn flares
    slab(m, "speaker", (x, y + 0.72, z), (1.30, 1.44, 1.05))
    for (dx, dy) in ((-0.30, 0.30), (0.30, 0.30), (-0.30, -0.30), (0.30, -0.30)):
        horn(m, "steel", (x + dx, y + 0.72 + dy, z + facing * 0.50),
             0.26, 0.34, rot=(90 * facing, 0, 0), segments=14)
    # corner braces
    for sx in (-1, 1):
        for sz in (-1, 1):
            slab(m, "steel", (x + sx * 0.64, y * 0.5, z + sz * 0.52),
                 (0.05, y, 0.05))
    return m, y + 1.44


def interior_props():
    """Trusses, ducts, mirror ball, bar, cloakroom, mezzanine, toilets."""
    m = Mesh()

    # --- ceiling trusses (4 beams across the hall) -------------------------
    for z in (-9.0, -5.0, -1.0, 2.0):
        wall(m, "steel", MX0, MX1, z - 0.09, z + 0.09, MH - 0.75, MH - 0.60)
        wall(m, "steel", MX0, MX1, z - 0.09, z + 0.09, MH - 1.25, MH - 1.12)
        for i in range(8):
            x = MX0 + 1.2 + i * 2.4
            m.add("steel", *place(box((0, 0, 0), (0.06, 0.62, 0.06)),
                                  translation=(x, MH - 0.95, z), rot=(0, 45, 0)))
    # --- ventilation ducts -------------------------------------------------
    for x in (-4.2, 4.2):
        m.add("steel", *place(cylinder(0.42, MZ0 + 0.4, MZ1 - 0.4, 16, caps=True),
                              translation=(x, MH - 1.9, 0.0), rot=(90, 0, 0)))
        for z in (-8.0, -4.0, 0.0, 2.2):
            m.add("steel", *place(torus(0.44, 0.05, segments=18, sides=8),
                                  translation=(x, MH - 1.9, z), rot=(90, 0, 0)))
        # hangers
        for z in (-8.0, -2.0, 1.8):
            wall(m, "steel", x - 0.03, x + 0.03, z - 0.03, z + 0.03,
                 MH - 1.5, MH - 0.6)

    # --- main bar in the bar wing -----------------------------------------
    bx = BX1 - 1.2
    wall(m, "woodDark", bx - 0.75, bx + 0.75, BZ0 + 1.6, BZ1 - 1.2, 0.0, 1.05)
    wall(m, "steel", bx - 0.85, bx + 0.85, BZ0 + 1.5, BZ1 - 1.1, 1.05, 1.14)
    # under-counter LED
    wall(m, "neonCyan", bx - 0.78, bx - 0.74, BZ0 + 1.7, BZ1 - 1.3, 0.12, 0.18)
    # back bar shelf with bottles
    wall(m, "woodDark", BX1 - 0.30, BX1 - 0.05, BZ0 + 1.4, BZ1 - 1.0, 1.4, 1.55)
    wall(m, "woodDark", BX1 - 0.30, BX1 - 0.05, BZ0 + 1.4, BZ1 - 1.0, 2.0, 2.15)
    wall(m, "neonAmber", BX1 - 0.32, BX1 - 0.28, BZ0 + 1.5, BZ1 - 1.1, 2.25, 2.32)
    for i in range(26):
        z = BZ0 + 1.9 + i * 0.46
        mat = "bottleGreen" if i % 2 == 0 else "bottleBrown"
        shelf_y = 1.55 if i % 3 else 2.15
        m.add(mat, *place(cylinder(0.055, 0.0, 0.28, 8, caps=True),
                          translation=(BX1 - 0.18, shelf_y, z)))
        m.add(mat, *place(cylinder(0.02, 0.28, 0.36, 6), translation=(BX1 - 0.18, shelf_y, z)))
    # beer taps on the counter
    for i in range(6):
        z = BZ0 + 3.0 + i * 0.9
        m.add("steel", *place(cylinder(0.045, 0.0, 0.42, 8, caps=True),
                              translation=(bx - 0.2, 1.14, z)))
        m.add("steel", *place(box((0, 0, 0), (0.10, 0.06, 0.16)),
                              translation=(bx - 0.2, 1.56, z + 0.12)))
    # bar stools
    for i in range(7):
        z = BZ0 + 2.6 + i * 0.95
        m.add("steel", *place(cylinder(0.045, 0.0, 0.68, 8, caps=True),
                              translation=(bx - 1.3, 0.0, z)))
        m.add("woodDark", *place(disc(0.20, 0.0, segments=14),
                                 translation=(bx - 1.3, 0.70, z)))
        m.add("steel", *place(disc(0.24, 0.0, segments=16),
                              translation=(bx - 1.3, 0.02, z)))

    # --- foyer / cloakroom -------------------------------------------------
    wall(m, "woodDark", BX0 + 0.8, BX0 + 4.6, BZ0 + 0.8, BZ0 + 1.6, 0.0, 1.1)
    wall(m, "steel", BX0 + 0.7, BX0 + 4.7, BZ0 + 0.75, BZ0 + 1.65, 1.1, 1.18)
    wall(m, "neonWhite", BX0 + 1.0, BX0 + 4.4, BZ0 + 1.62, BZ0 + 1.66, 1.9, 2.05)
    # turnstile
    for i in range(3):
        m.add("steel", *place(cylinder(0.05, 0.0, 1.0, 8, caps=True),
                              translation=(BX0 + 2.0 + i * 1.2, 0.0, BZ0 + 4.6)))
    m.add("steel", *place(cylinder(0.10, 0.0, 1.1, 8, caps=True),
                          translation=(BX0 + 2.0, 0.0, BZ0 + 4.6)))
    # separation wall between foyer and bar, with an opening
    wall(m, "brickDark", BX0 + 4.9, BX0 + 5.1, BZ0, BZ0 + 3.4, 0.0, BH - 0.4)
    wall(m, "brickDark", BX0 + 4.9, BX0 + 5.1, BZ0 + 6.6, BZ1, 0.0, BH - 0.4)
    wall(m, "brickDark", BX0 + 4.9, BX0 + 5.1, BZ0 + 3.4, BZ0 + 6.6, 3.2, BH - 0.4)

    # --- mezzanine with stairs (west side) --------------------------------
    wall(m, "steel", MX0 + 0.1, MX0 + 3.2, MZ0 + 0.2, MZ1 - 3.0, 3.25, 3.38)
    for z in (-9.0, -6.0, -3.0):
        wall(m, "steel", MX0 + 0.1, MX0 + 3.2, z - 0.05, z + 0.05, 0.0, 3.25)
    for z in range(-11, 0):
        pass
    # railing
    wall(m, "steel", MX0 + 3.1, MX0 + 3.2, MZ0 + 0.2, MZ1 - 3.0, 3.38, 4.35)
    # stairs up (flight along the west wall)
    for i in range(10):
        m.add("steel", *place(box((0, 0, 0), (1.2, 0.06, 0.30)),
                              translation=(MX0 + 1.9, 0.30 + i * 0.32, 1.2 - i * 0.30)))

    # --- toilets (two doors on the west wall) -----------------------------
    for z in (-3.5, -1.6):
        wall(m, "steel", MX0 + 0.02, MX0 + 0.10, z - 0.5, z + 0.5, 0.0, 2.1)
        wall(m, "neonWhite", MX0 + 0.10, MX0 + 0.13, z - 0.35, z + 0.35, 2.2, 2.32)

    # --- exit signs -------------------------------------------------------
    for (x, z) in ((-9.6, -11.2), (9.6, 2.6), (BX1 - 0.8, BZ1 - 0.8)):
        wall(m, "neonWhite", x - 0.35, x + 0.35, z - 0.06, z + 0.06, 2.75, 2.95)

    # --- wardrobe hooks and posters --------------------------------------
    for i in range(3):
        billboard(m, "graffiti", (MX0 + 0.06, 2.6, -6.0 + i * 3.0), 1.6, 1.1, "+x")

    # --- the columns from the plan ("Säulen") between floor and bar ------
    for z in (-10.0, -6.4, -2.8, 0.8):
        m.add("steel", *place(cylinder(0.20, 0.06, 4.10, 12, caps=True),
                              translation=(MX1 - 1.4, 0.0, z)))
        m.add("concreteDark", *place(box((0, 0, 0), (0.62, 0.10, 0.62)),
                                     translation=(MX1 - 1.4, 0.11, z)))
        m.add("concreteDark", *place(box((0, 0, 0), (0.62, 0.14, 0.62)),
                                     translation=(MX1 - 1.4, 4.10, z)))
    # a steel beam across the hall on top of them
    wall(m, "steel", MX1 - 1.6, MX1 - 1.2, MZ0 + 0.4, MZ1 - 0.4, 4.12, 4.42)

    # --- "2nd floor house": the VIP box over the east side ---------------
    hx0, hx1 = MX1 - 6.0, MX1 - 0.2
    hz0, hz1 = MZ0 + 0.4, MZ0 + 4.6
    wall(m, "woodDark", hx0, hx1, hz0, hz1, 5.55, 5.70)          # floor
    wall(m, "steel", hx0 - 0.10, hx0, hz0, hz1, 5.55, 6.55)      # railing posts
    wall(m, "steel", hx0 - 0.06, hx0 - 0.02, hz0, hz1, 6.45, 6.55)
    for z in (hz0 + 0.2, hz0 + 1.6, hz0 + 3.0, hz0 + 4.3):
        wall(m, "steel", hx0 - 0.09, hx0 - 0.01, z - 0.04, z + 0.04, 5.7, 6.5)
    # stairs up along the east wall
    for i in range(14):
        m.add("steel", *place(box((0, 0, 0), (1.1, 0.06, 0.28)),
                              translation=(hx1 - 0.7, 0.42 + i * 0.36,
                                           MZ1 - 2.0 - i * 0.34)))
    # its own little bar on the platform
    wall(m, "woodDark", hx1 - 2.1, hx1 - 1.4, hz0 + 1.0, hz0 + 3.4, 5.70, 6.70)
    wall(m, "steel", hx1 - 2.16, hx1 - 1.34, hz0 + 0.94, hz0 + 3.46, 6.70, 6.78)
    wall(m, "neonAmber", hx1 - 2.12, hx1 - 2.08, hz0 + 1.1, hz0 + 3.3, 6.85, 6.92)
    # a few stools
    for z in (hz0 + 1.4, hz0 + 2.2, hz0 + 3.0):
        m.add("steel", *place(cylinder(0.05, 5.70, 6.28, 8, caps=True),
                              translation=(hx1 - 2.6, 0.0, z)))
        m.add("woodDark", *place(disc(0.18, 0.0, segments=12),
                                 translation=(hx1 - 2.6, 6.30, z)))
    return m


def light_rig_mesh():
    """Moving heads, lasers and the neon strips that blink to the beat."""
    groups = {k: Mesh() for k in ("Pink", "Cyan", "Amber")}
    m = Mesh()
    # hanging fixtures under the trusses
    heads = []
    for z in (-9.0, -5.0, -1.0, 2.0):
        for x in (-6.0, -2.0, 2.0, 6.0):
            slab(m, "steel", (x, MH - 0.55, z), (0.08, 0.30, 0.08))
            m.add("steel", *place(box((0, 0, 0), (0.34, 0.34, 0.42)),
                                  translation=(x, MH - 0.82, z)))
            m.add("neonWhite", *place(cylinder(0.12, 0.0, 0.06, 14),
                                      translation=(x, MH - 1.02, z)))
            heads.append((x, MH - 1.05, z))
    # laser bars above the set list board (the board ends at y = 4.1)
    for y in (4.35, 4.95):
        m.add("neonPink", *place(box((0, 0, 0), (7.6, 0.06, 0.06)),
                                 translation=(0.0, y, MZ0 + 0.55)))
    # neon strips on the walls, per light group
    gp, gc, ga = groups["Pink"], groups["Cyan"], groups["Amber"]
    wall(gp, "neonPink", MX0 + 0.05, MX0 + 0.12, MZ0 + 0.6, MZ1 - 0.6, 4.6, 4.72)
    wall(gp, "neonPink", MX0 + 0.6, MX1 - 0.6, MZ1 - 0.14, MZ1 - 0.06, 4.6, 4.72)
    wall(gc, "neonCyan", MX1 - 0.12, MX1 - 0.05, MZ0 + 0.6, MZ1 - 0.6, 4.6, 4.72)
    wall(gc, "neonCyan", BX0 + 0.4, BX1 - 0.6, BZ0 + 0.08, BZ0 + 0.16, 3.4, 3.52)
    wall(ga, "neonAmber", BX0 + 5.2, BX1 - 0.4, BZ1 - 0.16, BZ1 - 0.08, 3.2, 3.32)
    wall(ga, "neonAmber", BX0 + 0.08, BX0 + 0.16, BZ0 + 3.4, BZ1 - 1.0, 3.2, 3.32)
    return m, groups, heads


# --------------------------------------------------------------------------
# garden
# --------------------------------------------------------------------------
def tree(m, x, z, h=6.0, r=1.9):
    m.add("bark", *place(cylinder(0.16, 0.0, h * 0.62, 10, caps=True),
                         translation=(x, 0.0, z)))
    for (dy, rr, off) in ((h * 0.66, r, 0.0), (h * 0.82, r * 0.78, 0.7),
                          (h * 0.74, r * 0.7, -0.8)):
        m.add("leaf", *place(sphere((0, 0, 0), 1.0, segments=12, rings=7),
                             translation=(x + off * 0.6, dy, z + off * 0.4),
                             scale=(rr, rr * 0.8, rr)))


def bistro_table(m, x, z, chairs=4, r=0.62, rot0=0.0):
    """A round beer-garden table with wicker chairs around it (SITZBEREICHE)."""
    m.add("woodDark", *place(disc(r, 0.0, segments=18),
                             translation=(x, 0.74, z)))
    m.add("steel", *place(cylinder(0.06, 0.0, 0.74, 8, caps=True),
                          translation=(x, 0.0, z)))
    m.add("steel", *place(disc(0.30, 0.0, segments=12), translation=(x, 0.03, z)))
    for i in range(chairs):
        a = math.radians(rot0 + 360.0 * i / chairs)
        cx, cz = x + math.cos(a) * (r + 0.55), z + math.sin(a) * (r + 0.55)
        m.add("woodDark", *place(box((0, 0, 0), (0.44, 0.06, 0.44)),
                                 translation=(cx, 0.45, cz)))
        m.add("woodDark", *place(box((0, 0, 0), (0.44, 0.40, 0.05)),
                                 rot=(8, -math.degrees(a) + 90, 0),
                                 translation=(cx + math.cos(a) * 0.20, 0.66,
                                              cz + math.sin(a) * 0.20)))
        for sx in (-1, 1):
            for sz in (-1, 1):
                m.add("steel", *place(box((0, 0, 0), (0.04, 0.45, 0.04)),
                                      translation=(cx + sx * 0.18, 0.22,
                                                   cz + sz * 0.18)))


def canopy(m, x0, x1, z0, z1, h=3.1):
    """A covered area (ÜBERDACHTER BEREICH): posts, a wooden roof, string lights."""
    for (x, z) in ((x0, z0), (x1, z0), (x0, z1), (x1, z1)):
        m.add("woodDark", *place(cylinder(0.11, 0.0, h, 8, caps=True),
                                 translation=(x, 0.0, z)))
    m.add("woodDark", *place(box((0, 0, 0), (x1 - x0 + 0.7, 0.14, z1 - z0 + 0.7)),
                             translation=((x0 + x1) * 0.5, h + 0.10,
                                          (z0 + z1) * 0.5)))
    # slats so it reads as a pergola rather than a solid box
    for i in range(int((z1 - z0) / 0.5) + 1):
        z = z0 + i * 0.5
        m.add("woodDark", *place(box((0, 0, 0), (x1 - x0 + 0.9, 0.06, 0.10)),
                                 translation=((x0 + x1) * 0.5, h + 0.24, z)))
    # string lights along the front beam
    for i in range(9):
        t = i / 8.0
        m.add("neonAmber", *place(sphere((0, 0, 0), 0.05, segments=8, rings=5),
                                  translation=(x0 + t * (x1 - x0), h - 0.14,
                                               z0 - 0.05)))


def lounge(m, x, z, w=3.0, d=2.2, rot=0.0):
    """A chill-out corner (CHILL-OUT ECKE): two sofas, a crate table and a rug."""
    a = math.radians(rot)
    for (dx, dz, length) in ((0.0, -d * 0.5, w), (0.0, d * 0.5, w),
                             (-w * 0.5, 0.0, d), (w * 0.5, 0.0, d)):
        cx = dx * math.cos(a) - dz * math.sin(a) + x
        cz = dx * math.sin(a) + dz * math.cos(a) + z
        m.add("speaker", *place(box((0, 0, 0), (length, 0.40, 0.80)),
                                rot=(0, -math.degrees(a), 0),
                                translation=(cx, 0.24, cz)))
        m.add("speaker", *place(box((0, 0, 0), (length, 0.55, 0.18)),
                                rot=(0, -math.degrees(a), 0),
                                translation=(cx, 0.60, cz)))
    # a low crate in the middle with a lamp on it
    m.add("woodDark", *place(box((0, 0, 0), (0.9, 0.45, 0.7)),
                             translation=(x, 0.24, z)))
    m.add("neonAmber", *place(sphere((0, 0, 0), 0.10, segments=10, rings=7),
                              translation=(x, 0.60, z)))


def garden_mesh():
    m = Mesh()
    # stone path from the club door to the garden bar
    wall(m, "concrete", GX0 + 2.2, GX0 + 4.4, GZ0, GZ1 - 2.0, 0.0, 0.05)
    wall(m, "concrete", GX0 + 2.2, GX1 - 3.0, GZ1 - 4.0, GZ1 - 2.0, 0.0, 0.05)

    # --- outdoor bar hut ("BAR 01") ---------------------------------------
    hx0, hx1, hz0, hz1 = GX0 + 0.8, GX0 + 5.4, GZ0 + 3.0, GZ0 + 6.0
    wall(m, "woodDark", hx0, hx1, hz0, hz1, 0.0, 2.5)
    wall(m, "concreteDark", hx0 - 0.4, hx1 + 0.4, hz0 - 0.4, hz1 + 0.4, 2.5, 2.62)
    # serving window + counter
    wall(m, "concreteDark", hx0 + 0.4, hx1 - 0.4, hz0 - 0.02, hz0 + 0.06, 1.05, 2.1)
    wall(m, "woodDark", hx0 + 0.2, hx1 - 0.2, hz0 - 0.35, hz0 + 0.1, 1.0, 1.10)
    # shelves with bottles inside, visible through the window
    for i in range(9):
        x = hx0 + 0.8 + i * 0.45
        m.add("bottleGreen" if i % 2 else "bottleBrown",
              *place(cylinder(0.05, 0.0, 0.26, 8, caps=True),
                     translation=(x, 1.35, hz0 + 0.30)))
    # little string lights
    for i in range(10):
        x = hx0 - 0.4 + i * 0.62
        y = 2.75 - 0.18 * math.sin(i * 0.9)
        m.add("neonAmber", *place(sphere((0, 0, 0), 0.055, segments=8, rings=5),
                                  translation=(x, y, hz0 - 0.5)))

    # --- pergola with string lights ---------------------------------------
    px0, px1, pz0, pz1 = GX0 + 8.0, GX1 - 1.0, GZ0 + 8.0, GZ0 + 13.0
    for (x, z) in ((px0, pz0), (px1, pz0), (px0, pz1), (px1, pz1)):
        m.add("woodDark", *place(cylinder(0.14, 0.0, 3.1, 8, caps=True),
                                 translation=(x, 0.0, z)))
    for i in range(6):
        z = pz0 + i * (pz1 - pz0) / 5.0
        m.add("woodDark", *place(box((0, 0, 0), (px1 - px0 + 0.6, 0.14, 0.12)),
                                 translation=((px0 + px1) * 0.5, 3.2, z)))
    for i in range(16):
        x = px0 + 0.4 + i * (px1 - px0 - 0.8) / 15.0
        m.add("neonAmber", *place(sphere((0, 0, 0), 0.06, segments=8, rings=5),
                                  translation=(x, 2.95, pz0 + 0.5)))
    # long table under the pergola
    wall(m, "woodDark", px0 + 1.0, px1 - 1.0, pz0 + 4.0, pz0 + 5.0, 0.72, 0.80)
    for x in (px0 + 1.4, px1 - 1.4):
        wall(m, "steel", x - 0.06, x + 0.06, pz0 + 4.1, pz0 + 4.9, 0.0, 0.72)

    # --- benches ----------------------------------------------------------
    def bench(x, z, rot_deg=0.0):
        b = Mesh()
        b.add("woodDark", *place(box((0, 0, 0), (2.0, 0.08, 0.44)),
                                 translation=(0, 0.44, 0)))
        b.add("woodDark", *place(box((0, 0, 0), (2.0, 0.34, 0.06)),
                                 translation=(0, 0.66, -0.20), rot=(-14, 0, 0)))
        for sx in (-0.85, 0.85):
            b.add("steel", *place(box((0, 0, 0), (0.06, 0.44, 0.42)),
                                  translation=(sx, 0.22, 0)))
        for (mat, part) in b.parts.items():
            m.add(mat, *place(part, translation=(x, 0.0, z), rot=(0, rot_deg, 0)))

    for (x, z, r) in ((GX0 + 5.6, GZ0 + 10.5, 0), (GX0 + 9.0, GZ0 + 10.5, 0),
                      (GX0 + 5.6, GZ0 + 14.0, 180), (GX0 + 9.0, GZ0 + 14.0, 180),
                      (GX0 + 2.0, GZ0 + 12.0, 90), (GX1 - 1.2, GZ0 + 12.0, 270)):
        bench(x, z, r)

    # --- the seating groups from the plan (SITZBEREICHE) ------------------
    for (x, z, n) in ((GX0 + 7.6, GZ0 + 8.4, 4), (GX0 + 10.6, GZ0 + 8.4, 4),
                      (GX0 + 7.6, GZ0 + 11.6, 4), (GX0 + 10.6, GZ0 + 11.6, 4),
                      (GX0 + 4.2, GZ0 + 9.6, 3), (GX0 + 12.2, GZ0 + 5.6, 3),
                      (GX0 + 2.6, GZ0 + 16.4, 4), (GX0 + 8.6, GZ0 + 16.4, 4)):
        bistro_table(m, x, z, chairs=n)

    # --- covered areas (ÜBERDACHTE BEREICHE) ------------------------------
    canopy(m, GX0 + 6.4, GX0 + 12.6, GZ0 + 6.6, GZ0 + 13.4)
    canopy(m, GX1 - 5.4, GX1 - 0.9, GZ0 + 3.4, GZ0 + 8.8)

    # --- two chill-out corners (CHILL-OUT ECKEN) --------------------------
    lounge(m, GX0 + 3.6, GZ0 + 17.2, 3.4, 2.4, 0.0)
    lounge(m, GX1 - 2.8, GZ0 + 11.4, 3.0, 2.2, 90.0)

    # --- trees ------------------------------------------------------------
    for (x, z) in ((GX0 + 1.0, GZ1 - 1.6), (GX0 + 6.6, GZ1 - 1.2),
                   (GX1 - 1.2, GZ1 - 1.4), (GX1 - 0.8, GZ0 + 2.0),
                   (GX0 + 10.5, GZ0 + 3.0), (GX1 - 2.2, GZ0 + 6.4)):
        tree(m, x, z)
    # bushes along the fence
    for i in range(6):
        m.add("leaf", *place(sphere((0, 0, 0), 0.55, segments=10, rings=6),
                             translation=(GX0 + 1.0 + i * 2.4, 0.45, GZ1 - 0.5),
                             scale=(1.2, 0.8, 1.0)))
    return m


def playlist_mesh():
    """The set list board and the marker that follows the running track.

    Returns (board mesh, marker node).  The marker lives on its own
    TransformGroup so the script only has to move it down by one row height.
    """
    board = Mesh()
    slab(board, "steel", (PANEL_X, PANEL_Y, PANEL_Z - 0.05),
         (PANEL_W + 0.22, PANEL_H + 0.22, 0.10))
    row_h = PANEL_H * (1.0 - PANEL_TOP - PANEL_BOTTOM) / float(len(TRACKS))
    # the title band above the rows ("DISTILLERY - DJ BOOTH")
    header_h = PANEL_H * PANEL_TOP
    billboard(board, "playlist",
              (PANEL_X, PANEL_Y + PANEL_H * 0.5 - header_h * 0.5, PANEL_Z + 0.02),
              PANEL_W, header_h, "+z", uv=(0.0, 0.0, 1.0, PANEL_TOP))
    top_y = PANEL_Y + PANEL_H * 0.5 - PANEL_H * PANEL_TOP
    for i, uv in enumerate(row_uvs()):
        cy = top_y - (i + 0.5) * row_h
        billboard(board, "playlist", (PANEL_X, cy, PANEL_Z + 0.02),
                  PANEL_W, row_h, "+z", uv=uv)

    marker_mesh = Mesh()
    marker_mesh.add("neonAmber", *place(box((0, 0, 0), (PANEL_W, 0.035, 0.03)),
                                       translation=(0, 0, 0)))
    marker_mesh.add("neonAmber", *place(box((0, 0, 0), (0.07, row_h * 0.7, 0.05)),
                                       translation=(-PANEL_W * 0.5 - 0.09, 0, 0)))
    marker = Node("TransformGroup", "playlistMarker",
                  translation="%g %g %g" % (PANEL_X + PANEL_W * 0.5, top_y - row_h * 0.5,
                                            PANEL_Z + 0.07))
    marker.add(Node("Shape", "playlistMarkerMesh", marker_mesh,
                    materials=["neonAmber"]))
    return board, marker, row_h


def source_lamps():
    """Two small lamps next to the board: which source is playing right now.

    Amber = the club playlist (PA, synced for everybody),
    cyan  = the game radio (local stream for this player).
    """
    out = []
    size = PANEL_H * 0.075
    for name, mat, dx in (("srcLampPa", "neonAmber", -0.11),
                          ("srcLampRadio", "neonCyan", 0.11)):
        mesh = Mesh()
        mesh.add(mat, *place(box((0, 0, 0), (size * 2.0, size, 0.035))))
        node = Node("TransformGroup", name,
                    translation="%g %g %g" % (
                        PANEL_X - PANEL_W * 0.5 + size * 1.6,
                        PANEL_Y + PANEL_H * 0.5 + size * 1.6, PANEL_Z + 0.03))
        # the second lamp sits right next to the first one
        node.attrs["translation"] = "%g %g %g" % (
            PANEL_X - PANEL_W * 0.5 + size * 1.6 + (0.0 if dx < 0 else size * 3.0),
            PANEL_Y + PANEL_H * 0.5 + size * 1.4, PANEL_Z + 0.03)
        node.add(Node("Shape", name + "Mesh", mesh, materials=[mat]))
        out.append(node)
    return out


# --------------------------------------------------------------------------
# collision + areas
# --------------------------------------------------------------------------
def collision_nodes():
    out = []

    def block(name, centre, size):
        m = Mesh()
        slab(m, "collision", centre, size)
        out.append(Node("Shape", name, m, materials=["collision"], **{
            "dynamic": "false", "compound": "true",
            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
            "castsShadows": "false", "receiveShadows": "false",
            "nonRenderable": "true"}))

    # main hall walls
    block("colMainFront", ((MX0 + MX1) * 0.5, MH * 0.5, MZ0 - WALL * 0.5),
          (MX1 - MX0 + WALL, MH, WALL))
    block("colMainBack", ((MX0 + MX1) * 0.5, MH * 0.5, MZ1 + WALL * 0.5),
          (MX1 - MX0 + WALL, MH, WALL))
    block("colMainWest", (MX0 - WALL * 0.5, MH * 0.5, (MZ0 + MZ1) * 0.5),
          (WALL, MH, MZ1 - MZ0))
    # bar wing walls
    block("colBarFront", ((BX0 + BX1) * 0.5, BH * 0.5, BZ0 - WALL * 0.5),
          (BX1 - BX0 + WALL, BH, WALL))
    block("colBarBack", ((BX0 + BX1) * 0.5, BH * 0.5, BZ1 + WALL * 0.5),
          (BX1 - BX0 + WALL, BH, WALL))
    block("colBarEast", (BX1 + WALL * 0.5, BH * 0.5, (BZ0 + BZ1) * 0.5),
          (WALL, BH, BZ1 - BZ0))
    # stage + bar counter
    block("colStage", ((-6.0 + 2.0) * 0.5, 0.45, MZ0 + 2.3), (8.0, 0.9, 3.9))
    block("colBarCounter", (BX1 - 1.2, 0.6, (BZ0 + BZ1) * 0.5), (1.7, 1.2, BZ1 - BZ0 - 2.6))
    # PA stacks
    for i, (x, z) in enumerate(((-7.6, -7.4), (3.6, -7.4), (-7.6, -3.2), (3.6, -3.2))):
        block("colPA%d" % (i + 1), (x, 1.8, z), (1.5, 3.6, 1.2))
    # garden bar hut
    block("colGardenBar", (GX0 + 3.1, 1.3, GZ0 + 4.5), (4.8, 2.6, 3.2))
    # the tower and the canopy posts from the plans
    block("colTower", ((TOWER_X0 + TOWER_X1) * 0.5, TOWER_H * 0.5,
                       (TOWER_Z0 + TOWER_Z1) * 0.5),
          (TOWER_X1 - TOWER_X0, TOWER_H, TOWER_Z1 - TOWER_Z0))
    for i, (x, z) in enumerate(((GX0 + 6.4, GZ0 + 6.6), (GX0 + 12.6, GZ0 + 6.6),
                                (GX0 + 6.4, GZ0 + 13.4), (GX0 + 12.6, GZ0 + 13.4),
                                (GX1 - 5.4, GZ0 + 3.4), (GX1 - 0.9, GZ0 + 3.4),
                                (GX1 - 5.4, GZ0 + 8.8), (GX1 - 0.9, GZ0 + 8.8))):
        block("colPost%d" % i, (x, 1.55, z), (0.24, 3.1, 0.24))
    return out


def build_scene():
    root = Node("TransformGroup", "distillery")

    root.add(Node("Shape", "shellMesh", shell_mesh()))
    root.add(Node("Shape", "stageMesh", stage_mesh()))
    root.add(Node("Shape", "floorMesh", dance_floor_mesh()))
    root.add(Node("Shape", "propsMesh", interior_props()))
    rig, groups, heads = light_rig_mesh()
    root.add(Node("Shape", "rigMesh", rig))
    for key, mesh in groups.items():
        g = Node("TransformGroup", "light" + key)
        g.add(Node("Shape", "neon" + key, mesh, materials=["neon" + key]))
        root.add(g)
    root.add(Node("Shape", "gardenMesh", garden_mesh()))

    # --- PA stacks --------------------------------------------------------
    pa = Mesh()
    for (x, z, facing) in ((-7.6, -7.4, 1), (3.6, -7.4, 1),
                           (-7.6, -3.2, 1), (3.6, -3.2, 1)):
        stack, _top = pa_stack(x, z, facing)
        for mat, part in stack.parts.items():
            pa.add(mat, *part)
    root.add(Node("Shape", "paMesh", pa))

    # --- signs ------------------------------------------------------------
    signs = Mesh()
    billboard(signs, "signDistillery", (-3.4, 5.30, MZ0 - WALL - 0.06), 8.4, 1.9, "-z")
    billboard(signs, "signLeipzig", (0.0, 3.62, MZ0 - WALL - 0.06), 3.6, 1.05, "-z")
    billboard(signs, "signBar", (GX0 + 3.1, 2.95, GZ0 - 0.42), 2.6, 0.9, "+z")
    # a backlit poster wall next to the door
    billboard(signs, "graffiti", (6.8, 2.6, MZ0 - WALL - 0.05), 3.0, 2.4, "-z")
    billboard(signs, "graffiti", (-5.6, 2.3, MZ0 - WALL - 0.05), 4.4, 2.6, "-z")
    billboard(signs, "graffiti", (GX0 + 2.0, 2.2, GZ0 - 0.42), 3.4, 2.2, "+z")
    root.add(Node("Shape", "signMesh", signs))

    # --- set list board at the DJ booth ----------------------------------
    board, marker, _row_h = playlist_mesh()
    root.add(Node("Shape", "playlistMesh", board, materials=["steel", "playlist"]))
    root.add(marker)
    for lamp in source_lamps():
        root.add(lamp)

    # --- mirror ball ------------------------------------------------------
    pivot = Node("TransformGroup", "mirrorBallPivot", translation="0 4.55 -1.2")
    ball = Mesh()
    ball.add("mirror", *sphere((0, 0, 0), 0.55, segments=24, rings=14))
    pivot.add(Node("Shape", "mirrorBall", ball, materials=["mirror"]))
    rod = Mesh()
    rod.add("steel", *place(cylinder(0.035, 0.0, 1.2, 8, caps=True),
                            translation=(0, 0.5, 0)))
    pivot.add(Node("Shape", "mirrorBallRod", rod, materials=["steel"]))
    root.add(pivot)

    # --- lights -----------------------------------------------------------
    lights = Node("TransformGroup", "lights")
    for i, (x, y, z) in enumerate(heads[:8]):
        col = ((1.0, 0.30, 0.65), (0.40, 0.85, 1.0), (1.0, 0.70, 0.30))[i % 3]
        lights.add(Node("Light", "headLight%d" % (i + 1), type="point", range="11",
                        diffuseColor="%g %g %g 1" % col, castShadowMap="false",
                        decayRate="2", translation="%g %g %g" % (x, y, z)))
    # warm lights for the bar and the foyer
    lights.add(Node("Light", "barLight", type="point", range="12",
                    diffuseColor="1.0 0.72 0.42 1", castShadowMap="false",
                    decayRate="2", translation="%g 3.2 %g" % (BX1 - 2.0, 0.0)))
    lights.add(Node("Light", "foyerLight", type="point", range="9",
                    diffuseColor="1.0 0.86 0.62 1", castShadowMap="false",
                    decayRate="2", translation="%g 2.8 %g" % (BX0 + 2.6, BZ0 + 2.6)))
    lights.add(Node("Light", "gardenLight", type="point", range="16",
                    diffuseColor="1.0 0.74 0.40 1", castShadowMap="false",
                    decayRate="2", translation="%g 3.4 %g" % (GX0 + 3.1, GZ0 + 5.0)))
    root.add(lights)

    for node in collision_nodes():
        root.add(node)

    # --- triggers and helper nodes ---------------------------------------
    root.add(trigger_node("clubTrigger", (MX1 - MX0 - 1.0, 5.0, MZ1 - MZ0 - 1.0),
                          ((MX0 + MX1) * 0.5, 2.5, (MZ0 + MZ1) * 0.5),
                          mask=trigger_mask(PLAYER, VEHICLE)))
    root.add(trigger_node("djTrigger", (3.4, 2.0, 2.0), (-1.6, 1.0, MZ0 + 3.0),
                          mask=trigger_mask(PLAYER)))
    root.add(Node("TransformGroup", "musicNode", translation="0 2.6 -1.4"))
    root.add(Node("TransformGroup", "djNode", translation="-1.6 1.1 -8.6"))

    # --- placement areas --------------------------------------------------
    root.add(line_area("testArea1", (MX0 - 2.0, 0.0, STREET_Z - 2.0),
                       (GX1 + 2.0, 0.0, GZ1 + 2.0)))
    root.add(area("clearArea1", MX0 - 3.0, 0.0, STREET_Z - 2.0,
                  (GX1 - MX0) + 6.0, (GZ1 - STREET_Z) + 4.0))
    root.add(area("levelArea1", MX0 - 3.0, 0.0, STREET_Z - 2.0,
                  (GX1 - MX0) + 6.0, (GZ1 - STREET_Z) + 4.0))
    root.add(area("paintArea1", MX0 - 3.0, 0.0, STREET_Z - 2.0,
                  (GX1 - MX0) + 6.0, (GZ1 - STREET_Z) + 4.0))
    root.add(area("indoorArea1", MX0 + 0.2, 0.05, MZ0 + 0.2,
                  (MX1 - MX0) - 0.4, (MZ1 - MZ0) - 0.4))
    root.add(area("outdoorArea1", GX0 + 0.2, 0.02, GZ0 + 0.2,
                  (GX1 - GX0) - 0.4, (GZ1 - GZ0) - 0.4))
    root.add(area("foliageArea1", MX0 - 3.0, 0.0, STREET_Z - 2.0,
                  (GX1 - MX0) + 6.0, (GZ1 - STREET_Z) + 4.0))
    return root


def write(out_path, asset_name="distillery"):
    return write_i3d(build_scene(), out_path, materials=MATERIALS, asset_name=asset_name)


if __name__ == "__main__":
    import sys
    stats, mappings = write(sys.argv[1] if len(sys.argv) > 1 else "/tmp/distillery_inline.i3d")
    print("%d shapes, %d verts, %d tris" % (stats["shapes"], stats["verts"], stats["tris"]))
