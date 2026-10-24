#!/usr/bin/env python3
"""Build FS25_Autokino - the drive-in cinema - and zip it.

  1. procedural scene  -> build/autokino_inline.i3d
  2. binarize          -> FS25_Autokino/autokino.i3d(.shapes)
  3. textures          -> FS25_Autokino/textures/*.dds
  4. film frames       -> FS25_Autokino/textures/film/*.dds  (tools/venue/film.py)
  5. soundtracks       -> FS25_Autokino/sounds/film{1,2,3}.ogg
  6. placeable XML     -> FS25_Autokino/autokino.xml (+ i3dMappings)
  7. scripts / modDesc -> FS25_Autokino/{scripts/Autokino.lua, modDesc.xml}
  8. images            -> icon + store picture + doc renders
  9. zip               -> dist/FS25_Autokino.zip

Usage:  python tools/build_autokino_mod.py
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_Autokino")
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

# sound track for each of the three films
SOUNDTRACKS = (("country", "film1"), ("techno", "film2"), ("chill", "film3"))

ICON_EYE = (34.0, 15.0, 30.0)
ICON_TARGET = (0.0, 5.0, -8.0)
ICON_FOV = 42


def step(msg):
    print("\n== " + msg)


def build_model():
    step("model")
    import binarize_i3d
    import autokino

    os.makedirs(BUILD, exist_ok=True)
    stats, mappings = autokino.write(os.path.join(BUILD, "autokino_inline.i3d"))
    res = binarize_i3d.binarize(os.path.join(BUILD, "autokino_inline.i3d"),
                                os.path.join(MOD, "autokino.i3d"))
    print("  autokino.i3d  %2d shapes, %5d tris, %s %d kB"
          % (stats["shapes"], stats["tris"], os.path.basename(res["shapes_path"]),
             res["size"] // 1024))
    return mappings


def build_textures():
    step("textures")
    import venue_textures
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    keep = {name for name in venue_textures.TEXTURES
            if name.split("_")[0] in ("gravel", "asphalt", "concrete", "darkMetal",
                                      "plank", "screen", "neonPink", "neonCyan",
                                      "neonYellow")}
    venue_textures.generate(os.path.join(MOD, "textures"),
                            os.path.join(BUILD, "autokino_tex"), only=keep)


def build_films():
    step("films")
    import film
    out = os.path.join(MOD, "textures", "film")
    film.generate(out, os.path.join(BUILD, "film_png"))


def build_music():
    step("soundtracks")
    import music
    tmp = os.path.join(BUILD, "autokino_music")
    made = music.generate(tmp, kinds=[k for k, _ in SOUNDTRACKS], bars=12)
    out = os.path.join(MOD, "sounds")
    os.makedirs(out, exist_ok=True)
    for kind, name in SOUNDTRACKS:
        src = os.path.join(tmp, made[kind])
        dst = os.path.join(out, name + ".ogg")
        shutil.copy2(src, dst)
        print("  %-14s from %s  %5.1f kB"
              % (name + ".ogg", made[kind], os.path.getsize(dst) / 1024.0))


def inject(mappings):
    step("placeable XML + scripts")
    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    with open(os.path.join(VENUE, "autokino.template.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in autokino.template.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    with open(os.path.join(MOD, "autokino.xml"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    shutil.copy2(os.path.join(VENUE, "autokino.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    shutil.copy2(os.path.join(VENUE, "Autokino.lua"),
                 os.path.join(MOD, "scripts", "Autokino.lua"))
    shutil.copy2(os.path.join(VENUE, "autokinoSounds.xml"),
                 os.path.join(MOD, "sounds", "autokinoSounds.xml"))
    print("  autokino.xml %d mappings, Autokino.lua, autokinoSounds.xml, modDesc.xml"
          % mappings.count("i3dMapping id="))


def scene():
    import autokino
    return autokino.build_scene()


SCREEN_CORNERS = ((-6.5, 3.2, -15.0), (6.5, 3.2, -15.0),
                 (6.5, 10.5, -15.0), (-6.5, 10.5, -15.0))


def _with_frame(img, size, eye, target, fov, film_key="ufo", frame=8):
    """Paste one of the drawn film frames onto the blank screen."""
    import film as films
    import venue

    fn = dict((key, f) for key, _title, f in films.FILMS)[film_key]
    frame_img = fn(frame, films.FRAMES).resize((640, 360))
    quad = venue.project_points(SCREEN_CORNERS, eye, target, fov, size)
    return venue.paste_quad(img, frame_img, quad)


def build_images():
    step("images")
    import autokino
    import images as ufo_images
    import render

    render.MAT_LOOK.update(autokino.LOOK)
    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = _with_frame(render.render(size=512, eye=ICON_EYE, target=ICON_TARGET,
                                     fov=ICON_FOV, ss=2, root=scene()),
                       512, ICON_EYE, ICON_TARGET, ICON_FOV)
    p = os.path.join(BUILD, "icon_autokino.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_autokino.dds"), "bc1", sys.executable)

    _with_frame(render.render(size=512, eye=ICON_EYE, target=ICON_TARGET, fov=ICON_FOV,
                              ss=2, return_alpha=True, root=scene()),
                512, ICON_EYE, ICON_TARGET, ICON_FOV, film_key="tractor", frame=4).save(
        os.path.join(MOD, "store_autokino.png"))

    _with_frame(render.render(size=900, eye=(30.0, 14.0, 30.0), target=(0.0, 5.0, -7.0),
                              fov=44, ss=2, root=scene()),
                900, (30.0, 14.0, 30.0), (0.0, 5.0, -7.0), 44, film_key="ufo", frame=6).save(
        os.path.join(docs, "autokino_hero.png"))
    _with_frame(render.render(size=800, eye=(0.0, 2.8, 6.0), target=(0.0, 6.6, -15.0),
                              fov=54, ss=2, root=scene()),
                800, (0.0, 2.8, 6.0), (0.0, 6.6, -15.0), 54, film_key="alien", frame=12).save(
        os.path.join(docs, "autokino_screen.png"))
    print("  icon, store picture, autokino_hero.png, autokino_screen.png")


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(VENUE, "validate.py"), "--mod", "autokino",
           "--zip", os.path.join(DIST, "FS25_Autokino.zip")]
    subprocess.run(cmd, check=True)


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_Autokino.zip")
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
    build_films()
    build_music()
    inject(mappings)
    build_images()
    make_zip()
    validate()
    print("\nOK - dist/FS25_Autokino.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
