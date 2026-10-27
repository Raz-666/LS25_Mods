#!/usr/bin/env python3
"""Procedural track, station and four-seat coaster car for Höhensturm."""

import math
import os
import sys

TOOL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ufo"))
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

from meshlib import Mesh, box, cylinder, place, sphere, torus  # noqa: E402
from model import Node  # noqa: E402
from path import (add, cross, dot, length, mul, parallel_transport_frames,
                  sub, unit)  # noqa: E402


MATERIALS = [
    {"name": "collision", "diffuse": None, "color": "0.6 0.1 0.6 1", "specular": "0.1 0.1 0.1"},
    {"name": "trackSteel", "diffuse": None, "color": "0.045 0.20 0.52 1", "specular": "0.62 0.78 1.0"},
    {"name": "supportSteel", "diffuse": None, "color": "0.065 0.105 0.17 1", "specular": "0.45 0.58 0.72"},
    {"name": "crossTie", "diffuse": None, "color": "0.16 0.21 0.27 1", "specular": "0.34 0.42 0.50"},
    {"name": "safetyOrange", "diffuse": None, "color": "1.0 0.29 0.035 1", "specular": "0.72 0.44 0.20"},
    {"name": "safetyYellow", "diffuse": None, "color": "1.0 0.75 0.055 1", "specular": "0.65 0.58 0.26"},
    {"name": "seatFabric", "diffuse": None, "color": "0.16 0.055 0.095 1", "specular": "0.18 0.15 0.17"},
    {"name": "seatCushion", "diffuse": None, "color": "0.58 0.065 0.075 1", "specular": "0.24 0.18 0.18"},
    {"name": "stationConcrete", "diffuse": None, "color": "0.38 0.43 0.47 1", "specular": "0.20 0.22 0.24"},
    {"name": "stationSteel", "diffuse": None, "color": "0.075 0.125 0.20 1", "specular": "0.55 0.63 0.72"},
    {"name": "stationBlue", "diffuse": None, "color": "0.035 0.18 0.33 1", "specular": "0.35 0.53 0.68"},
    {"name": "glassBlue", "diffuse": None, "color": "0.10 0.48 0.74 0.24", "specular": "0.85 0.95 1.0", "alpha": True},
    {"name": "neonCyan", "diffuse": None, "color": "0.02 0.95 1.0 1", "specular": "0.65 1.0 1.0"},
    {"name": "neonViolet", "diffuse": None, "color": "0.48 0.10 1.0 1", "specular": "0.78 0.62 1.0"},
    {"name": "neonMagenta", "diffuse": None, "color": "1.0 0.08 0.62 1", "specular": "1.0 0.66 0.90"},
    {"name": "neonAmber", "diffuse": None, "color": "1.0 0.42 0.06 1", "specular": "1.0 0.72 0.36"},
    {"name": "rubber", "diffuse": None, "color": "0.025 0.03 0.04 1", "specular": "0.12 0.12 0.12"},
    {"name": "metalBright", "diffuse": None, "color": "0.68 0.76 0.82 1", "specular": "0.9 0.95 1.0"},
]


# ---------------------------- basis / mesh tools ----------------------------
def _transform_geom(geom, center, right, up, forward):
    verts, normals, uvs, tris = geom
    out_v, out_n = [], []
    for v in verts:
        out_v.append(add(center, add(mul(right, v[0]), add(mul(up, v[1]), mul(forward, v[2])))))
    for n in normals:
        out_n.append(unit(add(mul(right, n[0]), add(mul(up, n[1]), mul(forward, n[2])))))
    return out_v, out_n, uvs, tris


def oriented_box(mesh, material, center, right, up, forward, size):
    right, up, forward = unit(right), unit(up), unit(forward)
    mesh.add(material, *_transform_geom(box((0, 0, 0), size), center, right, up, forward))


def beam_between(mesh, material, a, b, width=0.32, depth=None):
    """Add a rectangular steel member whose long axis runs from a to b."""
    delta = sub(b, a)
    span = length(delta)
    if span < 0.05:
        return
    forward = mul(delta, 1.0 / span)
    reference = (0.0, 1.0, 0.0)
    if abs(dot(forward, reference)) > 0.92:
        reference = (1.0, 0.0, 0.0)
    right = unit(cross(reference, forward), fallback=(1.0, 0.0, 0.0))
    up = unit(cross(forward, right), fallback=(0.0, 1.0, 0.0))
    oriented_box(mesh, material, mul(add(a, b), 0.5), right, up, forward,
                 (width, width if depth is None else depth, span))


def tube_mesh(mesh, material, points, frames, radius, sides=8, offset_right=0.0,
              offset_up=0.0, closed=True, uv_repeat=1.0):
    n = len(points)
    if n < 2:
        return
    verts, normals, uvs, tris = [], [], [], []
    for i in range(n):
        f = frames[i]
        center = add(points[i], add(mul(f["right"], offset_right), mul(f["up"], offset_up)))
        for j in range(sides):
            theta = 2.0 * math.pi * j / sides
            radial = add(mul(f["right"], math.cos(theta)), mul(f["up"], math.sin(theta)))
            verts.append(add(center, mul(radial, radius)))
            normals.append(radial)
            uvs.append((uv_repeat * i / max(1, n - 1), j / sides))
    segments = n if closed else n - 1
    for i in range(segments):
        i2 = (i + 1) % n
        for j in range(sides):
            j2 = (j + 1) % sides
            a, b = i * sides + j, i * sides + j2
            c, d = i2 * sides + j, i2 * sides + j2
            tris.append((a, c, b))
            tris.append((b, c, d))
    mesh.add(material, verts, normals, uvs, tris)


def _double_sided_glass_quad(mesh, points, normal):
    """Add one translucent pane visible from both sides of the station hall."""
    verts = list(points)
    normal = unit(normal, (0.0, 0.0, 1.0))
    uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    mesh.add("glassBlue", verts, [normal] * 4, uvs, [(0, 1, 2), (0, 2, 3)])
    inward = mul(normal, -1.0)
    mesh.add("glassBlue", verts, [inward] * 4, uvs, [(0, 2, 1), (0, 3, 2)])


def _open_frames(points):
    """Rotation-minimising frames for an open support arch."""
    n = len(points)
    tangents = []
    for i in range(n):
        if i == 0:
            d = sub(points[1], points[0])
        elif i == n - 1:
            d = sub(points[-1], points[-2])
        else:
            d = sub(points[i + 1], points[i - 1])
        tangents.append(unit(d, (0.0, 0.0, 1.0)))
    seed = (1.0, 0.0, 0.0)
    if abs(dot(seed, tangents[0])) > 0.9:
        seed = (0.0, 0.0, 1.0)
    up = unit(sub(seed, mul(tangents[0], dot(seed, tangents[0]))), (0.0, 1.0, 0.0))
    ups = [up]
    for i in range(1, n):
        old, new = tangents[i - 1], tangents[i]
        axis = cross(old, new)
        axis_len = length(axis)
        cosine = max(-1.0, min(1.0, dot(old, new)))
        if axis_len > 1e-10:
            axis = mul(axis, 1.0 / axis_len)
            angle = math.atan2(axis_len, cosine)
            c, s = math.cos(angle), math.sin(angle)
            u = ups[-1]
            ups.append(unit(add(add(mul(u, c), mul(cross(axis, u), s)),
                                mul(axis, dot(axis, u) * (1 - c)))))
        else:
            ups.append(ups[-1])
        ups[-1] = unit(sub(ups[-1], mul(new, dot(ups[-1], new))), (0, 1, 0))
    frames = []
    for p, t, u in zip(points, tangents, ups):
        r = unit(cross(u, t), (1, 0, 0))
        u = unit(cross(t, r), (0, 1, 0))
        frames.append({"point": p, "tangent": t, "up": u, "right": r})
    return frames


def add_text_pixels(mesh, text, center_x, center_y, z, pixel=0.145, material="neonCyan"):
    """Build compact 5x7 illuminated lettering on the station fascia."""
    glyphs = {
        "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
        "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
        "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
        "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
        "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
        "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
        "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
        "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
        "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
        "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
        "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
        "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
        "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
        "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
        "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
        "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
        "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
        "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
        "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
        "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
        "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
        "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
        "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
        "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
        "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
        "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
        "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
        "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
        "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
        "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
        "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
        "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
        "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
        "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
        "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
        "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
        " ": ("00000",) * 7,
    }
    text = text.upper()
    char_w = 6 * pixel
    total_w = max(0, len(text) * char_w - pixel)
    x0 = center_x - total_w * 0.5
    for ci, char in enumerate(text):
        pattern = glyphs.get(char, glyphs[" "])
        for row, bits in enumerate(pattern):
            for col, bit in enumerate(bits):
                if bit != "1":
                    continue
                x = x0 + ci * char_w + col * pixel
                y = center_y + (3 - row) * pixel
                oriented_box(mesh, material, (x, y, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                             (pixel * 0.82, pixel * 0.82, 0.08))


# ---------------------------- track architecture ---------------------------
def _add_track_arch(mesh, x, bottom_y, z0, radius, advance, color="supportSteel"):
    outer = radius + 4.5
    count = 220
    arch = []
    for i in range(count):
        u = i / (count - 1)
        theta = 2.0 * math.pi * u
        arch.append((x, bottom_y - 4.4 + outer * (1.0 - math.cos(theta)),
                     z0 + outer * math.sin(theta) + advance * u))
    frames = _open_frames(arch)
    tube_mesh(mesh, color, arch, frames, radius=0.52, sides=10, closed=False, uv_repeat=1.0)
    # Grounded feet and cross-braces anchor the arch pair.
    for side in (-1, 1):
        offset_x = x + side * 4.0
        for z in (z0, z0 + advance):
            top = (offset_x, bottom_y - 3.7, z)
            beam_between(mesh, "supportSteel", (offset_x, 0.25, z), top, 0.85)
            oriented_box(mesh, "safetyOrange", (offset_x, 0.18, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                         (2.0, 0.28, 2.0))
    # Two transverse ties make the big arch read as a portal truss.
    for theta in (math.pi * 0.5, math.pi * 1.5):
        y = bottom_y - 4.4 + outer * (1.0 - math.cos(theta))
        z = z0 + outer * math.sin(theta) + advance * theta / (2 * math.pi)
        beam_between(mesh, "crossTie", (x - 4.0, y, z), (x + 4.0, y, z), 0.45, 0.45)


def _add_supports(mesh, points, labels, frames):
    # Twin steel bents under the lift hill and high drop.
    for wanted, spacing, side_offset in (("lift", 19.0, 7.0), ("firstDrop", 20.0, 8.0),
                                          ("return", 32.0, 5.0)):
        travelled = 0.0
        next_at = spacing * 0.52
        previous = points[0]
        for i, p in enumerate(points):
            if i:
                travelled += length(sub(p, previous))
            previous = p
            if labels[i] != wanted or travelled < next_at:
                continue
            next_at = travelled + spacing
            f = frames[i]
            top_left = add(p, add(mul(f["right"], -side_offset), mul(f["up"], -0.75)))
            top_right = add(p, add(mul(f["right"], side_offset), mul(f["up"], -0.75)))
            base_z = p[2]
            base_left = (p[0] - side_offset, 0.25, base_z)
            base_right = (p[0] + side_offset, 0.25, base_z)
            beam_between(mesh, "supportSteel", base_left, top_left, 0.72)
            beam_between(mesh, "supportSteel", base_right, top_right, 0.72)
            beam_between(mesh, "crossTie", top_left, top_right, 0.58, 0.58)
            # Concrete pads and alternating X-braces keep the supports legible.
            oriented_box(mesh, "stationConcrete", (base_left[0], 0.14, base_left[2]),
                         (1, 0, 0), (0, 1, 0), (0, 0, 1), (2.2, 0.28, 2.2))
            oriented_box(mesh, "stationConcrete", (base_right[0], 0.14, base_right[2]),
                         (1, 0, 0), (0, 1, 0), (0, 0, 1), (2.2, 0.28, 2.2))
            if wanted != "return" and i + 30 < len(points):
                next_i = i + 30
                if labels[next_i] == wanted:
                    nf = frames[next_i]
                    nl = add(points[next_i], add(mul(nf["right"], -side_offset), mul(nf["up"], -0.75)))
                    nr = add(points[next_i], add(mul(nf["right"], side_offset), mul(nf["up"], -0.75)))
                    beam_between(mesh, "supportSteel", top_left, nr, 0.28, 0.32)
                    beam_between(mesh, "supportSteel", top_right, nl, 0.28, 0.32)


def _add_helix_tower(mesh):
    cx, cz = 38.0, 230.0
    half = 3.2
    levels = (0.25, 8.0, 16.0, 24.0, 32.5)
    corners = ((cx - half, cz - half), (cx + half, cz - half),
               (cx + half, cz + half), (cx - half, cz + half))
    for x, z in corners:
        beam_between(mesh, "supportSteel", (x, 0.2, z), (x, 34.0, z), 0.72)
        oriented_box(mesh, "stationConcrete", (x, 0.14, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                     (2.1, 0.28, 2.1))
    for y in levels[1:-1]:
        for i in range(4):
            x1, z1 = corners[i]
            x2, z2 = corners[(i + 1) % 4]
            beam_between(mesh, "crossTie", (x1, y, z1), (x2, y, z2), 0.42)
        # X-braced faces, kept inside the compact central tower.
        for i in (0, 1):
            a = corners[i]
            b = corners[(i + 1) % 4]
            beam_between(mesh, "supportSteel", (a[0], y - 7.75, a[1]),
                         (b[0], y, b[1]), 0.22, 0.26)
            beam_between(mesh, "supportSteel", (b[0], y - 7.75, b[1]),
                         (a[0], y, a[1]), 0.22, 0.26)


def _dome_point(theta, z, half_width, wall_y, dome_height):
    return (half_width * math.cos(theta), wall_y + dome_height * math.sin(theta), z)


def _add_station_dome(structure, glass, leds):
    """Build a translucent barrel-vault station hall with restrained LED trim."""
    half_width = 15.5
    wall_y = 6.25
    wall_floor_y = 2.65
    dome_height = 12.2
    z_min, z_max = -12.0, 30.0
    rib_count = 8
    z_ribs = [z_min + (z_max - z_min) * i / rib_count for i in range(rib_count + 1)]
    z_panels = [z_min + (z_max - z_min) * i / 10 for i in range(11)]
    angle_count = 16
    angles = [math.pi * i / angle_count for i in range(angle_count + 1)]

    # Each rib is a continuous curved truss, supported by glazed side walls.
    arch_angles = [math.pi * i / 32 for i in range(33)]
    for z in z_ribs:
        arch = [_dome_point(theta, z, half_width, wall_y, dome_height)
                for theta in arch_angles]
        tube_mesh(structure, "stationSteel", arch, _open_frames(arch),
                  radius=0.24, sides=10, closed=False)
        for side in (-1, 1):
            beam_between(structure, "stationSteel",
                         (side * half_width, wall_floor_y, z),
                         (side * half_width, wall_y, z), 0.26)

    # Longitudinal purlins stiffen the vault and make its curved glass bays legible.
    for i in range(9):
        theta = math.pi * i / 8
        line = [_dome_point(theta, z, half_width, wall_y, dome_height) for z in z_ribs]
        tube_mesh(structure, "crossTie", line, _open_frames(line),
                  radius=0.095, sides=8, closed=False)
    for side in (-1, 1):
        for y in (3.0, 4.6):
            line = [(side * half_width, y, z) for z in z_ribs]
            tube_mesh(structure, "stationSteel", line, _open_frames(line),
                      radius=0.09, sides=8, closed=False)

    # Translucent roof panels follow the barrel-vault curve; each pane is
    # double-sided so players see glass both from the platform and outdoors.
    for z0, z1 in zip(z_panels, z_panels[1:]):
        for theta0, theta1 in zip(angles, angles[1:]):
            points = (
                _dome_point(theta0, z0, half_width, wall_y, dome_height),
                _dome_point(theta1, z0, half_width, wall_y, dome_height),
                _dome_point(theta1, z1, half_width, wall_y, dome_height),
                _dome_point(theta0, z1, half_width, wall_y, dome_height),
            )
            theta_mid = 0.5 * (theta0 + theta1)
            normal = unit((math.cos(theta_mid) / half_width,
                           math.sin(theta_mid) / dome_height, 0.0))
            _double_sided_glass_quad(glass, points, normal)

    # Glazed lower side walls, split into smaller panes beneath the shoulders.
    wall_levels = (wall_floor_y, 4.45, wall_y)
    for side in (-1, 1):
        for z0, z1 in zip(z_panels, z_panels[1:]):
            for y0, y1 in zip(wall_levels, wall_levels[1:]):
                points = (
                    (side * half_width, y0, z0),
                    (side * half_width, y1, z0),
                    (side * half_width, y1, z1),
                    (side * half_width, y0, z1),
                )
                _double_sided_glass_quad(glass, points, (side, 0.0, 0.0))

    # Five luminous roof ribbons and two platform-edge guides create the
    # cyan/violet station glow without relying on expensive dynamic lights.
    for i, theta in enumerate((math.pi / 8, 3 * math.pi / 8, math.pi / 2,
                               5 * math.pi / 8, 7 * math.pi / 8)):
        line = [_dome_point(theta, z, half_width, wall_y, dome_height)
                for z in z_ribs]
        material = "neonCyan" if i % 2 == 0 else "neonViolet"
        tube_mesh(leds, material, line, _open_frames(line),
                  radius=0.085, sides=7, closed=False)
    for side in (-1, 1):
        line = [(side * 7.7, 2.06, z) for z in (-4.0, 2.0, 8.0, 14.0, 20.0, 24.0)]
        tube_mesh(leds, "neonCyan", line, _open_frames(line),
                  radius=0.065, sides=7, closed=False)


def _add_station(mesh):
    # Boarding deck, cantilevered steel underframe, queue rails and glass hall.
    oriented_box(mesh, "stationConcrete", (0.0, 1.40, 9.5), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (16.0, 0.42, 31.0))
    oriented_box(mesh, "stationBlue", (0.0, 1.64, 9.5), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (16.15, 0.12, 31.1))
    # The former solid canopy is replaced by the glass barrel-vault built in
    # _add_station_dome(), keeping the platform open and the track unobstructed.
    # Guardrails along the boarding platform with yellow gate panels.
    for x in (-7.2, 7.2):
        beam_between(mesh, "supportSteel", (x, 1.75, -4.0), (x, 2.95, 23.0), 0.16)
        beam_between(mesh, "safetyOrange", (x, 2.72, -4.0), (x, 2.72, 23.0), 0.15)
        for z in (-3.0, 1.0, 5.0, 9.0, 13.0, 17.0, 21.0):
            beam_between(mesh, "supportSteel", (x, 1.65, z), (x, 2.72, z), 0.12)
    # Queue lanes, two short switchback rails per side.
    for x in (-5.3, -2.8, 2.8, 5.3):
        beam_between(mesh, "metalBright", (x, 1.7, -3.5), (x, 2.2, 3.5), 0.10)
        beam_between(mesh, "metalBright", (x, 1.7, 11.5), (x, 2.2, 20.5), 0.10)
    # Fascia/sign: pixel-built letters on a blue panel.
    oriented_box(mesh, "stationBlue", (0.0, 7.42, -4.75), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (15.0, 2.0, 0.36))
    add_text_pixels(mesh, "HOHENSTURM", 0.0, 7.42, -4.98, pixel=0.17, material="neonCyan")
    add_text_pixels(mesh, "56 M INVERSION", 0.0, 6.84, -4.98, pixel=0.095, material="safetyYellow")
    # Stair / access ramp at the near end of the station.
    for i in range(7):
        z = -5.0 - i * 1.15
        y = 1.14 - i * 0.16
        oriented_box(mesh, "stationConcrete", (9.0, y, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                     (3.0, 0.18, 1.3))
    beam_between(mesh, "safetyOrange", (10.1, 0.35, -12.5), (10.1, 1.9, -4.5), 0.12)


def _add_led_hoop(mesh, center, frame, radius, material):
    """Place a bright, low-poly ring around the track frame."""
    ring_points = []
    ring_frames = []
    segments = 32
    for i in range(segments):
        theta = 2.0 * math.pi * i / segments
        cosine, sine = math.cos(theta), math.sin(theta)
        radial = unit(add(mul(frame["right"], cosine), mul(frame["up"], sine)))
        tangent = unit(add(mul(frame["right"], -sine), mul(frame["up"], cosine)))
        ring_points.append(add(center, mul(radial, radius)))
        ring_frames.append({
            "right": unit(cross(radial, tangent)),
            "up": radial,
            "tangent": tangent,
        })
    tube_mesh(mesh, material, ring_points, ring_frames, radius=0.105,
              sides=7, closed=True, uv_repeat=1.0)


def _add_light_node(parent, name, position, color, radius):
    parent.add(Node("Light", name,
                    translation="%.3f %.3f %.3f" % tuple(position),
                    type="point", color=color, emitDiffuse="true",
                    emitSpecular="false", castShadowMap="false",
                    range="%.1f" % radius))


def _add_loop_tunnels(mesh, points, labels, frames):
    """Build close-spaced LED hoops around the two loops and rising spiral."""
    palette = ("neonCyan", "neonViolet", "neonMagenta")
    spacing = length(sub(points[1], points[0]))
    stride = max(1, int(round(6.5 / max(spacing, 1e-6))))
    count = 0
    for tag in ("loop1", "spiral", "loop2"):
        indices = [i for i, label in enumerate(labels) if label == tag]
        if len(indices) < stride:
            continue
        for local_index in range(stride // 2, len(indices) - stride // 2, stride):
            i = indices[local_index]
            _add_led_hoop(mesh, points[i], frames[i], 3.35,
                          palette[(count + local_index // stride) % len(palette)])
            count += 1
    return count


def build_track_scene(points, labels, frames):
    root = Node("TransformGroup", "coasterRoot")
    visuals = root.add(Node("TransformGroup", "coasterVisuals"))

    rails = Mesh()
    # Twin running rails, blue energy strip, a central spine and anti-roll ties.
    for offset in (-0.86, 0.86):
        tube_mesh(rails, "trackSteel", points, frames, radius=0.145, sides=10,
                  offset_right=offset, offset_up=0.0, closed=True, uv_repeat=72.0)
        tube_mesh(rails, "neonCyan", points, frames, radius=0.035, sides=7,
                  offset_right=offset, offset_up=0.17, closed=True, uv_repeat=72.0)
    tube_mesh(rails, "supportSteel", points, frames, radius=0.105, sides=8,
              offset_right=0.0, offset_up=-0.62, closed=True, uv_repeat=72.0)

    ties = Mesh()
    for i in range(0, len(points), 5):
        p, f = points[i], frames[i]
        center = add(p, mul(f["up"], -0.34))
        oriented_box(ties, "crossTie", center, f["right"], f["up"], f["tangent"],
                     (2.45, 0.23, 0.28))
        # Orange maintenance clips beside both running rails.
        for side in (-1, 1):
            clip_center = add(p, add(mul(f["right"], side * 0.86), mul(f["up"], -0.21)))
            oriented_box(ties, "safetyOrange", clip_center, f["right"], f["up"], f["tangent"],
                         (0.28, 0.11, 0.36))

    visuals.add(Node("Shape", "trackRails", rails, materials=rails.order,
                     castsShadows="true", receiveShadows="true"))
    visuals.add(Node("Shape", "trackTies", ties, materials=ties.order,
                     castsShadows="true", receiveShadows="true"))

    supports = Mesh()
    station_glass = Mesh()
    station_leds = Mesh()
    tunnel_leds = Mesh()
    _add_supports(supports, points, labels, frames)
    _add_track_arch(supports, 20.0, 7.0, 180.0, 15.5, 11.0)
    _add_track_arch(supports, 60.0, 7.0, 270.0, 12.5, 9.0)
    _add_helix_tower(supports)
    _add_station(supports)
    _add_station_dome(supports, station_glass, station_leds)
    tunnel_count = _add_loop_tunnels(tunnel_leds, points, labels, frames)
    visuals.add(Node("Shape", "steelSupportsAndStation", supports, materials=supports.order,
                     castsShadows="true", receiveShadows="true"))
    visuals.add(Node("Shape", "stationGlass", station_glass, materials=station_glass.order,
                     castsShadows="false", receiveShadows="true"))
    visuals.add(Node("Shape", "stationLEDs", station_leds, materials=station_leds.order,
                     castsShadows="false", receiveShadows="false"))
    visuals.add(Node("Shape", "inversionLightTunnels", tunnel_leds, materials=tunnel_leds.order,
                     castsShadows="false", receiveShadows="false"))

    # A small number of no-shadow point lights provide real color spill; the
    # surrounding LED mesh carries the effect at much lower runtime cost.
    effect_lights = visuals.add(Node("TransformGroup", "rideEffectLights"))
    for name, position, color in (
        ("stationGlowLeft", (-7.5, 10.0, 4.0), "0.12 0.78 1.0"),
        ("stationGlowRight", (7.5, 10.0, 18.0), "0.60 0.22 1.0"),
        ("stationGlowFront", (0.0, 8.0, -7.0), "0.08 0.60 1.0"),
    ):
        _add_light_node(effect_lights, name, position, color, 22.0)
    for tag, color in (("loop1", "0.10 0.80 1.0"),
                       ("spiral", "0.62 0.18 1.0"),
                       ("loop2", "1.0 0.16 0.60")):
        indices = [i for i, label in enumerate(labels) if label == tag]
        for j, fraction in enumerate((0.30, 0.70)):
            if not indices:
                continue
            index = indices[int((len(indices) - 1) * fraction)]
            point, frame = points[index], frames[index]
            light_pos = add(point, add(mul(frame["right"], 3.8), mul(frame["up"], 1.5)))
            _add_light_node(effect_lights, tag + "Accent%d" % j,
                            light_pos, color, 20.0)
    # Kept as a generation invariant so the light tunnel cannot silently vanish.
    if tunnel_count < 40:
        raise ValueError("expected at least 40 LED hoops across the inversions, got %d" % tunnel_count)

    # Invisible NURBS placeholder is replaced by the build script with the
    # closed linear curve.  Keeping it in the scene tree gives the train-system
    # XML a normal, generated i3dMapping.
    curve_stub = Mesh()
    spline_node = root.add(Node("Shape", "coasterSpline", curve_stub,
                                visibility="false", castsShadows="false",
                                receiveShadows="false"))
    root.add(Node("TransformGroup", "rentMarker", translation="4.2 1.8 8.0"))
    root.add(Node("TransformGroup", "teleportNode", translation="3.2 1.7 12.5", rotation="0 180 0"))
    root.add(Node("TransformGroup", "placementStart", translation="-88 0 -55"))
    root.add(Node("TransformGroup", "placementEnd", translation="88 0 305"))
    root.add(Node("TransformGroup", "clearStart", translation="-90 0 -60"))
    root.add(Node("TransformGroup", "clearWidth", translation="90 0 -60"))
    root.add(Node("TransformGroup", "clearHeight", translation="-90 0 310"))
    return root, spline_node


# ------------------------------- car model ----------------------------------
def _seat_detail(mesh, x, z, driver=False):
    # Four sculpted bucket seats with steel side bolsters.
    oriented_box(mesh, "seatFabric", (x, 0.64, z), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (0.80, 0.24, 0.92))
    oriented_box(mesh, "seatCushion", (x, 0.79, z - 0.22), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (0.66, 0.18, 0.48))
    oriented_box(mesh, "seatFabric", (x, 1.15, z - 0.35), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (0.72, 0.78, 0.20))
    for side in (-1, 1):
        beam_between(mesh, "safetyOrange", (x + side * 0.37, 0.76, z - 0.54),
                     (x + side * 0.37, 1.32, z - 0.34), 0.12)
    # Individual over-the-lap restraint: bright yellow, wide and unmistakable.
    bar = Mesh()
    arc = []
    for i in range(21):
        a = math.pi * i / 20
        arc.append((x + 0.45 * math.cos(a), 0.91 + 0.35 * math.sin(a), z + 0.36))
    bar_frames = _open_frames(arc)
    tube_mesh(bar, "safetyYellow", arc, bar_frames, 0.085, sides=8, closed=False)
    mesh.merge(bar)
    # Small release handle at the right hip.
    oriented_box(mesh, "safetyOrange", (x + 0.52, 0.94, z + 0.31),
                 (1, 0, 0), (0, 1, 0), (0, 0, 1), (0.13, 0.10, 0.22))
    if driver:
        # The manual speed control is represented by an illuminated dash, not a steering wheel.
        oriented_box(mesh, "stationBlue", (x, 1.36, z + 0.72), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                     (0.70, 0.32, 0.18))
        oriented_box(mesh, "neonCyan", (x, 1.38, z + 0.82), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                     (0.44, 0.12, 0.04))


def _seat_character_nodes(parent, prefix, seat_index, camera_translation, exit_translation,
                          skin_translation=(0.0, 0.0, 0.0)):
    parent.add(Node("TransformGroup", prefix + "PlayerSkin", translation="%.3f %.3f %.3f" % skin_translation))
    parent.add(Node("TransformGroup", prefix + "RightFoot", translation="0.18 0.04 0.55"))
    parent.add(Node("TransformGroup", prefix + "LeftFoot", translation="-0.18 0.04 0.55"))
    parent.add(Node("TransformGroup", prefix + "RightHand", translation="0.28 0.72 0.16"))
    parent.add(Node("TransformGroup", prefix + "LeftHand", translation="-0.28 0.72 0.16"))
    parent.add(Node("TransformGroup", prefix + "ExitPoint",
                    translation="%.3f %.3f %.3f" % exit_translation))
    parent.add(Node("TransformGroup", prefix + "Camera", translation="%.3f %.3f %.3f" % camera_translation,
                    rotation="-5 0 0"))


def build_car_scene():
    # Local origin is the rail/heartline reference used by SplineVehicle.
    body = Mesh()
    # Low central spine, bumper, nose and end plates.
    oriented_box(body, "supportSteel", (0.0, 0.12, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (1.75, 0.34, 3.95))
    oriented_box(body, "safetyOrange", (0.0, 0.33, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (2.20, 0.28, 4.45))
    oriented_box(body, "stationBlue", (0.0, 0.48, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (2.02, 0.16, 4.16))
    oriented_box(body, "metalBright", (0.0, 0.55, 0.15), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (1.75, 0.12, 2.35))

    # Front/rear cowls and four protective side rails.
    oriented_box(body, "safetyOrange", (0.0, 0.70, 1.78), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (1.92, 0.64, 0.58))
    oriented_box(body, "safetyOrange", (0.0, 0.70, -1.78), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                 (1.92, 0.64, 0.58))
    for x in (-0.98, 0.98):
        beam_between(body, "supportSteel", (x, 0.52, -1.55), (x, 1.35, -1.2), 0.18)
        beam_between(body, "supportSteel", (x, 0.52, 1.55), (x, 1.35, 1.2), 0.18)
        beam_between(body, "safetyOrange", (x, 0.78, -1.2), (x, 0.78, 1.2), 0.16)
    # Side bumpers, polished end caps and compact headlights.
    for side in (-1, 1):
        oriented_box(body, "metalBright", (side * 1.09, 0.72, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1),
                     (0.12, 0.18, 3.72))
        body.add("neonCyan", *place(sphere((0, 0, 0), 0.09, 12, 8),
                                    translation=(side * 0.70, 0.92, 2.10)))
        body.add("safetyYellow", *place(sphere((0, 0, 0), 0.055, 10, 6),
                                        translation=(side * 0.70, 0.90, -2.08)))

    # Four individual positions in a true 2 x 2 layout: one operator + 3 riders.
    seat_positions = [(0.48, 0.62), (-0.48, 0.62), (0.48, -0.57), (-0.48, -0.57)]
    for i, (x, z) in enumerate(seat_positions):
        _seat_detail(body, x, z, driver=(i == 0))

    # Mechanical bogies and six rubber wheels are decorative; train motion is
    # supplied by the native FS25 train-system spline.
    for z in (-1.36, 0.0, 1.36):
        for side in (-1, 1):
            wheel = cylinder(0.28, -0.12, 0.12, 18, caps=True)
            body.add("rubber", *place(wheel, translation=(side * 0.78, 0.02, z), rot=(0, 0, 90)))
            body.add("metalBright", *place(torus(0.18, 0.035, 0, 20, 6),
                                            translation=(side * 0.78, 0.02, z), rot=(0, 0, 90)))

    root = Node("Shape", "coasterCar_main_component1", mesh=body, materials=body.order,
                dynamic="true", compound="true", collisionFilterGroup="0x10004",
                collisionFilterMask="0xfe3ffb83", clipDistance="300",
                castsShadows="true", receiveShadows="true")
    # SplineVehicle reference nodes, wheel animation nodes and camera targets.
    root.add(Node("TransformGroup", "frontNode", translation="0 0 2.10"))
    root.add(Node("TransformGroup", "backNode", translation="0 0 -2.10"))
    root.add(Node("TransformGroup", "dollyFrontNode", translation="0 0 1.35"))
    root.add(Node("TransformGroup", "dollyBackNode", translation="0 0 -1.35"))
    root.add(Node("TransformGroup", "wheel01", translation="-0.78 0.02 1.36"))
    root.add(Node("TransformGroup", "wheel02", translation="0.78 0.02 1.36"))
    root.add(Node("TransformGroup", "wheel03", translation="-0.78 0.02 -1.36"))
    root.add(Node("TransformGroup", "wheel04", translation="0.78 0.02 -1.36"))
    root.add(Node("TransformGroup", "surfaceSoundNode", translation="0 0 0"))
    root.add(Node("TransformGroup", "enterNode", translation="0 0.8 1.8"))
    root.add(Node("TransformGroup", "exitPoint", translation="1.55 0.05 -0.5"))
    root.add(Node("TransformGroup", "driverSeatNode", translation="0.48 0.88 0.62"))
    root.add(Node("TransformGroup", "driverRightFoot", translation="0.30 0.04 1.17"))
    root.add(Node("TransformGroup", "driverLeftFoot", translation="0.66 0.04 1.17"))
    root.add(Node("TransformGroup", "driverRightHand", translation="0.20 1.60 0.78"))
    root.add(Node("TransformGroup", "driverLeftHand", translation="0.76 1.60 0.78"))
    root.add(Node("TransformGroup", "outdoorCameraTarget", translation="0 1.45 0"))
    root.add(Node("Camera", "outdoorCamera", translation="0 2.8 -8.7", rotation="-5 180 0",
                  fov="45", nearClip="0.05", farClip="3500"))
    root.add(Node("Camera", "indoorCamera", translation="-0.48 2.05 0.62", rotation="-3 0 0",
                  fov="72", nearClip="0.03", farClip="3500"))
    root.add(Node("TransformGroup", "soundMotor", translation="0 0.8 0"))

    # Passenger seats #1-3 complete the 2x2 grid; the operator occupies front-left.
    seat_groups = [
        ("passengerSeat01", -0.48, 0.62, (-1.45, 0.05, 0.72)),
        ("passengerSeat02", 0.48, -0.57, (1.45, 0.05, -0.45)),
        ("passengerSeat03", -0.48, -0.57, (-1.45, 0.05, -0.45)),
    ]
    for prefix, x, z, exit_pos in seat_groups:
        group = root.add(Node("TransformGroup", prefix, translation="%.3f 0.88 %.3f" % (x, z)))
        group.add(Node("TransformGroup", prefix + "PlayerSkin"))
        group.add(Node("TransformGroup", prefix + "PlayerRightFoot", translation="-0.18 -0.84 0.55"))
        group.add(Node("TransformGroup", prefix + "PlayerLeftFoot", translation="0.18 -0.84 0.55"))
        group.add(Node("TransformGroup", prefix + "PlayerRightHand", translation="-0.28 -0.16 0.16"))
        group.add(Node("TransformGroup", prefix + "PlayerLeftHand", translation="0.28 -0.16 0.16"))
        group.add(Node("TransformGroup", prefix + "ExitPoint",
                       translation="%.3f %.3f %.3f" % exit_pos))
        group.add(Node("Camera", prefix + "Camera", translation="0 1.17 0.04",
                       rotation="-3 0 0", fov="72", nearClip="0.03", farClip="3500"))
    # Driver camera target and one small service/battery panel.
    root.add(Node("TransformGroup", "driverCharacterNode", translation="0 0 0"))
    return root


def renderer_materials():
    """Return the software-renderer colour/gloss values for our materials."""
    return {
        "collision": None,
        "trackSteel": ((0.055, 0.25, 0.69), 0.78, 0.05, 1.0),
        "supportSteel": ((0.055, 0.09, 0.15), 0.66, 0.0, 1.0),
        "crossTie": ((0.22, 0.28, 0.34), 0.35, 0.0, 1.0),
        "safetyOrange": ((1.0, 0.25, 0.035), 0.52, 0.05, 1.0),
        "safetyYellow": ((1.0, 0.76, 0.045), 0.42, 0.04, 1.0),
        "seatFabric": ((0.14, 0.035, 0.065), 0.25, 0.0, 1.0),
        "seatCushion": ((0.62, 0.055, 0.07), 0.24, 0.0, 1.0),
        "stationConcrete": ((0.43, 0.49, 0.55), 0.16, 0.0, 1.0),
        "stationSteel": ((0.07, 0.12, 0.20), 0.58, 0.0, 1.0),
        "stationBlue": ((0.035, 0.14, 0.30), 0.48, 0.0, 1.0),
        "glassBlue": ((0.08, 0.48, 0.70), 0.84, 0.0, 0.24),
        "neonCyan": ((0.025, 0.94, 1.0), 0.2, 0.92, 1.0),
        "neonViolet": ((0.40, 0.10, 1.0), 0.22, 1.05, 1.0),
        "neonMagenta": ((1.0, 0.06, 0.58), 0.20, 0.95, 1.0),
        "neonAmber": ((1.0, 0.42, 0.06), 0.32, 0.72, 1.0),
        "rubber": ((0.022, 0.025, 0.032), 0.7, 0.0, 1.0),
        "metalBright": ((0.68, 0.77, 0.85), 0.82, 0.03, 1.0),
    }
