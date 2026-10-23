#!/usr/bin/env python3
"""Build FS25_Disco - the farm disco - and zip it.

  1. procedural scene  -> build/disco_inline.i3d
  2. binarize          -> FS25_Disco/disco.i3d(.shapes)
  3. textures          -> FS25_Disco/textures/*.dds
  4. music             -> FS25_Disco/sounds/*.ogg   (tools/venue/music.py)
  5. placeable XML     -> FS25_Disco/disco.xml (+ i3dMappings)
  6. scripts / modDesc -> FS25_Disco/{scripts/Disco.lua, modDesc.xml}
  7. images            -> icon + store picture + doc renders
  8. validate          -> tools/venue/validate.py --mod disco
  9. zip               -> dist/FS25_Disco.zip

Usage:  python tools/build_disco_mod.py
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_Disco")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")
VENUE = os.path.join(TOOLS, "venue")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))
sys.path.insert(0, VENUE)

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt", ".lua")

ICON_EYE = (14.5, 8.2, 16.5)
ICON_TARGET = (-0.4, 3.2, 0.0)
ICON_FOV = 44


def step(msg):
    print("\n== " + msg)


def build_model():
    step("model")
    import binarize_i3d
    import disco

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "disco_inline.i3d")
    stats, mappings = disco.write(inline)
    res = binarize_i3d.binarize(inline, os.path.join(MOD, "disco.i3d"))
    print("  disco.i3d  %2d shapes, %5d tris, %s %d kB"
          % (stats["shapes"], stats["tris"], os.path.basename(res["shapes_path"]),
             res["size"] // 1024))
    return mappings


def build_textures():
    step("textures")
    import venue_textures
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    keep = {name for name in venue_textures.TEXTURES
            if name.split("_")[0] in ("concrete", "plank", "darkMetal", "speaker",
                                      "mirror", "danceFloor", "neonPink", "neonCyan",
                                      "neonYellow", "neonGreen", "gravel")}
    venue_textures.generate(os.path.join(MOD, "textures"),
                            os.path.join(BUILD, "disco_tex"), only=keep)


def build_music():
    step("music")
    import music
    out = os.path.join(MOD, "sounds")
    os.makedirs(out, exist_ok=True)
    made = music.generate(out, kinds=music.TRACKS, bars=12)
    for name in made.values():
        print("  %-14s %5.1f kB" % (name, os.path.getsize(os.path.join(out, name)) / 1024.0))


def inject(mappings):
    step("placeable XML + scripts")
    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    with open(os.path.join(VENUE, "disco.template.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in disco.template.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    with open(os.path.join(MOD, "disco.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    shutil.copy2(os.path.join(VENUE, "disco.modDesc.xml"), os.path.join(MOD, "modDesc.xml"))
    shutil.copy2(os.path.join(VENUE, "Disco.lua"),
                 os.path.join(MOD, "scripts", "Disco.lua"))
    shutil.copy2(os.path.join(VENUE, "discoSounds.xml"),
                 os.path.join(MOD, "sounds", "discoSounds.xml"))
    print("  disco.xml %d mappings, Disco.lua, discoSounds.xml, modDesc.xml"
          % mappings.count("i3dMapping id="))


def scene():
    import disco
    return disco.build_scene()


def build_images():
    step("images")
    import images as ufo_images
    import render

    render.MAT_LOOK.update(__import__("disco").LOOK)
    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV,
                         ss=2, root=scene())
    p = os.path.join(BUILD, "icon_disco.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_disco.dds"), "bc1", sys.executable)

    render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV, ss=2,
                  return_alpha=True, root=scene()).save(
        os.path.join(MOD, "store_disco.png"))

    render.render(size=900, eye=(17.5, 9.5, 18.5), target=(-0.5, 3.2, 0.0),
                  fov=44, ss=2, root=scene()).save(os.path.join(docs, "disco_hero.png"))
    render.render(size=800, eye=(0.6, 1.7, 10.4), target=(0.0, 2.4, -3.0),
                  fov=62, ss=2, root=scene()).save(os.path.join(docs, "disco_inside.png"))
    print("  icon, store picture, disco_hero.png, disco_inside.png")


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(VENUE, "validate.py"), "--mod", "disco",
           "--zip", os.path.join(DIST, "FS25_Disco.zip")]
    subprocess.run(cmd, check=True)


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_Disco.zip")
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
    mappings = build_model()
    build_textures()
    build_music()
    inject(mappings)
    build_images()
    make_zip()
    validate()
    print("\nOK - dist/FS25_Disco.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
