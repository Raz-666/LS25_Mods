# SPDX-License-Identifier: GPL-3.0-or-later
"""Model of the console edition: FS25_UFO2500 (no Lua at all).

The saucer is the same procedural mesh as the FS25_UFO2000.  What changes is
the trick that makes it a console mod:

  * the whole craft floats ``HOVER`` metres above the vehicle origin,
  * below it there is nothing but air - the craft rolls on **invisible wheels**
    that sit on the ground plane,
  * four wide-spread "care wheels" carry the vehicle (they do not damage crop),
  * a row of up to 15 narrow brush wheels presses the crop exactly where the
    saucer hovers - that is the whole crop circle mechanic, done with the
    base-game wheel destruction, no script involved,
  * the tractor beam is baked in as static geometry that ends on the ground,
    so you can see where the brush is.

The vehicle origin stays at ground level, so everything the game does with a
normal car (spawning, entering, physics, the shop) works unchanged.
"""

import model
from meshlib import Mesh, cylinder
from model import Node, _fmt

HOVER = 8.83             # the seat ends up 10.0 m above the ground
WHEEL_RADIUS = 0.55      # wheels hang at y = radius -> origin on the ground
CARE_X = 1.85            # track width of the load carrying wheels
CARE_Z = 1.55
CARE_WIDTH = 0.30

BRUSH_MODULES = 15       # 15 x 0.5 m = 7.5 m, the widest swath
BRUSH_PITCH = 0.50
BRUSH_WIDTH = 0.50

BEAM_RADIUS = 1.75       # matches the 3.5 m "standard" swath
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

CARE_WHEELS = (
    ("wheelCareFrontLeft", -CARE_X, CARE_Z),
    ("wheelCareFrontRight", CARE_X, CARE_Z),
    ("wheelCareRearLeft", -CARE_X, -CARE_Z),
    ("wheelCareRearRight", CARE_X, -CARE_Z),
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
    """Node name + local x for every brush module (centred, odd count)."""
    half = (BRUSH_MODULES - 1) * 0.5
    return [("wheelBrush%d" % i, (i - half) * BRUSH_PITCH) for i in range(BRUSH_MODULES)]


def brush_module_names(count):
    """The contiguous, centred set of brush modules used by one configuration."""
    half = (count - 1) // 2
    middle = BRUSH_MODULES // 2
    return ["wheelBrush%d" % i for i in range(middle - half, middle + half + 1)]


def build_scene(hover=HOVER):
    root = model.build_scene()

    # 1) lift the craft, keep the ground contacts where they are
    for name in SHIFTED:
        node = find(root, name)
        if node is None:
            raise RuntimeError("node %r not found in the base model" % name)
        _move(node, hover)

    # 2) landing legs folded in - the saucer never touches down
    for i in range(3):
        leg = find(root, "leg%d" % i)
        if leg is not None:
            rot = leg.attrs["rotation"].split()
            leg.attrs["rotation"] = "%s %s %s" % (rot[0], rot[1],
                                                  _fmt([float(rot[2]) + 74.0]))

    # 3) the beam is always on and ends just above the ground
    beam = find(root, "beamNode")
    if beam is not None:
        height = hover + 0.22 - BEAM_BOTTOM
        beam.attrs["visibility"] = "true"
        beam.attrs["scale"] = "%s %s %s" % (_fmt([BEAM_RADIUS]), _fmt([height]),
                                            _fmt([BEAM_RADIUS]))
    ring = find(root, "groundRing")
    if ring is not None:
        x, y, z = _xyz(ring)
        ring.attrs["translation"] = "%s %s %s" % (_fmt([x]), _fmt([RING_Y - hover]), _fmt([z]))
        ring.attrs["scale"] = "%s 1 %s" % (_fmt([BEAM_RADIUS]), _fmt([BEAM_RADIUS]))
        ring.attrs["visibility"] = "true"

    # 3b) the hull itself has to be solid up there: an invisible collision
    #     cylinder around the saucer (the "collisions" node is already lifted)
    collisions = find(root, "collisions")
    if collisions is not None:
        hull = Mesh()
        hull.add("collision", *cylinder(2.0, 0.30, 1.05, 16, caps=True))
        collisions.add(Node("Shape", "collisionHull", hull, materials=["collision"], **{
            "compoundChild": "true", "collisionFilterGroup": "0x10004",
            "collisionFilterMask": "0xfe3ffb83", "density": "0.001",
            "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
        }))

    # 4) invisible wheels: four load carrying care wheels ...
    for name, x, z in CARE_WHEELS:
        root.add(Node("TransformGroup", name,
                      translation="%s %s %s" % (_fmt([x]), _fmt([WHEEL_RADIUS]), _fmt([z]))))
    # ... and the brush row that presses the crop
    for name, x in brush_wheels():
        root.add(Node("TransformGroup", name,
                      translation="%s %s %s" % (_fmt([x]), _fmt([WHEEL_RADIUS]), _fmt([0]))))

    # 5) pool of green light on the ground, so the beam reads as "active"
    ground = root.add(Node("TransformGroup", "groundEffects"))
    ground.add(Node("Light", "groundGlow", translation="0 0.45 0",
                    type="point", color="0.45 1.0 0.8", emitDiffuse="true",
                    emitSpecular="false", castShadowMap="false", range="14"))

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
    print("%d shapes, %d tris -> %s (%d mappings)" % (s["shapes"], s["tris"], out,
                                                      m.count("i3dMapping id=")))
    sys.exit(0)
