# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of the FS25_UFO4500 header (the 6 m cutter that pulls in the crop).

The header is a separate store item, because in Farming Simulator only a
`cutter` vehicle harvests and a cutter only works when it is attached to a
combine.  The visible part is a simple bar with a reel, an auger and two
divider cones; the interesting bits are the nodes the base game needs:

  * `headerAttacher`      - input attacher joint (jointType="cutter")
  * `heightLeft/Right`    - height nodes for the lift animation
  * `groundRef`           - ground reference node (0.5 m threshold)
  * `areaStart/Width/Height` - the work area, 6 m wide and 0.8 m deep
"""

import math

import model
from meshlib import Mesh, box, cylinder, place, sphere, torus
from model import Node, _fmt

WIDTH = 6.0             # working width
DEPTH = 0.80            # work area depth
GROUND_Y = -0.85        # the header hangs 1.0 m above the ground -> area at 0.15 m


def bar_mesh():
    m = Mesh()
    y = -0.12
    # main bar and the back wall
    m.add("hullPaint", *place(box((0, 0, 0), (WIDTH + 0.20, 0.48, 0.85)),
                              translation=(0, y, 0.62)))
    m.add("hullMetal", *place(box((0, 0, 0), (WIDTH + 0.20, 0.16, 0.22)),
                              translation=(0, y - 0.34, 0.30)))
    # the trough behind the cutter bar
    m.add("cockpit", *place(box((0, 0, 0), (WIDTH - 0.10, 0.10, 0.55)),
                            rot=(12, 0, 0), translation=(0, y + 0.02, 0.72)))
    # side walls
    for sx in (-1, 1):
        m.add("hullPaint", *place(box((0, 0, 0), (0.14, 0.72, 0.95)),
                                  translation=(sx * (WIDTH * 0.5 + 0.03), y + 0.10, 0.62)))
        # divider cone, pointing forward and down
        m.add("hullPaint", *place(cylinder(0.24, 0.0, 1.35, 12, caps=True, top_radius=0.02),
                                  rot=(74, 0, -78 * sx),
                                  translation=(sx * (WIDTH * 0.5 + 0.05), y - 0.10, 1.15)))
        # skid plates that ride on the ground
        m.add("hullMetal", *place(box((0, 0, 0), (0.70, 0.10, 0.30)),
                                  translation=(sx * 2.45, GROUND_Y + 0.28, 0.95)))
    # cross members
    for x in (-2.0, 0.0, 2.0):
        m.add("hullMetal", *place(box((0, 0, 0), (0.12, 0.10, 0.80)),
                                  translation=(x, y + 0.30, 0.60)))
    return m


def reel_mesh():
    """Reel with six bats; the node rotates around the X axis."""
    m = Mesh()
    length = WIDTH - 0.10
    m.add("hullMetal", *place(cylinder(0.05, -length * 0.5, length * 0.5, 10, caps=True),
                              rot=(0, 0, -90)))
    for sx in (-1, 1):
        m.add("hullMetal", *place(torus(0.30, 0.035, 0, 20, 6), rot=(0, 90, 0),
                                  translation=(sx * length * 0.5, 0, 0)))
    for i in range(6):
        rad = math.radians(360.0 * i / 6.0)
        y, z = 0.34 * math.cos(rad), 0.34 * math.sin(rad)
        # the bats are all parallel to the reel axis (X)
        m.add("hullMetal", *place(box((0, 0, 0), (length, 0.05, 0.16)),
                                  translation=(0, y, z)))
        # reel teeth at both ends
        for sx in (-1, 1):
            m.add("lensGreen", *place(sphere((0, 0, 0), 0.05, 8, 6),
                                      translation=(sx * length * 0.45, y, z)))
        # spokes
        m.add("hullMetal", *place(box((0, 0, 0), (0.06, 0.05, 0.34)),
                                  rot=(0, 0, 0), translation=(0, y * 0.5, z * 0.5)))
    return m


def auger_mesh():
    length = WIDTH - 0.30
    m = Mesh()
    m.add("hullMetal", *place(cylinder(0.10, -length * 0.5, length * 0.5, 12, caps=True),
                              rot=(0, 0, -90)))
    for i in range(9):
        x = -length * 0.5 + (i + 0.5) * length / 9.0
        m.add("hullMetal", *place(torus(0.17, 0.028, 0, 16, 6), rot=(0, 90, 0),
                                  translation=(x, 0, 0)))
    return m


def build_scene():
    root = Node("TransformGroup", "ufo4500Header")

    root.add(Node("Shape", "headerMesh", bar_mesh()))

    reel = root.add(Node("TransformGroup", "reelNode", translation="0 0.42 0.98"))
    reel.add(Node("Shape", "reelMesh", reel_mesh()))

    auger = root.add(Node("TransformGroup", "augerNode", translation="0 -0.02 0.58"))
    auger.add(Node("Shape", "augerMesh", auger_mesh()))

    # nodes the vehicle XML refers to
    root.add(Node("TransformGroup", "headerAttacher"))
    for name, x in (("heightLeft", -2.6), ("heightRight", 2.6), ("heightCenter", 0.0)):
        root.add(Node("TransformGroup", name,
                      translation="%s %s 1.00" % (_fmt([x]), _fmt([GROUND_Y]))))
    root.add(Node("TransformGroup", "groundRef",
                  translation="0 %s 0.80" % _fmt([GROUND_Y])))
    root.add(Node("TransformGroup", "areaStart",
                  translation="%s %s 0.45" % (_fmt([-WIDTH * 0.5]), _fmt([GROUND_Y]))))
    root.add(Node("TransformGroup", "areaWidth",
                  translation="%s %s 0.45" % (_fmt([WIDTH * 0.5]), _fmt([GROUND_Y]))))
    root.add(Node("TransformGroup", "areaHeight",
                  translation="%s %s %s" % (_fmt([-WIDTH * 0.5]), _fmt([GROUND_Y]),
                                            _fmt([0.45 + DEPTH]))))
    # collision so the header cannot be driven through a wall
    coll = Mesh()
    coll.add("collision", *box((0, 0, 0), (WIDTH + 0.20, 0.55, 1.10)))
    root.add(Node("Shape", "headerCollision", coll, materials=["collision"], **{
        "dynamic": "false", "compound": "true",
        "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    }))
    return root


def write(path):
    return model.write_i3d(build_scene(), path, asset_name="ufo4500header")


if __name__ == "__main__":
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    out = os.path.join(repo, "build", "ufo4500header_inline.i3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stats, mappings = write(out)
    print("%d shapes, %d tris -> %s" % (stats["shapes"], stats["tris"], out))
    sys.exit(0)
