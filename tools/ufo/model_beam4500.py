# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of the FS25_UFO4500 - the big mother ship.

The 4500 is the beam-only harvester of the family: no cutter, no attacher
joint, no grain pipe and no header.  Everything it does, it does with the
tractor beam, exactly like the UFO 01 Crop Harvester - it is just a size
class bigger.

The hull is the proven UFO 01 scene, scaled up by ``SCALE`` and finished
with the parts that make the 4500 look like a ship of its own:

  * four hover turbine nacelles with glowing intake rings,
  * a wide emitter collar under the belly (the beam fires out of it),
  * armoured shoulder panels with rivets,
  * a second, larger ground ring for the wide beam,
  * two rear cargo pods.

Every node the Lua looks up (``beamNode…``, ``groundRing``, ``beamLight``,
``leg0..2``, ``patternPointer`` …) keeps its name, so the vehicle logic is
shared with the Crop Harvester.
"""

import math

import model_crop
from meshlib import TAU, Mesh, cylinder, disc, place, sphere, torus
from model import Node, _fmt

SCALE = 1.30                 # the 4500 is a third bigger than the UFO 01
POD_ANGLES = (45.0, 135.0, 225.0, 315.0)
POD_R = 2.62
POD_Y = 0.62


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def find(node, name):
    if node.name == name:
        return node
    for child in node.children:
        found = find(child, name)
        if found is not None:
            return found
    return None


def _at(angle_deg, radius, y):
    a = math.radians(angle_deg)
    return (radius * math.sin(a), y, radius * math.cos(a))


def pod_mesh():
    """One hover turbine pod, axis along +Y (the node turns it outwards).

    Nacelle with an intake lip and a glowing stator ring at the front, an
    exhaust nozzle at the back and a mounting strut to the hull.
    """
    m = Mesh()
    # nacelle body, slightly tapered towards the intake
    m.add("hullPaint", *place(cylinder(0.28, -0.62, 0.30, 26, caps=True,
                                       top_radius=0.33)))
    # intake lip, vent ring and the glowing stator disc
    m.add("hullMetal", *place(torus(0.315, 0.042, 0.30, 30, 8)))
    m.add("lensGreen", *place(disc(0.255, 0.31, 26, up=True)))
    for i in range(6):
        a = TAU * i / 6.0
        m.add("hullMetal", *place(cylinder(0.020, 0.24, 0.31, 6, caps=True),
                                  translation=(0.135 * math.cos(a), 0.0,
                                               0.135 * math.sin(a))))
    # exhaust nozzle at the back, with a hot ring
    m.add("hullMetal", *place(cylinder(0.11, -0.86, -0.60, 18, caps=True,
                                       top_radius=0.24)))
    m.add("lensWhite", *place(disc(0.095, -0.87, 18, up=False)))
    # two fins along the nacelle
    for a in (0.0, math.pi):
        m.add("hullMetal", *place(cylinder(0.028, -0.55, 0.24, 6, caps=True),
                                  scale=(3.2, 1.0, 0.55),
                                  translation=(0.0, 0.0, 0.0)))
        break
    # mounting strut back to the hull
    m.add("hullMetal", *place(cylinder(0.085, -0.62, -0.30, 12, caps=True,
                                       top_radius=0.105),
                              translation=(0.0, 0.0, 0.0)))
    return m


def emitter_mesh():
    """Wide collar under the belly: the beam leaves through this ring."""
    m = Mesh()
    # two concentric rings, the inner one carries the glow
    m.add("hullMetal", *place(torus(0.98, 0.085, 0.10, 56, 10)))
    m.add("hullPaint", *place(torus(0.80, 0.055, 0.06, 48, 9)))
    m.add("lensGreen", *place(torus(0.88, 0.030, 0.05, 52, 8)))
    # eight nozzle blocks pointing at the beam centre
    for i in range(8):
        a = TAU * i / 8.0
        m.add("hullMetal", *place(cylinder(0.055, 0.0, 0.20, 10, caps=True,
                                           top_radius=0.075),
                                  rot=(0, 0, 0),
                                  translation=(0.92 * math.cos(a), -0.02,
                                               0.92 * math.sin(a))))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.045, 12, 8),
                                  translation=(0.92 * math.cos(a), -0.06,
                                               0.92 * math.sin(a))))
    return m


def shoulder_mesh():
    """Armoured panel on one shoulder plus its rivet line."""
    m = Mesh()
    m.add("hullPaint", *place(cylinder(2.30, 0.30, 0.46, 40, caps=True,
                                       top_radius=2.24)))
    m.add("hullMetal", *place(torus(2.30, 0.035, 0.30, 48, 7)))
    m.add("hullMetal", *place(torus(2.24, 0.030, 0.46, 48, 7)))
    for i in range(16):
        a = TAU * i / 16.0
        m.add("hullMetal", *place(sphere((0, 0, 0), 0.035, 8, 6),
                                  translation=(2.28 * math.cos(a), 0.40,
                                               2.28 * math.sin(a))))
    return m


def cargo_pod_mesh():
    """Rear cargo pod: a rounded capsule with a hatch and a running light."""
    m = Mesh()
    m.add("hullPaint", *place(cylinder(0.32, -0.50, 0.50, 22, caps=True,
                                       top_radius=0.28),
                              rot=(0, 0, 90)))
    for x in (-0.28, 0.28):
        m.add("hullMetal", *place(torus(0.325, 0.032, 0, 26, 7), rot=(0, 90, 0),
                                  translation=(x, 0.0, 0.0)))
    # hatch on the outward face and the running light on the cap
    m.add("hullMetal", *place(disc(0.17, 0.505, 20, up=True), rot=(0, 90, 0)))
    m.add("lensRed", *place(sphere((0, 0, 0), 0.048, 10, 8),
                            translation=(0.51, 0.0, 0.0)))
    return m


def box_disc(radius, thickness):
    """Small flat cylinder used as a hatch cover."""
    return cylinder(radius, -thickness * 0.5, thickness * 0.5, 18, caps=True)


# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------
def build_scene():
    body = model_crop.build_scene()
    visual = find(body, "visual")
    if visual is None:
        raise RuntimeError("visual node missing in the crop model")

    # --- hover turbines ---------------------------------------------------
    for i, angle in enumerate(POD_ANGLES):
        pod = visual.add(Node("TransformGroup", "hoverPod%d" % i,
                             translation="%s %s %s" % tuple(
                                 _fmt([v]) for v in _at(angle, POD_R, POD_Y)),
                             rotation="90 %.1f 0" % angle))
        pod.add(Node("Shape", "hoverPodMesh%d" % i, pod_mesh()))

    # --- armoured shoulder ring, emitter collar, cargo pods ---------------
    visual.add(Node("Shape", "shoulderArmour", shoulder_mesh()))
    visual.add(Node("Shape", "beamEmitter", emitter_mesh()))
    for i, angle in enumerate((150.0, 210.0)):
        visual.add(Node("Shape", "cargoPod%d" % i, cargo_pod_mesh(),
                        translation="%s %s %s" % tuple(
                            _fmt([v]) for v in _at(angle, 2.30, 0.34)),
                        rotation="0 %.1f 0" % angle))

    # --- the whole ship is one size class bigger --------------------------
    root = Node("TransformGroup", "ufo4500Root",
                scale="%s %s %s" % (_fmt([SCALE]), _fmt([SCALE]), _fmt([SCALE])))
    root.add(body)
    return root


def write(path):
    return model_crop.base.write_i3d(build_scene(), path,
                                     materials=model_crop.MATERIALS,
                                     asset_name="ufo4500")


if __name__ == "__main__":
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    out = os.path.join(repo, "build", "ufo4500_inline.i3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    stats, mappings = write(out)
    print("%d shapes, %d tris -> %s" % (stats["shapes"], stats["tris"], out))
    sys.exit(0)
