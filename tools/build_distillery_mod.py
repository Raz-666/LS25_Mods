#!/usr/bin/env python3
"""Build FS25_Distillery - the Leipzig techno club - and zip it.

  1. procedural scene  -> build/distillery_inline.i3d
  2. binarize          -> FS25_Distillery/distillery.i3d(.shapes)
  3. textures          -> FS25_Distillery/textures/*.dds  (incl. the set list)
  4. music             -> FS25_Distillery/sounds/*.ogg   (tools/venue/music.py)
  5. placeable XML     -> FS25_Distillery/distillery.xml (+ i3dMappings)
  6. scripts / modDesc -> FS25_Distillery/{scripts/Distillery.lua, modDesc.xml}
  7. images            -> icon + store picture + doc renders
  8. zip               -> dist/FS25_Distillery.zip
  9. validate          -> tools/venue/validate.py --mod distillery

Usage:  python tools/build_distillery_mod.py [--skip-renders] [--skip-music]
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_Distillery")
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

ICON_EYE = (-36.0, 15.0, -44.0)
ICON_TARGET = (6.0, 4.0, -4.0)
ICON_FOV = 40


def step(msg):
    print("\n== " + msg)


def build_model():
    step("model")
    import binarize_i3d
    import distillery

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "distillery_inline.i3d")
    stats, mappings = distillery.write(inline)
    res = binarize_i3d.binarize(inline, os.path.join(MOD, "distillery.i3d"))
    print("  distillery.i3d  %2d shapes, %5d tris, %s %d kB"
          % (stats["shapes"], stats["tris"], os.path.basename(res["shapes_path"]),
             res["size"] // 1024))
    return mappings


def build_textures():
    step("textures")
    import club_textures
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    club_textures.generate(os.path.join(MOD, "textures"),
                           os.path.join(BUILD, "distillery_tex"))


def build_music():
    step("music")
    import distillery
    import music
    out = os.path.join(MOD, "sounds")
    os.makedirs(out, exist_ok=True)
    for i, (key, _title, _bpm) in enumerate(distillery.TRACKS):
        y = music.make_track(key, bars=32, seed=11 + i)
        path = os.path.join(out, key + ".ogg")
        size = music.write_ogg(path, y)
        print("  %-18s %5.1f s  %6.1f kB"
              % (key + ".ogg", len(y) / float(music.FS), size / 1024.0))


def inject(mappings):
    step("placeable XML + scripts")
    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    with open(os.path.join(VENUE, "distillery.template.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in distillery.template.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    with open(os.path.join(MOD, "distillery.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    shutil.copy2(os.path.join(VENUE, "distillery.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    shutil.copy2(os.path.join(VENUE, "Distillery.lua"),
                 os.path.join(MOD, "scripts", "Distillery.lua"))
    # keep the marker spacing of the script in sync with the board geometry
    import distillery
    row_h = (distillery.PANEL_H *
             (1.0 - distillery.PANEL_TOP - distillery.PANEL_BOTTOM) / len(distillery.TRACKS))
    with open(os.path.join(VENUE, "distillerySounds.xml"), encoding="utf-8") as fh:
        sounds = fh.read()
    sounds = re.sub(r'rowHeight="[^"]*"', 'rowHeight="%.3f"' % row_h, sounds, count=1)
    with open(os.path.join(MOD, "sounds", "distillerySounds.xml"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(sounds)
    print("  set list row height %.3f m" % row_h)
    print("  distillery.xml %d mappings, Distillery.lua, distillerySounds.xml, modDesc.xml"
          % mappings.count("i3dMapping id="))


def scene():
    import distillery
    return distillery.build_scene()


def load_textures():
    """The same PNGs the DDS files are made from, so the renders show the real
    brick, cobbles and neon lettering."""
    import club_textures
    import render

    mapping = {}
    for name in club_textures.TEXTURES:
        if not name.endswith("_diffuse"):
            continue
        mat = name[:-len("_diffuse")]
        mapping[mat] = os.path.join(BUILD, "distillery_tex", name + ".png")
    render.load_textures(mapping)


def build_images():
    step("images")
    import images as ufo_images
    import render

    import distillery
    render.MAT_LOOK.update(distillery.LOOK)
    load_textures()
    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV,
                         ss=2, root=scene())
    p = os.path.join(BUILD, "icon_distillery.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_distillery.dds"), "bc1", sys.executable)

    render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV, ss=2,
                  return_alpha=True, root=scene()).save(
        os.path.join(MOD, "store_distillery.png"))

    render.render(size=1000, eye=(2.0, 6.2, -40.0), target=(-1.0, 5.0, -12.0),
                  fov=40, ss=2, root=scene()).save(os.path.join(docs, "distillery_hero.png"))
    render.render(size=900, eye=(0.6, 1.75, 1.6), target=(-1.4, 2.6, -9.0),
                  fov=66, ss=2, root=scene()).save(os.path.join(docs, "distillery_floor.png"))
    render.render(size=1000, eye=(33.0, 9.0, 28.0), target=(15.0, 1.8, 11.0),
                  fov=46, ss=2, root=scene()).save(os.path.join(docs, "distillery_garden.png"))
    print("  icon, store picture, distillery_hero/floor/garden.png")


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_Distillery.zip")
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


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(VENUE, "validate.py"), "--mod", "distillery",
           "--zip", os.path.join(DIST, "FS25_Distillery.zip")]
    subprocess.run(cmd, check=True)


def main(argv):
    os.makedirs(MOD, exist_ok=True)
    mappings = build_model()
    build_textures()
    if "--skip-music" not in argv:
        build_music()
    inject(mappings)
    if "--skip-renders" not in argv:
        build_images()
    make_zip()
    validate()
    print("\nOK - dist/FS25_Distillery.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
