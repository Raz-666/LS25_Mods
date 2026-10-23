#!/usr/bin/env python3
"""Geometry test for the console edition: how much crop does the brush press?

There is no Lua in FS25_UFO2500, so instead of a script test this one measures
the *geometry* the base game will use:

  * reads the wheel nodes out of ufo2500.i3d and the wheel widths out of
    ufo2500.xml (the same numbers the game reads),
  * simulates a drive and rasterises every stamp that WheelDestruction would
    make (a wheel stamps ``width x min(0.5, width / 2)`` metres per frame),
  * compares the pressed area with the analytic swath ``2 * pi * R * width``.

    python tools/ufo/brush_test.py
"""

import math
import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD = os.path.join(REPO, "FS25_UFO2500")

GRID = 0.05            # raster resolution in metres
STEP = 0.10            # distance between two frames (a slow drive)
HOVER = 8.83
SEAT = 10.00

failures = []


def check(cond, msg):
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        failures.append(msg)


def load():
    veh = ET.parse(os.path.join(MOD, "ufo2500.xml")).getroot()
    i3d = ET.parse(os.path.join(MOD, "ufo2500.i3d")).getroot()
    scene = i3d.find("Scene")
    nodes = {n.get("name"): n for n in scene.iter() if n.get("name")}
    return veh, nodes


def world_y(i3d, name):
    """Accumulated y translation of a node (the i3d stores local transforms)."""
    def walk(node, y):
        tr = node.get("translation", "0 0 0").split()
        here = y + float(tr[1])
        if node.get("name") == name:
            return here
        for child in node:
            found = walk(child, here)
            if found is not None:
                return found
        return None
    for node in i3d.find("Scene"):
        found = walk(node, 0.0)
        if found is not None:
            return found
    raise KeyError(name)


def node_xy(nodes, name):
    tr = nodes[name].get("translation", "0 0 0").split()
    return float(tr[0]), float(tr[1]), float(tr[2])


def configs(veh, nodes):
    """[[(x, z, width), ...], ...] for every wheel configuration."""
    out = []
    for cfg in veh.findall("wheels/wheelConfigurations/wheelConfiguration"):
        wheels = []
        for w in cfg.findall("wheels/wheel"):
            phys = w.find("physics")
            x, _y, z = node_xy(nodes, phys.get("repr"))
            wheels.append((x, z, float(phys.get("width")), phys.get("repr")))
        out.append((cfg.get("name", "?"), cfg.get("saveId", "?"), wheels))
    return out


def stamp_rect(x, z, width, heading):
    """The rectangle WheelDestruction presses for one wheel in one frame."""
    length = min(0.5, 0.5 * width)
    # local axes of the craft: X across, Z along the driving direction
    ca, sa = math.cos(heading), math.sin(heading)
    ax, az = (ca * width * 0.5, sa * width * 0.5)          # across
    bx, bz = (-sa * length, ca * length)                    # along
    corners = [(x + ax + bx, z + az + bz), (x - ax + bx, z - az + bz),
               (x - ax - bx, z - az - bz), (x + ax - bx, z + az - bz)]
    return corners


def grid_of(rects, lo, size):
    """Boolean raster of the pressed area ("True = crop pressed down")."""
    grid = np.zeros((size, size), dtype=bool)
    for corners in rects:
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        i0 = max(int((min(xs) - lo) / GRID), 0)
        i1 = min(int((max(xs) - lo) / GRID) + 1, size)
        j0 = max(int((min(ys) - lo) / GRID), 0)
        j1 = min(int((max(ys) - lo) / GRID) + 1, size)
        if i1 <= i0 or j1 <= j0:
            continue
        px = lo + (np.arange(i0, i1) + 0.5) * GRID
        py = lo + (np.arange(j0, j1) + 0.5) * GRID
        gx, gy = np.meshgrid(px, py)
        inside = np.ones(gx.shape, dtype=bool)
        for k in range(4):
            ax, ay = corners[k]
            bx, by = corners[(k + 1) % 4]
            cross = (bx - ax) * (gy - ay) - (by - ay) * (gx - ax)
            inside &= cross >= -1e-9
        grid[j0:j1, i0:i1] |= inside
    return grid


def rasterise(rects, lo, size):
    """Union area of the rectangles in m^2."""
    return grid_of(rects, lo, size).sum() * GRID * GRID


def drive(wheels, path):
    """All stamps for one pass along ``path`` = [(x, z, heading), ...]."""
    rects = []
    active = [w for w in wheels if w[3].startswith("wheelBrush")]
    for cx, cz, heading in path:
        ca, sa = math.cos(heading), math.sin(heading)
        for x, z, width, _name in active:
            wx = cx + ca * x - sa * z
            wz = cz + sa * x + ca * z
            rects.append(stamp_rect(wx, wz, width, heading))
    return rects


def circle_path(radius):
    length = 2 * math.pi * radius
    n = max(int(length / STEP), 8)
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        # heading is the tangent of the circle
        out.append((radius * math.cos(a), radius * math.sin(a), a))
    return out


def main():
    veh, nodes = load()
    i3d = ET.parse(os.path.join(MOD, "ufo2500.i3d")).getroot()
    cfgs = configs(veh, nodes)

    print("\nfloating check")
    check(abs(node_xy(nodes, "visual")[1] - HOVER) < 0.01,
          "the craft floats %.2f m above the origin" % node_xy(nodes, "visual")[1])
    seat = world_y(i3d, "driverSeatNode")
    check(abs(seat - SEAT) < 0.02,
          "the cockpit ends up %.2f m above the ground" % seat)
    wheel_ys = [node_xy(nodes, w[3])[1] for _n, _s, wheels in cfgs for w in wheels]
    check(max(abs(y - 0.55) for y in wheel_ys) < 0.01,
          "all %d wheels stand on the contact plane (radius 0.55)" % len(wheel_ys))

    print("\nbrush widths")
    radius = 15.0
    path = circle_path(radius)
    for name, save_id, wheels in cfgs:
        brush = [w for w in wheels if w[3].startswith("wheelBrush")]
        care = [w for w in wheels if not w[3].startswith("wheelBrush")]
        swath = sum(w[2] for w in brush)
        xs = sorted(w[0] for w in brush)
        centred = abs(xs[0] + xs[-1]) < 1e-6
        rects = drive(wheels, path)
        area = rasterise(rects, -(radius + 8), int(2 * (radius + 8) / GRID) + 2)
        expected = 2 * math.pi * radius * swath
        label = save_id.lower().ljust(10)
        check(centred, "%s brush is centred on the craft" % label)
        check(abs(area - expected) / expected < 0.06,
              "%s circle r=%.0f m: %.0f m2 pressed, analytic %.0f m2 (%d care wheels)"
              % (label, radius, area, expected, len(care)))

    standard = [c for c in cfgs if c[1] == "STANDARD"][0]
    ring_r = float(nodes["groundRing"].get("scale").split()[0])
    swath = sum(w[2] for w in standard[2] if w[3].startswith("wheelBrush"))
    check(abs(ring_r * 2 - swath) < 0.01,
          "the ground ring under the saucer (%.1f m) matches the standard brush (%.1f m)"
          % (ring_r * 2, swath))

    print("\nstraight pass, 100 m")
    straight = [(0.0, i * STEP - 50.0, 0.0) for i in range(int(100 / STEP) + 1)]
    for name, save_id, wheels in cfgs:
        swath = sum(w[2] for w in wheels if w[3].startswith("wheelBrush"))
        rects = drive(wheels, straight)
        area = rasterise(rects, -60, int(120 / GRID) + 2)
        expected = 100.0 * swath
        check(abs(area - expected) / expected < 0.03,
              "%-10s %.1f m2 per 100 m (%.1f m wide), analytic %.1f m2"
              % (save_id.lower(), area, swath, expected))

    print("\n%d failures" % len(failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
