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
from sculpt import tube

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
    {"name": "beamRed", "diffuse": "beamRed_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamGreen", "diffuse": "beamGreen_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamBrown", "diffuse": "beamBrown_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamOrange", "diffuse": "beamOrange_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamLime", "diffuse": "beamLime_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamViolet", "diffuse": "beamViolet_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamBlue", "diffuse": "beamBlue_diffuse.dds", "gloss": None, "alpha": True},
    {"name": "beamCyan", "diffuse": "beamCyan_diffuse.dds", "gloss": None, "alpha": True},
]

# the eight working modes, in menu order: (id, beam material, beam node name)
BEAMS = (
    ("damage", "beamRed"),
    ("harvest", "beamGreen"),
    ("cultivate", "beamBrown"),
    ("plow", "beamOrange"),
    ("sow", "beamLime"),
    ("fertilize", "beamViolet"),
    ("load", "beamBlue"),
    ("unload", "beamCyan"),
)
MAT_INDEX = {m["name"]: i + 1 for i, m in enumerate(MATERIALS)}

HULL_R = 2.45            # outer radius of the saucer
DOME_R = 0.70            # tall, NARROW bell jar - the Simpsons look
RIM_Y = 0.80
HULL_Y = 0.22            # belly centre height
DOME_BASE = 1.00         # where the glass starts
DOME_TOP = 2.74          # top of the glass


LEG_SPLAY = "16"          # degrees the legs are splayed out at rest
CABIN_SQUEEZE = 0.72      # the interior is squeezed into the narrow dome


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
    """The flying disc: flat plate, rounded chrome bumper rim, rivets.

    Drawn like the saucers in the old Simpsons couch gags - two shells pressed
    together with a fat metal band in between, a small riveted collar on top
    that carries the bell jar.
    """
    m = Mesh()

    # --- belly: shallow dish, a bit stepped towards the middle -------------
    m.add("hullMetal", *lathe([
        (0.05, HULL_Y), (0.60, 0.16), (1.25, 0.11), (1.80, 0.13),
        (2.12, 0.22), (2.32, 0.36), (2.42, 0.48),
    ], 64, close_ends=False))
    # --- the fat bumper rim ------------------------------------------------
    m.add("hullMetal", *lathe([
        (2.42, 0.48), (2.49, 0.58), (2.50, 0.68), (2.44, 0.78), (2.30, 0.86),
    ], 64, close_ends=False))
    # --- upper shell: a soft comic mound, stepped up to the dome collar ----
    m.add("hullPaint", *lathe([
        (2.30, 0.86), (2.10, 0.915), (1.85, 0.965), (1.55, 1.000),
        (1.25, 1.025), (1.02, 1.038), (DOME_R + 0.24, 1.042),
    ], 64, close_ends=False))
    m.add("hullPaint", *disc(DOME_R + 0.24, 1.042, 44, up=True))
    # the step itself: a thin chrome lip that catches the light
    m.add("hullMetal", *place(torus(1.56, 0.010, 0, 56, 5), translation=(0, 1.002, 0)))

    # --- lines: one chrome band around the bumper, two panel seams ---------
    m.add("hullMetal", *torus(2.475, 0.045, 0.68, 64, 10))
    m.add("hullMetal", *torus(1.85, 0.014, 0.966, 56, 5))
    # rivets on the bumper and on the collar
    for i in range(32):
        a = TAU * i / 32
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.026, 8, 6),
                                  translation=(2.46 * math.cos(a), 0.545, 2.46 * math.sin(a))))
    for i in range(12):
        a = TAU * i / 12 + 0.1
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.022, 8, 6),
                                  translation=((DOME_R + 0.19) * math.cos(a), 1.01,
                                               (DOME_R + 0.19) * math.sin(a))))

    # --- twelve little running lights around the rim ----------------------
    for i in range(12):
        a = TAU * i / 12
        m.add("hullMetal", *place(cylinder(0.075, 0.0, 0.09, 12, caps=True),
                                  rot=(90, 0, 0),
                                  translation=(2.36 * math.cos(a), 0.68, 2.36 * math.sin(a))))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.070, 14, 8, scale=(1.0, 0.9, 0.6)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(2.45 * math.cos(a), 0.68, 2.45 * math.sin(a))))

    # --- three landing skids under the rim (the legs are separate) --------
    for i in range(3):
        a = TAU * i / 3 + math.pi / 2
        m.add("hullMetal", *place(box((0, 0, 0), (0.56, 0.14, 0.24)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(1.62 * math.cos(a), 0.10, 1.62 * math.sin(a))))

    # --- two head lamps, two tail lights ----------------------------------
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.095, 0.0, 0.11, 14, caps=True),
                                  rot=(90, 0, 0),
                                  translation=(side * 0.62, 0.58, 2.14)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.090, 14, 8, scale=(1.0, 1.0, 0.7)),
                                  translation=(side * 0.62, 0.58, 2.24)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.050, 12, 8, scale=(1.0, 1.0, 0.6)),
                                translation=(side * 1.52, 0.50, -1.80)))

    # --- beam emitter under the belly -------------------------------------
    m.add("hullMetal", *place(torus(0.46, 0.055, 0, 40, 8), translation=(0, 0.17, 0)))
    m.add("hullMetal", *place(cylinder(0.44, 0.11, 0.19, 32, caps=True)))
    m.add("lensGreen", *place(disc(0.40, 0.115, 32, up=False)))

    # --- a pair of short antennae on the rear -----------------------------
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.013, 0.0, 0.50, 8, caps=True),
                                  rot=(-16, 0, side * 10),
                                  translation=(side * 1.62, 0.95, -1.28)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.045, 10, 8),
                                translation=(side * 1.74, 1.43, -1.38)))
    return m


def antenna_beacon_mesh():
    m = Mesh()
    m.add("hullMetal", *cylinder(0.026, -0.30, 0.0, 10, caps=True))
    m.add("lensRed", *sphere((0, 0, 0), 0.085, 16, 10, scale=(1, 1.05, 1)))
    return m


def dome_mesh():
    """The tall, narrow bell jar - the signature Simpsons silhouette.

    Only 1.4 m across but 1.75 m tall: the pilot sits inside like in a
    telephone booth, which is exactly the joke.
    """
    m = Mesh()

    # heavy metal collar the glass sits in (also the cockpit floor)
    m.add("hullMetal", *lathe([
        (DOME_R + 0.24, 0.98), (DOME_R + 0.24, 1.06), (DOME_R + 0.12, 1.10),
        (DOME_R, 1.10),
    ], 44, close_ends=True))
    for i in range(14):
        a = TAU * i / 14
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.022, 8, 6),
                                  translation=((DOME_R + 0.19) * math.cos(a), 1.02,
                                               (DOME_R + 0.19) * math.sin(a))))

    # the glass itself: straight tube, big round shoulder, flat little top
    m.add("glass", *lathe([
        (DOME_R, 1.09), (DOME_R, 1.62), (DOME_R - 0.002, 2.10),
        (DOME_R - 0.008, 2.38), (DOME_R - 0.030, 2.56),
        (DOME_R - 0.090, 2.65), (DOME_R - 0.190, DOME_TOP),
        (DOME_R - 0.340, DOME_TOP + 0.05), (DOME_R - 0.500, DOME_TOP + 0.07),
        (0.03, DOME_TOP + 0.08),
    ], 48, close_ends=True))

    # one thin waist band, one thin base ring - no bird cage
    m.add("hullMetal", *place(torus(DOME_R + 0.004, 0.008, 0, 48, 5),
                              translation=(0, 1.12, 0)))
    m.add("hullMetal", *place(torus(DOME_R + 0.004, 0.007, 0, 48, 5),
                              translation=(0, 2.06, 0)))

    # little finial + red light on the very top
    m.add("hullMetal", *place(cylinder(0.045, 0.0, 0.09, 10, caps=True, top_radius=0.022),
                              translation=(0, DOME_TOP + 0.07, 0)))
    m.add("lensRed", *place(sphere((0, 0, 0), 0.050, 12, 8),
                            translation=(0, DOME_TOP + 0.18, 0)))
    return m


def cockpit_console_mesh(hoop_y=1.98, hoop=0.56):
    """Everything the pilot sees from the seat: console, screens, levers, lamps.

    `hoop_y` / `hoop` place the overhead instrument hoop; the harvester has a
    much taller dome and a pilot with a big head, so it hangs it higher.

    Laid out for the narrow bell jar: two instrument wings left and right, a
    low pedestal straight ahead and the whole centre of the glass kept clear so
    the pilot really looks out over the nose while working.
    """
    m = Mesh()

    # floor of the cockpit and its rim
    m.add("cockpit", *disc(0.78, 1.09, 40, up=True))
    m.add("hullMetal", *place(torus(0.79, 0.030, 0, 44, 6), translation=(0, 1.10, 0)))
    for i in range(8):
        a = TAU * i / 8
        m.add("hullMetal", *place(box((0, 0, 0), (0.26, 0.02, 0.030)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(0.40 * math.cos(a), 1.10, 0.40 * math.sin(a))))

    # --- the desk: a low curved shelf across the front --------------------
    for i in range(7):
        a = math.radians(-54 + i * 18)
        r = 0.66
        m.add("cockpit", *place(box((0, 0, 0), (0.30, 0.13, 0.20)),
                                rot=(0, -math.degrees(a), 0),
                                translation=(r * math.sin(a), 1.19, r * math.cos(a))))
    # thin chrome lip on the front edge of the desk
    m.add("hullMetal", *place(torus(0.76, 0.012, 0, 44, 5), translation=(0, 1.255, 0)))
    m.add("hullMetal", *place(torus(0.60, 0.012, 0, 44, 5), translation=(0, 1.255, 0)))

    # --- two instrument wings, angled towards the pilot -------------------
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.36, 0.24, 0.05)),
                                  rot=(14, side * 26, 0),
                                  translation=(side * 0.46, 1.34, 0.42)))
        # the green glass of the display sits a hair in front of the housing
        m.add("lensGreen", *place(box((0, 0, 0), (0.31, 0.19, 0.012)),
                                   rot=(14, side * 26, 0),
                                   translation=(side * 0.46, 1.342, 0.392)))
        # little button strips below the displays
        for b in range(4):
            m.add("lensWhite" if b % 2 == 0 else "lensRed",
                  *place(box((0, 0, 0), (0.035, 0.012, 0.022)),
                         rot=(12, side * 34, 0),
                         translation=(side * (0.40 + b * 0.075), 1.212, 0.36)))

    # --- centre pedestal: the mode dial, right under the pilot's eyes -----
    m.add("hullMetal", *place(cylinder(0.16, 1.19, 1.26, 20, caps=True),
                              translation=(0, 0, 0.44)))
    m.add("hullMetal", *place(cylinder(0.185, 1.25, 1.275, 20, caps=True),
                              translation=(0, 0, 0.44)))
    # eight glowing segments = the eight working modes
    for i in range(8):
        a = TAU * i / 8
        m.add("lensGreen", *place(box((0, 0, 0), (0.035, 0.010, 0.055)),
                                  rot=(0, -math.degrees(a), 0),
                                  translation=(0.115 * math.cos(a), 1.282,
                                               0.44 + 0.115 * math.sin(a))))
    m.add("lensRed", *place(sphere((0, 0, 0), 0.032, 10, 8),
                            translation=(0, 1.29, 0.44)))
    # the dial reads the ground pattern right below the ship
    m.add("lensWhite", *place(disc(0.10, 1.285, 24, up=True), translation=(0, 0, 0.44)))

    # --- keyboard row under the desk lip ----------------------------------
    for b in range(7):
        m.add("lensWhite" if b % 3 else "lensGreen",
              *place(box((0, 0, 0), (0.045, 0.014, 0.028)),
                     translation=(-0.33 + b * 0.11, 1.262, 0.60)))

    # throttle levers left and right of the seat
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.09, 0.05, 0.22)),
                                  translation=(side * 0.33, 1.155, 0.16)))
        m.add("cockpit", *place(cylinder(0.016, 0.0, 0.19, 8, caps=True),
                                rot=(-24, 0, side * 9),
                                translation=(side * 0.33, 1.17, 0.14)))
        m.add("lensRed", *place(sphere((0, 0, 0), 0.034, 10, 8),
                                translation=(side * 0.37, 1.33, 0.05)))

    # --- the seat the player sits in --------------------------------------
    m.add("cockpit", *place(box((0, 0, 0), (0.44, 0.10, 0.42)),
                            translation=(0, 1.20, -0.06)))
    m.add("cockpit", *place(box((0, 0, 0), (0.44, 0.46, 0.10)), rot=(-12, 0, 0),
                            translation=(0, 1.43, -0.28)))
    m.add("hullMetal", *place(cylinder(0.05, 1.09, 1.20, 8, caps=True),
                              translation=(0, 0, -0.06)))
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.05, 0.05, 0.28)),
                                  translation=(side * 0.23, 1.28, -0.06)))

    # --- overhead instrument hoop (you see it through the glass) ----------
    m.add("hullMetal", *place(torus(hoop, 0.012, 0, 40, 6),
                              translation=(0, hoop_y, 0)))
    for i in range(8):
        a = TAU * i / 8
        m.add("hullMetal", *place(box((0, 0, 0), (0.065, 0.032, 0.030)),
                                  rot=(0, -math.degrees(a) + 90, 0),
                                  translation=(hoop * math.cos(a), hoop_y - 0.025,
                                               hoop * math.sin(a))))
        mat = ("lensGreen", "lensRed", "lensWhite")[i % 3]
        m.add(mat, *place(sphere((0, 0, 0), 0.013, 8, 6),
                          translation=(hoop * math.cos(a), hoop_y - 0.055,
                                       hoop * math.sin(a))))
    # the hoop hangs from two thin brackets at the side of the glass
    for side in (-1, 1):
        m.add("hullMetal", *place(cylinder(0.008, 0.0, 0.30, 6, caps=True),
                                  rot=(0, 0, side * 10),
                                  translation=(side * hoop * 0.92, hoop_y, 0)))

    # --- little holo projector on the right of the pedestal ---------------
    m.add("hullMetal", *place(cylinder(0.040, 1.19, 1.30, 10, caps=True),
                              translation=(0.30, 0, 0.34)))
    m.add("lensGreen", *place(sphere((0, 0, 0), 0.055, 12, 8, scale=(1.0, 0.55, 1.0)),
                              translation=(0.30, 1.32, 0.34)))
    m.add("lensGreen", *place(torus(0.11, 0.006, 0, 24, 4),
                              translation=(0.30, 1.40, 0.34)))
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

    # the needle of the mode dial: points at one of the eight glowing segments
    needle = Mesh()
    needle.add("lensRed", *place(box((0, 0, 0), (0.018, 0.010, 0.105)),
                                 translation=(0, 0.008, 0.055)))
    needle.add("lensWhite", *place(sphere((0, 0, 0), 0.016, 10, 8),
                                   translation=(0, 0.010, 0.108)))
    needle.add("hullMetal", *place(cylinder(0.016, 0.0, 0.020, 10, caps=True)))
    return board, pointer, lever, slider, needle


def cockpit_detail_mesh():
    """Pipes, brackets and the little things that make it feel lived in."""
    m = Mesh()
    # cable bundle running from the console into the floor
    for i in range(3):
        m.add("hullMetal", *place(cylinder(0.016, 1.09, 1.22, 6, caps=True),
                                  rot=(0, 0, -14 + i * 14),
                                  translation=(-0.32 + i * 0.06, 0, -0.30)))
    # two storage boxes under the console
    for side in (-1, 1):
        m.add("cockpit", *place(box((0, 0, 0), (0.22, 0.14, 0.16)),
                                translation=(side * 0.42, 1.17, -0.42)))

    # a coffee mug on the left of the desk - the pilot is only humanoid
    m.add("hullPaint", *place(cylinder(0.024, 1.255, 1.300, 14, caps=True),
                              translation=(-0.30, 0, 0.58)))
    m.add("lensGreen", *place(torus(0.023, 0.006, 0, 16, 5),
                              translation=(-0.30, 1.300, 0.58)))

    # --- bobble-head alien on a spring, right in front of the pilot -------
    k = 0.62                                # the whole ornament is tiny
    bx, bz, by = 0.30, 0.56, 1.262
    m.add("hullMetal", *place(cylinder(0.040 * k, by - 0.02, by, 12, caps=True),
                              translation=(bx, 0, bz)))
    for i in range(5):                      # the spring
        m.add("hullMetal", *place(torus(0.020 * k, 0.006 * k, 0, 12, 4),
                                  translation=(bx, by + 0.012 + i * 0.011, bz)))
    # body: little green alien in a silver suit
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.050 * k, 12, 8, scale=(1.0, 1.15, 0.9)),
                              translation=(bx, by + 0.10, bz)))
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.058 * k, 14, 10, scale=(1.0, 0.92, 1.0)),
                              translation=(bx, by + 0.175, bz)))
    for side in (-1, 1):
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.020 * k, 10, 8, scale=(0.9, 1.25, 0.7)),
                                 translation=(bx + side * 0.023 * k, by + 0.18, bz + 0.046 * k)))
        # antennae with a little ball on top
        m.add("hullMetal", *place(cylinder(0.004, 0.0, 0.055 * k, 5, caps=True),
                                  rot=(0, 0, side * 22),
                                  translation=(bx + side * 0.018 * k, by + 0.215, bz - 0.006)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.014 * k, 8, 6),
                                  translation=(bx + side * 0.032 * k, by + 0.268, bz - 0.008)))
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


def beam_ring_mesh():
    """Flat annulus with radius 1 in the XZ plane - one "pulse" of the beam.

    Flat geometry on purpose: the beam node is scaled non-uniformly every
    frame (radius, height, radius), and a flat ring keeps its shape while a
    torus would be stretched into an ellipse.
    """
    m = Mesh()
    verts, normals, uvs, tris = [], [], [], []
    segments = 48
    for i in range(segments + 1):
        a = TAU * i / segments
        for r in (0.86, 1.0):
            verts.append((r * math.cos(a), 0.0, r * math.sin(a)))
            normals.append((0.0, 1.0, 0.0))
            uvs.append((i / segments, 0.0 if r < 1.0 else 1.0))
    for i in range(segments):
        a0 = i * 2
        tris += [(a0, a0 + 1, a0 + 2), (a0 + 1, a0 + 3, a0 + 2)]
    m.add("beam", verts, normals, uvs, tris)
    return m


def beam_swirl_mesh():
    """A helix inside the cone; the Lua turns it, which reads as a streaming
    energy vortex instead of a frozen cone."""
    m = Mesh()
    points, radii = [], []
    steps = 26
    for i in range(steps + 1):
        t = i / steps
        a = TAU * 2.4 * t
        r = 0.10 + 0.72 * t
        points.append((r * math.cos(a), -t, r * math.sin(a)))
        radii.append(0.030 + 0.045 * t)
    m.add("beam", *tube(points, radii, segments=7))
    return m


def beam_fx_nodes(parent, suffix):
    """Hanging a bright core, the swirl and four travelling rings under one
    beam node.  Names are unique per mode so the Lua can find them."""
    core = Mesh()
    core.add("lensWhite", *open_cone(0.0, 0.012, -0.97, 0.16, 28))
    parent.add(Node("Shape", "beamCore" + suffix, core, materials=["lensWhite"],
                    castsShadows="false", receiveShadows="false"))

    fx = parent.add(Node("TransformGroup", "beamFx" + suffix))
    fx.add(Node("Shape", "beamSwirl" + suffix, beam_swirl_mesh(),
                castsShadows="false", receiveShadows="false"))
    for i in range(4):
        fx.add(Node("Shape", "beamRing%s%d" % (suffix, i), beam_ring_mesh(),
                    castsShadows="false", receiveShadows="false"))
    return fx


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
        ("ufo_main_component1", cylinder(2.10, 0.0, 0.78, 16, caps=True)),
        ("collisionDome", cylinder(0.70, 0.78, 2.85, 16, caps=True)),
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

    # the interior is modelled at a comfortable size and squeezed into the
    # narrow bell jar (x/z only, so all the heights stay where they are)
    cabin = visual.add(Node("TransformGroup", "cabin",
                            scale="%s 1 %s" % (_fmt([CABIN_SQUEEZE]), _fmt([CABIN_SQUEEZE]))))
    cabin.add(Node("Shape", "consoleMesh", cockpit_console_mesh()))
    cabin.add(Node("Shape", "cockpitDetailMesh", cockpit_detail_mesh()))

    # --- cockpit instruments the script animates --------------------------
    board, pointer, lever, slider, needle = cockpit_ui_meshes()

    pattern_board = cabin.add(Node("TransformGroup", "patternBoard",
                                   translation="-0.56 1.34 0.24", rotation="0 66 0"))
    pattern_board.add(Node("Shape", "patternBoardMesh", board))
    pattern_pointer = pattern_board.add(Node("TransformGroup", "patternPointer",
                                             translation="-0.15 0.045 0.030"))
    pattern_pointer.add(Node("Shape", "patternPointerMesh", pointer, materials=["lensGreen"]))

    mode_panel = cabin.add(Node("TransformGroup", "modeLever",
                                translation="0.56 1.32 0.20", rotation="0 -62 0"))
    mode_panel.add(Node("Shape", "modeLeverMesh", lever))

    focus_panel = cabin.add(Node("TransformGroup", "focusSlider",
                                 translation="0.30 1.24 0.52", rotation="0 -14 -18"))
    focus_panel.add(Node("Shape", "focusSliderMesh", slider))

    mode_needle = cabin.add(Node("TransformGroup", "modeNeedle",
                                 translation="0 1.298 0.44"))
    mode_needle.add(Node("Shape", "modeNeedleMesh", needle))

    # seat for the player character - the game puts the player's own character
    # here (see <enterable><characterNode node="driverSeatNode"/></enterable>)
    visual.add(Node("TransformGroup", "driverSeatNode", translation="0 1.24 0.02"))

    beacon = visual.add(Node("TransformGroup", "beaconNode", translation="0 2.92 0"))
    beacon.add(Node("Shape", "beaconMesh", antenna_beacon_mesh(), materials=["lensRed"]))

    # one cone per working mode, each with its own colour; the script shows
    # exactly one of them
    for mode_id, material in BEAMS:
        node_name = "beamNode" + mode_id[0].upper() + mode_id[1:]
        beam = visual.add(Node("TransformGroup", node_name, translation="0 0.19 0",
                               visibility="false"))
        suffix = mode_id[0].upper() + mode_id[1:]
        beam.add(Node("Shape", "beamMesh" + suffix, beam_mesh(),
                      materials=[material], castsShadows="false", receiveShadows="false",
                      nonRenderable="false"))
        beam_fx_nodes(beam, suffix)

    # narrow second emitter, offset from the main cone so harvested grain can
    # be shown flowing into a truck / trailer without hiding the green beam
    transfer = visual.add(Node("TransformGroup", "transferBeamNode",
                               translation="3.0 0.19 0", visibility="false"))
    transfer.add(Node("Shape", "transferBeamMesh", beam_mesh(),
                      materials=["beamRed"], castsShadows="false",
                      receiveShadows="false", nonRenderable="false"))
    beam_fx_nodes(transfer, "Transfer")

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
    lights.add(Node("Light", "beaconLight", translation="0 2.92 0",
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
    inside_target = body.add(Node("TransformGroup", "indoorCameraTarget", translation="0 1.62 0.02"))
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

        # The node may name the material the shape should use while the mesh
        # itself carries a generic slot - the tractor beam is one such case:
        # one cone mesh, eight nodes, eight colours.  In that case the geometry
        # is taken as is and re-slotted to the node's material, instead of
        # silently producing an empty shape.
        source = [m for m in mats if m in mesh.parts]
        if source:
            slots = [(m, m) for m in source]
        else:
            source = [m for m in mesh.order if m != "collision"]
            slots = list(zip(source, mats[:len(source)]))

        verts, normals, uvs, tris = [], [], [], []
        subsets = []
        for part, slot in slots:
            if part not in mesh.parts:
                continue
            pv, pn, puv, pt = mesh.parts[part]
            first_vertex = len(verts)
            first_index = 3 * len(tris)
            verts.extend(pv)
            normals.extend(pn)
            uvs.extend(puv)
            tris.extend(pt)
            subsets.append((first_vertex, len(pv), first_index, 3 * len(pt), slot))

        self.stats["tris"] += len(tris)
        self.stats["verts"] += len(verts)
        self.stats["shapes"] += 1

        attr = [("name", node.name), ("shapeId", str(sid))]
        for k in ("dynamic", "compound", "compoundChild", "collisionFilterGroup",
                  "collisionFilterMask", "density", "clipDistance", "castsShadows",
                  "receiveShadows", "nonRenderable"):
            if k in node.attrs:
                attr.append((k, node.attrs[k]))
        mid_list = [self.material_id(slot) for _part, slot in slots
                    if _part in mesh.parts]
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
