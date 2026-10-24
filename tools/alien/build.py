#!/usr/bin/env python3
"""Builds the separate FS25_Alien mod: a little green mascot you can place.

The figure is the same mesh that used to sit inside the saucer.  It lives in its
own mod so the UFO can show the player's own character under the glass dome,
while the alien is still available as a decoration for the farm yard.

    python tools/alien/build.py
"""

import math
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tools", "ufo"))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "tools", "ufo"))

from meshlib import (TAU, Mesh, box, cylinder, disc, lathe, place, sphere,  # noqa: E402
                     torus)
import model as ufo_model                                  # noqa: E402
from model import Node, write_i3d                          # noqa: E402

MOD = os.path.join(REPO, "FS25_Alien")
SCALE = 1.35        # a garden gnome sized mascot, ~1.1 m tall


def limb(m, mat, p0, p1, r0, r1=None, segments=12):
    """A tapered tube between two points - the bendy arms and legs."""
    r1 = r0 if r1 is None else r1
    dx, dy, dz = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-6:
        return
    geom = cylinder(r1, 0.0, length, segments, caps=True, top_radius=r0)
    tilt = math.degrees(math.atan2(dx, dy))
    yaw = math.degrees(math.atan2(dz, math.sqrt(dx * dx + dy * dy)))
    m.add(mat, *place(geom, translation=p0, rot=(0, yaw, -tilt)))


def alien_mesh():
    """The little green buddy exactly as the reference sheet draws him.

    A huge pear-shaped head with big glossy almond eyes, a small body with a
    little belly, thin bendy arms folded in front, thin legs that end in striped
    socks - one blue, one red - plus two antennae with ball tips, a shy smile
    and rosy cheeks.
    """
    m = Mesh()

    # --- legs + socks ------------------------------------------------------
    for sx, sock in ((-1, "sockRed"), (1, "sockBlue")):
        # thigh and shin, very thin
        limb(m, "alienSkin", (0.060 * sx, 0.445, 0.0), (0.066 * sx, 0.265, -0.010),
             0.034, 0.028)
        limb(m, "alienSkin", (0.066 * sx, 0.270, -0.010), (0.062 * sx, 0.170, 0.006),
             0.028, 0.024)
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.030, 12, 9),
                                  translation=(0.066 * sx, 0.268, -0.008)))
        # the sock: a short striped tube plus the foot
        m.add(sock, *place(cylinder(0.037, 0.040, 0.168, 16, caps=True,
                                    top_radius=0.033),
                           translation=(0.062 * sx, 0.0, 0.006)))
        m.add(sock, *place(sphere((0, 0, 0), 0.046, 16, 10, scale=(1.0, 0.60, 1.85)),
                           translation=(0.062 * sx, 0.040, 0.048)))
        # a rolled cuff at the top of the sock
        m.add(sock, *place(torus(0.038, 0.009, 0, 16, 6),
                           translation=(0.062 * sx, 0.166, 0.006)))

    # --- hips / body -------------------------------------------------------
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.072, 18, 12, scale=(1.05, 0.78, 0.88)),
                              translation=(0, 0.450, 0)))
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.070, 18, 12, scale=(1.0, 0.85, 0.95)),
                              translation=(0, 0.500, 0.014)))
    # a slim, slightly pot-bellied torso - one smooth lathe
    m.add("alienSkin", *place(lathe([
        (0.024, 0.395), (0.060, 0.420), (0.076, 0.460), (0.080, 0.500),
        (0.074, 0.545), (0.062, 0.600), (0.052, 0.650), (0.046, 0.690),
    ], 26, close_ends=True)))
    # chest and collar bones
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.060, 16, 11, scale=(1.30, 0.80, 0.90)),
                              translation=(0, 0.700, 0.004)))
    # --- neck --------------------------------------------------------------
    m.add("alienSkin", *place(cylinder(0.032, 0.70, 0.80, 14, caps=True,
                                      top_radius=0.042)))

    # --- the big head ------------------------------------------------------
    m.add("alienSkin", *place(lathe([
        (0.022, 0.760), (0.060, 0.775), (0.110, 0.800), (0.158, 0.840),
        (0.190, 0.890), (0.205, 0.945), (0.207, 1.000), (0.196, 1.050),
        (0.170, 1.095), (0.122, 1.135), (0.065, 1.160), (0.0, 1.168),
    ], 34, close_ends=True)))

    # --- eyes: huge, glossy, almond shaped ---------------------------------
    for sx in (-1, 1):
        # huge almond eyes, tilted a little towards the nose
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.076, 24, 18, scale=(1.02, 1.18, 0.58)),
                                 rot=(0, 0, 4 * sx),
                                 translation=(0.080 * sx, 0.928, 0.150)))
        # two catch lights - the whole toy look comes from these
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.020, 12, 9, scale=(1.0, 1.1, 0.8)),
                                  translation=(0.100 * sx, 0.966, 0.196)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.010, 8, 6),
                                  translation=(0.060 * sx, 0.902, 0.200)))
        # rosy cheeks, flat against the face
        m.add("blush", *place(sphere((0, 0, 0), 0.028, 12, 8, scale=(1.15, 0.85, 0.16)),
                              rot=(0, 0, -12 * sx),
                              translation=(0.136 * sx, 0.862, 0.146)))

    # --- shy smile ---------------------------------------------------------
    for i in range(7):
        t = (i - 3) / 3.0                       # -1 .. 1 across the mouth
        m.add("eyeBlack", *place(sphere((0, 0, 0),
                                        0.021 - 0.006 * abs(t), 12, 9,
                                        scale=(1.0, 0.75, 0.5)),
                                 translation=(0.052 * t, 0.836 - 0.019 * (1 - t * t),
                                              0.196 - 0.012 * t * t)))

    # --- antennae with little balls ---------------------------------------
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.008, 0.0, 0.155, 10, caps=True,
                                          top_radius=0.006),
                                  rot=(0, 0, -26 * sx),
                                  translation=(0.052 * sx, 1.128, -0.012)))
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.026, 14, 10),
                                  translation=(0.092 * sx, 1.272, -0.012)))

    # --- thin arms, hands folded in front ---------------------------------
    for sx in (-1, 1):
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.038, 14, 10),
                                  translation=(0.076 * sx, 0.678, 0.004)))
        limb(m, "alienSkin", (0.076 * sx, 0.670, 0.006), (0.108 * sx, 0.560, 0.026),
             0.026, 0.021)
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.024, 12, 9),
                                  translation=(0.108 * sx, 0.556, 0.026)))
        limb(m, "alienSkin", (0.108 * sx, 0.550, 0.028), (0.046 * sx, 0.492, 0.100),
             0.020, 0.018)
        # the hand
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.032, 14, 10, scale=(1.0, 0.8, 1.15)),
                                  translation=(0.045 * sx, 0.498, 0.118)))
        for f in range(3):
            m.add("alienSkin", *place(sphere((0, 0, 0), 0.0115, 8, 6, scale=(1.0, 0.85, 1.6)),
                                      translation=((0.033 + f * 0.012) * sx, 0.492,
                                                   0.140)))
    return m


def alien_leader_mesh():
    """The tall one from the couch gag: big domed head, huge bulging eyes,
    a ribbed body and four tentacles - clearly Simpsons flavoured, still our
    own geometry."""
    m = Mesh()
    # --- domed head -------------------------------------------------------
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.30, 30, 18, scale=(1.0, 1.12, 0.92)),
                              translation=(0, 0.92, 0)))
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.26, 28, 16, scale=(1.02, 0.85, 1.0)),
                              translation=(0, 0.72, 0.02)))
    # brow ridge, the grumpy look
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.16, 16, 10, scale=(1.5, 0.32, 0.7)),
                              translation=(0, 0.99, 0.20)))
    # --- the eyes: big, bulging, with a heavy lid -------------------------
    for sx in (-1, 1):
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.105, 20, 14, scale=(1.0, 1.15, 0.85)),
                                  translation=(0.135 * sx, 0.90, 0.235)))
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.055, 16, 12, scale=(1.0, 1.1, 0.7)),
                                 translation=(0.145 * sx, 0.90, 0.312)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.014, 8, 6),
                                  translation=(0.163 * sx, 0.928, 0.345)))
        # eyelid
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.108, 16, 10, scale=(1.05, 0.45, 0.9)),
                                  translation=(0.135 * sx, 0.955, 0.232)))
    # --- mouth: a wide slit with a couple of teeth ------------------------
    m.add("eyeBlack", *place(sphere((0, 0, 0), 0.072, 16, 10, scale=(1.9, 0.30, 0.35)),
                             translation=(0, 0.755, 0.255)))
    for i in range(3):
        m.add("lensWhite", *place(box((0, 0, 0), (0.026, 0.030, 0.014)),
                                  translation=(-0.045 + i * 0.045, 0.762, 0.278)))
    # --- neck and collar of the space suit --------------------------------
    m.add("alienSkin", *place(cylinder(0.075, 0.58, 0.68, 14, caps=True)))
    m.add("hullMetal", *place(torus(0.115, 0.022, 0.60, 26, 8)))
    # --- ribbed torso -----------------------------------------------------
    m.add("alienSkin", *place(lathe([(0.10, 0.10), (0.16, 0.22), (0.19, 0.36),
                                     (0.17, 0.48), (0.11, 0.58)], 22, close_ends=True)))
    for i in range(4):
        m.add("alienSkin", *place(torus(0.175 - 0.012 * i, 0.022, 0.24 + i * 0.09, 24, 6)))
    # --- four tentacle arms -----------------------------------------------
    for sx in (-1, 1):
        for k, (tilt, reach, y) in enumerate(((26, 0.20, 0.42), (44, 0.29, 0.28),
                                              (58, 0.35, 0.16))):
            m.add("alienSkin", *place(sphere((0, 0, 0), 0.055 - 0.008 * k, 14, 10,
                                             scale=(1.0, 2.2, 1.0)),
                                      rot=(0, 0, sx * tilt),
                                      translation=(sx * reach, y, 0.03 + 0.02 * k)))
    # --- three stubby legs and a small metal base ring --------------------
    for i in range(3):
        a = TAU * i / 3 + math.pi / 2
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.055, 12, 8, scale=(1.0, 2.2, 1.0)),
                                  translation=(0.08 * math.cos(a), 0.10, 0.08 * math.sin(a))))
    return m


def build_scene():
    sub = Node("TransformGroup", "alien_mascot", scale="%s %s %s" % (SCALE, SCALE, SCALE))
    sub.add(Node("Shape", "alienMesh", alien_mesh()))
    # invisible collision cylinder so the mascot is solid in the world
    coll = Mesh()
    coll.add("collision", *cylinder(0.34, 0.0, 1.35, 12, caps=True))
    sub.add(Node("Shape", "alienCollision", coll, materials=["collision"], **{
        "dynamic": "false", "compound": "true",
        "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    }))
    return sub


def build_scene_leader():
    sub = Node("TransformGroup", "alienLeader", scale="%s %s %s" % (SCALE, SCALE, SCALE))
    sub.add(Node("Shape", "alienLeaderMesh", alien_leader_mesh()))
    coll = Mesh()
    coll.add("collision", *cylinder(0.36, 0.0, 1.55, 12, caps=True))
    sub.add(Node("Shape", "alienLeaderCollision", coll, materials=["collision"], **{
        "dynamic": "false", "compound": "true",
        "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    }))
    return sub


def zorp_mesh():
    """Captain Zorp, standing - the pilot from the cockpit blueprint.

    Green skin, black goggles pushed up on the forehead, olive flight suit with
    a belt, boots, a chest patch and his two communication antennae.  Same
    character that sits in the UFO 01 crop harvester, just out of the seat.
    """
    from model_crop import decal                    # shared flat-quad helper

    m = Mesh()
    # --- boots ------------------------------------------------------------
    for sx in (-1, 1):
        m.add("goggle", *place(box((0, 0, 0), (0.17, 0.11, 0.28)),
                               translation=(0.11 * sx, 0.055, 0.02)))
    # --- legs in the flight suit -----------------------------------------
    for sx in (-1, 1):
        m.add("suit", *place(cylinder(0.078, 0.10, 0.54, 14, caps=True),
                             translation=(0.11 * sx, 0, 0)))
    # --- torso ------------------------------------------------------------
    m.add("suit", *place(lathe([(0.16, 0.50), (0.20, 0.60), (0.235, 0.78),
                                (0.22, 0.90), (0.16, 0.99)], 22, close_ends=True)))
    # belt, buckle and the chest name plate
    m.add("hullMetal", *place(torus(0.203, 0.014, 0, 24, 6), translation=(0, 0.61, 0)))
    m.add("lensWhite", *place(box((0, 0, 0), (0.070, 0.050, 0.018)),
                              translation=(0, 0.61, 0.204)))
    # the plate sits a few millimetres proud of the suit so the chest does not
    # grow through it
    decal(m, "badge", (0.0, 0.82, 0.244), 0.17, 0.085, 0.0)
    # shoulder seams
    for sx in (-1, 1):
        m.add("goggle", *place(torus(0.070, 0.014, 0, 18, 5),
                               rot=(0, 0, 90 * sx),
                               translation=(0.20 * sx, 0.90, 0)))
    # --- arms, hands in the black gloves ---------------------------------
    for sx in (-1, 1):
        m.add("suit", *place(cylinder(0.056, 0.62, 0.90, 14, caps=True),
                             rot=(0, 0, -5 * sx), translation=(0.228 * sx, 0, 0.01)))
        m.add("suit", *place(sphere((0, 0, 0), 0.080, 16, 12),
                             translation=(0.200 * sx, 0.895, 0.01)))
        m.add("goggle", *place(sphere((0, 0, 0), 0.052, 14, 10, scale=(1.0, 1.2, 1.0)),
                               translation=(0.236 * sx, 0.598, 0.02)))
    # --- collar and neck --------------------------------------------------
    m.add("hullMetal", *place(torus(0.120, 0.022, 0, 22, 6), translation=(0, 1.00, 0)))
    m.add("alienSkin", *place(cylinder(0.062, 0.96, 1.07, 14, caps=True)))
    # --- head -------------------------------------------------------------
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.205, 26, 18, scale=(1.0, 1.06, 0.98)),
                              translation=(0, 1.25, 0.012)))
    for sx in (-1, 1):
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.073, 18, 12, scale=(1.0, 1.25, 0.62)),
                                 translation=(0.080 * sx, 1.265, 0.165)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.020, 10, 8),
                                  translation=(0.096 * sx, 1.300, 0.208)))
    m.add("eyeBlack", *place(sphere((0, 0, 0), 0.040, 14, 10, scale=(1.5, 0.34, 0.45)),
                             translation=(0, 1.172, 0.190)))
    # --- flight helmet, goggles pushed up on its brow ---------------------
    # the shell follows the skull (+18 mm) so it reads as a helmet instead of
    # a cap perched on top; the front edge stops above the big eyes
    m.add("helmet", *place(lathe([
        (0.214, 1.315), (0.205, 1.340), (0.192, 1.365), (0.175, 1.390),
        (0.151, 1.415), (0.118, 1.440), (0.086, 1.455), (0.040, 1.466),
        (0.0, 1.472),
    ], 30, close_ends=True), translation=(0, 0.010, 0.006)))
    m.add("helmetTrim", *place(torus(0.210, 0.018, 0, 28, 6),
                               translation=(0, 1.328, 0.006)))
    for sx in (-1, 1):
        m.add("helmetTrim", *place(cylinder(0.058, 0.0, 0.05, 16, caps=True),
                                   rot=(0, 0, 90 * sx),
                                   translation=(0.202 * sx, 1.372, 0.010)))
    m.add("goggle", *place(torus(0.158, 0.016, 0, 28, 6),
                           rot=(-30, 0, 0), translation=(0, 1.402, 0.078)))
    for sx in (-1, 1):
        m.add("goggle", *place(cylinder(0.050, 0.0, 0.032, 16, caps=True),
                               rot=(58, 0, 0),
                               translation=(0.068 * sx, 1.398, 0.148)))
        m.add("lensWhite", *place(disc(0.037, 0.0, 16, up=False),
                                  rot=(58, 0, 0),
                                  translation=(0.068 * sx, 1.406, 0.162)))
    m.add("hullMetal", *place(box((0, 0, 0), (0.057, 0.013, 0.013)),
                              rot=(30, 0, 0), translation=(0, 1.408, 0.146)))
    # --- antennae with glowing tips --------------------------------------
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.011, 0.0, 0.16, 8, caps=True),
                                  rot=(0, 0, -20 * sx),
                                  translation=(0.090 * sx, 1.492, -0.010)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.030, 12, 8),
                                  translation=(0.118 * sx, 1.612, -0.010)))
    return m


ZORP_SCALE = 1.15


def build_scene_zorp():
    sub = Node("TransformGroup", "zorp", scale="%s %s %s"
               % (ZORP_SCALE, ZORP_SCALE, ZORP_SCALE))
    sub.add(Node("Shape", "zorpMesh", zorp_mesh()))
    coll = Mesh()
    coll.add("collision", *cylinder(0.36, 0.0, 1.75, 12, caps=True))
    sub.add(Node("Shape", "zorpCollision", coll, materials=["collision"], **{
        "dynamic": "false", "compound": "true",
        "collisionFilterGroup": "0x1", "collisionFilterMask": "0x1",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    }))
    return sub


MATERIALS = [
    {"name": "alienSkin", "diffuse": "alienSkin_diffuse.dds", "gloss": "alienSkin_specular.dds"},
    {"name": "suit", "diffuse": "suit_diffuse.dds", "gloss": "suit_specular.dds"},
    {"name": "goggle", "diffuse": "goggle_diffuse.dds", "gloss": None},
    {"name": "badge", "diffuse": "zorpBadge_diffuse.dds", "gloss": None},
    {"name": "sockRed", "diffuse": "sockRed_diffuse.dds", "gloss": None},
    {"name": "sockBlue", "diffuse": "sockBlue_diffuse.dds", "gloss": None},
    {"name": "blush", "diffuse": "blush_diffuse.dds", "gloss": None},
    {"name": "helmet", "diffuse": "helmet_diffuse.dds", "gloss": "helmet_specular.dds"},
    {"name": "helmetTrim", "diffuse": "helmetTrim_diffuse.dds", "gloss": None},
    {"name": "eyeBlack", "diffuse": "eyeBlack_diffuse.dds", "gloss": None},
    {"name": "lensGreen", "diffuse": "lensGreen_diffuse.dds", "gloss": None},
    {"name": "lensWhite", "diffuse": "lensWhite_diffuse.dds", "gloss": None},
    {"name": "hullMetal", "diffuse": "hullMetal_diffuse.dds", "gloss": "hullMetal_specular.dds"},
    {"name": "collision", "diffuse": None, "color": "0.5 0.5 0.5 1", "specular": "0.1 0.1 0.1"},
]

PLACEABLE_XML = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<placeable type="decoObject" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/placeable.xsd">
    <annotation>Alien mascot for the UFO 2000 - a small decoration for the farm yard.</annotation>

    <storeData>
        <name>$l10n_alien_name</name>
        <functions>
            <function>$l10n_function_alien</function>
        </functions>
        <image>store_alien.png</image>
        <price>750</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <category>decoration</category>
        <vertexBufferMemoryUsage>0</vertexBufferMemoryUsage>
        <indexBufferMemoryUsage>0</indexBufferMemoryUsage>
        <textureMemoryUsage>0</textureMemoryUsage>
        <audioMemoryUsage>0</audioMemoryUsage>
    </storeData>

    <base>
        <filename>alien.i3d</filename>
        <canBeDeleted>true</canBeDeleted>
        <canBeRenamed>false</canBeRenamed>
    </base>

    <placement useRandomYRotation="false" useManualYRotation="true" alignToWorldY="true"/>

    <i3dMappings>
    </i3dMappings>
</placeable>
"""

LEADER_XML = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<placeable type="decoObject" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/placeable.xsd">
    <annotation>Alien visitor - the tall one, decoration for the farm yard.</annotation>

    <storeData>
        <name>$l10n_alienLeader_name</name>
        <functions>
            <function>$l10n_function_alien</function>
        </functions>
        <image>store_alienLeader.png</image>
        <price>1200</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <category>decoration</category>
        <vertexBufferMemoryUsage>0</vertexBufferMemoryUsage>
        <indexBufferMemoryUsage>0</indexBufferMemoryUsage>
        <textureMemoryUsage>0</textureMemoryUsage>
        <audioMemoryUsage>0</audioMemoryUsage>
    </storeData>

    <base>
        <filename>alienLeader.i3d</filename>
        <canBeDeleted>true</canBeDeleted>
        <canBeRenamed>false</canBeRenamed>
    </base>

    <placement useRandomYRotation="false" useManualYRotation="true" alignToWorldY="true"/>

    <i3dMappings>
    </i3dMappings>
</placeable>
"""

ZORP_XML = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<placeable type="decoObject" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/placeable.xsd">
    <annotation>Captain Zorp - the pilot of the UFO 01 crop harvester, standing.</annotation>

    <storeData>
        <name>$l10n_zorp_name</name>
        <functions>
            <function>$l10n_function_alien</function>
        </functions>
        <image>store_zorp.png</image>
        <price>1500</price>
        <lifetime>600</lifetime>
        <rotation>0</rotation>
        <category>decoration</category>
        <vertexBufferMemoryUsage>0</vertexBufferMemoryUsage>
        <indexBufferMemoryUsage>0</indexBufferMemoryUsage>
        <textureMemoryUsage>0</textureMemoryUsage>
        <audioMemoryUsage>0</audioMemoryUsage>
    </storeData>

    <base>
        <filename>zorp.i3d</filename>
        <canBeDeleted>true</canBeDeleted>
        <canBeRenamed>false</canBeRenamed>
    </base>

    <placement useRandomYRotation="false" useManualYRotation="true" alignToWorldY="true"/>

    <i3dMappings>
    </i3dMappings>
</placeable>
"""

MODDESC = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<modDesc descVersion="96" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/modDesc.xsd">
    <author>Arena.ai Agent Mode</author>
    <version>1.1.0.0</version>

    <title>
        <en>Alien Mascot</en>
        <de>Alien-Maskottchen</de>
    </title>

    <description>
        <en><![CDATA[A little green buddy for the farm yard - the same alien that peers out of the UFO 2000.

* Placeable decoration, can be put anywhere, rotated freely and picked up again
* The UFO 2000 mod shows your own character under its glass dome, so the alien
  now lives in his own small mod
* Model and textures are generated by scripts, no base game assets were used

Three of them are in the box:
* Alien mascot - the little green buddy, 750
* Alien visitor (the tall one) - the big domed head with the huge eyes, 1,200
* Captain Zorp - the pilot from the cockpit blueprint: green skin, goggles
  pushed up on the forehead, olive flight suit, 1,500

Category: decorations]]></en>
        <de><![CDATA[Ein kleiner grüner Kumpel für den Hof - genau der Alien, der aus dem UFO 2000 schaut.

* Aufstellbare Deko, überall platzierbar, frei drehbar und wieder aufnehmbar
* Im UFO 2000 sitzt jetzt dein eigener Charakter unter der Glaskuppel, deshalb
  wohnt der Alien ab sofort in seinem eigenen kleinen Mod
* Modell und Texturen werden von Skripten erzeugt, keine Spieldateien kopiert

Drei sind in der Kiste:
* Alien-Maskottchen - der kleine grüne Kumpel, 750
* Alien-Besuch (der Große) - der mit dem Riesenschädel und den Glubschaugen, 1.200
* Captain Zorp - der Pilot aus dem Cockpit-Blueprint: grüne Haut, Brille auf
  die Stirn geschoben, olivgrüner Fluganzug, 1.500

Kategorie: Deko]]></de>
    </description>

    <iconFilename>icon_alien.dds</iconFilename>
    <multiplayer supported="true"/>

    <storeItems>
        <storeItem xmlFilename="alien.xml"/>
        <storeItem xmlFilename="alienLeader.xml"/>
        <storeItem xmlFilename="zorp.xml"/>
    </storeItems>
</modDesc>
"""

TRANSLATIONS = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<l10n>
    <text name="alien_name"><de>Alien-Maskottchen</de><en>Alien mascot</en></text>
    <text name="function_alien"><de>Dekoration</de><en>Decoration</en></text>
    <text name="alienLeader_name"><de>Alien-Besuch (der Große)</de><en>Alien Visitor (the tall one)</en></text>
    <text name="zorp_name"><de>Captain Zorp</de><en>Captain Zorp</en></text>
</l10n>
"""


def _sock(base_rgb, size=128):
    """A knitted sock: coloured and cream rings, a ribbed cuff and a heel."""
    import numpy as np
    from PIL import Image, ImageDraw
    w = h = size
    img = Image.new("RGB", (w, h), base_rgb)
    d = ImageDraw.Draw(img)
    band = max(3, h // 12)
    for i in range(0, h, band * 2):
        d.rectangle([0, i, w, i + band - 1], fill=(238, 232, 214))
    # ribs
    for x in range(0, w, 6):
        d.line([(x, 0), (x, h)], fill=tuple(int(c * 0.86) for c in base_rgb), width=1)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    rng = np.random.default_rng(4)
    grain = rng.random((h, w)).astype(np.float32)
    arr *= (0.93 + 0.14 * grain)[..., None]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype("uint8"))


def _blush(size=64):
    """Soft rose cheek colour, no pattern."""
    import numpy as np
    from PIL import Image
    n = np.random.default_rng(9).random((size, size)).astype(np.float32)
    arr = np.dstack([np.full((size, size), 0.86), np.full((size, size), 0.46),
                     np.full((size, size), 0.50)])
    arr *= (0.94 + 0.10 * n)[..., None]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype("uint8"))


def build_alien_textures():
    """The two striped socks and the cheek colour, as DDS."""
    made = []
    for name, img in (("sockRed", _sock((196, 46, 52))),
                      ("sockBlue", _sock((46, 92, 186))),
                      ("blush", _blush())):
        png = os.path.join(REPO, "build", name + "_diffuse.png")
        os.makedirs(os.path.dirname(png), exist_ok=True)
        img.save(png)
        subprocess_run([sys.executable, os.path.join(REPO, "tools", "png2dds.py"), png,
                        os.path.join(MOD, "textures", name + "_diffuse.dds"),
                        "--format", "bc1"])
        made.append(name)
    return made


def ensure_crop_textures():
    """The suit and goggle maps are produced by the crop harvester build; make
    them here too so the alien mod can be built on its own."""
    out = os.path.join(REPO, "FS25_CropHarvester", "textures")
    if os.path.isfile(os.path.join(out, "suit_diffuse.dds")):
        return
    os.makedirs(out, exist_ok=True)
    import textures_crop
    textures_crop.generate(out, os.path.join(REPO, "build", "crop_textures"),
                           png2dds=os.path.join(REPO, "tools", "png2dds.py"),
                           python=sys.executable, verbose=False)


def make_badge():
    """Small chest plate with CAPTAIN ZORP's name on it."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (128, 64), (208, 212, 216))
    d = ImageDraw.Draw(img)
    d.rectangle([2, 2, 125, 61], outline=(120, 126, 132), width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    except OSError:
        font = ImageFont.load_default()
    d.text((64, 26), "ZORP", font=font, anchor="mm", fill=(34, 42, 50))
    d.text((64, 47), "UFO 01", font=ImageFont.load_default(), anchor="mm",
           fill=(72, 80, 88))
    return img


def game_root():
    """Scene the way it looks in game (collision and hidden helpers are fine,
    the renderer skips them)."""
    return build_scene()


def subprocess_run(cmd):
    import subprocess
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)


def step(text):
    print("== " + text)


def main():
    step("alien model")
    root = build_scene()
    os.makedirs(MOD, exist_ok=True)
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    os.makedirs(os.path.join(REPO, "build"), exist_ok=True)
    inline = os.path.join(REPO, "build", "alien_inline.i3d")
    stats, mappings = write_i3d(root, inline, materials=MATERIALS, asset_name="alien")
    print("   %(tris)d triangles, %(verts)d vertices, %(shapes)d shapes" % stats)

    step("the tall one")
    inline2 = os.path.join(REPO, "build", "alienLeader_inline.i3d")
    stats2, _ = write_i3d(build_scene_leader(), inline2, materials=MATERIALS,
                          asset_name="alienLeader")
    print("   %(tris)d triangles" % stats2)

    step("Captain Zorp")
    inline3 = os.path.join(REPO, "build", "zorp_inline.i3d")
    stats3, _ = write_i3d(build_scene_zorp(), inline3, materials=MATERIALS,
                          asset_name="zorp")
    print("   %(tris)d triangles" % stats3)

    step("placeable + modDesc + translations")
    open(os.path.join(MOD, "alien.xml"), "w", encoding="utf-8").write(PLACEABLE_XML)
    open(os.path.join(MOD, "alienLeader.xml"), "w", encoding="utf-8").write(LEADER_XML)
    open(os.path.join(MOD, "zorp.xml"), "w", encoding="utf-8").write(ZORP_XML)
    open(os.path.join(MOD, "modDesc.xml"), "w", encoding="utf-8").write(MODDESC)
    os.makedirs(os.path.join(MOD, "translations"), exist_ok=True)
    for lang in ("de", "en"):
        open(os.path.join(MOD, "translations", "translation_%s.xml" % lang), "w", encoding="utf-8").write(TRANSLATIONS)

    step("textures")
    src = os.path.join(REPO, "FS25_UFO2000", "textures")
    for name in ("alienSkin_diffuse.dds", "alienSkin_specular.dds", "eyeBlack_diffuse.dds",
                 "lensGreen_diffuse.dds", "lensWhite_diffuse.dds",
                 "hullMetal_diffuse.dds", "hullMetal_specular.dds"):
        shutil.copyfile(os.path.join(src, name), os.path.join(MOD, "textures", name))
        print("   " + name)

    step("socks + cheeks")
    print("   " + ", ".join(build_alien_textures()))

    step("Zorp textures (flight suit, goggles, name plate)")
    ensure_crop_textures()
    crop_tex = os.path.join(REPO, "FS25_CropHarvester", "textures")
    for name in ("suit_diffuse.dds", "suit_specular.dds", "goggle_diffuse.dds",
                 "helmet_diffuse.dds", "helmet_specular.dds",
                 "helmetTrim_diffuse.dds"):
        shutil.copyfile(os.path.join(crop_tex, name), os.path.join(MOD, "textures", name))
        print("   " + name)
    badge_png = os.path.join(REPO, "build", "zorpBadge_diffuse.png")
    make_badge().save(badge_png)
    subprocess_run([sys.executable, os.path.join(REPO, "tools", "png2dds.py"), badge_png,
                    os.path.join(MOD, "textures", "zorpBadge_diffuse.dds"), "--format", "bc1"])
    print("   zorpBadge_diffuse.dds")

    step("icon + store picture")
    import render as ufo_render
    from PIL import Image
    icon = ufo_render.render(size=512, eye=(1.35, 1.25, 1.9), target=(0, 0.62, 0), fov=40, ss=2,
                             background="sky", root=game_root())
    icon.save(os.path.join(REPO, "build", "icon_alien.png"))
    subprocess_run([sys.executable, os.path.join(REPO, "tools", "png2dds.py"),
                    os.path.join(REPO, "build", "icon_alien.png"),
                    os.path.join(MOD, "icon_alien.dds"), "--format", "bc1"])
    store = ufo_render.render(size=512, eye=(1.5, 1.3, 2.05), target=(0, 0.55, 0), fov=40, ss=2,
                              background=(0.95, 0.97, 0.94), return_alpha=True, root=game_root())
    store.save(os.path.join(MOD, "store_alien.png"))
    ufo_render.render(size=512, eye=(1.55, 1.75, 2.1), target=(0, 0.85, 0), fov=40, ss=2,
                      background=(0.95, 0.97, 0.94), return_alpha=True,
                      root=build_scene_leader()).save(os.path.join(MOD, "store_alienLeader.png"))
    # Zorp is a full figure, so he needs his own materials and a taller frame
    ufo_render.MAT_LOOK.update({
        "suit": ((0.28, 0.40, 0.22), 0.35, 0.0, 1.0),
        "goggle": ((0.16, 0.17, 0.19), 0.55, 0.0, 1.0),
        "badge": ((0.86, 0.88, 0.90), 0.4, 0.15, 1.0),
        "sockRed": ((0.78, 0.22, 0.24), 0.15, 0.0, 1.0),
        "sockBlue": ((0.22, 0.38, 0.72), 0.15, 0.0, 1.0),
        "blush": ((0.86, 0.52, 0.54), 0.15, 0.0, 1.0),
        "helmet": ((0.88, 0.89, 0.86), 0.45, 0.0, 1.0),
        "helmetTrim": ((0.84, 0.42, 0.12), 0.35, 0.0, 1.0),
    })
    ufo_render.load_textures({
        "suit": os.path.join(REPO, "build", "crop_textures", "suit_diffuse.png"),
        "badge": os.path.join(REPO, "build", "zorpBadge_diffuse.png"),
        "sockRed": os.path.join(REPO, "build", "sockRed_diffuse.png"),
        "sockBlue": os.path.join(REPO, "build", "sockBlue_diffuse.png"),
        "blush": os.path.join(REPO, "build", "blush_diffuse.png"),
    })
    ufo_render.render(size=512, eye=(1.60, 1.80, 2.50), target=(0, 0.92, 0), fov=36, ss=2,
                      background=(0.95, 0.97, 0.94), return_alpha=True,
                      root=build_scene_zorp()).save(os.path.join(MOD, "store_zorp.png"))
    ufo_render.render(size=700, eye=(2.2, 2.1, 3.0), target=(0, 0.92, 0), fov=36, ss=2,
                      root=build_scene_zorp()).save(
                          os.path.join(REPO, "docs", "renders", "alien_zorp.png"))
    print("   icon_alien.dds, store_alien.png, store_alienLeader.png, store_zorp.png")

    step("binarize")
    import subprocess
    for src_inline, out_name in ((inline, "alien"), (inline2, "alienLeader"),
                                 (inline3, "zorp")):
        subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "i3d", "binarize_i3d.py"),
                               src_inline, "--out", os.path.join(MOD, out_name + ".i3d")])
        print("   %s.i3d + %s.i3d.shapes" % (out_name, out_name))

    step("validate + zip")
    import zipfile
    import subprocess
    subprocess.call([sys.executable, os.path.join(HERE, "validate.py"),
                     "--zip", os.path.join(REPO, "dist", "FS25_Alien.zip")] +
                    (["--xsd", os.environ["FS25_MOD_SCHEMA_DIR"]] if os.environ.get("FS25_MOD_SCHEMA_DIR") else []))
    dist = os.path.join(REPO, "dist")
    os.makedirs(dist, exist_ok=True)
    zpath = os.path.join(dist, "FS25_Alien.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root_dir, _dirs, files in os.walk(MOD):
            for name in sorted(files):
                full = os.path.join(root_dir, name)
                z.write(full, os.path.relpath(full, MOD))
    print("   %s (%.2f MB)" % (zpath, os.path.getsize(zpath) / 1048576.0))
    return stats


if __name__ == "__main__":
    main()
