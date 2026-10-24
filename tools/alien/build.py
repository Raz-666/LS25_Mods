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


def alien_mesh():
    """Little green buddy with big shiny eyes, antennae and a friendly smile."""
    m = Mesh()
    # body and head (classic grey-alien silhouette, but green and chubby)
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.20, 28, 16, scale=(1.0, 1.15, 0.88)),
                              translation=(0, 0.23, 0)))
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.19, 28, 16, scale=(1.02, 1.06, 0.96)),
                              translation=(0, 0.54, 0.01)))
    # big shiny eyes
    for sx in (-1, 1):
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.068, 18, 14, scale=(1.0, 1.35, 0.6)),
                                 translation=(0.078 * sx, 0.56, 0.148)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.018, 10, 8),
                                  translation=(0.096 * sx, 0.598, 0.196)))
    # friendly smile
    m.add("eyeBlack", *place(sphere((0, 0, 0), 0.030, 14, 10, scale=(1.6, 0.34, 0.45)),
                             translation=(0, 0.448, 0.168)))
    # antennae with glowing tips
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.009, 0.0, 0.12, 8, caps=True),
                                  rot=(0, 0, -18 * sx), translation=(0.055 * sx, 0.665, 0)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.025, 12, 8),
                                  translation=(0.092 * sx, 0.782, 0)))
    # stubby arms
    for sx in (-1, 1):
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.075, 14, 10, scale=(0.75, 1.35, 0.75)),
                                  rot=(0, 0, 34 * sx), translation=(0.185 * sx, 0.27, 0.03)))
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.050, 12, 8),
                                  translation=(0.245 * sx, 0.155, 0.05)))
        # little feet
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.075, 14, 10, scale=(1.0, 0.5, 1.6)),
                                  translation=(0.085 * sx, 0.04, 0.04)))
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
    # --- goggles pushed up on the forehead --------------------------------
    m.add("goggle", *place(torus(0.160, 0.016, 0, 28, 6),
                           rot=(-16, 0, 0), translation=(0, 1.398, 0.020)))
    for sx in (-1, 1):
        m.add("goggle", *place(cylinder(0.054, 0.0, 0.030, 16, caps=True),
                               rot=(52, 0, 0),
                               translation=(0.070 * sx, 1.408, 0.158)))
        m.add("lensWhite", *place(disc(0.041, 0.0, 16, up=False),
                                  rot=(52, 0, 0),
                                  translation=(0.070 * sx, 1.420, 0.172)))
    m.add("hullMetal", *place(box((0, 0, 0), (0.060, 0.014, 0.014)),
                              rot=(16, 0, 0), translation=(0, 1.426, 0.150)))
    # --- antennae with glowing tips --------------------------------------
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.011, 0.0, 0.16, 8, caps=True),
                                  rot=(0, 0, -20 * sx),
                                  translation=(0.085 * sx, 1.410, -0.010)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.030, 12, 8),
                                  translation=(0.115 * sx, 1.560, -0.010)))
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

    step("Zorp textures (flight suit, goggles, name plate)")
    ensure_crop_textures()
    crop_tex = os.path.join(REPO, "FS25_CropHarvester", "textures")
    for name in ("suit_diffuse.dds", "suit_specular.dds", "goggle_diffuse.dds"):
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
    })
    ufo_render.load_textures({
        "suit": os.path.join(REPO, "build", "crop_textures", "suit_diffuse.png"),
        "badge": os.path.join(REPO, "build", "zorpBadge_diffuse.png"),
    })
    ufo_render.render(size=512, eye=(1.35, 1.55, 2.0), target=(0, 0.95, 0), fov=38, ss=2,
                      background=(0.95, 0.97, 0.94), return_alpha=True,
                      root=build_scene_zorp()).save(os.path.join(MOD, "store_zorp.png"))
    ufo_render.render(size=700, eye=(1.9, 1.9, 2.6), target=(0, 0.95, 0), fov=38, ss=2,
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
