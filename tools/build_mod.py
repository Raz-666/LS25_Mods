#!/usr/bin/env python3
"""Build the FS25 UFO 2000 mod from source and zip it for the mods folder.

Steps
  1. procedural model  -> build/ufo_inline.i3d + build/i3dMappings.xml
  2. binarize          -> FS25_UFO2000/ufo.i3d + ufo.i3d.shapes
  3. inject the i3d node mappings into FS25_UFO2000/ufo.xml
  4. textures          -> FS25_UFO2000/textures/*.dds
  5. sounds            -> FS25_UFO2000/sounds/*.ogg
  6. images            -> icon / store picture / brand
  7. validate          -> tools/ufo/validate.py
  8. zip               -> dist/FS25_UFO2000.zip (modDesc.xml at the zip root)

Usage:  python tools/build_mod.py [--skip-media]
Needs numpy, pillow and soundfile (see requirements.txt).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_UFO2000")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"

ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".lua", ".txt")


def step(msg):
    print("\n== %s" % msg)


def ensure_source_mod():
    """Seed the ignored working mod folder from the last built archive.

    The human-maintained specialization, description and translations now live
    under tools/ufo; dist/ remains the seed for generated XML/media assets.
    """
    if not os.path.isfile(os.path.join(MOD, "ufo.xml")):
        archive = os.path.join(DIST, "FS25_UFO2000.zip")
        if not os.path.isfile(archive):
            sys.exit("missing source vehicle XML and %s" % archive)
        os.makedirs(MOD, exist_ok=True)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(MOD)
    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    os.makedirs(os.path.join(MOD, "translations"), exist_ok=True)
    shutil.copy2(os.path.join(TOOLS, "ufo", "UFO2000.lua"),
                 os.path.join(MOD, "scripts", "UFO2000.lua"))
    shutil.copy2(os.path.join(TOOLS, "ufo", "ufo.xml"),
                 os.path.join(MOD, "ufo.xml"))
    shutil.copy2(os.path.join(TOOLS, "ufo", "ufo.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    for lang in ("de", "en"):
        shutil.copy2(os.path.join(TOOLS, "ufo", "ufo_translation_%s.xml" % lang),
                     os.path.join(MOD, "translations", "translation_%s.xml" % lang))


def build_model():

    step("model + i3d")
    import model as ufo_model
    root = ufo_model.build_scene()
    stats, mappings = ufo_model.write_i3d(root, os.path.join(BUILD, "ufo_inline.i3d"))
    with open(os.path.join(BUILD, "i3dMappings.xml"), "w", encoding="utf-8") as fh:
        fh.write(mappings + "\n")
    print("  %d shapes, %d vertices, %d triangles" % (stats["shapes"], stats["verts"], stats["tris"]))

    import binarize_i3d
    res = binarize_i3d.binarize(os.path.join(BUILD, "ufo_inline.i3d"),
                                os.path.join(MOD, "ufo.i3d"))
    print("  wrote %s (%d kB)" % (os.path.basename(res["shapes_path"]), res["size"] // 1024))


def inject_mappings():
    step("i3d mappings -> ufo.xml")
    xml_path = os.path.join(MOD, "ufo.xml")
    with open(xml_path, encoding="utf-8") as fh:
        xml = fh.read()
    with open(os.path.join(BUILD, "i3dMappings.xml"), encoding="utf-8") as fh:
        block = fh.read().rstrip("\n")
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in ufo.xml")
    xml = pattern.sub(lambda _: MAP_START + "\n    <i3dMappings>\n" + block +
                      "\n    </i3dMappings>\n" + MAP_END, xml, count=1)
    with open(xml_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  %d mappings injected" % block.count("i3dMapping id="))


def build_textures():
    step("textures")
    import textures as ufo_textures
    ufo_textures.generate(os.path.join(MOD, "textures"), os.path.join(BUILD, "textures"),
                          png2dds=os.path.join(TOOLS, "png2dds.py"), python=sys.executable,
                          verbose=True)


def build_sounds():
    step("sounds")
    import sounds as ufo_sounds
    ufo_sounds.generate(os.path.join(MOD, "sounds"), os.path.join(REPO, "docs", "sound_demo.ogg"))


def build_images():
    step("images")
    import images as ufo_images
    ufo_images.build_all(python=sys.executable)


def validate():
    step("validation")
    commands = (
        [sys.executable, os.path.join(TOOLS, "ufo", "validate.py")],
        [sys.executable, os.path.join(TOOLS, "ufo", "luatest.py")],
    )
    for command in commands:
        subprocess.run(command, check=True)


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_UFO2000.zip")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _dirs, files in os.walk(MOD):
            for name in sorted(files):
                if not name.lower().endswith(ZIP_EXT):
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, MOD).replace(os.sep, "/")
                z.write(full, rel)
    # modDesc.xml must be at the root of the archive
    with zipfile.ZipFile(out) as z:
        assert "modDesc.xml" in z.namelist(), "modDesc.xml is not at the zip root"
    size = os.path.getsize(out)
    print("  %s (%.1f MB, %d files)" % (out, size / 1048576.0,
                                        len(zipfile.ZipFile(out).namelist())))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-media", action="store_true", help="only rebuild model and xml")
    args = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)
    ensure_source_mod()
    build_model()
    inject_mappings()
    if not args.skip_media:
        build_textures()
        build_sounds()
        build_images()
    make_zip()
    validate()


if __name__ == "__main__":
    main()
