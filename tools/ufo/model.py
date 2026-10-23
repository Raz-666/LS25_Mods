# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural model of the FS25 UFO 2000.

Builds the whole `<Scene>` of ``ufo.i3d`` (body, glass dome, alien pilot, rim
lights, landing gear, tractor beam) plus the collision compound and the nodes
the vehicle XML refers to (cameras, sound, enter/exit points, animation pivots).

The scene is written with inline `<IndexedTriangleSet>` geometry which
``tools/i3d/binarize_i3d.py`` turns into the FS25 ``.i3d.shapes`` file.
"""

import math

from meshlib import (Mesh, box, cylinder, disc, lathe, open_cone, place,
                     sphere, torus, TAU)

MATERIALS = [
    # name, textures (diffuse, gloss/specular), flags
    {"name": "collision", "diffuse": None, "gloss": None, "color": "0.6 0.1 0.6 1", "specular": "0.1 0.1 0.1"},
    {"name": "hullPaint", "diffuse": "hullPaint_diffuse.dds", "gloss": "hullPaint_specular.dds"},
    {"name": "hullMetal", "diffuse": "hullMetal_diffuse.dds", "gloss": "hullMetal_specular.dds"},
    {"name": "cockpit", "diffuse": "cockpit_diffuse.dds", "gloss": "cockpit_specular.dds"},
    {"name": "glass", "diffuse": "glass_diffuse.dds", "gloss": "glass_specular.dds", "alpha": True},
    {"name": "lensGreen", "diffuse": "lensGreen_diffuse.dds", "gloss": None},
    {"name": "lensRed", "diffuse": "lensRed_diffuse.dds", "gloss": None},
    {"name": "lensWhite", "diffuse": "lensWhite_diffuse.dds", "gloss": None},
    {"name": "alienSkin", "diffuse": "alienSkin_diffuse.dds", "gloss": "alienSkin_specular.dds"},
    {"name": "eyeBlack", "diffuse": "eyeBlack_diffuse.dds", "gloss": None},
    {"name": "beam", "diffuse": "beam_diffuse.dds", "gloss": None, "alpha": True},
]
MAT_INDEX = {m["name"]: i + 1 for i, m in enumerate(MATERIALS)}

HULL_R = 2.45            # outer radius of the saucer
DOME_R = 0.92            # tall, narrow bell jar - the Simpsons look
RIM_Y = 0.86
HULL_Y = 0.26            # belly centre height
DOME_BASE = 1.06         # where the glass starts
DOME_TOP = 2.92          # top of the glass


LEG_SPLAY = "16"          # degrees the legs are splayed out at rest


def _fmt(values):
    out = []
    for v in values:
        s = ("%.6g" % v)
        out.append("0" if s == "-0" else s)
    return " ".join(out)


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def hull_mesh():
    """The flying disc: flat, wide, comic-book thick rim, rivets, panel lines."""
    m = Mesh()

    # --- belly: dark metal, slightly stepped like a moulded plastic toy ----
    m.add("hullMetal", *lathe([
        (0.04, HULL_Y), (0.55, 0.20), (1.10, 0.15), (1.60, 0.17),
        (2.00, 0.26), (2.24, 0.40), (2.36, 0.52),
    ], 60, close_ends=False))
    # --- thick, rounded rim (the "bumper" of the saucer) -------------------
    m.add("hullPaint", *lathe([
        (2.36, 0.52), (2.44, 0.60), (2.47, 0.72), (2.42, 0.84), (2.30, 0.92),
    ], 60, close_ends=False))
    # --- upper shell: flat on top, so the dome sits on real ground --------
    m.add("hullPaint", *lathe([
        (2.30, 0.92), (2.05, 0.99), (1.62, 1.04), (1.20, 1.06), (DOME_R + 0.10, 1.07),
    ], 60, close_ends=False))
    m.add("hullPaint", *disc(DOME_R + 0.10, 1.07, 40, up=True))

    # --- accent rings and panel lines -------------------------------------
    m.add("hullMetal", *torus(2.43, 0.055, 0.72, 60, 10))
    m.add("hullMetal", *torus(1.70, 0.022, 1.035, 52, 6))
    m.add("hullMetal", *torus(1.15, 0.018, 1.06, 44, 6))
    m.add("hullMetal", *torus(0.58, 0.016, 0.215, 40, 6))
    # rivets all around the rim
    for i in range(28):
        a = TAU * i / 28
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.030, 8, 6),
                                  translation=(2.40 * math.cos(a), 0.60, 2.40 * math.sin(a))))
    for i in range(20):
        a = TAU * i / 20 + 0.08
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.026, 8, 6),
                                  translation=(1.86 * math.cos(a), 1.02, 1.86 * math.sin(a))))

    # --- rim light pods: 12 around the saucer ------------------------------
    for i in range(12):
        a = TAU * i / 12
        m.add("hullMetal", *place(cylinder(0.10, 0.0, 0.10, 12, caps=True),
                                  rot=(90, 0, 0),
                                  translation=(2.30 * math.cos(a), 0.72, 2.30 * math.sin(a))))
        geom = sphere((0, 0, 0), 0.085, 14, 8, scale=(1.0, 0.9, 0.55))
        m.add("lensGreen", *place(geom, rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(2.40 * math.cos(a), 0.72, 2.40 * math.sin(a))))

    # --- four landing skids under the rim (the legs are separate) ---------
    for i in range(4):
        a = TAU * i / 4 + math.pi / 4
        m.add("hullMetal", *place(box((0, 0, 0), (0.62, 0.16, 0.26)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(1.55 * math.cos(a), 0.13, 1.55 * math.sin(a))))

    # --- front head lamps -------------------------------------------------
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.10, 0.0, 0.12, 12, caps=True),
                                  rot=(90, 0, 0),
                                  translation=(side * 0.55, 0.62, 2.20)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.095, 14, 8, scale=(1.0, 1.0, 0.7)),
                                  translation=(side * 0.55, 0.62, 2.30)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.055, 12, 8, scale=(1.0, 1.0, 0.6)),
                                translation=(side * 1.45, 0.55, -1.85)))

    # --- tractor beam emitter under the belly -----------------------------
    m.add("hullMetal", *place(torus(0.52, 0.06, 0, 40, 8), translation=(0, 0.20, 0)))
    m.add("hullMetal", *place(cylinder(0.50, 0.14, 0.22, 32, caps=True)))
    m.add("lensGreen", *place(disc(0.46, 0.145, 32, up=False)))

    # --- two antennae on the rear rim -------------------------------------
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.014, 0.0, 0.55, 8, caps=True),
                                  rot=(-18, 0, side * 12),
                                  translation=(side * 1.55, 1.02, -1.35)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.05, 10, 8),
                                translation=(side * 1.68, 1.53, -1.46)))
    return m


def antenna_beacon_mesh():
    m = Mesh()
    m.add("hullMetal", *cylinder(0.026, -0.30, 0.0, 10, caps=True))
    m.add("lensRed", *sphere((0, 0, 0), 0.085, 16, 10, scale=(1, 1.05, 1)))
    return m


def dome_mesh():
    """The tall narrow bell jar - the signature Simpsons shape.

    Narrow enough to read as "eng und schmal", tall enough that the player
    character inside is visible from every angle.
    """
    m = Mesh()

    # heavy metal collar the glass sits in
    m.add("hullMetal", *lathe([
        (DOME_R + 0.22, 1.03), (DOME_R + 0.22, 1.14), (DOME_R + 0.06, 1.20),
        (DOME_R, 1.20),
    ], 44, close_ends=True))
    for i in range(16):
        a = TAU * i / 16
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.030, 8, 6),
                                  translation=((DOME_R + 0.16) * math.cos(a), 1.10,
                                               (DOME_R + 0.16) * math.sin(a))))

    # the glass: almost a cylinder, rounding off into a neat dome on top
    m.add("glass", *lathe([
        (DOME_R, 1.18), (DOME_R, 1.55), (DOME_R - 0.01, 2.10),
        (DOME_R - 0.03, 2.50), (DOME_R - 0.10, 2.74), (DOME_R - 0.24, 2.88),
        (DOME_R - 0.42, DOME_TOP), (DOME_R - 0.62, DOME_TOP + 0.05),
        (DOME_R - 0.80, DOME_TOP + 0.07), (0.04, DOME_TOP + 0.08),
    ], 48, close_ends=True))

    # one thin waist band - just enough structure, no bird cage
    m.add("hullMetal", *place(torus(DOME_R + 0.004, 0.009, 0, 48, 5),
                              translation=(0, 2.14, 0)))
    m.add("hullMetal", *place(torus(DOME_R + 0.002, 0.008, 0, 44, 5),
                              translation=(0, 1.30, 0)))

    # little finial on the very top
    m.add("hullMetal", *place(cylinder(0.05, 0.0, 0.10, 10, caps=True, top_radius=0.02),
                              translation=(0, DOME_TOP + 0.06, 0)))
    m.add("lensWhite", *place(sphere((0, 0, 0), 0.045, 12, 8),
                              translation=(0, DOME_TOP + 0.17, 0)))
    return m


def cockpit_console_mesh():
    """Everything the pilot sees from the seat: console, screens, levers, lamps."""
    m = Mesh()

    # floor of the cockpit, slightly raised
    m.add("cockpit", *disc(DOME_R - 0.04, 1.09, 40, up=True))
    m.add("hullMetal", *place(torus(DOME_R - 0.06, 0.03, 0, 44, 6), translation=(0, 1.10, 0)))
    for i in range(8):                       # floor grating
        a = TAU * i / 8
        m.add("hullMetal", *place(box((0, 0, 0), (0.30, 0.02, 0.035)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(0.45 * math.cos(a), 1.11, 0.45 * math.sin(a))))

    # --- the main console: a curved desk with one big screen --------------
    for i in range(7):
        a = math.radians(-60 + i * 20)
        r = DOME_R - 0.16
        px, pz = r * math.sin(a), r * math.cos(a)
        m.add("cockpit", *place(box((0, 0, 0), (0.26, 0.30, 0.14)),
                                rot=(0, -math.degrees(a), 0),
                                translation=(px, 1.18, pz)))
    # one wide screen, tilted back towards the pilot
    # the screen stands upright on the desk and looks at the pilot
    m.add("hullMetal", *place(box((0, 0, 0), (0.64, 0.34, 0.05)), rot=(14, 0, 0),
                              translation=(0, 1.38, 0.66)))
    m.add("lensGreen", *place(box((0, 0, 0), (0.57, 0.28, 0.014)), rot=(14, 0, 0),
                              translation=(0, 1.385, 0.632)))
    m.add("hullMetal", *place(box((0, 0, 0), (0.70, 0.04, 0.07)), rot=(14, 0, 0),
                              translation=(0, 1.56, 0.70)))
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.24, 0.18, 0.03)), rot=(14, side * 26, 0),
                                  translation=(side * 0.50, 1.33, 0.50)))
        m.add("lensWhite", *place(box((0, 0, 0), (0.18, 0.13, 0.010)), rot=(14, side * 26, 0),
                                  translation=(side * 0.50, 1.335, 0.484)))
    # keyboard-ish button rows on the desk
    for row in range(2):
        for b in range(7):
            m.add("lensWhite" if (b + row) % 3 else "lensRed",
                  *place(box((0, 0, 0), (0.05, 0.016, 0.03)),
                         translation=(-0.36 + b * 0.12, 1.27 + row * 0.035, 0.50 - row * 0.03)))

    # throttle levers left and right of the seat
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.10, 0.05, 0.24)),
                                  translation=(side * 0.34, 1.16, 0.26)))
        m.add("cockpit", *place(cylinder(0.018, 0.0, 0.20, 8, caps=True),
                                rot=(-28, 0, side * 10),
                                translation=(side * 0.34, 1.18, 0.24)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.038, 10, 8),
                                translation=(side * 0.38, 1.36, 0.14)))

    # --- the seat the player sits in --------------------------------------
    m.add("cockpit", *place(box((0, 0, 0), (0.46, 0.10, 0.44)),
                            translation=(0, 1.20, 0.02)))
    m.add("cockpit", *place(box((0, 0, 0), (0.46, 0.50, 0.10)), rot=(-12, 0, 0),
                            translation=(0, 1.44, -0.20)))
    m.add("hullMetal", *place(cylinder(0.05, 1.09, 1.20, 8, caps=True),
                              translation=(0, 0, 0.02)))
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.05, 0.05, 0.30)),
                                  translation=(side * 0.24, 1.28, 0.02)))

    # --- overhead instrument ring (you see it through the glass) ----------
    # a hoop above the pilot, with the lamp ring the cockpit blinks with
    hoop = DOME_R - 0.14
    m.add("hullMetal", *place(torus(hoop, 0.016, 0, 44, 6), translation=(0, 1.82, 0)))
    for i in range(10):
        a = TAU * i / 10
        m.add("hullMetal", *place(box((0, 0, 0), (0.10, 0.055, 0.045)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(hoop * math.cos(a), 1.78, hoop * math.sin(a))))
        mat = ("lensGreen", "lensRed", "lensWhite")[i % 3]
        m.add(mat, *place(sphere((0, 0, 0), 0.024, 8, 6),
                          translation=(hoop * math.cos(a), 1.74, hoop * math.sin(a))))

    # --- little holo projector on the right end of the desk ---------------
    m.add("hullMetal", *place(cylinder(0.045, 1.18, 1.30, 10, caps=True),
                              translation=(0.34, 0, 0.30)))
    m.add("lensGreen", *place(sphere((0, 0, 0), 0.060, 12, 8, scale=(1.0, 0.55, 1.0)),
                              translation=(0.34, 1.32, 0.30)))
    m.add("lensGreen", *place(torus(0.12, 0.007, 0, 24, 4),
                              translation=(0.34, 1.40, 0.30)))
    return m


def cockpit_ui_meshes():
    """Interactive looking instruments on the console.

    The Lua script moves three nodes so the inside of the cockpit really
    shows what is selected:
      * patternPointer  - the lit frame around the chosen ground pattern
      * modeLever       - the harvest / flatten switch
      * focusSlider     - the beam focus knob
    """
    board = Mesh()
    # backing plate of the pattern selector, on the left hand console
    board.add("hullMetal", *box((0, 0, 0), (0.40, 0.20, 0.022)))
    tiles = []
    for row in range(2):
        for col in range(5):
            x = -0.15 + col * 0.075
            y = 0.045 - row * 0.075
            tiles.append(place(box((0, 0, 0), (0.058, 0.058, 0.014)),
                               translation=(x, y, 0.012)))
            # a tiny pictogram on every tile
            board.add("lensGreen" if (row + col) % 2 == 0 else "lensWhite",
                      *place(box((0, 0, 0), (0.034, 0.034, 0.008)),
                             translation=(x, y, 0.020)))
    for geom in tiles:
        board.add("cockpit", *geom)

    pointer = Mesh()
    pointer.add("lensGreen", *box((0, 0, 0), (0.070, 0.070, 0.010)))
    pointer.add("lensGreen", *place(box((0, 0, 0), (0.086, 0.012, 0.010)),
                                    translation=(0, 0.042, 0)))
    pointer.add("lensGreen", *place(box((0, 0, 0), (0.086, 0.012, 0.010)),
                                    translation=(0, -0.042, 0)))

    lever = Mesh()
    lever.add("hullMetal", *place(box((0, 0, 0), (0.16, 0.03, 0.10))))
    lever.add("hullPaint", *place(cylinder(0.016, 0.0, 0.20, 8, caps=True),
                                  translation=(0, 0.02, 0)))
    lever.add("lensRed", *place(sphere((0, 0, 0), 0.030, 10, 8),
                                translation=(0, 0.22, 0)))

    slider = Mesh()
    slider.add("hullMetal", *place(box((0, 0, 0), (0.24, 0.016, 0.05))))
    slider.add("lensWhite", *place(box((0, 0, 0), (0.045, 0.05, 0.06))))
    return board, pointer, lever, slider


def cockpit_detail_mesh():
    """Pipes, brackets and a handrail - the bits that make it look lived in."""
    m = Mesh()
    # handrail around the inside of the glass
    m.add("hullMetal", *place(torus(DOME_R - 0.06, 0.018, 0, 48, 6), translation=(0, 1.56, 0)))
    for i in range(6):
        a = TAU * i / 6 + 0.3
        m.add("hullMetal", *place(cylinder(0.014, 1.20, 1.56, 6, caps=True),
                                  translation=((DOME_R - 0.06) * math.cos(a), 0,
                                               (DOME_R - 0.06) * math.sin(a))))
    # cable bundle running from the console into the floor
    for i in range(3):
        m.add("hullMetal", *place(cylinder(0.016, 1.09, 1.22, 6, caps=True),
                                  rot=(0, 0, -14 + i * 14),
                                  translation=(-0.32 + i * 0.06, 0, -0.30)))
    # two storage boxes under the console
    for side in (-1, 1):
        m.add("cockpit", *place(box((0, 0, 0), (0.22, 0.14, 0.16)),
                                translation=(side * 0.42, 1.17, -0.42)))
    return m


def leg_mesh_local():
    """One landing leg in local space (+Y up, pivot at the hull attachment)."""
    m = Mesh()
    # upper strut
    m.add("hullMetal", *cylinder(0.075, -0.30, 0.02, 12, caps=True, top_radius=0.11))
    m.add("hullMetal", *place(torus(0.12, 0.030, 0, 20, 8), translation=(0, -0.02, 0)))
    # hydraulic piston
    m.add("hullMetal", *cylinder(0.045, -0.52, -0.28, 10, caps=True))
    m.add("hullPaint", *cylinder(0.075, -0.62, -0.50, 10, caps=True))
    # foot with a wide pad and a green landing light
    m.add("hullMetal", *place(lathe([(0.10, -0.70), (0.16, -0.74), (0.19, -0.80),
                                     (0.16, -0.84), (0.06, -0.86)], 18, close_ends=True)))
    m.add("lensGreen", *place(torus(0.13, 0.020, 0, 20, 6), translation=(0, -0.76, 0)))
    m.add("lensWhite", *place(sphere((0, 0, 0), 0.032, 10, 6), translation=(0, -0.05, 0.10)))
    return m


LEG_ANGLES = (30, 150, 270)      # degrees around the hull, 270 = rear


def leg_nodes(parent):
    """Three separately animatable legs.

    Each node sits on the hull, rotated so its local +X points outwards and its
    local Z is tangential; rotating the node around Z splays / retracts the leg.
    The first rotation value (splay) is also baked into the node transform.
    """
    nodes = []
    for i, deg in enumerate(LEG_ANGLES):
        a = math.radians(deg)
        pos = (1.86 * math.cos(a), 0.34, 1.86 * math.sin(a))
        node = Node("TransformGroup", "leg%d" % i, translation="%s" % _fmt(pos),
                    rotation="0 %s %s" % (_fmt([-deg]), LEG_SPLAY))
        m = Mesh()
        src = leg_mesh_local()
        for mat in src.order:
            v, n, uv, t = src.parts[mat]
            m.add(mat, v, n, uv, t)
        node.add(Node("Shape", "leg%dMesh" % i, m))
        parent.add(node)
        nodes.append(node)
    return nodes


def beam_mesh():
    """Unit cone: apex at the hull, bottom radius 1 at y = -1.

    The Lua script scales it every frame so that it always ends exactly on the
    ground - the radius at the ground is the radius of the crop circle.
    """
    m = Mesh()
    m.add("beam", *open_cone(0.0, 0.035, -1.0, 1.0, 44))
    return m


def circle_ring_mesh():
    """Unit radius marker ring, sits flat on the ground below the craft."""
    m = Mesh()
    m.add("lensGreen", *place(torus(1.0, 0.012, 0.0, 64, 6)))
    m.add("lensGreen", *place(torus(0.94, 0.006, 0.0, 64, 6)))
    return m


def collision_meshes():
    """(name, geometry) pairs for the compound collision; the first one is the
    main rigid body shape (node 0>, "ufo_main_component1")."""
    return [
        ("ufo_main_component1", cylinder(2.10, 0.0, 0.80, 16, caps=True)),
        ("collisionDome", cylinder(0.92, 0.80, 2.90, 16, caps=True)),
    ]


# --------------------------------------------------------------------------
# i3d scene tree
# --------------------------------------------------------------------------
class Node:
    def __init__(self, kind, name, mesh=None, materials=None, **attrs):
        self.kind = kind
        self.name = name
        self.mesh = mesh
        self.materials = materials or []
        self.attrs = attrs
        self.children = []

    def add(self, child):
        self.children.append(child)
        return child


def build_scene():
    """Return (root Node, mapping list)."""
    main_mesh = Mesh()
    main_mesh.add("collision", *collision_meshes()[0][1])
    body = Node("Shape", "ufo_main_component1", mesh=main_mesh, materials=["collision"], **{
        "dynamic": "true", "compound": "true", "collisionFilterGroup": "0x10004",
        "collisionFilterMask": "0xfe3ffb83", "clipDistance": "300",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    })

    visual = body.add(Node("TransformGroup", "visual"))
    visual.add(Node("Shape", "hullMesh", hull_mesh()))
    visual.add(Node("Shape", "domeGlass", dome_mesh(),
                    materials=["glass"], castsShadows="false", receiveShadows="true"))
    leg_nodes(visual)

    visual.add(Node("Shape", "consoleMesh", cockpit_console_mesh()))
    visual.add(Node("Shape", "cockpitDetailMesh", cockpit_detail_mesh()))

    # --- cockpit instruments the script animates --------------------------
    board, pointer, lever, slider = cockpit_ui_meshes()

    pattern_board = visual.add(Node("TransformGroup", "patternBoard",
                                    translation="-0.56 1.34 0.24", rotation="0 66 0"))
    pattern_board.add(Node("Shape", "patternBoardMesh", board))
    pattern_pointer = pattern_board.add(Node("TransformGroup", "patternPointer",
                                             translation="-0.15 0.045 0.030"))
    pattern_pointer.add(Node("Shape", "patternPointerMesh", pointer, materials=["lensGreen"]))

    mode_panel = visual.add(Node("TransformGroup", "modeLever",
                                 translation="0.56 1.32 0.20", rotation="0 -62 0"))
    mode_panel.add(Node("Shape", "modeLeverMesh", lever))

    focus_panel = visual.add(Node("TransformGroup", "focusSlider",
                                  translation="0.30 1.24 0.52", rotation="0 -14 -18"))
    focus_panel.add(Node("Shape", "focusSliderMesh", slider))

    # seat for the player character - the game puts the player's own character
    # here (see <enterable><characterNode node="driverSeatNode"/></enterable>)
    visual.add(Node("TransformGroup", "driverSeatNode", translation="0 1.24 0.02"))

    beacon = visual.add(Node("TransformGroup", "beaconNode", translation="0 3.02 0"))
    beacon.add(Node("Shape", "beaconMesh", antenna_beacon_mesh(), materials=["lensRed"]))

    beam = visual.add(Node("TransformGroup", "beamNode", translation="0 0.22 0", visibility="false"))
    beam.add(Node("Shape", "beamMesh", beam_mesh(), materials=["beam"],
                  castsShadows="false", receiveShadows="false", nonRenderable="false"))

    ring = visual.add(Node("TransformGroup", "groundRing", translation="0 0.05 0",
                           visibility="false", scale="1 1 1"))
    ring.add(Node("Shape", "groundRingMesh", circle_ring_mesh(), materials=["lensGreen"],
                  castsShadows="false", receiveShadows="false"))

    collisions = body.add(Node("TransformGroup", "collisions"))
    for name, geom in collision_meshes()[1:]:
        m = Mesh()
        m.add("collision", *geom)
        collisions.add(Node("Shape", name, m, materials=["collision"], **{
            "compoundChild": "true", "collisionFilterGroup": "0x10004",
            "collisionFilterMask": "0xfe3ffb83", "density": "0.001",
            "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
        }))

    lights = body.add(Node("TransformGroup", "lights"))
    lights.add(Node("Light", "headLightLeft", translation="0.62 0.66 1.95", rotation="-8 180 0",
                    type="spot", color="0.85 1.0 0.92", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="45", coneAngle="72", dropOff="3"))
    lights.add(Node("Light", "headLightRight", translation="-0.62 0.66 1.95", rotation="-8 180 0",
                    type="spot", color="0.85 1.0 0.92", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="45", coneAngle="72", dropOff="3"))
    lights.add(Node("Light", "workLight", translation="0 0.30 0", rotation="-90 0 0",
                    type="spot", color="0.65 1.0 0.85", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="60", coneAngle="88", dropOff="2"))
    lights.add(Node("Light", "beamLight", translation="0 0.22 0", rotation="-90 0 0",
                    type="spot", color="0.55 1.0 0.95", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="42", coneAngle="52", dropOff="1.5"))
    lights.add(Node("Light", "beaconLight", translation="0 3.02 0",
                    type="point", color="1 0.18 0.12", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="26"))
    lights.add(Node("Light", "tailLight", translation="0 0.72 -2.20",
                    type="point", color="1 0.25 0.15", emitDiffuse="true", emitSpecular="true",
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

    cam_target = body.add(Node("TransformGroup", "outdoorCameraTarget", translation="0 1.15 0"))
    cam_target.add(Node("Camera", "outdoorCamera", translation="0 0 -9", rotation="0 180 0",
                        fov="45", nearClip="0.05", farClip="5000"))
    inside_target = body.add(Node("TransformGroup", "indoorCameraTarget", translation="0 1.66 0.06"))
    inside_target.add(Node("Camera", "indoorCamera", rotation="-8 180 0", fov="70",
                           nearClip="0.03", farClip="5000"))

    return body


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------
class Writer:
    def __init__(self, materials):
        self.materials = materials
        self.material_index = {m["name"]: i + 1 for i, m in enumerate(materials)}
        self.files = []
        self.shape_xml = []
        self.node_id = 0
        self.shape_id = 0
        self.mappings = []
        self.stats = {"tris": 0, "verts": 0, "shapes": 0}

    # -- files / materials -------------------------------------------------
    def file_id(self, rel):
        if rel not in self.files:
            self.files.append(rel)
        return self.files.index(rel) + 1

    def material_id(self, name):
        return self.material_index[name]

    # -- geometry ----------------------------------------------------------
    def write_shape(self, node):
        self.shape_id += 1
        sid = self.shape_id
        mesh = node.mesh
        mats = node.materials or [m for m in mesh.order if m != "collision"]
        if not mats:
            mats = list(mesh.order)

        verts, normals, uvs, tris = [], [], [], []
        subsets = []
        for mat in mats:
            if mat not in mesh.parts:
                continue
            pv, pn, puv, pt = mesh.parts[mat]
            first_vertex = len(verts)
            first_index = 3 * len(tris)
            verts.extend(pv)
            normals.extend(pn)
            uvs.extend(puv)
            tris.extend(pt)
            subsets.append((first_vertex, len(pv), first_index, 3 * len(pt), mat))

        self.stats["tris"] += len(tris)
        self.stats["verts"] += len(verts)
        self.stats["shapes"] += 1

        attr = [("name", node.name), ("shapeId", str(sid))]
        for k in ("dynamic", "compound", "compoundChild", "collisionFilterGroup",
                  "collisionFilterMask", "density", "clipDistance", "castsShadows",
                  "receiveShadows", "nonRenderable"):
            if k in node.attrs:
                attr.append((k, node.attrs[k]))
        mid_list = [self.material_id(m) for m in mats if m in mesh.parts]
        attr.append(("materialIds", " ".join(str(m) for m in mid_list)))

        lines = ["      <IndexedTriangleSet %s>" % _attrs(attr)]
        lines.append('        <Vertices normal="true" uv0="true" count="%d">' % len(verts))
        for v, n, uv in zip(verts, normals, uvs):
            lines.append('          <v p="%s" n="%s" t0="%s"/>' % (_fmt(v), _fmt(n), _fmt(uv)))
        lines.append("        </Vertices>")
        lines.append('        <Triangles count="%d">' % len(tris))
        for t in tris:
            lines.append('          <t vi="%d %d %d"/>' % t)
        lines.append("        </Triangles>")
        lines.append("        <Subsets>")
        for fv, nv, fi, ni, mat in subsets:
            lines.append('          <Subset firstVertex="%d" numVertices="%d" firstIndex="%d" '
                         'numIndices="%d" materialSlotName="%s"/>' % (fv, nv, fi, ni, mat))
        lines.append("        </Subsets>")
        lines.append("      </IndexedTriangleSet>")
        self.shape_xml.extend(lines)
        return sid

    # -- scene -------------------------------------------------------------
    def write_node(self, node, depth, path):
        self.node_id += 1
        nid = self.node_id
        self.mappings.append((node.name, path))
        indent = "    " * depth
        attrs = [("name", node.name)]
        if node.kind == "Shape":
            sid = self.write_shape(node)
            attrs.append(("shapeId", str(sid)))
        for k, v in node.attrs.items():
            attrs.append((k, v))
        attrs.append(("nodeId", str(nid)))
        if not node.children:
            return ["%s<%s %s/>" % (indent, node.kind, _attrs(attrs))]
        lines = ["%s<%s %s>" % (indent, node.kind, _attrs(attrs))]
        for i, child in enumerate(node.children):
            child_path = ("0>%d" % i) if path == "0>" else ("%s|%d" % (path, i))
            lines.extend(self.write_node(child, depth + 1, child_path))
        lines.append("%s</%s>" % (indent, node.kind))
        return lines


def _attrs(pairs):
    return " ".join('%s="%s"' % (k, v) for k, v in pairs)


def write_i3d(root, out_path, materials=MATERIALS, asset_name="ufo"):
    w = Writer(materials)
    scene_lines = w.write_node(root, 3, "0>")
    # materials first: they register the texture files
    mat_lines = []
    for mat in materials:
        attrs = [("name", mat["name"]), ("materialId", str(w.material_index[mat["name"]]))]
        if mat.get("alpha"):
            attrs.append(("alphaBlending", "true"))
        children = []
        if mat.get("diffuse") is None:
            attrs.append(("diffuseColor", mat.get("color", "0.5 0.5 0.5 1")))
            attrs.append(("specularColor", mat.get("specular", "0.2 0.2 0.2")))
        else:
            children.append(('      <Texture fileId="%d"/>' % w.file_id(mat["diffuse"])))
        if mat.get("gloss"):
            children.append(('      <Glossmap fileId="%d"/>' % w.file_id(mat["gloss"])))
        if children:
            mat_lines.append("    <Material %s>" % _attrs(attrs))
            mat_lines.extend(children)
            mat_lines.append("    </Material>")
        else:
            mat_lines.append("    <Material %s/>" % _attrs(attrs))

    header = ('<i3D name="%s" version="1.6" ' % asset_name
              + 'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
              + 'xsi:noNamespaceSchemaLocation="http://i3d.giants.ch/schema/i3d-1.6.xsd">')
    lines = ['<?xml version="1.0" encoding="iso-8859-1"?>',
             header,
             "  <Asset>",
             '    <Export program="tools/ufo/model.py (procedural FS25 pipeline)" version="1.0"/>',
             "  </Asset>",
             "  <Files>"]
    for i, f in enumerate(w.files, start=1):
        lines.append('    <File fileId="%d" filename="textures/%s"/>' % (i, f))
    lines.append("  </Files>")
    lines.append("  <Materials>")
    lines.extend(mat_lines)
    lines.append("  </Materials>")
    lines.append("  <Shapes>")
    lines.extend(w.shape_xml)
    lines.append("  </Shapes>")
    lines.append("  <Dynamics>")
    lines.append("  </Dynamics>")
    lines.append("  <Scene>")
    lines.extend(scene_lines)
    lines.append("  </Scene>")
    lines.append("</i3D>")
    with open(out_path, "w", encoding="iso-8859-1", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    mappings = "\n".join('        <i3dMapping id="%s" node="%s"/>' % (n, p) for n, p in w.mappings)
    return w.stats, mappings
