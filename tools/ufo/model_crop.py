# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of FS25_CropHarvester - the retro-comic "UFO 01 CROP HARVESTER".

Reference: the UFO Multi-Harvester blueprint.  The design is the cartoon
saucer from the sheet: a compact metal disc dominated by one huge glass dome,
Captain Zorp squeezed in behind the levers, the lettering "CROP HARVESTER"
and "UFO 01" on the hull, a ring antenna on the dome, glowing nozzles and -
under the belly - the beam that does all the field work.

The geometry reuses the proven parts of the UFO 2000 (hull, legs, cockpit,
beam cone) and adds the harvester-specific bits: the wide dome, the pilot,
the decals and the five colour-coded beams of the blueprint.
"""

import math

import model as base
from meshlib import (Mesh, box, cylinder, disc, lathe, open_cone, place,
                     sphere, torus, TAU)
from model import Node, _fmt

# --- hull ------------------------------------------------------------------
DOME_R = 1.30                 # glass radius - the dome is the whole point
DOME_BASE = 1.06              # where the glass starts
DOME_TOP = 3.02               # top of the glass
HULL_R = base.HULL_R

# blueprint colours: harvest green, sow/fertilise blue, cultivate purple,
# crop circles yellow, transport red
BEAMS = (
    ("Damage", "beamYellow"),        # 1 crop circles / flatten
    ("Harvest", "beamGreen"),        # 2 harvest
    ("Cultivate", "beamPurple"),     # 3 cultivate
    ("Plow", "beamPurple"),          # 4 plow
    ("Sow", "beamBlue"),             # 5 sow
    ("Fertilize", "beamBlue"),       # 6 fertilise
    ("Load", "beamRed"),             # 7 suction
    ("Unload", "beamRed"),           # 8 pour
)

MATERIALS = [
    {"name": "collision", "diffuse": None, "gloss": None,
     "color": "0.6 0.1 0.6 1", "specular": "0.1 0.1 0.1"},
    {"name": "hullPaint", "diffuse": "hullPaint_diffuse.dds",
     "gloss": "hullPaint_specular.dds"},
    {"name": "hullMetal", "diffuse": "hullMetal_diffuse.dds",
     "gloss": "hullMetal_specular.dds"},
    {"name": "cockpit", "diffuse": "cockpit_diffuse.dds",
     "gloss": "cockpit_specular.dds"},
    {"name": "glass", "diffuse": "glass_diffuse.dds",
     "gloss": "glass_specular.dds", "alpha": True},
    {"name": "lensGreen", "diffuse": "lensGreen_diffuse.dds", "gloss": None},
    {"name": "lensRed", "diffuse": "lensRed_diffuse.dds", "gloss": None},
    {"name": "lensWhite", "diffuse": "lensWhite_diffuse.dds", "gloss": None},
    {"name": "alienSkin", "diffuse": "alienSkin_diffuse.dds",
     "gloss": "alienSkin_specular.dds"},
    {"name": "eyeBlack", "diffuse": "eyeBlack_diffuse.dds", "gloss": None},
    {"name": "suit", "diffuse": "suit_diffuse.dds", "gloss": "suit_specular.dds"},
    {"name": "goggle", "diffuse": "goggle_diffuse.dds", "gloss": None},
    {"name": "helmet", "diffuse": "helmet_diffuse.dds", "gloss": "helmet_specular.dds"},
    {"name": "helmetTrim", "diffuse": "helmetTrim_diffuse.dds", "gloss": None},
    {"name": "decal", "diffuse": "decal_diffuse.dds", "gloss": None},
    {"name": "beam", "diffuse": "beam_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamGreen", "diffuse": "beamGreen_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamBlue", "diffuse": "beamBlue_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamPurple", "diffuse": "beamViolet_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamYellow", "diffuse": "beamLime_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamRed", "diffuse": "beamRed_diffuse.dds", "gloss": None, "alpha": True},
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def quad(mesh, mat, corners, uv=None):
    """A flat quad (corners counter clockwise seen from the front).

    `uv` may be one (u0, v0, u1, v1) rectangle or four (u, v) pairs.

    The corners run bottom-left, bottom-right, top-right, top-left, while the
    FS25 (DirectX) convention puts v = 0 on the TOP row of the texture - so a
    rectangle hands out v0 to the top corners and v1 to the bottom ones.
    """
    verts = list(corners)
    if uv is None:
        uvs = [(0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]
    elif len(uv) == 4 and not isinstance(uv[0], (tuple, list)):
        u0, v0, u1, v1 = uv
        uvs = [(u0, v1), (u1, v1), (u1, v0), (u0, v0)]
    else:
        uvs = list(uv)
    a, b, c = verts[0], verts[1], verts[2]
    ux, uy, uz = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    vx, vy, vz = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    nx, ny, nz = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    n = (nx / ln, ny / ln, nz / ln)
    mesh.add(mat, verts, [n] * 4, uvs, [(0, 1, 2), (0, 2, 3)])


def decal(mesh, mat, centre, width, height, yaw, uv=None):
    """A flat lettering panel sitting on the hull, facing outwards at `yaw`."""
    cx, cy, cz = centre
    hw, hh = width * 0.5, height * 0.5
    a = math.radians(yaw)
    dx, dz = math.sin(a), math.cos(a)
    # right vector of the panel
    rx, rz = math.cos(a), -math.sin(a)
    pts = [
        (cx - rx * hw, cy - hh, cz - rz * hw),
        (cx + rx * hw, cy - hh, cz + rz * hw),
        (cx + rx * hw, cy + hh, cz + rz * hw),
        (cx - rx * hw, cy + hh, cz - rz * hw),
    ]
    _ = (dx, dz)
    quad(mesh, mat, pts, uv)


def fin(mesh, mat, yaw, r0, length, height, thick=0.06):
    """A small triangular tail fin, standing on the edge of the hull."""
    a = math.radians(yaw)
    nx, nz = math.sin(a), math.cos(a)          # outwards
    tx, tz = math.cos(a), -math.sin(a)         # sideways
    y0 = 0.80
    prof = ((0.0, -0.18), (length * 0.70, height), (length, -0.10))
    verts, tris = [], []
    for side in (-1, 1):
        for (dr, dy) in prof:
            verts.append(((r0 + dr) * nx + side * thick * tx, y0 + dy,
                          (r0 + dr) * nz + side * thick * tz))
    # the two flat sides
    tris += [(0, 2, 1), (3, 4, 5)]
    # the three edges
    for i in range(3):
        j = (i + 1) % 3
        tris += [(i, j, j + 3), (i, j + 3, i + 3)]
    normal = (tx, 0.0, tz)
    mesh.add(mat, verts, [normal] * 6, [(0.0, 0.0)] * 6, tris)


# --------------------------------------------------------------------------
# hull + dome
# --------------------------------------------------------------------------
def hull_mesh():
    """The saucer: base UFO 2000 hull, but without the narrow collar - the
    harvester carries a wide dome instead."""
    m = base.hull_mesh()
    # a wide, riveted base ring for the big bubble
    m.add("hullMetal", *lathe([
        (DOME_R - 0.02, 1.05), (DOME_R + 0.20, 1.02), (DOME_R + 0.34, 0.96),
        (DOME_R + 0.40, 0.92),
    ], 56, close_ends=True))
    for i in range(20):
        a = TAU * i / 20
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.028, 8, 6),
                                  translation=((DOME_R + 0.22) * math.cos(a), 1.04,
                                               (DOME_R + 0.22) * math.sin(a))))
    # exhaust nozzles at the rear, like the sheet (glowing green)
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.20, -0.30, 0.02, 16, caps=True),
                                  rot=(90, 0, 0),
                                  translation=(side * 0.85, 0.30, -2.15)))
        m.add("lensGreen", *place(disc(0.17, 0.0, 16, up=False),
                                  rot=(90, 0, 0),
                                  translation=(side * 0.85, 0.30, -2.46)))
    # "CROP HARVESTER" on both shoulders, "UFO 01" on the nose
    for yaw in (62, -62):
        a = math.radians(yaw)
        decal(m, "decal", (2.505 * math.sin(a), 0.64, 2.505 * math.cos(a)),
              1.00, 0.32, yaw, uv=(0.0, 0.0, 0.72, 1.0))
    decal(m, "decal", (0.0, 0.64, 2.505), 0.72, 0.28, 0.0,
          uv=(0.72, 0.0, 1.0, 1.0))
    # the two tail fins from the sheet: a triangular fin on each rear quarter
    for yaw in (146.0, -146.0):
        fin(m, "hullPaint", yaw, 2.16, 0.95, 0.78, 0.08)
    return m


def dome_mesh():
    """One big glass bubble, no cage, a ring antenna on top."""
    m = Mesh()
    # the glass: nearly a hemisphere, slightly flattened at the top
    m.add("glass", *lathe([
        (DOME_R, DOME_BASE),
        (DOME_R, DOME_BASE + 0.55),
        (DOME_R - 0.02, 1.92),
        (DOME_R - 0.06, 2.28),
        (DOME_R - 0.16, 2.60),
        (DOME_R - 0.34, 2.84),
        (DOME_R - 0.58, DOME_TOP),
        (DOME_R - 0.86, DOME_TOP + 0.05),
        (DOME_R - 1.14, DOME_TOP + 0.06),
        (0.04, DOME_TOP + 0.06),
    ], 56, close_ends=True))
    # a collar where the glass meets the hull - low enough not to cut the
    # pilot in half when the dome is seen from the front
    m.add("hullMetal", *place(torus(DOME_R + 0.006, 0.014, 0, 56, 6),
                              translation=(0, 1.12, 0)))
    # finial, ring antenna and its glowing tip
    m.add("hullMetal", *place(cylinder(0.05, 0.0, 0.26, 12, caps=True,
                                      top_radius=0.035),
                              translation=(0, DOME_TOP + 0.05, 0)))
    m.add("hullMetal", *place(torus(0.26, 0.024, 0, 32, 8),
                              translation=(0, DOME_TOP + 0.30, 0)))
    m.add("hullMetal", *place(cylinder(0.022, 0.0, 0.10, 8, caps=True),
                              translation=(0, DOME_TOP + 0.26, 0)))
    m.add("lensWhite", *place(sphere((0, 0, 0), 0.075, 16, 10),
                              translation=(0, DOME_TOP + 0.34, 0)))
    return m


# --------------------------------------------------------------------------
# Captain Zorp, the pilot
# --------------------------------------------------------------------------
def pilot_mesh():
    """Captain Zorp sitting in the dome: green skin, goggles pushed up,
    two communication antennae, flight suit V2 with a chest patch."""
    m = Mesh()
    # --- torso in the flight suit -----------------------------------------
    m.add("suit", *place(lathe([(0.16, 0.00), (0.21, 0.14), (0.24, 0.30),
                                (0.21, 0.44), (0.15, 0.52)], 20, close_ends=True),
                         translation=(0, 0.02, 0)))
    # chest patch and belt
    m.add("goggle", *place(box((0, 0, 0), (0.13, 0.10, 0.02)),
                           translation=(0.10, 0.34, 0.20)))
    m.add("hullMetal", *place(torus(0.215, 0.018, 0, 22, 6),
                              translation=(0, 0.16, 0)))
    # --- head -------------------------------------------------------------
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.21, 24, 16, scale=(1.0, 1.06, 0.98)),
                              translation=(0, 0.72, 0.01)))
    # big glossy eyes
    for sx in (-1, 1):
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.075, 18, 12, scale=(1.0, 1.25, 0.62)),
                                 translation=(0.082 * sx, 0.735, 0.155)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.020, 10, 8),
                                  translation=(0.098 * sx, 0.775, 0.198)))
    # grin
    m.add("eyeBlack", *place(sphere((0, 0, 0), 0.040, 14, 10, scale=(1.5, 0.34, 0.45)),
                             translation=(0, 0.640, 0.180)))
    # --- goggles pushed up on the forehead --------------------------------
    # a rubber strap around the skull, sitting just above the eyes ...
    m.add("goggle", *place(torus(0.152, 0.015, 0, 28, 6),
                           rot=(-34, 0, 0), translation=(0, 0.905, 0.086)))
    # ... and the two lenses tilted up onto the brow so they read from the
    # front instead of vanishing inside the head
    for sx in (-1, 1):
        m.add("goggle", *place(cylinder(0.050, 0.0, 0.032, 16, caps=True),
                               rot=(56, 0, 0),
                               translation=(0.066 * sx, 0.902, 0.152)))
        m.add("lensWhite", *place(disc(0.037, 0.0, 16, up=False),
                                  rot=(56, 0, 0),
                                  translation=(0.066 * sx, 0.910, 0.167)))
    m.add("hullMetal", *place(box((0, 0, 0), (0.057, 0.013, 0.013)),
                              rot=(34, 0, 0),
                              translation=(0, 0.910, 0.150)))
    # --- flight helmet: a white bowl with an orange trim, worn open so the
    # goggles rest on the forehead (see the Zorp concept sheet) -------------
    # the helmet sits ON the head: a bowl from the temples up, open at the
    # face so the eyes and the grin stay visible
    m.add("helmet", *place(lathe([
        (0.176, 0.852), (0.186, 0.878), (0.190, 0.906), (0.182, 0.934),
        (0.162, 0.956), (0.126, 0.972), (0.068, 0.984), (0.0, 0.988),
    ], 30, close_ends=True), translation=(0, 0, 0.006)))
    m.add("helmetTrim", *place(torus(0.180, 0.017, 0, 28, 6),
                               translation=(0, 0.854, 0.006)))
    # the ear cups
    for sx in (-1, 1):
        m.add("helmetTrim", *place(cylinder(0.058, 0.0, 0.05, 16, caps=True),
                                   rot=(0, 0, 90 * sx),
                                   translation=(0.181 * sx, 0.900, 0.010)))
    # a little antenna stub and the chin strap ends
    m.add("hullMetal", *place(cylinder(0.012, 0.0, 0.10, 8, caps=True),
                              rot=(0, 0, 14),
                              translation=(0.155, 0.968, -0.045)))

    # --- communication antennae ------------------------------------------
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.011, 0.0, 0.16, 8, caps=True),
                                  rot=(0, 0, -20 * sx),
                                  translation=(0.085 * sx, 0.88, -0.01)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.030, 12, 8),
                                  translation=(0.120 * sx, 1.012, -0.010)))
    # --- arms on the levers, gloves ---------------------------------------
    for sx in (-1, 1):
        m.add("suit", *place(sphere((0, 0, 0), 0.060, 14, 10, scale=(1.0, 2.0, 1.0)),
                             rot=(52, 0, 18 * sx),
                             translation=(0.20 * sx, 0.31, 0.20)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.052, 12, 8),
                                  translation=(0.20 * sx, 0.20, 0.33)))
    # --- seat behind him --------------------------------------------------
    m.add("cockpit", *place(box((0, 0, 0), (0.46, 0.62, 0.10)),
                            rot=(8, 0, 0), translation=(0, 0.42, -0.16)))
    return m


# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------
def collision_meshes():
    return [
        ("ufo_main_component1", cylinder(2.10, 0.0, 0.80, 16, caps=True)),
        ("collisionDome", cylinder(DOME_R + 0.05, 0.80, DOME_TOP + 0.10, 16, caps=True)),
    ]


def build_scene():
    main_mesh = Mesh()
    main_mesh.add("collision", *collision_meshes()[0][1])
    body = Node("Shape", "crop_main_component1", mesh=main_mesh, materials=["collision"], **{
        "dynamic": "true", "compound": "true", "collisionFilterGroup": "0x10004",
        "collisionFilterMask": "0xfe3ffb83", "clipDistance": "300",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    })

    visual = body.add(Node("TransformGroup", "visual"))
    visual.add(Node("Shape", "hullMesh", hull_mesh()))
    visual.add(Node("Shape", "domeGlass", dome_mesh(), materials=["glass"],
                    castsShadows="false", receiveShadows="true"))
    base.leg_nodes(visual)

    # --- cabin -------------------------------------------------------------
    cabin = visual.add(Node("TransformGroup", "cabin"))
    cabin.add(Node("Shape", "consoleMesh",
                    base.cockpit_console_mesh(hoop_y=2.38, hoop=0.74)))
    cabin.add(Node("Shape", "cockpitDetailMesh", base.cockpit_detail_mesh()))

    board, pointer, lever, slider, needle = base.cockpit_ui_meshes()
    pattern_board = cabin.add(Node("TransformGroup", "patternBoard",
                                   translation="-0.62 1.34 0.26", rotation="0 62 0"))
    pattern_board.add(Node("Shape", "patternBoardMesh", board))
    pattern_pointer = pattern_board.add(Node("TransformGroup", "patternPointer",
                                             translation="-0.15 0.045 0.030"))
    pattern_pointer.add(Node("Shape", "patternPointerMesh", pointer,
                             materials=["lensGreen"]))

    mode_panel = cabin.add(Node("TransformGroup", "modeLever",
                                translation="0.62 1.32 0.22", rotation="0 -58 0"))
    mode_panel.add(Node("Shape", "modeLeverMesh", lever))

    focus_panel = cabin.add(Node("TransformGroup", "focusSlider",
                                 translation="0.34 1.24 0.56", rotation="0 -14 -18"))
    focus_panel.add(Node("Shape", "focusSliderMesh", slider))

    mode_needle = cabin.add(Node("TransformGroup", "modeNeedle",
                                 translation="0 1.298 0.48"))
    mode_needle.add(Node("Shape", "modeNeedleMesh", needle))

    # Captain Zorp: hidden as soon as a player takes the seat
    pilot = cabin.add(Node("TransformGroup", "pilotNode", translation="0 1.22 0.30",
                           rotation="0 0 0"))
    pilot.add(Node("Shape", "pilotMesh", pilot_mesh()))

    visual.add(Node("TransformGroup", "driverSeatNode", translation="0 1.24 0.02"))

    beacon = visual.add(Node("TransformGroup", "beaconNode", translation="0 3.10 0"))
    beacon.add(Node("Shape", "beaconMesh", base.antenna_beacon_mesh(),
                    materials=["lensRed"]))

    for mode_id, material in BEAMS:
        beam = visual.add(Node("TransformGroup", "beamNode" + mode_id,
                               translation="0 0.19 0", visibility="false"))
        beam.add(Node("Shape", "beamMesh" + mode_id, base.beam_mesh(),
                      materials=[material], castsShadows="false",
                      receiveShadows="false", nonRenderable="false"))

    ring = visual.add(Node("TransformGroup", "groundRing", translation="0 0.05 0",
                           visibility="false", scale="1 1 1"))
    ring.add(Node("Shape", "groundRingMesh", base.circle_ring_mesh(),
                  materials=["lensGreen"], castsShadows="false",
                  receiveShadows="false"))

    collisions = body.add(Node("TransformGroup", "collisions"))
    for name, geom in collision_meshes()[1:]:
        m = Mesh()
        m.add("collision", *geom)
        collisions.add(Node("Shape", name, m, materials=["collision"], **{
            "compoundChild": "true", "collisionFilterGroup": "0x10004",
            "collisionFilterMask": "0xfe3ffb83", "density": "0.001",
            "castsShadows": "false", "receiveShadows": "false",
            "nonRenderable": "true",
        }))

    lights = body.add(Node("TransformGroup", "lights"))
    for name, tx in (("headLightLeft", "0.62 0.66 1.95"), ("headLightRight", "-0.62 0.66 1.95")):
        lights.add(Node("Light", name, translation=tx, rotation="-8 180 0", type="spot",
                        color="0.85 1.0 0.92", emitDiffuse="true", emitSpecular="true",
                        castShadowMap="false", range="45", coneAngle="72", dropOff="3"))
    lights.add(Node("Light", "workLight", translation="0 0.30 0", rotation="-90 0 0",
                    type="spot", color="0.65 1.0 0.85", emitDiffuse="true",
                    emitSpecular="true", castShadowMap="false", range="60",
                    coneAngle="88", dropOff="2"))
    lights.add(Node("Light", "beamLight", translation="0 0.22 0", rotation="-90 0 0",
                    type="spot", color="0.55 1.0 0.95", emitDiffuse="true",
                    emitSpecular="true", castShadowMap="false", range="42",
                    coneAngle="52", dropOff="1.5"))
    lights.add(Node("Light", "beaconLight", translation="0 3.10 0", type="point",
                    color="1 0.18 0.12", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="26"))
    lights.add(Node("Light", "tailLight", translation="0 0.72 -2.20", type="point",
                    color="1 0.25 0.15", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="8"))

    fill = Mesh()
    fill.add("collision", *cylinder(0.16, -0.05, 0.05, 10, caps=True))
    body.add(Node("Shape", "exactFillRootNode", mesh=fill, materials=["collision"], **{
        "kinematic": "true", "compound": "true", "collisionFilterGroup": "0x40000000",
        "collisionFilterMask": "0x20000000", "castsShadows": "false",
        "receiveShadows": "false", "nonRenderable": "true",
    }))

    body.add(Node("TransformGroup", "enterReferenceNode", translation="0 1.05 2.45"))
    body.add(Node("TransformGroup", "exitPoint", translation="2.7 0.05 0.0"))
    body.add(Node("TransformGroup", "soundMotor", translation="0 1.0 0.0"))

    cam_target = body.add(Node("TransformGroup", "outdoorCameraTarget",
                               translation="0 1.35 0"))
    cam_target.add(Node("Camera", "outdoorCamera", translation="0 0 -9",
                        rotation="0 180 0", fov="45", nearClip="0.05", farClip="5000"))
    inside_target = body.add(Node("TransformGroup", "indoorCameraTarget",
                                  translation="0 1.72 0.02"))
    inside_target.add(Node("Camera", "indoorCamera", rotation="-8 180 0", fov="74",
                           nearClip="0.03", farClip="5000"))
    return body


def write(out_path, asset_name="cropharvester"):
    return base.write_i3d(build_scene(), out_path, materials=MATERIALS,
                          asset_name=asset_name)


if __name__ == "__main__":
    import sys
    stats, mappings = write(sys.argv[1] if len(sys.argv) > 1 else "/tmp/crop.i3d")
    print(stats)
    print(mappings)
