# SPDX-License-Identifier: GPL-3.0-or-later
"""FS25_Autokino - a drive-in cinema for the farm.

A 13 x 7.3 m screen on a steel frame, a projector hut, a gravel lot with painted
bays and a neon sign.  The screen is its own shape (`screenMesh`) so the Lua
script can swap the frame texture - the film itself is a set of 12 hand drawn
cartoon frames per production (tools/venue/film.py).

Nodes the script uses:  screenMesh, screenLight, filmSoundNode,
                        testArea1/.., *Area1 nodes
"""

from meshlib import Mesh, box, cylinder, disc, place, sphere
from model import Node, write_i3d
from triggers import PLAYER, VEHICLE, trigger_mask, trigger_node
from venue import area, line_area, neon_sign, quad, slab

LOT_X = 22.0            # half width of the lot
LOT_Z = 19.0            # half depth of the lot
SCREEN_W = 13.0
SCREEN_H = 7.3
SCREEN_Y = 3.2          # bottom edge
SCREEN_Z = -15.0

MATERIALS = [
    {"name": "collision", "diffuse": None, "color": "0.6 0.1 0.6 1",
     "specular": "0.1 0.1 0.1"},
    {"name": "gravel", "diffuse": "gravel_diffuse.dds",
     "gloss": "gravel_specular.dds"},
    {"name": "asphalt", "diffuse": "asphalt_diffuse.dds",
     "gloss": "asphalt_specular.dds"},
    {"name": "concrete", "diffuse": "concrete_diffuse.dds",
     "gloss": "concrete_specular.dds"},
    {"name": "darkMetal", "diffuse": "darkMetal_diffuse.dds",
     "gloss": "darkMetal_specular.dds"},
    {"name": "plank", "diffuse": "plank_diffuse.dds",
     "gloss": "plank_specular.dds"},
    {"name": "screen", "diffuse": "screen_diffuse.dds", "gloss": None},
    {"name": "neonPink", "diffuse": "neonPink_diffuse.dds", "gloss": None},
    {"name": "neonCyan", "diffuse": "neonCyan_diffuse.dds", "gloss": None},
    {"name": "neonYellow", "diffuse": "neonYellow_diffuse.dds", "gloss": None},
]

LOOK = {
    "collision": None,
    "gravel": ((0.29, 0.27, 0.24), 0.10, 0.0, 1.0),
    "asphalt": ((0.13, 0.13, 0.14), 0.35, 0.0, 1.0),
    "concrete": ((0.60, 0.59, 0.57), 0.30, 0.05, 1.0),
    "darkMetal": ((0.10, 0.10, 0.11), 0.55, 0.0, 1.0),
    "plank": ((0.38, 0.26, 0.16), 0.22, 0.0, 1.0),
    "screen": ((0.94, 0.94, 0.93), 0.20, 0.55, 1.0),
    "neonPink": ((1.0, 0.30, 0.64), 0.3, 0.95, 1.0),
    "neonCyan": ((0.30, 0.94, 1.0), 0.3, 0.95, 1.0),
    "neonYellow": ((1.0, 0.88, 0.34), 0.3, 0.95, 1.0),
}


# --------------------------------------------------------------------------
def screen_mesh():
    """The picture itself - a single quad, material `screen`."""
    m = Mesh()
    z = SCREEN_Z
    quad([(-SCREEN_W / 2, SCREEN_Y, z), (SCREEN_W / 2, SCREEN_Y, z),
          (SCREEN_W / 2, SCREEN_Y + SCREEN_H, z),
          (-SCREEN_W / 2, SCREEN_Y + SCREEN_H, z)], "screen", m)
    return m


def frame_mesh():
    """Steel frame, posts, side masking and the walkway under the screen."""
    m = Mesh()
    z = SCREEN_Z
    w2, h = SCREEN_W / 2, SCREEN_H
    # black border around the picture
    for (cx, cy, sx, sy) in ((0, SCREEN_Y - 0.3, SCREEN_W + 1.4, 0.6),
                             (0, SCREEN_Y + h + 0.3, SCREEN_W + 1.4, 0.6),
                             (-w2 - 0.35, SCREEN_Y + h / 2, 0.7, h),
                             (w2 + 0.35, SCREEN_Y + h / 2, 0.7, h)):
        slab(m, "darkMetal", (cx, cy, z - 0.06), (sx, sy, 0.22))
    # back wall of the screen tower
    slab(m, "darkMetal", (0, SCREEN_Y + h / 2, z - 0.55), (SCREEN_W + 1.6, h + 1.4, 0.5))
    for sx in (-1, 1):
        for dz in (0.0, 1.4):
            slab(m, "darkMetal", (sx * (w2 + 0.2), (SCREEN_Y + h) / 2, z - 0.2 + dz),
                 (0.28, SCREEN_Y + h, 0.28))
    # horizontal rails behind the screen tower
    for y in (SCREEN_Y + 0.6, SCREEN_Y + h - 0.6):
        slab(m, "darkMetal", (0, y, z - 0.9), (SCREEN_W + 2.4, 0.18, 0.18))
    # catwalk in front of the screen
    slab(m, "darkMetal", (0, SCREEN_Y - 0.75, z + 0.9), (SCREEN_W + 1.6, 0.12, 1.6))
    for sx in range(-6, 7):
        slab(m, "darkMetal", (sx * 1.05, SCREEN_Y - 0.35, z + 1.65), (0.08, 0.9, 0.08))
    return m


def lot_mesh():
    """Gravel yard, asphalt lanes, painted bays with tyre stops."""
    m = Mesh()
    slab(m, "gravel", (0, -0.15, 0), (2 * LOT_X + 4, 0.3, 2 * LOT_Z + 4))
    # asphalt lane in front of the screen and the entry road
    slab(m, "asphalt", (0, 0.01, SCREEN_Z + 4.2), (2 * LOT_X - 2, 0.04, 5.0))
    slab(m, "asphalt", (LOT_X - 1.0, 0.01, 0), (6.0, 0.04, 2 * LOT_Z - 2))
    # parking bays: 4 rows of 6
    for row in range(4):
        z = -7.0 + row * 6.0
        for i in range(-3, 4):
            slab(m, "concrete", (i * 5.2, 0.02, z), (0.12, 0.03, 4.6))
        for i in range(-3, 3):
            slab(m, "concrete", (i * 5.2 + 2.6, 0.02, z + 2.45), (5.2, 0.03, 0.12))
            # tyre stop
            slab(m, "concrete", (i * 5.2 + 2.6, 0.10, z - 1.9), (2.6, 0.2, 0.3))
    return m


def booth_mesh():
    """Projector hut at the back of the lot with a beam cone."""
    m = Mesh()
    z = LOT_Z - 3.0
    slab(m, "plank", (0, 1.4, z), (4.0, 2.8, 3.0))
    slab(m, "darkMetal", (0, 2.95, z), (4.4, 0.3, 3.4))
    for sx in (-1, 1):
        slab(m, "darkMetal", (sx * 1.2, 1.5, z - 1.55), (1.0, 1.4, 0.06))
    slab(m, "neonCyan", (0, 2.35, z - 1.56), (3.4, 0.08, 0.06))
    # projector on a tripod in front of the hut
    m.add("darkMetal", *place(cylinder(0.06, 0.0, 1.1, 8, caps=True),
                              translation=(0, 0.0, z - 2.2)))
    slab(m, "darkMetal", (0, 1.25, z - 2.2), (0.75, 0.45, 0.9))
    m.add("darkMetal", *place(cylinder(0.16, 0.0, 0.28, 14, caps=True),
                              translation=(0, 1.25, z - 2.75), rot=(90, 0, 0)))
    m.add("neonYellow", *place(disc(0.12, 0.0, segments=14),
                               translation=(0, 1.25, z - 2.9), rot=(90, 0, 0)))
    return m


def detail_mesh():
    """Neon sign on the frame, spot masts and litter bins."""
    m = Mesh()
    # sign above the screen
    sign, width = neon_sign("neonPink", "AUTOKINO", pixel=0.16, gap=0.30,
                            z=SCREEN_Z + 0.16, y=SCREEN_Y + SCREEN_H + 1.25)
    # lamp masts along the lanes
    for (sx, sz) in ((-LOT_X + 1.5, -12.0), (LOT_X - 1.5, -12.0),
                     (-LOT_X + 1.5, 6.0), (LOT_X - 1.5, 6.0)):
        m.add("darkMetal", *place(cylinder(0.12, 0.0, 6.0, 10, caps=True),
                                  translation=(sx, 0.0, sz)))
        slab(m, "neonYellow", (sx, 6.1, sz), (0.7, 0.16, 0.7))
    for i in range(4):
        slab(m, "darkMetal", (-8.0 + i * 5.4, 0.35, 12.5), (0.5, 0.7, 0.5))
    return m, sign


def collision_nodes():
    out = []
    for (name, centre, size) in (
            ("colScreen", (0, (SCREEN_Y + SCREEN_H) * 0.5, SCREEN_Z - 0.4),
             (SCREEN_W + 1.6, SCREEN_Y + SCREEN_H, 1.0)),
            ("colBooth", (0, 1.4, LOT_Z - 3.0), (4.0, 2.8, 3.0)),
            ("colMast1", (-LOT_X + 1.5, 3.0, -12.0), (0.3, 6.0, 0.3)),
            ("colMast2", (LOT_X - 1.5, 3.0, -12.0), (0.3, 6.0, 0.3)),
            ("colMast3", (-LOT_X + 1.5, 3.0, 6.0), (0.3, 6.0, 0.3)),
            ("colMast4", (LOT_X - 1.5, 3.0, 6.0), (0.3, 6.0, 0.3)),
    ):
        m = Mesh()
        slab(m, "collision", centre, size)
        out.append(Node("Shape", name, m, materials=["collision"], **{
            "dynamic": "false", "compound": "true",
            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
            "castsShadows": "false", "receiveShadows": "false",
            "nonRenderable": "true"}))
    return out


def build_scene():
    root = Node("TransformGroup", "autokino")
    root.add(Node("Shape", "lotMesh", lot_mesh()))
    root.add(Node("Shape", "frameMesh", frame_mesh()))
    root.add(Node("Shape", "screenMesh", screen_mesh(), materials=["screen"]))
    root.add(Node("Shape", "boothMesh", booth_mesh()))
    detail, sign = detail_mesh()
    root.add(Node("Shape", "detailMesh", detail))
    root.add(sign)

    root.add(Node("Light", "screenLight", type="point", range="45",
                  diffuseColor="0.85 0.85 1.0 1", castShadowMap="false",
                  decayRate="2", translation="0 6.0 -8.0"))

    for node in collision_nodes():
        root.add(node)

    root.add(trigger_node("cinemaTrigger", (2 * LOT_X - 4, 6.0, 2 * LOT_Z - 6),
                          (0.0, 3.0, 2.0), mask=trigger_mask(PLAYER, VEHICLE)))
    root.add(Node("TransformGroup", "filmSoundNode", translation="0 3.0 -8.0"))

    root.add(line_area("testArea1", (-LOT_X, 0.0, LOT_Z), (LOT_X, 0.0, SCREEN_Z - 2.0)))
    for name in ("clearArea1", "levelArea1", "paintArea1", "foliageArea1"):
        root.add(area(name, -LOT_X - 2.0, 0.0, SCREEN_Z - 3.0,
                      2 * LOT_X + 4.0, LOT_Z - SCREEN_Z + 5.0))
    root.add(area("indoorArea1", -3.0, 0.05, LOT_Z - 4.4, 6.0, 3.0))
    return root


def write(out_path, asset_name="autokino"):
    return write_i3d(build_scene(), out_path, materials=MATERIALS, asset_name=asset_name)


if __name__ == "__main__":
    import sys
    stats, mappings = write(sys.argv[1] if len(sys.argv) > 1 else "/tmp/autokino_inline.i3d")
    print("%d shapes, %d verts, %d tris" % (stats["shapes"], stats["verts"], stats["tris"]))
