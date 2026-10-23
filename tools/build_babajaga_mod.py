#!/usr/bin/env python3
"""Build FS25_BabaJaga - the chicken hut - and zip it.

One store item, a placeable husbandry of the base game type `chickenHusbandry`,
so the mod needs no Lua and is console safe.

  1. procedural scene  -> build/babajaga_inline.i3d
  2. binarize          -> FS25_BabaJaga/babaJaga.i3d(.shapes)
  3. textures          -> FS25_BabaJaga/textures/*.dds
  4. template          -> babaJaga.xml (+ i3dMappings)
  5. images            -> icon + store picture + doc render
  6. validate          -> tools/babajaga/validate.py
  7. zip               -> dist/FS25_BabaJaga.zip

Usage:  python tools/build_babajaga_mod.py
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_BabaJaga")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))
sys.path.insert(0, os.path.join(TOOLS, "babajaga"))

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt")

ICON_EYE = (11.0, 5.6, 12.2)
ICON_TARGET = (0.9, 3.3, 0.6)
ICON_FOV = 40


def step(msg):
    print("\n== " + msg)


def build_model():
    step("model")
    import binarize_i3d
    import hut as babajaga

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "babajaga_inline.i3d")
    stats, mappings = babajaga.write(inline)
    res = binarize_i3d.binarize(inline, os.path.join(MOD, "babaJaga.i3d"))
    print("  babaJaga.i3d  %2d shapes, %5d tris, %s %d kB"
          % (stats["shapes"], stats["tris"], os.path.basename(res["shapes_path"]),
             res["size"] // 1024))
    return mappings


def build_textures():
    step("textures")
    import assets
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    assets.generate(os.path.join(MOD, "textures"), os.path.join(BUILD, "babajaga_tex"))


def inject(mappings):
    step("placeable XML")
    with open(os.path.join(TOOLS, "babajaga", "babajaga.template.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in babajaga.template.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    shutil.copy2(os.path.join(TOOLS, "babajaga", "modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    path = os.path.join(MOD, "babaJaga.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  babaJaga.xml  %d mappings, modDesc copied"
          % mappings.count("i3dMapping id="))


def scene():
    import hut as babajaga
    return babajaga.build_scene()


def build_images():
    step("images")
    import images as ufo_images
    import render

    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV,
                         ss=2, root=scene())
    p = os.path.join(BUILD, "icon_babajaga.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_babajaga.dds"), "bc1", sys.executable)

    render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV, ss=2,
                  return_alpha=True, root=scene()).save(
        os.path.join(MOD, "store_babajaga.png"))

    render.render(size=900, eye=(10.5, 3.4, 9.5), target=(0.6, 3.4, 0.4), fov=40, ss=2,
                  root=scene()).save(os.path.join(docs, "babajaga_hero.png"))
    print("  icon, store picture, hero render")


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(TOOLS, "babajaga", "validate.py")]
    subprocess.run(cmd, check=True)


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_BabaJaga.zip")
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _dirs, files in os.walk(MOD):
            for name in sorted(files):
                if not name.lower().endswith(ZIP_EXT):
                    continue
                full = os.path.join(root, name)
                zf.write(full, os.path.relpath(full, MOD))
                count += 1
    print("  %s (%.1f MB, %d files)" % (out, os.path.getsize(out) / 1e6, count))


def main():
    os.makedirs(MOD, exist_ok=True)
    mut = build_model()
    build_textures()
    inject(mut)
    build_images()
    validate()
    make_zip()
    print("\nOK - dist/FS25_BabaJaga.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
