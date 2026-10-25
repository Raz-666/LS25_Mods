# SPDX-License-Identifier: GPL-3.0-or-later
"""Sculpting helpers on top of :mod:`meshlib`.

``meshlib`` gives us the primitives (sphere, lathe, box, torus).  This module
adds the things a character or a cockpit actually needs:

* ``deform`` - push every vertex of a primitive through a function, so a plain
  sphere becomes a head with a jaw, cheeks and a brow;
* ``recalc_normals`` - after such a deformation the old normals are wrong, so
  they are rebuilt from the triangles;
* ``tube`` - sweep a circle along a polyline (antennae, fingers, cables, roll
  bars, beam swirls) with parallel transport so the tube does not twist;
* ``sphere_uv`` / ``blob`` - a UV sphere with a smooth, per-ring radius table;
* ``ring_arc`` - a partial torus (eyelids, handles, cockpit dials);
* ``panel`` - a slightly domed plate for hull panelling;
* ``bevel_box`` - a box with chamfered edges, for instrument housings.

Everything returns the usual ``(verts, normals, uvs, tris)`` tuple, so it can
be fed straight into :class:`meshlib.Mesh`.
"""

import math

from meshlib import Mesh, place, sphere, torus  # noqa: F401  (re-export for convenience)

TAU = 2.0 * math.pi


# --------------------------------------------------------------------------
# geometry utilities
# --------------------------------------------------------------------------
def recalc_normals(verts, tris):
    """Area-weighted vertex normals from the triangle list."""
    normals = [[0.0, 0.0, 0.0] for _ in verts]
    for a, b, c in tris:
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        ux, uy, uz = bx - ax, by - ay, bz - az
        vx, vy, vz = cx - ax, cy - ay, cz - az
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        for i in (a, b, c):
            normals[i][0] += nx
            normals[i][1] += ny
            normals[i][2] += nz
    out = []
    for nx, ny, nz in normals:
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        out.append((nx / length, ny / length, nz / length))
    return out


def deform(geom, fn, recalc=True):
    """Map every vertex through ``fn(x, y, z) -> (x, y, z)``."""
    verts, normals, uvs, tris = geom
    new = [tuple(fn(*v)) for v in verts]
    if recalc:
        normals = recalc_normals(new, tris)
    return new, list(normals), list(uvs), list(tris)


def smoothstep(edge0, edge1, x):
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def sphere_uv(radius=1.0, segments=32, rings=20, profile=None):
    """A UV sphere whose radius can be modulated per latitude.

    ``profile(t)`` gets ``t`` in 0 (south pole) .. 1 (north pole) and returns a
    multiplier, which is how the egg-shaped heads and bellies are made.
    """
    verts, uvs, tris = [], [], []
    for i in range(rings + 1):
        v = i / rings
        phi = math.pi * v
        ry = math.cos(phi)
        rr = math.sin(phi)
        scale = 1.0 if profile is None else profile(v)
        for j in range(segments + 1):
            u = j / segments
            theta = TAU * u
            verts.append((radius * rr * math.cos(theta) * scale,
                          radius * ry * scale,
                          radius * rr * math.sin(theta) * scale))
            uvs.append((u, v))
    for i in range(rings):
        for j in range(segments):
            a = i * (segments + 1) + j
            b = a + segments + 1
            tris += [(a, b, a + 1), (a + 1, b, b + 1)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def yaw_ring(radius_z, radius_x, y, segments=16, closed=True):
    """A closed ellipse on the XZ plane at height ``y`` (belt, ring, seam)."""
    verts, uvs, tris = [], [], []
    for i in range(segments):
        a = TAU * i / segments
        verts.append((math.cos(a) * radius_x, y, math.sin(a) * radius_z))
        uvs.append((i / segments, 0.0))
    for i in range(segments):
        j = (i + 1) % segments
        k = segments + i
        tris.append((i, j, i))
    return verts, [], uvs, tris


def shell_band(radius_z, radius_x, y, height, thickness=0.012, segments=24):
    """A belt / seam / collar: a short hollow tube ring around the body."""
    verts, uvs, tris = [], [], []
    for i in range(segments):
        a = TAU * i / segments
        for (dx, dz, yy) in ((math.cos(a), math.sin(a), y + height * 0.5),
                             (math.cos(a), math.sin(a), y - height * 0.5)):
            verts.append((dz * radius_x, yy, dx * radius_z))
            uvs.append((i / segments, 0.0 if yy > y else 1.0))
    for i in range(segments):
        j = (i + 1) % segments
        # outer wall
        tris += [(i * 2, j * 2, i * 2 + 1), (j * 2, j * 2 + 1, i * 2 + 1)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def spherical_cap(radius, max_angle_deg, segments=32, rings=10):
    """A cap of a sphere around +Y, used for eyes, lens covers and domes.

    Nested caps of slightly growing radius make a clean eye (sclera -> iris ->
    pupil) without a single intersecting surface, which is what used to cause
    the ugly z-fighting on the mascot's eyes.
    """
    angle = math.radians(max_angle_deg)
    verts, uvs, tris = [], [], []
    for i in range(rings + 1):
        t = i / rings
        a = angle * t
        rr = radius * math.sin(a)
        yy = radius * math.cos(a)
        for j in range(segments + 1):
            u = j / segments
            th = TAU * u
            verts.append((rr * math.cos(th), yy, rr * math.sin(th)))
            uvs.append((u, t))
    for i in range(rings):
        for j in range(segments):
            a0 = i * (segments + 1) + j
            b0 = a0 + segments + 1
            tris += [(a0, a0 + 1, b0), (a0 + 1, b0 + 1, b0)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def tube(points, radii, segments=12, caps=True, uv_scale=1.0):
    """Sweep a circle along a polyline (parallel transport frames).

    ``points`` are the centre line, ``radii`` one radius per point - either a
    number for all points or a list.
    """
    if not isinstance(radii, (list, tuple)):
        radii = [radii] * len(points)
    # tangents
    tangents = []
    for i in range(len(points)):
        if i == 0:
            t = _sub(points[1], points[0])
        elif i == len(points) - 1:
            t = _sub(points[-1], points[-2])
        else:
            t = _sub(points[i + 1], points[i - 1])
        tangents.append(_norm(t))
    # an arbitrary start frame, then transport it along the curve
    up = (0.0, 1.0, 0.0)
    if abs(_dot(tangents[0], up)) > 0.95:
        up = (1.0, 0.0, 0.0)
    normal = _norm(_cross(tangents[0], up))
    frames = []
    for i, t in enumerate(tangents):
        if i:
            # remove the part of the previous normal that is parallel to t
            d = _dot(normal, t)
            normal = _norm(_sub(normal, _mul(t, d)))
        frames.append((normal, _norm(_cross(t, normal))))

    verts, uvs, tris = [], [], []
    total = 0.0
    lengths = [0.0]
    for i in range(1, len(points)):
        total += _len(_sub(points[i], points[i - 1]))
        lengths.append(total)
    for i, p in enumerate(points):
        n, b = frames[i]
        r = radii[i]
        v = lengths[i] * uv_scale
        for j in range(segments + 1):
            a = TAU * j / segments
            ca, sa = math.cos(a), math.sin(a)
            verts.append((p[0] + (n[0] * ca + b[0] * sa) * r,
                          p[1] + (n[1] * ca + b[1] * sa) * r,
                          p[2] + (n[2] * ca + b[2] * sa) * r))
            uvs.append((j / segments, v))
    for i in range(len(points) - 1):
        for j in range(segments):
            a = i * (segments + 1) + j
            b = a + segments + 1
            tris += [(a, b, a + 1), (a + 1, b, b + 1)]
    if caps:
        base = len(verts)
        verts.append(tuple(points[0]))
        uvs.append((0.5, 0.0))
        for j in range(segments):
            tris.append((base, j + 1, j))
        base2 = len(verts)
        verts.append(tuple(points[-1]))
        uvs.append((0.5, 1.0))
        ring = (len(points) - 1) * (segments + 1)
        for j in range(segments):
            tris.append((base2, ring + j, ring + j + 1))
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def ring_arc(radius, tube_r, start_deg, end_deg, y=0.0, segments=32, sides=8):
    """A partial torus - eyelids, roll bars, gauge bezels."""
    verts, uvs, tris = [], [], []
    span = math.radians(end_deg - start_deg)
    for i in range(segments + 1):
        t = i / segments
        a = math.radians(start_deg) + span * t
        cx, cz = math.cos(a) * radius, math.sin(a) * radius
        for j in range(sides + 1):
            b = TAU * j / sides
            rr = radius + tube_r * math.cos(b)
            verts.append((math.cos(a) * rr, y + tube_r * math.sin(b),
                          math.sin(a) * rr))
            uvs.append((t, j / sides))
    for i in range(segments):
        for j in range(sides):
            a = i * (sides + 1) + j
            b = a + sides + 1
            tris += [(a, b, a + 1), (a + 1, b, b + 1)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def bevel_box(size, bevel=0.02, segments=1):
    """A box with rounded edges, built as a lathe-free hull of 8 corners.

    Cheap approximation: an axis aligned box whose corner vertices are pulled
    slightly inwards towards the centre, plus a chamfer ring so the silhouette
    catches light.
    """
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    b = bevel
    verts, uvs, tris = [], [], []
    # three stacked rectangles: bottom chamfer, body, top chamfer
    levels = [(-sy, sx - b, sz - b), (-sy + b, sx, sz),
              (sy - b, sx, sz), (sy, sx - b, sz - b)]
    for (y, ex, ez) in levels:
        for (dx, dz) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            verts.append((dx * ex, y, dz * ez))
            uvs.append((0.5 + dx * 0.5, 0.5 + dz * 0.5))
    for i in range(3):
        a = i * 4
        b2 = a + 4
        for j in range(4):
            k = (j + 1) % 4
            tris += [(a + j, b2 + j, a + k), (a + k, b2 + j, b2 + k)]
    # caps
    tris += [(0, 2, 1), (0, 3, 2)]
    base = 12
    tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def panel(width, height, bulge=0.0, segments=6, tiles=1.0):
    """A slightly domed plate, for hull panelling and cockpit dial faces."""
    verts, uvs, tris = [], [], []
    for i in range(segments + 1):
        v = i / segments
        for j in range(segments + 1):
            u = j / segments
            x = (u - 0.5) * width
            z = (v - 0.5) * height
            y = bulge * math.sin(math.pi * u) * math.sin(math.pi * v)
            verts.append((x, y, z))
            uvs.append((u * tiles, v * tiles))
    row = segments + 1
    for i in range(segments):
        for j in range(segments):
            a = i * row + j
            b = a + row
            tris += [(a, b, a + 1), (a + 1, b, b + 1)]
    normals = recalc_normals(verts, tris)
    return verts, normals, uvs, tris


def zigzag_ring(radius, y, count=12, depth=0.05):
    """A ring of small teeth - knurled knobs, rivet rows, gear rims."""
    m = Mesh()
    for i in range(count):
        a = TAU * i / count
        m.add("__tmp__", *place(
            bevel_box((depth * 2, depth * 1.2, depth * 1.2), bevel=depth * 0.4),
            rot=(0, -math.degrees(a), 0),
            translation=(math.cos(a) * radius, y, math.sin(a) * radius)))
    return m


# --------------------------------------------------------------------------
# tiny vector helpers
# --------------------------------------------------------------------------
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(a):
    return math.sqrt(_dot(a, a))


def _norm(a):
    length = _len(a) or 1.0
    return (a[0] / length, a[1] / length, a[2] / length)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def bezier(p0, p1, p2, p3, steps=10):
    """Cubic bezier sample points - for curved antennae and cables."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1.0 - t
        x = (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] +
             3 * mt * t * t * p2[0] + t ** 3 * p3[0])
        y = (mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] +
             3 * mt * t * t * p2[1] + t ** 3 * p3[1])
        z = (mt ** 3 * p0[2] + 3 * mt * mt * t * p1[2] +
             3 * mt * t * t * p2[2] + t ** 3 * p3[2])
        out.append((x, y, z))
    return out


def radii_curve(steps, r0, r1, power=1.0):
    return [r0 + (r1 - r0) * ((i / steps) ** power) for i in range(steps + 1)]
