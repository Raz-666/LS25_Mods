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

from meshlib import Mesh, place, sphere, cylinder, torus   # noqa: E402
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


MATERIALS = [
    {"name": "alienSkin", "diffuse": "alienSkin_diffuse.dds", "gloss": "alienSkin_specular.dds"},
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

MODDESC = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<modDesc descVersion="96" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="https://validation.gdn.giants-software.com/xml/fs25/modDesc.xsd">
    <author>Arena.ai Agent Mode</author>
    <version>1.0.0.0</version>

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

Price: 750  |  Category: decorations]]></en>
        <de><![CDATA[Ein kleiner grüner Kumpel für den Hof - genau der Alien, der aus dem UFO 2000 schaut.

* Aufstellbare Deko, überall platzierbar, frei drehbar und wieder aufnehmbar
* Im UFO 2000 sitzt jetzt dein eigener Charakter unter der Glaskuppel, deshalb
  wohnt der Alien ab sofort in seinem eigenen kleinen Mod
* Modell und Texturen werden von Skripten erzeugt, keine Spieldateien kopiert

Preis: 750  |  Kategorie: Deko]]></de>
    </description>

    <iconFilename>icon_alien.dds</iconFilename>
    <multiplayer supported="true"/>

    <storeItems>
        <storeItem xmlFilename="alien.xml"/>
    </storeItems>
</modDesc>
"""

TRANSLATIONS = """<?xml version="1.0" encoding="utf-8" standalone="no"?>
<l10n>
    <text name="alien_name"><de>Alien-Maskottchen</de><en>Alien mascot</en></text>
    <text name="function_alien"><de>Dekoration</de><en>Decoration</en></text>
</l10n>
"""


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

    step("placeable + modDesc + translations")
    open(os.path.join(MOD, "alien.xml"), "w", encoding="utf-8").write(PLACEABLE_XML)
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
    print("   icon_alien.dds, store_alien.png")

    step("binarize")
    import subprocess
    subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "i3d", "binarize_i3d.py"),
                           inline, "--out", os.path.join(MOD, "alien.i3d")])
    print("   alien.i3d + alien.i3d.shapes")

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
