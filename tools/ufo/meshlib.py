# SPDX-License-Identifier: GPL-3.0-or-later
"""Tiny procedural mesh toolkit for GIANTS i3d 1.6 (FS25).

Everything is plain Python lists; geometry is built in the vehicle component
space (metres, Y up, +Z forward, +X left).  A ``Mesh`` collects triangles per
material name, which later becomes one ``<IndexedTriangleSet>`` with one
``<Subset>`` per material.

Primitives return ``(vertices, normals, uvs, triangles)`` and can be placed with
``place()`` (translate + rotate around X/Y/Z).
"""

import math

TAU = 2.0 * math.pi


# --------------------------------------------------------------------------
# mesh container
# --------------------------------------------------------------------------
class Mesh:
    def __init__(self):
        self.parts = {}          # material name -> [verts, normals, uvs, tris]
        self.order = []          # material names in insertion order

    def add(self, material, verts, normals, uvs, tris):
        if not tris:
            return
        if material not in self.parts:
            self.parts[material] = [[], [], [], []]
            self.order.append(material)
        p = self.parts[material]
        base = len(p[0])
        p[0].extend(verts)
        p[1].extend(normals)
        p[2].extend(uvs)
        p[3].extend((a + base, b + base, c + base) for a, b, c in tris)

    def merge(self, other):
        for mat in other.order:
            v, n, uv, t = other.parts[mat]
            self.add(mat, v, n, uv, t)
        return self

    def bbox(self):
        lo = [1e30] * 3
        hi = [-1e30] * 3
        for mat in self.order:
            for v in self.parts[mat][0]:
                for i in range(3):
                    lo[i] = min(lo[i], v[i])
                    hi[i] = max(hi[i], v[i])
        return lo, hi

    def tri_count(self):
        return sum(len(self.parts[m][3]) for m in self.order)

    def vert_count(self):
        return sum(len(self.parts[m][0]) for m in self.order)


# --------------------------------------------------------------------------
# transform helpers
# --------------------------------------------------------------------------
def _rot(point, rot):
    x, y, z = point
    rx, ry, rz = (math.radians(a) for a in rot)
    if rz:
        c, s = math.cos(rz), math.sin(rz)
        x, y = x * c - y * s, x * s + y * c
    if rx:
        c, s = math.cos(rx), math.sin(rx)
        y, z = y * c - z * s, y * s + z * c
    if ry:
        c, s = math.cos(ry), math.sin(ry)
        x, z = x * c + z * s, -x * s + z * c
    return x, y, z


def place(geom, translation=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0)):
    verts, normals, uvs, tris = geom
    tv, tn = [], []
    for v in verts:
        tv.append(_add(_rot((v[0] * scale[0], v[1] * scale[1], v[2] * scale[2]), rot), translation))
    for n in normals:
        tn.append(_rot(n, rot))
    return tv, tn, uvs, tris


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def norm(v):
    ln = math.sqrt(sum(c * c for c in v))
    if ln < 1e-12:
        return tuple(1.0 if i == 1 else 0.0 for i in range(len(v)))
    return tuple(c / ln for c in v)


# --------------------------------------------------------------------------
# primitives
# --------------------------------------------------------------------------
def lathe(profile, segments=48, close_ends=True):
    """Revolve a polyline ``[(r, y), ...]`` around the Y axis.

    The profile is traversed from the bottom centre outwards and back to the
    top centre; outward normals follow from the profile tangent.  ``close_ends``
    adds small discs when the profile does not reach r == 0.
    """
    n = len(profile)
    seg_n = []                       # profile-space normals per point
    for i in range(n):
        if i == 0:
            dr, dy = profile[1][0] - profile[0][0], profile[1][1] - profile[0][1]
        elif i == n - 1:
            dr, dy = profile[-1][0] - profile[-2][0], profile[-1][1] - profile[-2][1]
        else:
            dr = profile[i + 1][0] - profile[i - 1][0]
            dy = profile[i + 1][1] - profile[i - 1][1]
        seg_n.append(norm((dy, -dr)))

    arc = [0.0]
    for i in range(1, n):
        arc.append(arc[-1] + math.hypot(profile[i][0] - profile[i - 1][0], profile[i][1] - profile[i - 1][1]))
    total = arc[-1] or 1.0

    verts, normals, uvs, tris = [], [], [], []
    for i, (r, y) in enumerate(profile):
        nr, ny = seg_n[i]
        for s in range(segments + 1):
            a = TAU * s / segments
            ca, sa = math.cos(a), math.sin(a)
            verts.append((r * ca, y, r * sa))
            normals.append(norm((nr * ca, ny, nr * sa)))
            uvs.append((s / segments, arc[i] / total))
    for i in range(n - 1):
        for s in range(segments):
            a = i * (segments + 1) + s
            b = a + 1
            c = a + segments + 1
            d = c + 1
            tris.append((a, c, b))
            tris.append((b, c, d))

    if close_ends:
        r0, y0 = profile[0]
        r1, y1 = profile[-1]
        if r0 > 1e-4:
            verts, normals, uvs, tris = _merge_disc(verts, normals, uvs, tris, r0, y0, segments, down=True)
        if r1 > 1e-4:
            verts, normals, uvs, tris = _merge_disc(verts, normals, uvs, tris, r1, y1, segments, down=False)
    return verts, normals, uvs, tris


def _merge_disc(verts, normals, uvs, tris, radius, y, segments, down):
    base = len(verts)
    ny = -1.0 if down else 1.0
    verts.append((0.0, y, 0.0))
    normals.append((0.0, ny, 0.0))
    uvs.append((0.5, 0.5))
    for s in range(segments + 1):
        a = TAU * s / segments
        verts.append((radius * math.cos(a), y, radius * math.sin(a)))
        normals.append((0.0, ny, 0.0))
        uvs.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
    for s in range(segments):
        a, b = base + 1 + s, base + 2 + s
        if down:
            tris.append((base, b, a))
        else:
            tris.append((base, a, b))
    return verts, normals, uvs, tris


def disc(radius, y, segments=32, up=True):
    v, n, u, t = [], [], [], []
    v.append((0.0, y, 0.0))
    n.append((0.0, 1.0 if up else -1.0, 0.0))
    u.append((0.5, 0.5))
    for s in range(segments + 1):
        a = TAU * s / segments
        v.append((radius * math.cos(a), y, radius * math.sin(a)))
        n.append((0.0, 1.0 if up else -1.0, 0.0))
        u.append((0.5 + 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a)))
    for s in range(segments):
        if up:
            t.append((0, 1 + s, 2 + s))
        else:
            t.append((0, 2 + s, 1 + s))
    return v, n, u, t


def cylinder(radius, y0, y1, segments=24, caps=True, top_radius=None):
    r1 = radius if top_radius is None else top_radius
    prof = [(radius, y0), (r1, y1)]
    return lathe(prof, segments, close_ends=caps)


def sphere(center=(0, 0, 0), radius=1.0, segments=24, rings=12, scale=(1.0, 1.0, 1.0)):
    cx, cy, cz = center
    verts, normals, uvs, tris = [], [], [], []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        sy, sr = math.cos(phi), math.sin(phi)
        for s in range(segments + 1):
            a = TAU * s / segments
            nx, ny, nz = sr * math.cos(a), sy, sr * math.sin(a)
            verts.append((cx + radius * scale[0] * nx, cy + radius * scale[1] * ny, cz + radius * scale[2] * nz))
            normals.append(norm((nx / scale[0], ny / scale[1], nz / scale[2])))
            uvs.append((s / segments, i / rings))
    for i in range(rings):
        for s in range(segments):
            a = i * (segments + 1) + s
            b, c, d = a + 1, a + segments + 1, a + segments + 2
            tris.append((a, c, b))
            tris.append((b, c, d))
    return verts, normals, uvs, tris


def box(center=(0, 0, 0), size=(1, 1, 1)):
    cx, cy, cz = center
    sx, sy, sz = (s * 0.5 for s in size)
    faces = [
        ((0, 0, 1), [(-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]),
        ((0, 0, -1), [(sx, -sy, -sz), (-sx, -sy, -sz), (-sx, sy, -sz), (sx, sy, -sz)]),
        ((1, 0, 0), [(sx, -sy, sz), (sx, -sy, -sz), (sx, sy, -sz), (sx, sy, sz)]),
        ((-1, 0, 0), [(-sx, -sy, -sz), (-sx, -sy, sz), (-sx, sy, sz), (-sx, sy, -sz)]),
        ((0, 1, 0), [(-sx, sy, sz), (sx, sy, sz), (sx, sy, -sz), (-sx, sy, -sz)]),
        ((0, -1, 0), [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, -sy, sz), (-sx, -sy, sz)]),
    ]
    verts, normals, uvs, tris = [], [], [], []
    for nrm, pts in faces:
        base = len(verts)
        for p in pts:
            verts.append((cx + p[0], cy + p[1], cz + p[2]))
            normals.append(nrm)
        uvs.extend([(0, 0), (1, 0), (1, 1), (0, 1)])
        tris.append((base, base + 1, base + 2))
        tris.append((base, base + 2, base + 3))
    return verts, normals, uvs, tris


def torus(radius, tube, y=0.0, segments=40, sides=10):
    verts, normals, uvs, tris = [], [], [], []
    for i in range(segments + 1):
        a = TAU * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for j in range(sides + 1):
            b = TAU * j / sides
            cb, sb = math.cos(b), math.sin(b)
            verts.append(((radius + tube * cb) * ca, y + tube * sb, (radius + tube * cb) * sa))
            normals.append(norm((cb * ca, sb, cb * sa)))
            uvs.append((i / segments, j / sides))
    for i in range(segments):
        for j in range(sides):
            a = i * (sides + 1) + j
            b, c, d = a + 1, a + sides + 1, a + sides + 2
            tris.append((a, c, b))
            tris.append((b, c, d))
    return verts, normals, uvs, tris


def open_cone(apex_y, top_radius, bottom_y, bottom_radius, segments=32):
    """Frustum without caps (used for the light beam)."""
    return lathe([(top_radius, apex_y), (bottom_radius, bottom_y)], segments, close_ends=False)
