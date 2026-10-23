# SPDX-License-Identifier: GPL-3.0-or-later
"""FS25_Disco - a farm disco you can walk into and dance in.

Procedural scene: barn shell with a gable roof, neon "DISCO" lettering, a
checkerboard dance floor, DJ booth with speakers, bar, tables and a spinning
mirror ball.  The Lua script switches the playlist and blinks the light
groups, so the geometry only has to provide the named nodes:

  discoTrigger      box around the hall (player / vehicle)
  musicNode         where the music comes from
  mirrorBallPivot   rotating mirror ball
  lightPink/Cyan/Yellow   light groups that blink in turn
  neonPink/Cyan/Yellow    emissive strips (children of the groups)

Coordinates: floor at y = 0, the hall is 16 x 12 m, walls 4.6 m high.
"""

import math

from meshlib import Mesh, box, cylinder, disc, place, sphere

from venue import area, line_area, neon_sign, quad, slab
from model import Node, write_i3d
from triggers import PLAYER, VEHICLE, trigger_mask, trigger_node

HALF_X = 8.0
HALF_Z = 6.0
WALL_H = 4.6
WALL_T = 0.25
ROOF_H = 2.0
ROOF_OVER = 0.55
DOOR_W = 5.0
DOOR_H = 3.3

MATERIALS = [
    {"name": "collision", "diffuse": None, "color": "0.6 0.1 0.6 1",
     "specular": "0.1 0.1 0.1"},
    {"name": "concrete", "diffuse": "concrete_diffuse.dds",
     "gloss": "concrete_specular.dds"},
    {"name": "plank", "diffuse": "plank_diffuse.dds",
     "gloss": "plank_specular.dds"},
    {"name": "darkMetal", "diffuse": "darkMetal_diffuse.dds",
     "gloss": "darkMetal_specular.dds"},
    {"name": "speaker", "diffuse": "speaker_diffuse.dds",
     "gloss": "speaker_specular.dds"},
    {"name": "mirror", "diffuse": "mirror_diffuse.dds",
     "gloss": "mirror_specular.dds"},
    {"name": "danceFloor", "diffuse": "danceFloor_diffuse.dds",
     "gloss": "danceFloor_specular.dds"},
    {"name": "neonPink", "diffuse": "neonPink_diffuse.dds", "gloss": None},
    {"name": "neonCyan", "diffuse": "neonCyan_diffuse.dds", "gloss": None},
    {"name": "neonYellow", "diffuse": "neonYellow_diffuse.dds", "gloss": None},
    {"name": "neonGreen", "diffuse": "neonGreen_diffuse.dds", "gloss": None},
    {"name": "gravel", "diffuse": "gravel_diffuse.dds",
     "gloss": "gravel_specular.dds"},
]


# --------------------------------------------------------------------------
# small geometry helpers
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# the neon lettering on the front gable (a 5x7 pixel font)
# --------------------------------------------------------------------------
# --------------------------------------------------------------------------
# scene parts
# --------------------------------------------------------------------------
def shell_mesh():
    """Floor slab, walls, gables and roof of the barn."""
    m = Mesh()
    # outside apron
    slab(m, "gravel", (0, -0.14, 0), (2 * HALF_X + 6.0, 0.28, 2 * HALF_Z + 6.0))
    # hall floor
    slab(m, "concrete", (0, -0.06, 0), (2 * HALF_X + 0.5, 0.14, 2 * HALF_Z + 0.5))
    # back wall
    slab(m, "plank", (0, WALL_H * 0.5, -HALF_Z), (2 * HALF_X, WALL_H, WALL_T))
    # side walls
    for sx in (-1, 1):
        slab(m, "plank", (sx * HALF_X, WALL_H * 0.5, 0),
             (WALL_T, WALL_H, 2 * HALF_Z))
    # front wall with the door opening
    side_w = (2 * HALF_X - DOOR_W) * 0.5
    for sx in (-1, 1):
        slab(m, "plank",
             (sx * (DOOR_W * 0.5 + side_w * 0.5), WALL_H * 0.5, HALF_Z),
             (side_w, WALL_H, WALL_T))
    slab(m, "plank", (0, (WALL_H + DOOR_H) * 0.5, HALF_Z),
         (DOOR_W, WALL_H - DOOR_H, WALL_T))
    # door frame
    for sx in (-1, 1):
        slab(m, "darkMetal", (sx * DOOR_W * 0.5, DOOR_H * 0.5, HALF_Z + 0.16),
             (0.20, DOOR_H, 0.16))
    slab(m, "darkMetal", (0, DOOR_H, HALF_Z + 0.16), (DOOR_W + 0.4, 0.22, 0.16))

    # gable triangles front/back
    for sz in (-1, 1):
        z = sz * HALF_Z
        verts = [(-HALF_X, WALL_H, z), (HALF_X, WALL_H, z), (0.0, WALL_H + ROOF_H, z)]
        n = (0.0, 0.0, float(sz))
        m.add("plank", verts, [n] * 3, [(0, 0), (1, 0), (0.5, 1)],
              [(0, 1, 2)] if sz < 0 else [(0, 2, 1)])

    # roof: two slopes, ridge along Z (the gables face the yard)
    slope = math.sqrt((HALF_X + ROOF_OVER) ** 2 + ROOF_H ** 2)
    ang = math.degrees(math.atan2(ROOF_H, HALF_X + ROOF_OVER))
    for sx in (-1, 1):
        centre = (sx * (HALF_X + ROOF_OVER) * 0.5, WALL_H + ROOF_H * 0.5, 0.0)
        geo = box((0, 0, 0), (slope, 0.16, 2 * HALF_Z + 2 * ROOF_OVER))
        m.add("darkMetal", *place(geo, translation=centre,
                                  rot=(0, 0, -sx * ang)))
    # ridge cap
    slab(m, "darkMetal", (0, WALL_H + ROOF_H + 0.06, 0),
         (0.30, 0.14, 2 * HALF_Z + 2 * ROOF_OVER))
    # fascia boards hide the joint between wall and roof
    for sx in (-1, 1):
        slab(m, "plank", (sx * (HALF_X + 0.18), WALL_H + 0.06, 0),
             (0.16, 0.34, 2 * HALF_Z + 2 * ROOF_OVER))
    # canopy over the entrance, with posts
    slab(m, "darkMetal", (0, DOOR_H + 0.28, HALF_Z + 0.95),
         (DOOR_W + 0.9, 0.16, 1.5))
    for sx in (-1, 1):
        slab(m, "darkMetal",
             (sx * (DOOR_W * 0.5 + 0.30), DOOR_H * 0.5, HALF_Z + 1.55),
             (0.14, DOOR_H, 0.14))
    return m


def interior_mesh():
    """Dance floor, stage, DJ booth, bar, tables, speakers."""
    m = Mesh()

    # checkered dance floor, 9 x 9 m, sunk 3 cm above the concrete
    quad([(-4.5, 0.03, 4.5), (4.5, 0.03, 4.5), (4.5, 0.03, -4.5), (-4.5, 0.03, -4.5)],
         "danceFloor", m)
    # glowing rim around the floor
    for (cx, cz, sx, sz) in ((0, 4.55, 9.2, 0.12), (0, -4.55, 9.2, 0.12),
                             (4.55, 0, 0.12, 9.2), (-4.55, 0, 0.12, 9.2)):
        slab(m, "neonYellow", (cx, 0.05, cz), (sx, 0.06, sz))

    # dark wainscot band around the inside of the walls
    for sx in (-1, 1):
        slab(m, "darkMetal", (sx * (HALF_X - 0.16), 0.9, 0), (0.12, 1.8, 2 * HALF_Z - 0.6))
    slab(m, "darkMetal", (0, 0.9, -HALF_Z + 0.16), (2 * HALF_X - 0.6, 1.8, 0.12))

    # DJ booth at the back
    slab(m, "darkMetal", (0, 0.55, -4.6), (5.4, 1.10, 0.9))
    slab(m, "speaker", (0, 1.18, -4.6), (5.6, 0.16, 1.05))
    slab(m, "neonCyan", (0, 0.72, -4.12), (5.0, 0.08, 0.06))
    # mixing desk
    slab(m, "darkMetal", (0, 1.34, -4.75), (2.6, 0.16, 0.7))
    for i in range(6):
        slab(m, "neonGreen", (-0.9 + i * 0.36, 1.44, -4.62), (0.10, 0.06, 0.10))

    # speaker towers
    for (sx, sz) in ((-6.4, -4.2), (6.4, -4.2), (-6.6, 4.6), (6.6, 4.6)):
        slab(m, "speaker", (sx, 1.15, sz), (1.1, 2.3, 1.0))
        slab(m, "darkMetal", (sx, 2.32, sz), (1.2, 0.10, 1.1))
        for y in (0.75, 1.35, 1.95):
            c = cylinder(0.38, -0.02, 0.02, 20, caps=True)
            m.add("darkMetal", *place(c, translation=(sx, y, sz + 0.52),
                                      rot=(90, 0, 0)))
            c2 = cylinder(0.20, -0.02, 0.02, 16, caps=True)
            m.add("darkMetal", *place(c2, translation=(sx, y, sz + 0.56),
                                      rot=(90, 0, 0)))

    # bar on the right
    slab(m, "plank", (6.3, 0.55, 0.4), (0.9, 1.10, 5.6))
    slab(m, "darkMetal", (6.0, 1.12, 0.4), (1.5, 0.10, 5.8))
    slab(m, "neonPink", (5.62, 0.78, 0.4), (0.06, 0.08, 5.2))
    # bottles on the shelf
    for i in range(9):
        z = -2.1 + i * 0.62
        slab(m, "neonGreen", (7.4, 1.85, z), (0.16, 0.42, 0.16))
        slab(m, "darkMetal", (7.55, 1.6, z), (0.55, 0.06, 0.62))

    # tables with stools on the left
    for (tx, tz) in ((-5.6, 2.6), (-5.6, -1.4)):
        m.add("plank", *place(disc(0.85, 0.0, segments=24, up=True),
                              translation=(tx, 0.78, tz)))
        m.add("darkMetal", *place(cylinder(0.09, 0.0, 0.78, 12, caps=True),
                                  translation=(tx, 0.0, tz)))
        m.add("darkMetal", *place(disc(0.30, 0.0, segments=16), translation=(tx, 0.02, tz)))
        for k in range(3):
            a = math.radians(k * 120 + 30)
            sxp, szp = tx + math.cos(a) * 1.45, tz + math.sin(a) * 1.45
            m.add("darkMetal", *place(cylinder(0.06, 0.0, 0.52, 10, caps=True),
                                      translation=(sxp, 0.0, szp)))
            m.add("neonPink", *place(disc(0.26, 0.0, segments=16, up=True),
                                     translation=(sxp, 0.54, szp)))
    return m


def neon_mesh():
    """Neon tubes on the walls, split into three light groups."""
    groups = {}
    for key, mat in (("Pink", "neonPink"), ("Cyan", "neonCyan"),
                     ("Yellow", "neonYellow")):
        groups[key] = (mat, Mesh())

    # pink: around the DJ booth and the door
    m = groups["Pink"][1]
    slab(m, "neonPink", (0, 3.55, -HALF_Z + 0.3), (2 * HALF_X - 1.0, 0.10, 0.10))
    for sx in (-1, 1):
        slab(m, "neonPink", (sx * (DOOR_W * 0.5 + 0.35), 2.0, HALF_Z + 0.12),
             (0.10, 3.4, 0.10))

    # cyan: side walls, two rows
    m = groups["Cyan"][1]
    for sx in (-1, 1):
        for y in (2.6, 3.8):
            slab(m, "neonCyan", (sx * (HALF_X - 0.2), y, 0), (0.10, 0.10, 2 * HALF_Z - 1.2))

    # yellow: dance floor rim + roof edge inside
    m = groups["Yellow"][1]
    slab(m, "neonYellow", (0, 4.35, -HALF_Z + 0.22), (2 * HALF_X - 1.4, 0.10, 0.10))
    for sx in (-1, 1):
        slab(m, "neonYellow", (sx * (HALF_X - 0.22), 4.35, 0), (0.10, 0.10, 2 * HALF_Z - 1.4))

    # outside: a neon line under the eaves
    m = groups["Pink"][1]
    slab(m, "neonPink", (0, WALL_H - 0.16, HALF_Z + 0.20),
         (2 * HALF_X - 0.4, 0.09, 0.09))
    for sx in (-1, 1):
        slab(m, "neonPink", (sx * (HALF_X + 0.02), WALL_H - 0.16, 0),
             (0.09, 0.09, 2 * HALF_Z - 0.4))

    nodes = []
    for key, (mat, mesh) in groups.items():
        group = Node("TransformGroup", "light" + key)
        group.add(Node("Shape", "neon" + key, mesh, materials=[mat]))
        nodes.append(group)
    # two ceiling lamps per group so the blink also lights the room
    lamps = {
        "Pink": ((1.0, 0.30, 0.64), (-4.6, 3.9, 1.6)),
        "Cyan": ((0.35, 0.90, 1.0), (4.6, 3.9, 1.6)),
        "Yellow": ((1.0, 0.86, 0.40), (0.0, 3.4, -3.4)),
    }
    for node in nodes:
        key = node.name[len("light"):]
        colour, pos = lamps[key]
        node.add(Node("Light", "lamp" + key,
                      type="point", range="13",
                      diffuseColor="%g %g %g 1" % colour,
                      castShadowMap="false", decayRate="2"))
        node.children[-1].attrs["translation"] = "%g %g %g" % pos
    return nodes


def mirror_ball():
    pivot = Node("TransformGroup", "mirrorBallPivot", translation="0 3.35 0")
    m = Mesh()
    m.add("mirror", *sphere((0, 0, 0), 0.62, segments=28, rings=16))
    pivot.add(Node("Shape", "mirrorBall", m, materials=["mirror"]))
    rod = Mesh()
    rod.add("darkMetal", *place(cylinder(0.045, 0.0, 1.15, 8, caps=True),
                                translation=(0, 0.55, 0)))
    pivot.add(Node("Shape", "mirrorBallRod", rod, materials=["darkMetal"]))
    return pivot


def collision_nodes():
    out = []
    for (name, centre, size) in (
            ("colBack", (0, WALL_H * 0.5, -HALF_Z), (2 * HALF_X, WALL_H, 0.4)),
            ("colLeft", (-HALF_X, WALL_H * 0.5, 0), (0.4, WALL_H, 2 * HALF_Z)),
            ("colRight", (HALF_X, WALL_H * 0.5, 0), (0.4, WALL_H, 2 * HALF_Z)),
            ("colRoof", (0, WALL_H + ROOF_H * 0.5, 0), (2 * HALF_X, 0.35, 2 * HALF_Z)),
            ("colBar", (6.3, 0.6, 0.4), (1.0, 1.2, 5.6)),
            ("colStage", (0, 0.6, -4.6), (5.4, 1.2, 0.9)),
    ):
        m = Mesh()
        slab(m, "collision", centre, size)
        out.append(Node("Shape", name, m, materials=["collision"], **{
            "dynamic": "false", "compound": "true",
            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
            "castsShadows": "false", "receiveShadows": "false",
            "nonRenderable": "true",
        }))
    # front wall halves (door stays open)
    side_w = (2 * HALF_X - DOOR_W) * 0.5
    for sx in (-1, 1):
        m = Mesh()
        slab(m, "collision",
             (sx * (DOOR_W * 0.5 + side_w * 0.5), WALL_H * 0.5, HALF_Z),
             (side_w, WALL_H, 0.4))
        out.append(Node("Shape", "colFront" + ("L" if sx < 0 else "R"), m,
                        materials=["collision"], **{
                            "dynamic": "false", "compound": "true",
                            "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
                            "castsShadows": "false", "receiveShadows": "false",
                            "nonRenderable": "true",
                        }))
    return out


def build_scene():
    root = Node("TransformGroup", "disco")
    root.add(Node("Shape", "shellMesh", shell_mesh()))
    root.add(Node("Shape", "interiorMesh", interior_mesh()))
    for node in neon_mesh():
        root.add(node)
    root.add(mirror_ball())

    sign, width = neon_sign("neonPink", "DISCO", pixel=0.14, gap=0.28,
                            z=HALF_Z + 0.02, y=4.78)
    root.add(sign)

    for node in collision_nodes():
        root.add(node)

    root.add(trigger_node("discoTrigger", (2 * HALF_X - 1.2, 5.0, 2 * HALF_Z - 1.2),
                          (0.0, 2.5, 0.0), mask=trigger_mask(PLAYER, VEHICLE)))
    root.add(Node("TransformGroup", "musicNode", translation="0 2.4 0"))

    # --- areas the placeable XML needs -------------------------------------
    root.add(line_area("testArea1", (-HALF_X - 0.8, 0.0, HALF_Z + 0.8),
                       (HALF_X + 0.8, 0.0, -HALF_Z - 0.8)))
    root.add(area("clearArea1", -HALF_X - 2.0, 0.0, -HALF_Z - 2.0,
                  2 * HALF_X + 4.0, 2 * HALF_Z + 4.0))
    root.add(area("levelArea1", -HALF_X - 2.0, 0.0, -HALF_Z - 2.0,
                  2 * HALF_X + 4.0, 2 * HALF_Z + 4.0))
    root.add(area("paintArea1", -HALF_X - 2.0, 0.0, -HALF_Z - 2.0,
                  2 * HALF_X + 4.0, 2 * HALF_Z + 4.0))
    root.add(area("indoorArea1", -HALF_X + 0.1, 0.05, -HALF_Z + 0.1,
                  2 * HALF_X - 0.2, 2 * HALF_Z - 0.2))
    root.add(area("foliageArea1", -HALF_X - 2.0, 0.0, -HALF_Z - 2.0,
                  2 * HALF_X + 4.0, 2 * HALF_Z + 4.0))
    return root


def write(out_path, asset_name="disco"):
    root = build_scene()
    return write_i3d(root, out_path, materials=MATERIALS, asset_name=asset_name)


if __name__ == "__main__":
    import sys
    stats, mappings = write(sys.argv[1] if len(sys.argv) > 1 else "/tmp/disco_inline.i3d")
    print("%d shapes, %d verts, %d tris" % (stats["shapes"], stats["verts"], stats["tris"]))


# albedo / gloss / emissive / opacity for the software renderer (icons, docs)
LOOK = {
    "collision": None,
    "concrete": ((0.34, 0.33, 0.31), 0.25, 0.0, 1.0),
    "plank": ((0.38, 0.26, 0.16), 0.22, 0.0, 1.0),
    "darkMetal": ((0.10, 0.10, 0.11), 0.55, 0.0, 1.0),
    "speaker": ((0.11, 0.11, 0.13), 0.15, 0.0, 1.0),
    "mirror": ((0.62, 0.66, 0.72), 0.95, 0.15, 1.0),
    "danceFloor": ((0.80, 0.80, 0.84), 0.60, 0.10, 1.0),
    "neonPink": ((1.0, 0.30, 0.64), 0.3, 0.95, 1.0),
    "neonCyan": ((0.30, 0.94, 1.0), 0.3, 0.95, 1.0),
    "neonYellow": ((1.0, 0.88, 0.34), 0.3, 0.95, 1.0),
    "neonGreen": ((0.40, 1.0, 0.48), 0.3, 0.95, 1.0),
    "gravel": ((0.29, 0.27, 0.24), 0.10, 0.0, 1.0),
}
