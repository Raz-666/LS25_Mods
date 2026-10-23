# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of Baba Jaga's hut (FS25_BabaJaga) - a placeable chicken coop.

A crooked log izba on one big chicken leg, built to look like the hut from the
old fairy tale films: steep shingled gable roof, mossy log walls, shutters,
a rope ladder, a hanging lantern, a crooked smoking chimney - and around it a
chicken yard with troughs, a sign post and skull poles on the fence corners.

Everything is procedural: no base game assets are copied.  On top of the
visible meshes the scene carries all the helper nodes the base game husbandry
specializations need:

  * a flat CPU mesh (`navigationMeshShape`) from which the game builds the
    navmesh for the chickens, using the fence contour as the border,
  * trigger boxes for the animal loading trigger, the info trigger and the
    egg pallet spawner,
  * area nodes (start + width + height) for clearing, levelling, the indoor
    area and the grass in the yard,
  * the fence corner nodes of the base game chicken net fence,
  * the fill node the player tips grain into.

The mod contains no Lua at all, so it is console safe.
"""

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "ufo"))

import model  # noqa: E402
from meshlib import Mesh, box, cylinder, lathe, place, sphere, torus, TAU  # noqa: E402
from model import Node, _fmt  # noqa: E402
from triggers import ANIMAL, PLAYER, VEHICLE, trigger_mask, trigger_node  # noqa: E402

# --- dimensions (metres) ---------------------------------------------------
LEG_TOP = 2.80           # the feathered thigh ends here, the shank begins
HUT_FLOOR = 3.55         # floor of the cabin
HUT_W, HUT_D, HUT_H = 4.60, 3.60, 2.50
ROOF_H = 2.30            # steep, fairy tale roof
ROOF_OVER = 0.55         # eave overhang
YARD = 6.00              # half size of the fenced chicken yard
TROUGH_X, TROUGH_Z = 2.55, 2.45   # the two feeding troughs in the yard
DOOR_X = 0.15
FRONT = HUT_D * 0.5      # z of the front wall (the gable side, door here)

MATERIALS = [
    {"name": "collision", "diffuse": None, "color": "0.6 0.1 0.6 1", "specular": "0.1 0.1 0.1"},
    {"name": "navMesh", "diffuse": None, "color": "0.35 0.55 0.30 1", "specular": "0.1 0.1 0.1"},
    {"name": "woodLog", "diffuse": "woodLog_diffuse.dds", "gloss": "woodLog_specular.dds"},
    {"name": "woodDark", "diffuse": "woodDark_diffuse.dds", "gloss": "woodDark_specular.dds"},
    {"name": "roof", "diffuse": "roof_diffuse.dds", "gloss": "roof_specular.dds"},
    {"name": "legSkin", "diffuse": "legSkin_diffuse.dds", "gloss": "legSkin_specular.dds"},
    {"name": "claw", "diffuse": "claw_diffuse.dds", "gloss": None},
    {"name": "glow", "diffuse": "glow_diffuse.dds", "gloss": None},
    {"name": "stone", "diffuse": "stone_diffuse.dds", "gloss": "stone_specular.dds"},
    {"name": "feed", "diffuse": None, "color": "0.86 0.72 0.36 1", "specular": "0.2 0.2 0.2"},
    {"name": "feather", "diffuse": None, "color": "0.30 0.20 0.12 1", "specular": "0.15 0.15 0.15"},
    {"name": "moss", "diffuse": None, "color": "0.20 0.34 0.13 1", "specular": "0.05 0.05 0.05"},
    {"name": "iron", "diffuse": None, "color": "0.16 0.16 0.17 1", "specular": "0.5 0.5 0.5"},
    {"name": "bone", "diffuse": None, "color": "0.86 0.83 0.72 1", "specular": "0.2 0.2 0.2"},
    {"name": "rope", "diffuse": None, "color": "0.55 0.44 0.26 1", "specular": "0.1 0.1 0.1"},
]


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _ring_of(m, mat, geom, count, radius, y, phase=0.0, scale=(1.0, 1.0, 1.0),
             tilt=0.0):
    """Put `count` copies of `geom` on a circle - used for feathers and scales."""
    for i in range(count):
        a = TAU * i / count + phase
        m.add(mat, *place(geom,
                          rot=(tilt, -math.degrees(a), 0.0),
                          scale=scale,
                          translation=(radius * math.cos(a), y, radius * math.sin(a))))


# --------------------------------------------------------------------------
# the chicken leg
# --------------------------------------------------------------------------
def leg_mesh():
    """The chicken leg: feathered thigh, scaly shank, three fat toes + talons."""
    m = Mesh()
    y0 = HUT_FLOOR
    knee = LEG_TOP

    # --- feathered thigh, hanging out of the floor of the cabin ------------
    m.add("feather", *place(lathe([(0.34, knee - 0.05), (0.50, knee + 0.30),
                                   (0.66, knee + 0.55), (0.74, y0 - 0.02)],
                                  segments=22, close_ends=True)))
    # shaggy feather rows, longer towards the bottom
    for k, y in enumerate((y0 - 0.05, y0 - 0.22, y0 - 0.40, y0 - 0.58,
                           y0 - 0.74, y0 - 0.88)):
        r = 0.70 - 0.075 * k
        _ring_of(m, "feather", sphere((0, 0, 0), 1.0, 10, 6),
                 13 + k, r, y, phase=0.24 * k,
                 scale=(0.115, 0.30 + 0.02 * k, 0.075), tilt=12 + 4 * k)
        _ring_of(m, "feather", sphere((0, 0, 0), 1.0, 8, 6),
                 9 + k, r - 0.06, y - 0.06, phase=0.5 + 0.2 * k,
                 scale=(0.09, 0.24, 0.06), tilt=22 + 4 * k)
    # a ring of long feathers right at the bottom edge
    for i in range(11):
        a = TAU * i / 11 + 0.15
        m.add("feather", *place(sphere((0, 0, 0), 1.0, 8, 6),
                                rot=(22, -math.degrees(a), 0),
                                scale=(0.085, 0.34, 0.065),
                                translation=(0.34 * math.cos(a), knee + 0.10,
                                             0.34 * math.sin(a))))

    # --- the knee ----------------------------------------------------------
    m.add("legSkin", *place(sphere((0, 0, 0), 1.0, 18, 12, scale=(0.25, 0.22, 0.25)),
                            translation=(0, knee - 0.02, 0)))

    # --- the scaly shank ---------------------------------------------------
    profile = [(0.180, 0.46), (0.170, 0.62), (0.176, 0.95), (0.186, 1.30),
               (0.198, 1.65), (0.212, 2.00), (0.232, 2.35), (0.258, knee - 0.05)]
    m.add("legSkin", *place(lathe(profile, segments=20, close_ends=True)))
    # big scale bands - this is what makes it read as a chicken leg
    for i in range(12):
        y = 0.52 + i * 0.18
        r = 0.176 + 0.0068 * i
        m.add("legSkin", *place(torus(r, 0.030, 0, 22, 6), translation=(0, y, 0)))
    # scales in between, alternating so no two rows line up
    for i in range(11):
        y = 0.61 + i * 0.18
        for j in range(8):
            a = TAU * j / 8 + (0.39 if i % 2 else 0.0)
            r = 0.180 + 0.0075 * i
            m.add("legSkin", *place(sphere((0, 0, 0), 1.0, 8, 6),
                                    rot=(0, -math.degrees(a), 0),
                                    scale=(0.085, 0.075, 0.045),
                                    translation=(r * math.cos(a), y, r * math.sin(a))))

    # --- the spur on the back of the leg -----------------------------------
    m.add("claw", *place(cylinder(0.055, 0.0, 0.22, 8, caps=True, top_radius=0.0),
                         rot=(-146, 0, 0), translation=(0, 1.62, -0.18)))

    # --- ankle / heel, wider than the shank --------------------------------
    m.add("legSkin", *place(sphere((0, 0, 0), 1.0, 18, 12, scale=(0.24, 0.22, 0.24)),
                            translation=(0, 0.46, 0)))
    m.add("legSkin", *place(sphere((0, 0, 0), 1.0, 16, 10, scale=(0.20, 0.16, 0.20)),
                            translation=(0, 0.30, 0)))

    # --- the foot: three fat toes forward, one back ------------------------
    # a cone that grows along +Y, turned to point outwards and down
    toes = ((0.0, 1.00), (44.0, 0.95), (-44.0, 0.95), (180.0, 0.80))
    for ang, length in toes:
        rad = math.radians(ang)
        dx, dz = math.cos(rad), math.sin(rad)
        yaw = 90.0 - ang                     # ry that turns +Z towards (dx, dz)
        segs = ((0.14, 0.150, 0.22), (0.34, 0.130, 0.195),
                (0.53, 0.108, 0.170), (0.70, 0.090, 0.145),
                (0.85 * length, 0.072, 0.120))
        for dist, r, y in segs:
            m.add("legSkin", *place(sphere((0, 0, 0), r, 12, 8, scale=(1.05, 0.85, 1.30)),
                                    rot=(0, yaw, 0),
                                    translation=(dx * dist * length, y,
                                                 dz * dist * length)))
        # talon: one thick hook sitting on the toe tip, buried in the ground
        base = 0.80 * length
        m.add("claw", *place(lathe([(0.082, 0.0), (0.070, 0.09), (0.050, 0.17),
                                    (0.024, 0.23), (0.0, 0.27)],
                                   segments=10, close_ends=True),
                             rot=(94.0, yaw, 0.0),
                             translation=(dx * base, 0.105, dz * base)))
    return m


# --------------------------------------------------------------------------
# the hut
# --------------------------------------------------------------------------
def _window(m, x, y, z, axis, w=0.85, h=1.00):
    """Window with frame, mullions, warm light and open shutters."""
    s = 1.0 if z > 0 else -1.0
    if axis == "z":
        out = 0.10 * s
        m.add("woodDark", *place(box((0, 0, 0), (w + 0.22, h + 0.22, 0.14)),
                                 translation=(x, y, z + out)))
        m.add("glow", *place(box((0, 0, 0), (w, h, 0.10)),
                             translation=(x, y, z + out + 0.06)))
        m.add("woodDark", *place(box((0, 0, 0), (0.07, h, 0.12)),
                                 translation=(x, y, z + out + 0.07)))
        m.add("woodDark", *place(box((0, 0, 0), (w, 0.07, 0.12)),
                                 translation=(x, y, z + out + 0.07)))
        m.add("woodDark", *place(box((0, 0, 0), (w + 0.34, 0.10, 0.24)),
                                 translation=(x, y - h * 0.5 - 0.14, z + out + 0.04)))
        for side in (-1, 1):
            m.add("woodDark", *place(box((0, 0, 0), (w * 0.52, h + 0.06, 0.07)),
                                     rot=(0, side * 105, 0),
                                     translation=(x + side * (w * 0.5 + 0.30), y,
                                                  z + out + 0.02)))
    else:
        s = 1.0 if x > 0 else -1.0
        out = 0.10 * s
        m.add("woodDark", *place(box((0, 0, 0), (0.14, h + 0.22, w + 0.22)),
                                 translation=(x + out, y, z)))
        m.add("glow", *place(box((0, 0, 0), (0.10, h, w)),
                             translation=(x + out + 0.06, y, z)))
        m.add("woodDark", *place(box((0, 0, 0), (0.12, h, 0.07)),
                                 translation=(x + out + 0.07, y, z)))
        m.add("woodDark", *place(box((0, 0, 0), (0.12, 0.07, w)),
                                 translation=(x + out + 0.07, y, z)))
        m.add("woodDark", *place(box((0, 0, 0), (0.24, 0.10, w + 0.34)),
                                 translation=(x + out + 0.04, y - h * 0.5 - 0.14, z)))
        for side in (-1, 1):
            m.add("woodDark", *place(box((0, 0, 0), (0.07, h + 0.06, w * 0.52)),
                                     rot=(0, side * 105, 0),
                                     translation=(x + out + 0.02, y,
                                                  z + side * (w * 0.5 + 0.30))))


def hut_mesh():
    m = Mesh()
    y0 = HUT_FLOOR
    hw, hd = HUT_W * 0.5, HUT_D * 0.5

    # --- stone foundation --------------------------------------------------
    m.add("stone", *place(box((0, 0, 0), (HUT_W + 0.12, 0.26, HUT_D + 0.12)),
                          translation=(0, y0 - 0.14, 0)))
    # rounded boulders around the rim, so the floor does not look like a slab
    for i in range(14):
        a = TAU * i / 14
        m.add("stone", *place(sphere((0, 0, 0), 1.0, 10, 7),
                              rot=(0, -math.degrees(a), 0),
                              scale=(0.20, 0.15, 0.16),
                              translation=((hw + 0.02) * math.cos(a) * 1.34,
                                           y0 - 0.18, (hd + 0.02) * math.sin(a) * 1.34)))

    # --- log walls (front/back logs and side logs interlock at the corners) -
    rows = 7
    for r in range(rows):
        y = y0 + 0.22 + r * 0.345
        for side in (-1, 1):
            m.add("woodLog", *place(cylinder(0.185, -hw - 0.30, hw + 0.30, 12, caps=True),
                                    rot=(0, 0, 90),
                                    translation=(0, y, side * hd)))
        yy = y + 0.17
        for side in (-1, 1):
            m.add("woodLog", *place(cylinder(0.185, -hd - 0.30, hd + 0.30, 12, caps=True),
                                    rot=(90, 0, 0),
                                    translation=(side * hw, yy, 0)))
    # moss in the gaps
    for i in range(16):
        a = TAU * i / 16
        m.add("moss", *place(sphere((0, 0, 0), 1.0, 8, 6),
                             scale=(0.16, 0.05, 0.10),
                             translation=((hw + 0.05) * math.cos(a) * 1.36,
                                          y0 + 0.20 + (i % 7) * 0.345 + 0.17,
                                          (hd + 0.05) * math.sin(a) * 1.36)))

    # --- door --------------------------------------------------------------
    dz = FRONT + 0.10
    m.add("woodDark", *place(box((0, 0, 0), (1.20, 2.15, 0.10)),
                             translation=(DOOR_X, y0 + 1.07, dz - 0.04)))
    for k in range(5):
        x = DOOR_X - 0.44 + k * 0.22
        m.add("woodLog", *place(box((0, 0, 0), (0.20, 1.95, 0.10)),
                                translation=(x, y0 + 1.00, dz + 0.02)))
    for k, y in enumerate((y0 + 0.42, y0 + 1.62)):
        m.add("iron", *place(box((0, 0, 0), (1.00, 0.10, 0.05)),
                             translation=(DOOR_X, y, dz + 0.08)))
        for side in (-1, 1):
            m.add("iron", *place(box((0, 0, 0), (0.16, 0.07, 0.04)),
                                 rot=(0, 0, side * 18),
                                 translation=(DOOR_X + side * 0.44, y + side * 0.07,
                                              dz + 0.08)))
    m.add("iron", *place(torus(0.075, 0.022, 0, 16, 6),
                         rot=(90, 0, 0), translation=(DOOR_X + 0.40, y0 + 1.02, dz + 0.14)))
    m.add("woodDark", *place(box((0, 0, 0), (1.44, 0.14, 0.26)),
                             translation=(DOOR_X, y0 + 2.16, dz + 0.06)))
    for side in (-1, 1):
        m.add("woodDark", *place(box((0, 0, 0), (0.14, 2.20, 0.14)),
                                 translation=(DOOR_X + side * 0.64, y0 + 1.10, dz + 0.04)))
    m.add("woodDark", *place(box((0, 0, 0), (1.60, 0.12, 0.50)),
                             translation=(DOOR_X, y0 - 0.06, FRONT + 0.22)))

    # --- windows -----------------------------------------------------------
    _window(m, -1.62, y0 + 1.35, FRONT, "z")
    _window(m, 1.62, y0 + 1.35, FRONT, "z")
    _window(m, -hw, y0 + 1.35, -0.45, "x")
    _window(m, hw, y0 + 1.35, 0.55, "x")

    # --- gable ends (stacked logs, shrinking towards the ridge) ------------
    steps = 7
    for side in (-1, 1):
        for k in range(steps):
            yy = y0 + HUT_H + 0.10 + k * (ROOF_H / steps) * 0.94
            width = HUT_W * (1.0 - (k + 0.4) / steps) * 0.96
            m.add("woodLog", *place(cylinder(0.15, -width * 0.5, width * 0.5, 10, caps=True),
                                    rot=(0, 0, 90),
                                    translation=(0, yy, side * hd)))

    # --- the steep shingled roof ------------------------------------------
    slope = math.degrees(math.atan2(ROOF_H, hw))
    half = math.hypot(ROOF_H, hw) + ROOF_OVER
    for side in (-1, 1):
        m.add("roof", *place(box((0, 0, 0), (half, 0.16, HUT_D + 0.70)),
                             rot=(0, 0, -side * (90 - slope)),
                             translation=(side * hw * 0.5, y0 + HUT_H + ROOF_H * 0.5,
                                          0)))
        # fascia board along the eave
        m.add("woodDark", *place(box((0, 0, 0), (0.12, 0.26, HUT_D + 0.74)),
                                 translation=(side * (hw + 0.06),
                                              y0 + HUT_H - 0.10, 0)))
        # barge boards on the two gable edges
        for zside in (-1, 1):
            m.add("woodDark", *place(box((0, 0, 0), (half + 0.10, 0.14, 0.12)),
                                     rot=(0, 0, -side * (90 - slope)),
                                     translation=(side * hw * 0.5,
                                                  y0 + HUT_H + ROOF_H * 0.5,
                                                  zside * (hd + 0.33))))
    # ridge beam
    m.add("woodDark", *place(cylinder(0.14, -hd - 0.34, hd + 0.34, 10, caps=True),
                             rot=(90, 0, 0),
                             translation=(0, y0 + HUT_H + ROOF_H + 0.02, 0)))

    # --- crooked chimney ---------------------------------------------------
    cx, cz = -1.45, -0.70
    m.add("stone", *place(box((0, 0, 0), (0.72, 0.85, 0.66)), rot=(0, 9, 2),
                          translation=(cx, y0 + HUT_H + 0.60, cz)))
    m.add("stone", *place(box((0, 0, 0), (0.62, 0.80, 0.58)), rot=(0, 14, 4),
                          translation=(cx - 0.06, y0 + HUT_H + 1.36, cz - 0.05)))
    m.add("stone", *place(box((0, 0, 0), (0.52, 0.55, 0.50)), rot=(0, 18, 6),
                          translation=(cx - 0.14, y0 + HUT_H + 1.98, cz - 0.11)))
    m.add("iron", *place(box((0, 0, 0), (0.70, 0.08, 0.66)), rot=(0, 18, 0),
                         translation=(cx - 0.17, y0 + HUT_H + 2.28, cz - 0.13)))

    # --- porch over the door ----------------------------------------------
    m.add("woodDark", *place(box((0, 0, 0), (2.30, 0.13, 1.20)),
                             translation=(DOOR_X, y0 + 2.34, FRONT + 0.55)))
    for side in (-1, 1):
        m.add("woodDark", *place(box((0, 0, 0), (0.13, 1.05, 0.13)),
                                 rot=(-38, 0, 0),
                                 translation=(DOOR_X + side * 1.02, y0 + 1.90,
                                              FRONT + 0.52)))
    # hanging lantern under the porch
    m.add("iron", *place(cylinder(0.018, y0 + 1.72, y0 + 2.30, 6, caps=True),
                         translation=(DOOR_X - 0.92, 0, FRONT + 0.80)))
    m.add("iron", *place(box((0, 0, 0), (0.30, 0.06, 0.30)),
                         translation=(DOOR_X - 0.92, y0 + 1.74, FRONT + 0.80)))
    m.add("glow", *place(box((0, 0, 0), (0.24, 0.30, 0.24)),
                         translation=(DOOR_X - 0.92, y0 + 1.57, FRONT + 0.80)))
    m.add("iron", *place(box((0, 0, 0), (0.30, 0.05, 0.30)),
                         translation=(DOOR_X - 0.92, y0 + 1.40, FRONT + 0.80)))

    # --- rope ladder from the porch down to the ground --------------------
    lx = DOOR_X + 1.55
    lz = FRONT + 1.02
    for side in (-1, 1):
        m.add("rope", *place(cylinder(0.028, 0.12, y0 + 2.28, 6, caps=True),
                             translation=(lx + side * 0.24, 0, lz)))
    rungs = int((y0 + 2.05) / 0.34)
    for i in range(rungs):
        y = 0.30 + i * 0.34
        m.add("woodDark", *place(cylinder(0.035, -0.24, 0.24, 8, caps=True),
                                 rot=(0, 0, 90), translation=(lx, y, lz)))
    return m


def detail_mesh():
    """Yard props: troughs, sign post, skull poles, broom, firewood."""
    m = Mesh()
    # two feeding troughs in the yard (they are also the food places)
    for z in (TROUGH_Z, -TROUGH_Z):
        for sx in (-1, 1):
            m.add("woodDark", *place(box((0, 0, 0), (0.10, 0.40, 1.40)),
                                     translation=(TROUGH_X + sx * 0.32, 0.20, z)))
        for sz in (-1, 1):
            m.add("woodDark", *place(box((0, 0, 0), (0.74, 0.40, 0.10)),
                                     translation=(TROUGH_X, 0.20, z + sz * 0.65)))
        m.add("woodDark", *place(box((0, 0, 0), (0.74, 0.08, 1.40)),
                                 translation=(TROUGH_X, 0.04, z)))
        m.add("feed", *place(box((0, 0, 0), (0.56, 0.05, 1.22)),
                             translation=(TROUGH_X, 0.30, z)))
        m.add("feed", *place(sphere((0, 0, 0), 0.28, 14, 8, scale=(0.8, 0.35, 2.1)),
                             translation=(TROUGH_X, 0.31, z)))

    # sign post with a board
    m.add("woodDark", *place(cylinder(0.08, 0.0, 1.60, 8, caps=True),
                             translation=(-2.9, 0, 2.9)))
    m.add("woodLog", *place(box((0, 0, 0), (1.05, 0.40, 0.08)), rot=(0, 35, 0),
                            translation=(-2.9, 1.45, 2.9)))
    m.add("woodDark", *place(box((0, 0, 0), (0.90, 0.06, 0.10)), rot=(0, 35, 0),
                             translation=(-2.9, 1.45, 2.9)))

    # skull poles on the four fence corners (very Baba Jaga)
    for name, pos in fence_corners():
        x, _, z = pos
        m.add("woodDark", *place(cylinder(0.07, 0.0, 1.55, 8, caps=True),
                                 translation=(x, 0, z)))
        m.add("bone", *place(sphere((0, 0, 0), 0.17, 14, 10, scale=(0.95, 1.05, 0.95)),
                             translation=(x, 1.70, z)))
        m.add("bone", *place(box((0, 0, 0), (0.19, 0.09, 0.14)),
                             translation=(x, 1.53, z + 0.05)))
        for side in (-1, 1):
            m.add("iron", *place(sphere((0, 0, 0), 0.048, 10, 8),
                                 translation=(x + side * 0.065, 1.73, z + 0.13)))
            m.add("bone", *place(cylinder(0.030, 0.0, 0.14, 6, caps=True),
                                 rot=(-20, 0, side * 22),
                                 translation=(x + side * 0.10, 1.85, z - 0.02)))

    # broom leaning against the trough
    m.add("woodDark", *place(cylinder(0.035, 0.05, 1.45, 8, caps=True),
                             rot=(0, 0, 12), translation=(1.55, 0, 3.25)))
    for i in range(5):
        m.add("rope", *place(box((0, 0, 0), (0.06, 0.34, 0.06)), rot=(0, i * 22, 10),
                             translation=(1.58 + 0.05 * i, 0.20, 3.28)))

    # a little pile of firewood by the leg
    for i in range(4):
        m.add("woodLog", *place(cylinder(0.13, -0.55, 0.55, 10, caps=True),
                                rot=(0, 0, 90),
                                translation=(-2.2, 0.13 + (i // 2) * 0.24,
                                             1.9 + (i % 2) * 0.30)))
    return m


def collision_meshes():
    """(name, geometry) - the hut and the leg are solid."""
    return [
        ("babaJagaHutCol", box((0, HUT_FLOOR + 1.25, 0), (HUT_W + 0.2, 2.5, HUT_D + 0.2))),
        ("babaJagaRoofCol", box((0, HUT_FLOOR + HUT_H + ROOF_H * 0.5, 0),
                                (HUT_W * 0.72, ROOF_H * 1.05, HUT_D + 0.6))),
        ("babaJagaLegCol", cylinder(0.42, 0.0, LEG_TOP + 0.1, 12, caps=True)),
    ]


# --------------------------------------------------------------------------
# helper nodes
# --------------------------------------------------------------------------
def area(name, x, y, z, width, height):
    """Area start node with the width / height vector nodes as children."""
    start = Node("TransformGroup", name, translation="%s %s %s"
                 % (_fmt([x]), _fmt([y]), _fmt([z])))
    start.add(Node("TransformGroup", name + "Width", translation="%s 0 0" % _fmt([width])))
    start.add(Node("TransformGroup", name + "Height", translation="0 0 %s" % _fmt([height])))
    return start


def line_area(name, start, end):
    """Two point area (start + end node), used by test and tip occlusion areas."""
    node = Node("TransformGroup", name, translation="%s %s %s"
                % tuple(_fmt([v]) for v in start))
    node.add(Node("TransformGroup", name + "End",
                  translation="%s 0 %s" % (_fmt([end[0] - start[0]]),
                                           _fmt([end[2] - start[2]]))))
    return node


def fill_node(name, pos):
    mesh = Mesh()
    mesh.add("collision", *cylinder(0.20, -0.06, 0.06, 10, caps=True))
    return Node("Shape", name, mesh, materials=["collision"], **{
        "kinematic": "true",
        "compound": "true",
        "collisionFilterGroup": "0x40000000",
        "collisionFilterMask": "0x20000000",
        "castsShadows": "false",
        "receiveShadows": "false",
        "nonRenderable": "true",
        "translation": "%s %s %s" % tuple(_fmt([v]) for v in pos),
    })


def navmesh_mesh():
    """Flat CPU slab from which the game builds the chicken navmesh."""
    m = Mesh()
    m.add("navMesh", *box((0, 0.04, 0), (YARD * 2 - 0.6, 0.06, YARD * 2 - 0.6)))
    return m


def fence_corners():
    return (("fence1Node1", (-YARD, 0.0, -YARD)),
            ("fence1Node2", (YARD, 0.0, -YARD)),
            ("fence1Node3", (YARD, 0.0, YARD)),
            ("fence1Node4", (-YARD, 0.0, YARD)))


# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------
def build_scene():
    root = Node("TransformGroup", "babaJaga")

    # --- visible geometry --------------------------------------------------
    root.add(Node("Shape", "hutMesh", hut_mesh()))
    root.add(Node("Shape", "legMesh", leg_mesh()))
    root.add(Node("Shape", "detailMesh", detail_mesh()))

    # --- collision ---------------------------------------------------------
    for name, geom in collision_meshes():
        m = Mesh()
        m.add("collision", *geom)
        root.add(Node("Shape", name, m, materials=["collision"], **{
            "dynamic": "false", "compound": "true",
            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
            "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
        }))

    # --- napf / fill node the player tips grain into ------------------------
    root.add(fill_node("foodFillRoot", (TROUGH_X, 0.55, TROUGH_Z)))

    # --- trigger boxes -----------------------------------------------------
    root.add(trigger_node("loadingTrigger", (4.2, 2.6, 3.4), (0.0, 1.3, 3.6),
                          mask=trigger_mask(PLAYER, VEHICLE, ANIMAL)))
    root.add(trigger_node("infoTrigger", (5.6, 4.0, 5.0), (0.0, 2.0, 0.0),
                          mask=PLAYER))
    root.add(trigger_node("palletTrigger", (2.2, 2.0, 2.2), (-3.9, 1.0, 3.9),
                          mask=PLAYER))

    # --- area nodes --------------------------------------------------------
    root.add(line_area("testArea1", (-YARD - 0.6, 0.0, -YARD - 0.6),
                       (YARD + 0.6, 0.0, YARD + 0.6)))
    root.add(area("clearArea1", -YARD - 1.0, 0.0, -YARD - 1.0,
                  2 * (YARD + 1.0), 2 * (YARD + 1.0)))
    root.add(area("levelArea1", -4.6, 0.0, -4.6, 9.2, 9.2))
    root.add(area("paintArea1", -YARD, 0.0, -YARD, 2 * YARD, 2 * YARD))
    root.add(area("foliageArea1", -YARD, 0.0, -YARD, 2 * YARD, 2 * YARD))
    root.add(area("indoorArea1", -1.9, HUT_FLOOR + 0.2, -1.5, 3.8, 3.0))
    root.add(line_area("tipOcclusionUpdateArea1", (-YARD - 1.5, 0.0, -YARD - 1.5),
                       (YARD + 1.5, 0.0, YARD + 1.5)))

    # egg pallet spawn area + teleport node
    root.add(line_area("palletArea1", (-4.9, 0.05, 5.0), (-1.5, 0.05, 5.0)))
    root.add(Node("TransformGroup", "teleportNode", translation="0 0.1 3.4"))

    # --- navmesh + fence ---------------------------------------------------
    nav = root.add(Node("TransformGroup", "navigationRootNode"))
    nav.add(Node("Shape", "navigationMeshShape", navmesh_mesh(), materials=["navMesh"], **{
        "static": "true",
        "collisionFilterGroup": "0x0",
        "collisionFilterMask": "0x0",
        "castsShadows": "false",
        "receiveShadows": "false",
        "nonRenderable": "true",
    }))
    for name, pos in fence_corners():
        root.add(Node("TransformGroup", name,
                      translation="%s %s %s" % tuple(_fmt([v]) for v in pos)))

    # --- food places and markers ------------------------------------------
    root.add(Node("TransformGroup", "foodPlace1",
                  translation="%s 0.4 %s" % (_fmt([TROUGH_X]), _fmt([TROUGH_Z]))))
    root.add(Node("TransformGroup", "foodPlace2",
                  translation="%s 0.4 %s" % (_fmt([TROUGH_X]), _fmt([-TROUGH_Z]))))
    root.add(Node("TransformGroup", "markerFood",
                  translation="%s 0.8 %s" % (_fmt([TROUGH_X]), _fmt([TROUGH_Z]))))
    root.add(Node("TransformGroup", "markerAnimals", translation="0 1.0 4.4"))
    return root


def write(path):
    return model.write_i3d(build_scene(), path, materials=MATERIALS,
                           asset_name="babaJaga")


if __name__ == "__main__":
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    out = os.path.join(repo, "build", "babajaga_inline.i3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stats, mappings = write(out)
    print("%d shapes, %d tris -> %s" % (stats["shapes"], stats["tris"], out))
    sys.exit(0)
