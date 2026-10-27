# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural Baba Jaga residential hut (separate from the chicken coop).

The log shell reuses the original coop's art, but the interior is a walkable
home. A steep, treaded timber stair replaces the visual-only rope ladder, and
native FS25 farmhouse/wardrobe and animated-object triggers are supplied by the
placeable XML. No Lua or custom specialization is shipped, preserving console
compatibility.
"""

import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "ufo"))

import hut as baba  # noqa: E402
import model  # noqa: E402
from meshlib import Mesh, box, cylinder, place, sphere, torus  # noqa: E402
from model import Node, _fmt  # noqa: E402
from triggers import PLAYER, trigger_node  # noqa: E402

HUT_FLOOR = baba.HUT_FLOOR
HUT_W = baba.HUT_W
HUT_D = baba.HUT_D
HUT_H = baba.HUT_H
ROOF_H = baba.ROOF_H
LEG_TOP = baba.LEG_TOP
DOOR_X = baba.DOOR_X
FRONT = baba.FRONT
HALF_W = HUT_W * 0.5
HALF_D = HUT_D * 0.5
DOOR_W = 1.40
DOOR_H = 2.15
BALCONY_DEPTH = 1.70
BALCONY_FRONT = FRONT + BALCONY_DEPTH
STAIR_COUNT = 18
STAIR_RUN = 0.25
STAIR_RISE = HUT_FLOOR / STAIR_COUNT
STAIR_TREAD_DEPTH = 0.34
STAIR_TREAD_WIDTH = 1.38

MATERIALS = list(baba.MATERIALS) + [
    {"name": "linen", "diffuse": None, "color": "0.76 0.66 0.51 1", "specular": "0.12 0.12 0.12"},
    {"name": "linenLight", "diffuse": None, "color": "0.88 0.81 0.67 1", "specular": "0.14 0.14 0.14"},
]


def _collision_node(root, name, geometry):
    mesh = Mesh()
    mesh.add("collision", *geometry)
    root.add(Node("Shape", name, mesh, materials=["collision"], **{
        "static": "true",
        "compound": "true",
        "collisionFilterGroup": "0x1",
        "collisionFilterMask": "0x1",
        "castsShadows": "false",
        "receiveShadows": "false",
        "nonRenderable": "true",
    }))


def _door_leaf_mesh():
    """Door leaf in pivot-local coordinates; hinge is the local origin."""
    m = Mesh()
    m.add("woodDark", *box((DOOR_W * 0.5, DOOR_H * 0.5, 0.0),
                            (DOOR_W, DOOR_H, 0.13)))
    # Individual vertical planks and two iron cross braces.
    for i in range(6):
        x = 0.12 + i * (DOOR_W - 0.24) / 5
        m.add("woodLog", *box((x, DOOR_H * 0.5, 0.074),
                               (0.17, DOOR_H - 0.18, 0.025)))
    for y in (0.42, DOOR_H - 0.42):
        m.add("iron", *box((DOOR_W * 0.5, y, 0.10), (DOOR_W - 0.16, 0.095, 0.055)))
    m.add("iron", *place(torus(0.07, 0.020, 0.0, 16, 6),
                          rot=(90, 0, 0),
                          translation=(DOOR_W - 0.16, 1.02, 0.125)))
    # The ring is a visual handle, placed just inside the free edge.
    return m


def _architecture_mesh():
    """Balcony, porch rails, door frame and a few Baba Jaga home details."""
    m = Mesh()

    # Walkable upper balcony: stout joists and a plank deck level with the hut.
    balcony_z = FRONT + BALCONY_DEPTH * 0.5
    m.add("woodDark", *box((0.0, HUT_FLOOR - 0.09, balcony_z),
                            (HUT_W + 0.18, 0.18, BALCONY_DEPTH)))
    plank_count = 20
    plank_w = (HUT_W + 0.04) / plank_count
    for i in range(plank_count):
        x = -(HUT_W + 0.04) * 0.5 + (i + 0.5) * plank_w
        m.add("woodLog", *box((x, HUT_FLOOR + 0.015, balcony_z),
                               (plank_w * 0.90, 0.035, BALCONY_DEPTH - 0.08)))

    # Side balustrades.
    side_x = HALF_W - 0.08
    side_posts = (FRONT + 0.12, FRONT + BALCONY_DEPTH * 0.52, BALCONY_FRONT - 0.10)
    for x in (-side_x, side_x):
        for z in side_posts:
            m.add("woodDark", *box((x, HUT_FLOOR + 0.52, z), (0.13, 1.04, 0.13)))
        m.add("woodDark", *box((x, HUT_FLOOR + 1.02, balcony_z),
                                (0.16, 0.14, BALCONY_DEPTH)))
        m.add("woodDark", *box((x, HUT_FLOOR + 0.46, balcony_z),
                                (0.12, 0.12, BALCONY_DEPTH)))

    # Front rail split around the stair opening, leaving a generous clear path.
    stair_left = DOOR_X - 0.91
    stair_right = DOOR_X + 0.91
    rail_spans = ((-HALF_W + 0.08, stair_left), (stair_right, HALF_W - 0.08))
    for x0, x1 in rail_spans:
        if x1 <= x0:
            continue
        center_x = (x0 + x1) * 0.5
        width = x1 - x0
        m.add("woodDark", *box((center_x, HUT_FLOOR + 1.02, BALCONY_FRONT - 0.06),
                                (width, 0.14, 0.14)))
        m.add("woodDark", *box((center_x, HUT_FLOOR + 0.46, BALCONY_FRONT - 0.06),
                                (width, 0.12, 0.12)))
        for x in (x0 + 0.05, center_x, x1 - 0.05):
            m.add("woodDark", *box((x, HUT_FLOOR + 0.52, BALCONY_FRONT - 0.06),
                                    (0.12, 1.04, 0.12)))

    # Real frame around the animated door (the shell has a matching opening).
    frame_z = FRONT + 0.10
    left = DOOR_X - DOOR_W * 0.5 - 0.09
    right = DOOR_X + DOOR_W * 0.5 + 0.09
    for x in (left, right):
        m.add("woodDark", *box((x, HUT_FLOOR + DOOR_H * 0.5, frame_z),
                                (0.18, DOOR_H + 0.12, 0.18)))
    m.add("woodDark", *box((DOOR_X, HUT_FLOOR + DOOR_H + 0.04, frame_z),
                            (DOOR_W + 0.40, 0.18, 0.18)))
    m.add("iron", *box((right - 0.02, HUT_FLOOR + 1.02, frame_z + 0.13),
                        (0.055, 0.28, 0.05)))

    # Warm bed, wool rug, chest and a usable-looking wardrobe inside.
    rug = box((-0.48, HUT_FLOOR + 0.035, -0.28), (2.05, 0.05, 2.55))
    m.add("linen", *rug)
    bed_x, bed_z = -1.23, -0.64
    m.add("woodDark", *box((bed_x, HUT_FLOOR + 0.22, bed_z), (1.30, 0.32, 2.08)))
    m.add("woodLog", *box((bed_x, HUT_FLOOR + 0.46, bed_z), (1.22, 0.22, 1.98)))
    m.add("linenLight", *box((bed_x, HUT_FLOOR + 0.60, bed_z), (1.18, 0.12, 1.94)))
    m.add("linen", *box((bed_x, HUT_FLOOR + 0.69, bed_z - 0.70), (1.04, 0.14, 0.38)))
    for x in (bed_x - 0.52, bed_x + 0.52):
        for z in (bed_z - 0.89, bed_z + 0.89):
            m.add("woodDark", *box((x, HUT_FLOOR + 0.34, z), (0.12, 0.66, 0.12)))

    wardrobe_x, wardrobe_z = 1.43, -0.98
    m.add("woodDark", *box((wardrobe_x, HUT_FLOOR + 0.94, wardrobe_z),
                            (0.92, 1.88, 0.68)))
    for side in (-1, 1):
        x = wardrobe_x + side * 0.22
        m.add("woodLog", *box((x, HUT_FLOOR + 0.94, wardrobe_z + 0.36),
                               (0.40, 1.72, 0.045)))
        m.add("iron", *sphere((x - side * 0.11, HUT_FLOOR + 0.94, wardrobe_z + 0.42),
                               0.045, 10, 7))

    # Small bedside stool and candle lantern to finish the interior silhouette.
    m.add("woodDark", *box((-0.12, HUT_FLOOR + 0.26, -1.15), (0.46, 0.38, 0.46)))
    m.add("glow", *sphere((-0.12, HUT_FLOOR + 0.66, -1.15), 0.11, 12, 8))

    return m


def _stair_mesh():
    m = Mesh()
    for i in range(STAIR_COUNT):
        top_y = (i + 1) * STAIR_RISE
        z = BALCONY_FRONT + (STAIR_COUNT - 1 - i) * STAIR_RUN
        m.add("woodDark", *box((DOOR_X, top_y - 0.07, z),
                                (STAIR_TREAD_WIDTH, 0.14, STAIR_TREAD_DEPTH)))
        # Pale narrow nosing makes every tread legible from the ground.
        m.add("woodLog", *box((DOOR_X, top_y + 0.008, z + STAIR_TREAD_DEPTH * 0.34),
                               (STAIR_TREAD_WIDTH - 0.08, 0.025, 0.055)))

    # Twin diagonal stringers support the open-riser, ladder-like staircase.
    total_z = (STAIR_COUNT - 1) * STAIR_RUN
    length = math.hypot(HUT_FLOOR, total_z)
    angle = math.degrees(math.atan2(-total_z, HUT_FLOOR))
    center_z = BALCONY_FRONT + total_z * 0.5
    for side in (-1, 1):
        x = DOOR_X + side * (STAIR_TREAD_WIDTH * 0.5 - 0.04)
        m.add("woodDark", *place(box((0, 0, 0), (0.14, length, 0.14)),
                                  rot=(angle, 0, 0),
                                  translation=(x, HUT_FLOOR * 0.5, center_z)))
        # Handrail above the steps, with regularly spaced balusters.
        hand_length = math.hypot(HUT_FLOOR, total_z)
        hand_angle = angle
        m.add("woodLog", *place(box((0, 0, 0), (0.14, hand_length, 0.14)),
                                 rot=(hand_angle, 0, 0),
                                 translation=(DOOR_X + side * 0.96,
                                              HUT_FLOOR * 0.5 + 0.78, center_z)))
        for i in range(0, STAIR_COUNT, 3):
            top_y = (i + 1) * STAIR_RISE
            z = BALCONY_FRONT + (STAIR_COUNT - 1 - i) * STAIR_RUN
            rail_y = top_y + 0.78
            height = max(0.38, rail_y - top_y)
            m.add("woodDark", *box((DOOR_X + side * 0.96,
                                     top_y + height * 0.5, z),
                                    (0.085, height, 0.085)))
    return m


def _stair_collision_mesh():
    m = Mesh()
    for i in range(STAIR_COUNT):
        top_y = (i + 1) * STAIR_RISE
        z = BALCONY_FRONT + (STAIR_COUNT - 1 - i) * STAIR_RUN
        m.add("collision", *box((DOOR_X, top_y - 0.07, z),
                                 (STAIR_TREAD_WIDTH, 0.14, STAIR_TREAD_DEPTH)))
    return m


def collision_meshes():
    """Collision boxes leave a real door opening and support every tread."""
    wall_y = HUT_FLOOR + HUT_H * 0.5
    wall_h = HUT_H
    wall_t = 0.38
    door_left = DOOR_X - DOOR_W * 0.5
    door_right = DOOR_X + DOOR_W * 0.5
    front_left_w = door_left + HALF_W
    front_right_w = HALF_W - door_right
    header_h = max(0.20, wall_h - DOOR_H)
    header_y = HUT_FLOOR + wall_h - header_h * 0.5

    result = [
        ("residenceFloorCol", box((0, HUT_FLOOR - 0.09, 0),
                                  (HUT_W + 0.06, 0.18, HUT_D + 0.06))),
        ("residenceBackWallCol", box((0, wall_y, -HALF_D),
                                     (HUT_W, wall_h, wall_t))),
        ("residenceLeftWallCol", box((-HALF_W, wall_y, 0),
                                     (wall_t, wall_h, HUT_D))),
        ("residenceRightWallCol", box((HALF_W, wall_y, 0),
                                      (wall_t, wall_h, HUT_D))),
        ("residenceFrontLeftWallCol", box(((-HALF_W + door_left) * 0.5, wall_y, HALF_D),
                                          (front_left_w, wall_h, wall_t))),
        ("residenceFrontRightWallCol", box(((door_right + HALF_W) * 0.5, wall_y, HALF_D),
                                           (front_right_w, wall_h, wall_t))),
        ("residenceDoorHeaderCol", box((DOOR_X, header_y, HALF_D),
                                       (DOOR_W, header_h, wall_t))),
        ("residenceRoofCol", box((0, HUT_FLOOR + HUT_H + ROOF_H * 0.5, 0),
                                 (HUT_W * 0.74, ROOF_H * 1.05, HUT_D + 0.60))),
        ("residenceLegCol", cylinder(0.48, 0.0, HUT_FLOOR, 12, caps=True)),
        ("residenceBalconyCol", box((0, HUT_FLOOR - 0.09,
                                     FRONT + BALCONY_DEPTH * 0.5),
                                    (HUT_W + 0.18, 0.18, BALCONY_DEPTH))),
    ]
    stair = _stair_collision_mesh()
    result.append(("residenceStairsCol", stair))
    return result


def build_scene():
    root = Node("TransformGroup", "babaJagaHouse")

    # The existing coop shell is used only as art; its working door, canopy and
    # visual-only rope ladder are replaced by the residence features below.
    root.add(Node("Shape", "hutMesh", baba.hut_mesh(
        include_door=False, include_porch=False, include_ladder=False,
        walkable_door=True)))
    root.add(Node("Shape", "legMesh", baba.leg_mesh()))
    root.add(Node("Shape", "residenceMesh", _architecture_mesh()))
    root.add(Node("Shape", "stairMesh", _stair_mesh()))

    # The animated leaf is a child of its hinge transform, so native FS25
    # AnimatedObject can rotate it without Lua.
    pivot_x = DOOR_X - DOOR_W * 0.5
    pivot = root.add(Node("TransformGroup", "doorPivot",
                          translation="%s %s %s" % (_fmt([pivot_x]),
                                                       _fmt([HUT_FLOOR]),
                                                       _fmt([FRONT + 0.11]))))
    pivot.add(Node("Shape", "doorLeafMesh", _door_leaf_mesh()))

    for name, geom in collision_meshes():
        if isinstance(geom, Mesh):
            mesh = geom
        else:
            mesh = Mesh()
            mesh.add("collision", *geom)
        root.add(Node("Shape", name, mesh, materials=["collision"], **{
            "static": "true", "compound": "true",
            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
            "castsShadows": "false", "receiveShadows": "false",
            "nonRenderable": "true",
        }))

    # Native player-only interaction volumes.
    root.add(trigger_node("doorTrigger", (2.0, 2.4, 1.8),
                          (DOOR_X, HUT_FLOOR + 1.1, FRONT + 0.82), mask=PLAYER))
    root.add(trigger_node("sleepTrigger", (1.55, 2.0, 1.55),
                          (-1.18, HUT_FLOOR + 0.85, -0.65), mask=PLAYER))
    root.add(trigger_node("wardrobeTrigger", (1.50, 2.1, 1.45),
                          (1.42, HUT_FLOOR + 0.95, -0.90), mask=PLAYER))

    # Placement, ground preparation and indoor-area helpers.
    root.add(baba.line_area("testArea1", (-4.0, 0.0, -4.2),
                             (4.0, 0.0, BALCONY_FRONT + (STAIR_COUNT - 1) * STAIR_RUN + 1.0)))
    root.add(baba.area("clearArea1", -4.0, 0.0, -4.2, 8.0,
                       BALCONY_FRONT + (STAIR_COUNT - 1) * STAIR_RUN + 5.2))
    root.add(baba.area("levelArea1", -3.6, 0.0, -3.6, 7.2,
                       BALCONY_FRONT + (STAIR_COUNT - 1) * STAIR_RUN + 4.8))
    root.add(baba.area("paintArea1", -3.0, 0.0, -3.0, 6.0, 6.0))
    root.add(baba.area("indoorArea1", -1.8, HUT_FLOOR + 0.05, -1.45, 3.6, 2.9))
    root.add(Node("TransformGroup", "spawnNode",
                  translation="0.52 %s 0.48" % _fmt([HUT_FLOOR + 0.08])))
    root.add(Node("TransformGroup", "sleepingCamera",
                  translation="-1.18 %s -0.68" % _fmt([HUT_FLOOR + 1.1])))
    return root


def write(path):
    return model.write_i3d(build_scene(), path, materials=MATERIALS,
                           asset_name="babaJagaHouse")


if __name__ == "__main__":
    repo = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
    out = os.path.join(repo, "build", "babaJagaHouse_inline.i3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stats, mappings = write(out)
    print("%d shapes, %d tris -> %s" % (stats["shapes"], stats["tris"], out))
