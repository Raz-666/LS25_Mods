# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of Baba Jaga's hut (FS25_BabaJaga) - a placeable chicken coop.

A log cabin with a shingled roof and a crooked chimney, standing on one big
chicken leg with claws, plus a fenced chicken yard around it.

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
from meshlib import Mesh, box, cylinder, place, sphere, torus, TAU
from model import Node, _fmt
from triggers import ANIMAL, PLAYER, VEHICLE, trigger_mask, trigger_node

# --- dimensions (metres) ---------------------------------------------------
LEG_HEIGHT = 3.10        # from the ground to the "ankle"
HUT_FLOOR = 3.55         # floor of the cabin
HUT_W, HUT_D, HUT_H = 4.30, 3.40, 2.35
ROOF_H = 1.75
YARD = 6.00              # half size of the fenced chicken yard
TROUGH_X, TROUGH_Z = 2.55, 2.45   # the two feeding troughs in the yard

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
]


# --------------------------------------------------------------------------
# the chicken leg
# --------------------------------------------------------------------------
def leg_mesh():
    m = Mesh()
    # feathered thigh, hanging down from the floor of the cabin
    m.add("woodDark", *place(cylinder(0.62, HUT_FLOOR - 0.55, HUT_FLOOR - 0.05, 20,
                                      caps=True, top_radius=0.42)))
    for i in range(9):
        a = TAU * i / 9
        m.add("woodDark", *place(sphere((0, 0, 0), 0.20, 10, 8, scale=(1.5, 0.8, 1.0)),
                                 rot=(0, -math.degrees(a), 18),
                                 translation=(0.46 * math.cos(a), HUT_FLOOR - 0.30,
                                              0.46 * math.sin(a))))
    # the scaly shank
    m.add("legSkin", *place(cylinder(0.26, 0.24, HUT_FLOOR - 0.45, 16, caps=True,
                                     top_radius=0.42)))
    for k in range(8):
        y = 0.55 + k * 0.32
        r = 0.42 - 0.020 * k
        m.add("legSkin", *place(torus(r, 0.035, 0, 16, 6), translation=(0, y, 0)))
    # ankle
    m.add("legSkin", *place(sphere((0, 0, 0), 0.30, 16, 10, scale=(1.0, 0.9, 1.0)),
                            translation=(0, 0.32, 0)))
    # three forward toes and one rear toe, built from shrinking spheres so
    # they curve nicely without any rotation maths
    for a in (90, 210, 330):
        rad = math.radians(a)
        dx, dz = math.cos(rad), math.sin(rad)
        for t in range(5):
            r = 0.17 - 0.018 * t
            dist = 0.22 + 0.21 * t
            m.add("legSkin", *place(sphere((0, 0, 0), r, 12, 8, scale=(1.0, 0.8, 1.0)),
                                    translation=(dx * dist, 0.20 - 0.015 * t, dz * dist)))
        # claw tip that digs into the ground
        m.add("claw", *place(sphere((0, 0, 0), 0.11, 12, 8, scale=(0.85, 0.75, 1.7)),
                             rot=(0, -a + 90, -26),
                             translation=(dx * 1.28, 0.09, dz * 1.28)))
    # rear toe
    for t in range(4):
        r = 0.13 - 0.018 * t
        m.add("legSkin", *place(sphere((0, 0, 0), r, 10, 8, scale=(1.0, 0.8, 1.0)),
                                translation=(0, 0.19 - 0.012 * t, -(0.22 + 0.19 * t))))
    m.add("claw", *place(sphere((0, 0, 0), 0.09, 10, 8, scale=(0.8, 0.8, 1.4)),
                         rot=(0, 0, -22), translation=(0, 0.09, -0.98)))
    return m


# --------------------------------------------------------------------------
# the hut
# --------------------------------------------------------------------------
def hut_mesh():
    m = Mesh()
    y0 = HUT_FLOOR

    m.add("woodDark", *place(box((0, 0, 0), (HUT_W, 0.18, HUT_D)),
                             translation=(0, y0 + 0.09, 0)))

    rows = 6
    for r in range(rows):
        y = y0 + 0.26 + r * 0.34
        for side in (-1, 1):
            m.add("woodLog", *place(cylinder(0.19, -HUT_W * 0.5, HUT_W * 0.5, 12,
                                             caps=True),
                                    rot=(0, 0, 90),
                                    translation=(0, y, side * HUT_D * 0.5)))
        for side in (-1, 1):
            m.add("woodLog", *place(cylinder(0.19, -HUT_D * 0.5 - 0.18,
                                             HUT_D * 0.5 + 0.18, 12, caps=True),
                                    rot=(90, 0, 0),
                                    translation=(side * HUT_W * 0.5, y, 0)))

    for sx in (-1, 1):
        for sz in (-1, 1):
            m.add("woodDark", *place(cylinder(0.16, y0, y0 + HUT_H, 12, caps=True),
                                     translation=(sx * HUT_W * 0.5, 0, sz * HUT_D * 0.5)))

    for side in (-1, 1):
        steps = 6
        for k in range(steps):
            y = y0 + HUT_H + k * (ROOF_H / steps) * 0.92
            width = HUT_W * (1.0 - k / float(steps)) * 0.98
            m.add("woodLog", *place(cylinder(0.15, -width * 0.5, width * 0.5, 10, caps=True),
                                    rot=(0, 0, 90),
                                    translation=(0, y + 0.07, side * HUT_D * 0.5)))

    slope = math.degrees(math.atan2(ROOF_H, HUT_D * 0.5))
    half_len = math.hypot(ROOF_H, HUT_D * 0.5) + 0.55
    for side in (-1, 1):
        m.add("roof", *place(box((0, 0, 0), (HUT_W + 0.55, 0.16, half_len)),
                             rot=(side * (90 - slope), 0, 0),
                             translation=(0, y0 + HUT_H + ROOF_H * 0.5,
                                          side * (HUT_D * 0.25 + 0.14))))
    m.add("woodDark", *place(cylinder(0.13, -HUT_W * 0.5 - 0.32, HUT_W * 0.5 + 0.32, 10,
                                      caps=True), rot=(0, 0, 90),
                             translation=(0, y0 + HUT_H + ROOF_H + 0.03, 0)))

    # door
    m.add("woodDark", *place(box((0, 0, 0), (0.98, 1.72, 0.10)),
                             translation=(0.05, y0 + 0.90, HUT_D * 0.5 + 0.10)))
    for k in range(3):
        m.add("woodLog", *place(box((0, 0, 0), (0.92, 0.06, 0.05)),
                                translation=(0.05, y0 + 0.42 + k * 0.56,
                                             HUT_D * 0.5 + 0.16)))
    m.add("legSkin", *place(sphere((0, 0, 0), 0.055, 10, 8),
                            translation=(0.38, y0 + 0.92, HUT_D * 0.5 + 0.18)))

    # windows with warm light behind them
    for sx in (-1, 1):
        m.add("glow", *place(box((0, 0, 0), (0.06, 0.72, 0.86)),
                             translation=(sx * (HUT_W * 0.5 + 0.13), y0 + 1.42, -0.35)))
        for dz in (-0.44, 0.44):
            m.add("woodDark", *place(box((0, 0, 0), (0.10, 0.86, 0.10)),
                                     translation=(sx * (HUT_W * 0.5 + 0.16),
                                                  y0 + 1.42, -0.35 + dz)))
        for dy in (-0.40, 0.40):
            m.add("woodDark", *place(box((0, 0, 0), (0.10, 0.10, 0.96)),
                                     translation=(sx * (HUT_W * 0.5 + 0.16),
                                                  y0 + 1.42 + dy, -0.35)))

    # crooked chimney
    m.add("stone", *place(box((0, 0, 0), (0.62, 1.55, 0.62)), rot=(0, 12, 3),
                          translation=(-1.15, y0 + HUT_H + 0.95, -0.55)))
    m.add("stone", *place(box((0, 0, 0), (0.76, 0.14, 0.76)), rot=(0, 12, 0),
                          translation=(-1.18, y0 + HUT_H + 1.72, -0.58)))
    m.add("stone", *place(torus(0.30, 0.06, 0, 20, 6),
                          translation=(-1.22, y0 + HUT_H + 2.05, -0.60)))

    # porch beam with a lantern
    m.add("woodDark", *place(box((0, 0, 0), (1.60, 0.14, 0.14)),
                             translation=(0.05, y0 + 1.85, HUT_D * 0.5 + 0.42)))
    m.add("woodDark", *place(cylinder(0.05, y0 + 1.30, y0 + 1.85, 8, caps=True),
                             translation=(0.78, 0, HUT_D * 0.5 + 0.42)))
    m.add("glow", *place(box((0, 0, 0), (0.20, 0.26, 0.20)),
                         translation=(0.05, y0 + 1.66, HUT_D * 0.5 + 0.42)))
    return m


def detail_mesh():
    """Small extras: a broom leaning at the wall and a sign post."""
    m = Mesh()
    y0 = HUT_FLOOR
    m.add("woodDark", *place(cylinder(0.035, y0 + 0.05, y0 + 1.45, 8, caps=True),
                             rot=(0, 0, 12), translation=(1.72, 0, 0.95)))
    m.add("woodLog", *place(box((0, 0, 0), (0.30, 0.42, 0.12)), rot=(0, 0, 10),
                            translation=(1.86, y0 + 0.28, 0.95)))
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
        # wheat/grain inside, slightly heaped
        m.add("feed", *place(box((0, 0, 0), (0.56, 0.05, 1.22)),
                             translation=(TROUGH_X, 0.30, z)))
        m.add("feed", *place(sphere((0, 0, 0), 0.28, 14, 8, scale=(0.8, 0.35, 2.1)),
                             translation=(TROUGH_X, 0.31, z)))
    # sign post with a little sign board, leaning towards the visitor
    m.add("woodDark", *place(cylinder(0.08, 0.0, 1.60, 8, caps=True),
                             translation=(-2.9, 0, 2.9)))
    m.add("woodLog", *place(box((0, 0, 0), (1.05, 0.40, 0.08)), rot=(0, 35, 0),
                            translation=(-2.9, 1.45, 2.9)))
    m.add("woodDark", *place(box((0, 0, 0), (0.90, 0.06, 0.10)), rot=(0, 35, 0),
                             translation=(-2.9, 1.45, 2.9)))
    return m


def collision_meshes():
    """(name, geometry, is_component) - the hut is solid, the leg is, too."""
    return [
        ("babaJagaHutCol", box((0, HUT_FLOOR + 1.2, 0), (HUT_W + 0.1, 2.4, HUT_D + 0.1))),
        ("babaJagaRoofCol", box((0, HUT_FLOOR + HUT_H + ROOF_H * 0.55, 0),
                                (HUT_W + 0.5, ROOF_H * 1.1, HUT_D * 0.9))),
        ("babaJagaLegCol", cylinder(0.55, 0.0, HUT_FLOOR, 12, caps=True)),
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
