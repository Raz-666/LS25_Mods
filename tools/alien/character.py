# SPDX-License-Identifier: GPL-3.0-or-later
"""The FS25_Alien characters, sculpted rather than assembled.

The old figures were a stack of spheres and cylinders; this module builds them
the way the reference sheets look:

* an egg-shaped skull with a brow ridge, cheek bulges, a narrow chin and a
  slightly flattened face,
* huge glossy eyes with an eyeball, iris, pupil, two catch lights and real
  eyelids,
* a tiny nose and a mouth line that is a tube along a curve, not a row of dots,
* thin arms with an elbow, a wrist and hands with three fingers and a thumb,
* legs with knees and ankles, standing in knitted socks - one red, one blue,
  with a rolled cuff, a heel and a toe cap,
* antennae that curve (bezier) and end in a ball.

``alien_mesh()``, ``leader_mesh()`` and ``zorp_mesh()`` return a
:class:`meshlib.Mesh`; ``pilot_mesh()`` is the seated version used inside the
cockpit of the UFO.

All coordinates are in metres, +Y up, +Z is the direction the character looks.
"""

import math

from meshlib import TAU, Mesh, box, cylinder, disc, lathe, place, sphere, torus
from sculpt import (bezier, deform, panel, radii_curve, recalc_normals,
                    ring_arc, smoothstep, sphere_uv, spherical_cap, tube)

# --------------------------------------------------------------------------
# proportions - one place to tune the whole figure
# --------------------------------------------------------------------------
EYE_Y = 0.845
HEAD_Y = 0.820
HEAD_R = 0.152
NECK_TOP = 0.665
SHOULDER_Y = 0.600
HIP_Y = 0.395
KNEE_Y = 0.255
ANKLE_Y = 0.150


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _mirror(points, sx):
    return [(p[0] * sx, p[1], p[2]) for p in points]


def _head_mesh():
    """Egg-shaped skull with brow, cheeks, jaw and a flat forehead."""
    base = sphere_uv(HEAD_R, segments=40, rings=28)

    def shape(x, y, z):
        # overall: a bit taller than wide, slightly flatter at the face
        y *= 1.08
        z *= 1.00 if z < 0 else 0.93
        # jaw: narrow towards the chin, but keep a soft cheek
        t = max(0.0, -y / HEAD_R)
        jaw = 1.0 - 0.34 * t ** 2.0
        x *= jaw
        z *= 1.0 - 0.24 * max(0.0, -y / HEAD_R) ** 2
        # the cranium is the widest part, a touch wider than the jaw
        x *= 1.0 + 0.06 * smoothstep(0.05, 0.14, y)
        # cranium bulges backwards and the brow comes forward
        if z < 0:
            y += 0.030 * (-z / HEAD_R) ** 2
        brow = math.exp(-((y - 0.052) / 0.045) ** 2) * \
            math.exp(-((abs(x) - 0.070) / 0.075) ** 2)
        z += 0.016 * brow * max(0.0, z / HEAD_R)
        # cheek apples under the eyes
        cheek = math.exp(-((abs(x) - 0.082) / 0.050) ** 2) * \
            math.exp(-((y + 0.030) / 0.045) ** 2)
        x += math.copysign(0.014 * cheek, x)
        z += 0.012 * cheek
        # chin: a small, soft point
        chin = math.exp(-((x / 0.045) ** 2 + ((y + 0.120) / 0.040) ** 2))
        y -= 0.008 * chin
        z += 0.008 * chin
        return x, y, z

    return deform(base, shape)


def _eye(m, sx, centre=None, radius=0.066, tilt=0.0, scale=(1.0, 1.10, 0.86)):
    """One of the huge dark eyes from the sheets.

    The eye is three nested spherical caps (sclera, iris, pupil) plus the
    catch lights and two thin lid crescents.  Because the caps are nested
    instead of intersecting, the eye stays clean at every angle - the old
    version stacked full spheres inside each other and z-fought.
    """
    cx, cy, cz = centre
    yaw = math.degrees(tilt) + 6.0 * sx

    def cap(r, angle, mat, dy=0.0, dz=0.0):
        m.add(mat, *place(spherical_cap(r, angle, 34, 12),
                          rot=(90, yaw, 0),
                          scale=(scale[0], scale[2], scale[1]),
                          translation=(cx + dz * sx, cy + dy, cz)))

    cap(radius * 0.985, 104, "eyeWhite")              # the white of the eye
    cap(radius * 1.004, 79, "iris")                   # big dark iris
    cap(radius * 1.020, 30, "eyeBlack")               # pupil
    # catch lights, sitting on the iris
    m.add("lensWhite", *place(sphere_uv(radius * 0.22, 16, 12),
                              scale=(1.0, 1.0, 0.32),
                              translation=(cx - 0.026 * sx, cy + 0.030,
                                           cz + radius * scale[2] * 0.72)))
    m.add("lensWhite", *place(sphere_uv(radius * 0.085, 12, 9),
                              scale=(1.0, 1.0, 0.4),
                              translation=(cx + 0.028 * sx, cy - 0.028,
                                           cz + radius * scale[2] * 0.68)))
    # eyelids: two crescents that hug the eyeball
    m.add("alienSkin", *place(ring_arc(radius * 1.005, 0.0068, 202, 338, 0, 28, 8),
                              rot=(-90, 0, 0),
                              translation=(cx, cy + radius * 0.02, cz - 0.002)))
    m.add("alienSkin", *place(ring_arc(radius * 0.995, 0.0042, 20, 160, 0, 26, 7),
                              rot=(-90, 0, 0),
                              translation=(cx, cy - radius * 0.02, cz - 0.002)))
    # the wet line along the lower lid
    m.add("lensWhite", *place(ring_arc(radius * 0.97, 0.0016, 32, 148, 0, 22, 5),
                              rot=(-90, 0, 0),
                              translation=(cx, cy - radius * 0.06, cz + 0.006)))


def _brow(m, sx, x, y, z):
    pts = bezier((x - 0.045 * sx, y - 0.004, z - 0.012),
                 (x - 0.018 * sx, y + 0.020, z + 0.010),
                 (x + 0.020 * sx, y + 0.020, z + 0.012),
                 (x + 0.048 * sx, y - 0.002, z - 0.010), steps=8)
    m.add("alienSkin", *tube(pts, radii_curve(8, 0.0062, 0.0026), segments=8))


def _mouth(m, y, z, width, smile=0.012, mat="eyeBlack"):
    """A smile that is a real curve: the tube follows the lip line."""
    pts = []
    for i in range(13):
        t = (i / 12.0) * 2.0 - 1.0
        pts.append((t * width * 0.5, y + smile * (t * t) - 0.004 * (1 - t * t),
                    z - 0.010 * t * t))
    m.add(mat, *tube(pts, [0.0045 + 0.0025 * (1 - abs((i / 12.0) * 2 - 1))
                           for i in range(13)], segments=8))
    # lower lip: a soft skin ridge under the line
    lip = [(p[0], p[1] - 0.009, p[2] + 0.002) for p in pts[2:-2]]
    m.add("alienSkin", *tube(lip, radii_curve(len(lip) - 1, 0.006, 0.006),
                             segments=8))


def _antenna(m, sx, base=(0.058, 0.955, -0.020), height=0.145, bulb=0.024):
    """A curved antenna with a ball on the end."""
    p0 = (base[0] * sx, base[1], base[2])
    p1 = (0.072 * sx, base[1] + height * 0.55, base[2] - 0.014)
    p2 = (0.090 * sx, base[1] + height * 0.95, base[2] + 0.008)
    p3 = (0.086 * sx, base[1] + height, base[2] + 0.024)
    pts = bezier(p0, p1, p2, p3, steps=10)
    m.add("alienSkin", *tube(pts, radii_curve(10, 0.0165, 0.0095, 0.75), segments=10))
    tip = pts[-1]
    m.add("alienSkin", *place(sphere_uv(bulb, 18, 14),
                                translation=(tip[0], tip[1] + bulb * 0.4, tip[2])))


def _hand(m, mat, wrist, direction, fingers=3, spread=0.016, curled=False):
    """A small hand: palm, three fingers and a thumb, all as tapered tubes."""
    px, py, pz = wrist
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    dx, dy, dz = dx / length, dy / length, dz / length
    # palm
    palm = (px + dx * 0.016, py + dy * 0.016, pz + dz * 0.016)
    m.add(mat, *place(sphere_uv(0.019, 16, 12),
                      scale=(1.0, 0.85, 1.25),
                      rot=(0, math.degrees(math.atan2(dx, dz)), 0),
                      translation=palm))
    for i in range(fingers):
        off = (i - (fingers - 1) * 0.5) * spread
        bend = 0.012 if curled else 0.004
        p0 = (palm[0] + off * 0.6, palm[1], palm[2] + off * 0.15)
        p1 = (p0[0] + dx * 0.020 + off * 0.35, p0[1] - bend, p0[2] + dz * 0.020)
        p2 = (p1[0] + dx * 0.018, p1[1] - bend * 1.4, p1[2] + dz * 0.018)
        tip = (p2[0] + dx * 0.010, p2[1] - bend * 0.6, p2[2] + dz * 0.010)
        pts = bezier(p0, p1, p2, tip, steps=6)
        m.add(mat, *tube(pts, radii_curve(6, 0.0072, 0.0042), segments=7))
    # thumb
    t0 = (palm[0] - dx * 0.006, palm[1] + 0.002, palm[2] - dz * 0.006)
    t1 = (t0[0] - dz * 0.018 + dx * 0.010, t0[1] - 0.004, t0[2] + dx * 0.018 + dz * 0.010)
    t2 = (t1[0] + dx * 0.014, t1[1] - 0.008, t1[2] + dz * 0.014)
    m.add(mat, *tube(bezier(t0, t1, t1, t2, steps=5),
                     radii_curve(5, 0.008, 0.005), segments=7))


def _arm(m, sx, mat, shoulder, elbow, wrist, hand_dir, curled=False):
    m.add(mat, *place(sphere_uv(0.021, 16, 12),
                      scale=(1.25, 0.95, 1.0), translation=shoulder))
    upper = bezier(shoulder, shoulder, elbow, elbow, steps=6)
    m.add(mat, *tube(upper, radii_curve(6, 0.0175, 0.0135), segments=10))
    m.add(mat, *place(sphere_uv(0.0145, 14, 10), translation=elbow))
    lower = bezier(elbow, elbow, wrist, wrist, steps=6)
    m.add(mat, *tube(lower, radii_curve(6, 0.0135, 0.0095), segments=10))
    _hand(m, mat, wrist, hand_dir, curled=curled)


def _leg(m, sx, mat_skin, sock, hip, knee, ankle, toe_shift=0.0):
    ay = ankle[1]
    m.add(mat_skin, *tube(bezier(hip, hip, knee, knee, steps=6),
                          radii_curve(6, 0.024, 0.018), segments=10))
    m.add(mat_skin, *place(sphere_uv(0.019, 14, 10), translation=knee))
    m.add(mat_skin, *tube(bezier(knee, knee, ankle, ankle, steps=6),
                          radii_curve(6, 0.018, 0.014), segments=10))

    # knitted sock: rolled cuff, shaft, heel, foot and a toe cap
    fx = ankle[0]
    fz = ankle[2]
    m.add(sock, *place(cylinder(0.0250, ay - 0.034, ay + 0.092, 22, caps=False,
                                top_radius=0.0272),
                       translation=(fx, 0.0, fz)))
    m.add("sockCuff", *place(torus(0.0278, 0.0062, 0, 22, 8),
                             translation=(fx, ay + 0.094, fz)))
    m.add(sock, *place(torus(0.0268, 0.0046, 0, 22, 8),
                       translation=(fx, ay + 0.066, fz)))
    # foot: heel behind, toes in front, rolled slightly outward
    m.add(sock, *place(sphere_uv(0.028, 22, 14),
                       scale=(1.0, 0.85, 1.75),
                       translation=(fx, ay - 0.046, fz + 0.022 + toe_shift)))
    m.add(sock, *place(sphere_uv(0.023, 18, 12),
                       scale=(1.05, 0.9, 1.0),
                       translation=(fx, ay - 0.050, fz + 0.064 + toe_shift)))
    # the ribbing of the knit, a few thin rings around the shaft
    for i in range(3):
        m.add(sock, *place(torus(0.0258, 0.0026, 0, 22, 6),
                           translation=(fx, ay + 0.012 + i * 0.019, fz)))


def _socks_and_colours(m, sx, sock):
    pass


# --------------------------------------------------------------------------
# bodies
# --------------------------------------------------------------------------
def _torso(m, mat, ribbed=False):
    m.add(mat, *place(lathe([
        (0.010, 0.335), (0.046, 0.352), (0.062, 0.380), (0.070, 0.412),
        (0.074, 0.450), (0.072, 0.492), (0.066, 0.532), (0.060, 0.572),
        (0.054, 0.606), (0.046, 0.632), (0.036, 0.650), (0.0, 0.658),
    ], 30, close_ends=True)))
    # belly: a soft, slightly forward bulge
    m.add(mat, *place(sphere_uv(0.058, 22, 16),
                      scale=(1.0, 0.95, 0.85),
                      translation=(0, 0.425, 0.020)))
    # chest plate and collar bones
    m.add(mat, *place(sphere_uv(0.052, 20, 14),
                      scale=(1.25, 0.62, 0.82),
                      translation=(0, 0.590, 0.006)))
    if ribbed:
        for i in range(4):
            m.add(mat, *place(torus(0.052 - 0.004 * i, 0.006, 0.470 + i * 0.042, 22, 6)))


def _neck(m, mat):
    m.add(mat, *place(lathe([(0.026, 0.638), (0.030, 0.660), (0.032, 0.690),
                             (0.034, 0.712)], 18, close_ends=False)))


def alien_mesh(pose="shy"):
    """The little green buddy: big head, huge eyes, striped socks."""
    m = Mesh()
    _legs(m, "alienSkin")
    _torso(m, "alienSkin")
    _neck(m, "alienSkin")
    m.add("alienSkin", *_head_at(0.0))
    _face(m)

    # arms: shy = hands clasped in front, crossed = folded, open = hanging
    if pose == "crossed":
        for sx in (-1, 1):
            _arm(m, sx, "alienSkin",
                 shoulder=(0.050 * sx, 0.588, 0.004),
                 elbow=(0.088 * sx, 0.476, 0.038),
                 wrist=(-0.026 * sx, 0.486, 0.084),
                 hand_dir=(-0.85 * sx, 0.0, 0.45), curled=True)
    else:
        for sx in (-1, 1):
            _arm(m, sx, "alienSkin",
                 shoulder=(0.050 * sx, 0.588, 0.004),
                 elbow=(0.082 * sx, 0.472, 0.030),
                 wrist=(0.038 * sx, 0.428, 0.078),
                 hand_dir=(-0.5 * sx, -0.35, 0.75), curled=True)
    return m


def _legs(m, skin):
    for sx, sock in ((-1, "sockRed"), (1, "sockBlue")):
        _leg(m, sx, skin, sock,
             hip=(0.048 * sx, HIP_Y, 0.0),
             knee=(0.052 * sx, KNEE_Y, 0.006),
             ankle=(0.050 * sx, ANKLE_Y, 0.028),
             toe_shift=0.004 * sx)


def _head_at(dy):
    verts, normals, uvs, tris = _head_mesh()
    return place((verts, normals, uvs, tris), translation=(0, HEAD_Y + dy, 0.012))


def _face(m, eye_scale=1.0, mouth_width=0.070, y_shift=0.0):
    y0 = HEAD_Y + y_shift
    for sx in (-1, 1):
        _eye(m, sx, centre=(0.068 * sx, y0 + 0.022, 0.108),
             radius=0.058 * eye_scale)
        _brow(m, sx, 0.068 * sx, y0 + 0.076, 0.118)
        # rosy cheek, flat against the face
        m.add("blush", *place(sphere_uv(0.024, 18, 12),
                              scale=(1.25, 0.85, 0.10),
                              rot=(0, -40 * sx, -4 * sx),
                              translation=(0.080 * sx, y0 - 0.052, 0.112)))
    # nose: two tiny nostrils on a soft pad
    m.add("alienSkin", *place(sphere_uv(0.0105, 14, 10),
                              scale=(1.05, 0.80, 0.62),
                              translation=(0, y0 - 0.030, 0.152)))
    _mouth(m, y0 - 0.080, 0.134, mouth_width)
    _antenna(m, -1, base=(0.050, y0 + 0.124, -0.014), height=0.100, bulb=0.021)
    _antenna(m, 1, base=(0.050, y0 + 0.124, -0.014), height=0.100, bulb=0.021)


def leader_mesh():
    """The tall one: same sculpt, longer limbs, ribbed body, arms crossed."""
    m = Mesh()
    _legs(m, "alienSkin")
    _torso(m, "alienSkin", ribbed=True)
    _neck(m, "alienSkin")
    m.add("alienSkin", *_head_at(0.0))
    _face(m, eye_scale=1.05, mouth_width=0.080)
    for sx in (-1, 1):
        _arm(m, sx, "alienSkin",
             shoulder=(0.060 * sx, 0.585, 0.0),
             elbow=(0.098 * sx, 0.462, 0.034),
             wrist=(-0.026 * sx, 0.486, 0.082),
             hand_dir=(-0.8 * sx, 0.0, 0.5), curled=True)
    return m


def _helmet(m, y=0.0, with_strap=True):
    """Flight helmet: a real dome that sits on the skull, rolled rim, ear cups,
    a short antenna stub and the goggles parked on the brow.

    The dome is a spherical cap around +Y whose rim ends just above the eyes;
    everything else (rim, cups, strap) is placed relative to that rim.
    """
    c_y = HEAD_Y + 0.006 + y          # centre of the skull
    c_z = 0.010
    r = 0.174
    angle = 78.0                       # where the shell is cut
    m.add("helmet", *place(spherical_cap(r, angle, 44, 18),
                           scale=(1.0, 1.02, 1.04),
                           translation=(0, c_y, c_z)))
    # the rolled rim
    rim_y = c_y + r * math.cos(math.radians(angle)) * 1.02
    rim_r = r * math.sin(math.radians(angle))
    m.add("helmetTrim", *place(torus(rim_r * 1.005, 0.0125, 0, 46, 9),
                               scale=(1.0, 1.0, 1.04),
                               translation=(0, rim_y, c_z)))
    # ear cups
    for sx in (-1, 1):
        m.add("helmetTrim", *place(cylinder(0.030, 0.0, 0.024, 18, caps=True),
                                   rot=(0, 0, 90 * sx),
                                   translation=(rim_r * 0.99 * sx, c_y + 0.030, c_z - 0.004)))
        m.add("goggle", *place(sphere_uv(0.024, 16, 12), scale=(0.6, 1.0, 1.0),
                               translation=(rim_r * 1.02 * sx, c_y + 0.030, c_z - 0.004)))
    # antenna stub with a glowing bead
    pts = bezier((0.080, c_y + r * 0.86, -0.055), (0.092, c_y + r * 1.05, -0.070),
                 (0.092, c_y + r * 1.14, -0.068), (0.088, c_y + r * 1.20, -0.062), steps=8)
    m.add("hullMetal", *tube(pts, radii_curve(8, 0.0060, 0.0038), segments=8))
    m.add("lensRed", *place(sphere_uv(0.012, 12, 9),
                            translation=(0.088, c_y + r * 1.23, -0.062)))
    # --- goggles, parked on the brow -------------------------------------
    g_y = rim_y + 0.040
    g_z = c_z + 0.196
    # thin strap that disappears under the lenses
    m.add("goggle", *place(torus(0.172, 0.0050, 0, 44, 6),
                           rot=(-10, 0, 0), translation=(0, g_y, c_z)))
    for sx in (-1, 1):
        # rubber cup, then the rim, then the glass
        m.add("goggle", *place(cylinder(0.034, 0.0, 0.014, 20, caps=True),
                               rot=(64, 0, 0),
                               translation=(0.056 * sx, g_y + 0.002, g_z - 0.012)))
        m.add("helmetTrim", *place(torus(0.032, 0.0048, 0, 22, 5),
                                   rot=(64, 0, 0),
                                   translation=(0.056 * sx, g_y + 0.008, g_z)))
        m.add("lensWhite", *place(disc(0.026, 0.0, 20, up=False), rot=(64, 0, 0),
                                  translation=(0.056 * sx, g_y + 0.012, g_z - 0.002)))
    m.add("goggle", *place(box((0, 0, 0), (0.036, 0.010, 0.010)),
                           rot=(14, 0, 0), translation=(0, g_y + 0.006, g_z - 0.008)))
    if with_strap:
        # chin strap down the sides of the head
        for sx in (-1, 1):
            m.add("helmetTrim", *place(ring_arc(0.158, 0.0048, 268, 356, 0, 16, 6),
                                       rot=(0, 90 - 8 * sx, 0),
                                       translation=(0.010 * sx, c_y - 0.052, c_z)))


def zorp_mesh():
    """Captain Zorp in his olive flight suit, boots, helmet and goggles."""
    m = Mesh()
    for sx in (-1, 1):
        _leg(m, sx, "suit", "goggle",
             hip=(0.050 * sx, HIP_Y, 0.0),
             knee=(0.054 * sx, KNEE_Y, 0.006),
             ankle=(0.052 * sx, ANKLE_Y, 0.028))
        # a proper boot over the sock: shaft, foot, rounded toe and a low sole
        m.add("goggle", *place(cylinder(0.031, 0.0, 0.072, 22, caps=True,
                                        top_radius=0.035),
                               translation=(0.052 * sx, 0.026, 0.028)))
        m.add("goggle", *place(sphere_uv(0.034, 22, 16), scale=(1.0, 0.66, 1.6),
                               translation=(0.052 * sx, 0.030, 0.058)))
        m.add("goggle", *place(sphere_uv(0.030, 18, 12), scale=(1.0, 0.86, 1.0),
                               translation=(0.052 * sx, 0.026, 0.092)))
        m.add("iron", *place(cylinder(0.0345, 0.0, 0.013, 22, caps=True,
                                      top_radius=0.033),
                             rot=(0, 0, 0),
                             translation=(0.052 * sx, 0.0, 0.030)))
        m.add("iron", *place(sphere_uv(0.031, 18, 12), scale=(1.0, 0.30, 1.55),
                             translation=(0.052 * sx, 0.014, 0.060)))
    _torso(m, "suit")
    # belt with a buckle and two seam lines
    m.add("goggle", *place(torus(0.0705, 0.0105, 0.412, 26, 7)))
    m.add("helmet", *place(box((0, 0, 0), (0.032, 0.024, 0.012)),
                           translation=(0, 0.412, 0.070)))
    for y in (0.470, 0.545):
        m.add("suit", *place(torus(0.0665 - (y - 0.47) * 0.10, 0.0035, y, 26, 5)))
    _neck(m, "alienSkin")
    m.add("alienSkin", *_head_at(0.0))
    _face(m)

    from model_crop import decal
    decal(m, "badge", (0.0, 0.566, 0.064), 0.072, 0.038, 0.0)
    for sx in (-1, 1):
        _arm(m, sx, "suit",
             shoulder=(0.052 * sx, 0.588, 0.004),
             elbow=(0.084 * sx, 0.470, 0.022),
             wrist=(0.074 * sx, 0.356, 0.042),
             hand_dir=(0.1 * sx, -0.7, 0.6))
        m.add("goggle", *place(sphere_uv(0.023, 16, 12), scale=(1.0, 0.9, 1.15),
                               translation=(0.076 * sx, 0.334, 0.054)))
    _helmet(m)
    return m


def pilot_mesh():
    """Zorp seated behind the levers of the crop harvester."""
    m = Mesh()
    # seat is in the cockpit; here only the body from the hips up
    for sx in (-1, 1):
        m.add("suit", *tube(bezier((0.052 * sx, 0.020, 0.010),
                                   (0.052 * sx, 0.020, 0.010),
                                   (0.058 * sx, -0.010, 0.180),
                                   (0.060 * sx, -0.040, 0.300), steps=6),
                            radii_curve(6, 0.026, 0.020), segments=10))
        m.add("goggle", *place(sphere_uv(0.028, 16, 12), scale=(1.0, 0.8, 1.5),
                               translation=(0.060 * sx, -0.040, 0.345)))
    _torso(m, "suit")
    m.add("goggle", *place(torus(0.070, 0.010, 0.415, 24, 6)))
    _neck(m, "alienSkin")
    verts, normals, uvs, tris = _head_at(0.0)
    m.add("alienSkin", verts, normals, uvs, tris)
    _face(m)
    _helmet(m, with_strap=False)
    # arms reaching for the levers
    for sx in (-1, 1):
        _arm(m, sx, "suit",
             shoulder=(0.060 * sx, 0.585, 0.0),
             elbow=(0.105 * sx, 0.500, 0.105),
             wrist=(0.085 * sx, 0.430, 0.235),
             hand_dir=(-0.1 * sx, -0.6, 0.8))
        m.add("goggle", *place(sphere_uv(0.021, 14, 10), scale=(1.0, 0.9, 1.1),
                               translation=(0.082 * sx, 0.415, 0.250)))
    return m
