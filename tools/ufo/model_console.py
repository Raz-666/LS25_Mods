# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of the console edition FS25_UFO2500 (no Lua at all).

The saucer uses the same procedural mesh as FS25_UFO2000 and stands 20 m in
the air:

  * the cockpit (driver seat) is exactly 20.00 m above the ground,
  * the hull floats 18.83 m above the vehicle origin,
  * the craft rolls on two wide invisible wheels in line (like a motorcycle,
    just wider) plus two tiny invisible outriggers that keep it upright,
  * below the middle sits the brush: up to 15 invisible 0.5 m wheels that press
    the crop down, using nothing but the base game wheel destruction,
  * a "landing" animation (driven by the base game foldable + AnimatedVehicle
    specializations) lowers the whole craft to street level, so the player can
    get out without falling 20 m,
  * inside the dome there is a real cockpit: dashboard, three screens, buttons
    and two beacon lights from the base game that blink.
"""

import math

import model
from meshlib import TAU, Mesh, box, cylinder, disc, place, sphere, torus
from model import Node, _fmt

HOVER = 18.83            # seat ends up 20.0 m above the ground
LANDED = 0.95            # visual node position at the end of the landing animation
WHEEL_RADIUS = 0.55      # wheels hang at y = radius -> origin on the ground
TRACK_Z = 1.85           # the two wide wheels sit in line, front / rear
TRACK_WIDTH = 0.70       # ... and they are wide, like a fat motorcycle tyre
OUTRIGGER_X = 1.95       # tiny hidden wheels against tipping over

BRUSH_MODULES = 15
BRUSH_PITCH = 0.50
BRUSH_WIDTH = 0.50

BEAM_RADIUS = 1.75
BEAM_BOTTOM = 0.16
RING_Y = 0.07

# nodes that belong to the floating craft and therefore move up
SHIFTED = (
    "visual",
    "collisions",
    "lights",
    "soundMotor",
    "outdoorCameraTarget",
    "indoorCameraTarget",
    "exactFillRootNode",
)

LOAD_WHEELS = (
    ("wheelFront", TRACK_Z, True),
    ("wheelRear", -TRACK_Z, False),
)
OUTRIGGERS = (
    ("wheelOutriggerLeft", -OUTRIGGER_X, 0.0),
    ("wheelOutriggerRight", OUTRIGGER_X, 0.0),
)


def find(node, name):
    if node.name == name:
        return node
    for child in node.children:
        found = find(child, name)
        if found is not None:
            return found
    return None


def _xyz(node):
    return [float(v) for v in node.attrs.get("translation", "0 0 0").split()]


def _move(node, dy):
    x, y, z = _xyz(node)
    node.attrs["translation"] = "%s %s %s" % (_fmt([x]), _fmt([y + dy]), _fmt([z]))


def brush_wheels():
    half = (BRUSH_MODULES - 1) * 0.5
    return [("wheelBrush%d" % i, (i - half) * BRUSH_PITCH) for i in range(BRUSH_MODULES)]


def brush_module_names(count):
    half = (count - 1) // 2
    middle = BRUSH_MODULES // 2
    return ["wheelBrush%d" % i for i in range(middle - half, middle + half + 1)]


def leg_angles():
    """Rest (folded) and landed (extended) splay of the three legs."""
    out = []
    for i in range(3):
        node = "leg%d" % i
        deg = 30 + 120 * i
        z_rest = float(model.LEG_SPLAY) + 74.0
        out.append((node, -deg, z_rest, float(model.LEG_SPLAY)))
    return out


# --------------------------------------------------------------------------
# cockpit interior
# --------------------------------------------------------------------------
def cockpit_detail_mesh():
    """Dashboard, console, screens, buttons and levers - inside the bell jar.

    Laid out for the narrow dome of the PC model: floor, two angled instrument
    wings, a low pedestal with the mode dial and the seat.  Nothing sticks out
    of the glass any more.
    """
    m = Mesh()

    # floor plate / seat base
    m.add("cockpit", *disc(0.78, 1.158, 40))
    m.add("hullMetal", *place(torus(0.79, 0.028, 0, 40, 6), translation=(0, 1.158, 0)))
    m.add("hullMetal", *place(cylinder(0.26, 1.16, 1.34, 18, caps=True),
                              translation=(0, 0, -0.50)))

    # low curved desk in front of the pilot
    for i in range(7):
        a = math.radians(-54 + i * 18)
        m.add("cockpit", *place(box((0, 0, 0), (0.30, 0.13, 0.20)),
                                rot=(0, -math.degrees(a), 0),
                                translation=(0.66 * math.sin(a), 1.19,
                                             0.66 * math.cos(a))))
    m.add("hullMetal", *place(torus(0.76, 0.012, 0, 44, 5), translation=(0, 1.255, 0)))

    # two angled instrument wings with green glass
    for side in (-1, 1):
        m.add("hullMetal", *place(box((0, 0, 0), (0.36, 0.24, 0.05)),
                                  rot=(14, side * 26, 0),
                                  translation=(side * 0.46, 1.34, 0.42)))
        m.add("lensGreen", *place(box((0, 0, 0), (0.31, 0.19, 0.012)),
                                  rot=(14, side * 26, 0),
                                  translation=(side * 0.46, 1.342, 0.392)))
        for b in range(4):
            m.add("lensWhite" if b % 2 == 0 else "lensRed",
                  *place(box((0, 0, 0), (0.035, 0.012, 0.022)),
                         rot=(14, side * 26, 0),
                         translation=(side * (0.34 + b * 0.070), 1.238, 0.48)))

    # the mode dial on the centre pedestal
    m.add("hullMetal", *place(cylinder(0.16, 1.19, 1.26, 20, caps=True),
                              translation=(0, 0, 0.44)))
    m.add("hullMetal", *place(cylinder(0.185, 1.25, 1.275, 20, caps=True),
                              translation=(0, 0, 0.44)))
    for i in range(8):
        a = TAU * i / 8
        m.add("lensGreen", *place(box((0, 0, 0), (0.035, 0.010, 0.055)),
                                  rot=(0, -math.degrees(a), 0),
                                  translation=(0.115 * math.cos(a), 1.282,
                                               0.44 + 0.115 * math.sin(a))))
    m.add("lensWhite", *place(disc(0.10, 1.285, 24, up=True), translation=(0, 0, 0.44)))
    m.add("lensRed", *place(sphere((0, 0, 0), 0.032, 10, 8),
                            translation=(0, 1.29, 0.44)))

    # throttle levers left and right of the seat
    m.add("hullMetal", *place(cylinder(0.020, 0.0, 0.18, 8, caps=True),
                              rot=(-24, 0, 9), translation=(0.33, 1.17, 0.14)))
    m.add("lensRed", *place(sphere((0, 0, 0), 0.034, 10, 6),
                            translation=(0.37, 1.33, 0.05)))
    m.add("hullMetal", *place(cylinder(0.020, 0.0, 0.16, 8, caps=True),
                              rot=(-24, 0, -9), translation=(-0.33, 1.17, 0.14)))
    m.add("hullMetal", *place(sphere((0, 0, 0), 0.04, 10, 6),
                              translation=(-0.37, 1.31, 0.05)))

    # overhead switch panel between the beacon lights
    m.add("hullMetal", *place(box((0, 0, 0), (0.46, 0.05, 0.18)), rot=(14, 0, 0),
                              translation=(0, 1.66, 0.10)))
    for k in range(3):
        m.add("lensWhite", *place(box((0, 0, 0), (0.08, 0.02, 0.05)), rot=(14, 0, 0),
                                  translation=(-0.14 + k * 0.14, 1.695, 0.10)))
    return m


# --------------------------------------------------------------------------
# scene
# --------------------------------------------------------------------------
def build_scene(hover=HOVER):
    root = model.build_scene()

    # 1) lift the craft, keep the ground contacts where they are
    for name in SHIFTED:
        node = find(root, name)
        if node is None:
            raise RuntimeError("node %r not found in the base model" % name)
        _move(node, hover)

    # 2) landing legs: folded while flying, extended by the landing animation
    for name, _deg, z_rest, _z_landed in leg_angles():
        leg = find(root, name)
        if leg is not None:
            rot = leg.attrs["rotation"].split()
            leg.attrs["rotation"] = "%s %s %s" % (rot[0], rot[1], _fmt([z_rest]))

    # 3) the beam is always on and ends just above the ground.
    # The PC model has one cone per working mode; the console edition only has
    # the crop circle brush, so it keeps a single green cone and hides the rest.
    height = hover + 0.19 - BEAM_BOTTOM
    for mode_id, _material in model.BEAMS:
        other = find(root, "beamNode" + mode_id[0].upper() + mode_id[1:])
        if other is not None:
            other.attrs["visibility"] = "false"
    beam = find(root, "beamNodeDamage")
    if beam is not None:
        beam.attrs["visibility"] = "true"
        beam.attrs["scale"] = "%s %s %s" % (_fmt([BEAM_RADIUS]), _fmt([height]),
                                            _fmt([BEAM_RADIUS]))
    ring = find(root, "groundRing")
    if ring is not None:
        x, y, z = _xyz(ring)
        ring.attrs["translation"] = "%s %s %s" % (_fmt([x]), _fmt([RING_Y - hover]), _fmt([z]))
        ring.attrs["scale"] = "%s 1 %s" % (_fmt([BEAM_RADIUS]), _fmt([BEAM_RADIUS]))
        ring.attrs["visibility"] = "true"

    # 3b) invisible collision hull around the saucer
    collisions = find(root, "collisions")
    if collisions is not None:
        hull = Mesh()
        hull.add("collision", *cylinder(2.0, 0.30, 1.05, 16, caps=True))
        collisions.add(Node("Shape", "collisionHull", hull, materials=["collision"], **{
            "compoundChild": "true", "collisionFilterGroup": "0x10004",
            "collisionFilterMask": "0xfe3ffb83", "density": "0.001",
            "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
        }))

    # 3c) the cockpit inside the dome
    visual = find(root, "visual")
    visual.add(Node("Shape", "cockpitDetail", cockpit_detail_mesh()))
    visual.add(Node("TransformGroup", "cockpitBeacon1", translation="-0.44 1.62 0.30"))
    visual.add(Node("TransformGroup", "cockpitBeacon2", translation="0.44 1.62 0.30"))

    # 4) invisible wheels: two wide ones in line, two tiny outriggers ...
    for name, z, _steer in LOAD_WHEELS:
        root.add(Node("TransformGroup", name,
                      translation="0 %s %s" % (_fmt([WHEEL_RADIUS]), _fmt([z]))))
    for name, x, z in OUTRIGGERS:
        root.add(Node("TransformGroup", name,
                      translation="%s %s %s" % (_fmt([x]), _fmt([WHEEL_RADIUS]), _fmt([z]))))
    # ... and the brush row that presses the crop
    for name, x in brush_wheels():
        root.add(Node("TransformGroup", name,
                      translation="%s %s 0" % (_fmt([x]), _fmt([WHEEL_RADIUS]))))

    # 5) pool of green light on the ground
    ground = root.add(Node("TransformGroup", "groundEffects"))
    ground.add(Node("Light", "groundGlow", translation="0 0.45 0",
                    type="point", color="0.45 1.0 0.8", emitDiffuse="true",
                    emitSpecular="false", castShadowMap="false", range="16"))

    return root


def write(path):
    root = build_scene()
    stats, mappings = model.write_i3d(root, path, asset_name="ufo2500")
    return stats, mappings


if __name__ == "__main__":
    import os
    import sys
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    out = os.path.join(repo, "build", "ufo2500_inline.i3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    s, m = write(out)
    print("%d shapes, %d tris -> %s (%d mappings)"
          % (s["shapes"], s["tris"], out, m.count("i3dMapping id=")))
    sys.exit(0)
