#!/usr/bin/env python3
"""Build the separate FS25_BabaJagaHouse residential home mod.

This is intentionally separate from FS25_BabaJaga, which remains the working
chicken husbandry. The residence uses the same procedural art, but adds
walkable collisions, real stair treads, a balcony, and native farmhouse,
wardrobe, and animated-door placeable XML. No Lua is packaged.

Usage: python tools/build_babajaga_house_mod.py
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_BabaJagaHouse")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")
BABAJAGA = os.path.join(TOOLS, "babajaga")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))
sys.path.insert(0, BABAJAGA)

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".txt")


def step(message):
    print("\n== " + message)


def build_model():
    step("procedural residential model")
    import binarize_i3d
    import residence

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "babaJagaHouse_inline.i3d")
    stats, mappings = residence.write(inline)
    result = binarize_i3d.binarize(inline, os.path.join(MOD, "babaJagaHouse.i3d"))
    print("  babaJagaHouse.i3d  %2d shapes, %5d tris, %s %d kB"
          % (stats["shapes"], stats["tris"], os.path.basename(result["shapes_path"]),
             result["size"] // 1024))
    return mappings


def build_textures():
    step("shared Baba Jaga textures")
    import assets

    out = os.path.join(MOD, "textures")
    os.makedirs(out, exist_ok=True)
    made = assets.generate(out, os.path.join(BUILD, "babajaga_house_textures"))
    print("  %d DDS textures" % len(made))


def inject_placeable(mappings):
    step("native residential placeable XML")
    with open(os.path.join(BABAJAGA, "residence.template.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        raise RuntimeError("mapping markers missing in residence.template.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    path = os.path.join(MOD, "babaJagaHouse.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    shutil.copy2(os.path.join(BABAJAGA, "residence.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    print("  %d generated I3D mappings" % mappings.count("i3dMapping id="))


def _render_scene(ground=False):
    import residence
    from meshlib import Mesh, disc
    from model import Node

    root = residence.build_scene()
    if ground:
        ground_mesh = Mesh()
        ground_mesh.add("moss", *disc(10.0, 0.0, segments=64, up=True))
        root.add(Node("Shape", "renderGround", ground_mesh, translation="0 -0.05 0"))
    return root


def build_images():
    step("shop artwork and render")
    import images as ufo_images
    import render

    texture_dir = os.path.join(BUILD, "babajaga_house_textures")
    texture_map = {}
    for name in os.listdir(texture_dir):
        if name.endswith("_diffuse.png"):
            texture_map[name[:-len("_diffuse.png")]] = os.path.join(texture_dir, name)
    render.load_textures(texture_map)

    icon = render.render(size=512, eye=(12.2, 7.0, 14.2), target=(0.2, 4.0, 1.8),
                         fov=39, ss=2, root=_render_scene(ground=True))
    icon_png = os.path.join(BUILD, "icon_babaJagaHouse.png")
    icon.save(icon_png)
    ufo_images._dds(icon_png, os.path.join(MOD, "icon_babaJagaHouse.dds"),
                    "bc1", sys.executable)

    render.render(size=512, eye=(12.2, 7.0, 14.2), target=(0.2, 4.0, 1.8),
                  fov=39, ss=2, return_alpha=True,
                  root=_render_scene()).save(os.path.join(MOD, "store_babaJagaHouse.png"))

    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)
    render.render(size=900, eye=(15.5, 8.0, 13.0), target=(0.2, 4.2, 1.7),
                  fov=39, ss=2, root=_render_scene(ground=True)).save(
                      os.path.join(docs, "babajaga_house_hero.png"))
    print("  icon, store image and house render created")


def validate():
    step("static validation")
    subprocess.run([sys.executable, os.path.join(BABAJAGA, "validate_house.py")],
                   check=True)


def make_zip():
    step("package")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_BabaJagaHouse.zip")
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for root, _dirs, files in os.walk(MOD):
            for name in sorted(files):
                if not name.lower().endswith(ZIP_EXT):
                    continue
                full = os.path.join(root, name)
                archive.write(full, os.path.relpath(full, MOD))
                count += 1
    print("  %s (%.1f MB, %d files)"
          % (out, os.path.getsize(out) / 1e6, count))


def main():
    os.makedirs(MOD, exist_ok=True)
    mappings = build_model()
    build_textures()
    inject_placeable(mappings)
    build_images()
    validate()
    make_zip()
    print("\nOK - dist/FS25_BabaJagaHouse.zip (separate from the chicken coop)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
