#!/usr/bin/env python3
"""Build the console edition FS25_UFO2500 (no Lua) and zip it.

Steps
  1. procedural scene -> build/ufo2500_inline.i3d + i3dMappings
  2. binarize         -> FS25_UFO2500/ufo2500.i3d + ufo2500.i3d.shapes
  3. inject the i3d mappings and the wheel configurations into ufo2500.xml
  4. textures/sounds  -> copied from FS25_UFO2000 (same materials, same audio)
  5. images           -> icon_ufo2500.dds, store_ufo2500.png, docs renders
  6. validate         -> tools/ufo/validate2500.py
  7. zip              -> dist/FS25_UFO2500.zip

Usage:  python tools/build_console_mod.py [--skip-media]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_UFO2500")
SOURCE_MOD = os.path.join(REPO, "FS25_UFO2000")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))

TEMPLATE = os.path.join(TOOLS, "ufo", "ufo2500.template.xml")
MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
WHEEL_MARKER = "            <!-- WHEELS -->"

ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt")

# ---------------------------------------------------------------------------
# wheel configurations
# ---------------------------------------------------------------------------
# (node, isLeft, steerable) - two wide wheels in line, like a motorcycle
LOAD_WHEELS = (
    ("wheelFront", "true", True),
    ("wheelRear", "false", False),
)
# tiny hidden wheels against tipping over
OUTRIGGERS = (
    ("wheelOutriggerLeft", "true"),
    ("wheelOutriggerRight", "false"),
)

# (l10n key, saveId, number of 0.5 m brush modules)
BRUSH_CONFIGS = (
    ("ufo2500_brushPen", "PEN", 1),
    ("ufo2500_brushRing", "RING", 3),
    ("ufo2500_brushStandard", "STANDARD", 7),
    ("ufo2500_brushHarvester", "HARVESTER", 15),
)
DEFAULT_CONFIG = "STANDARD"

# spring/damper scale roughly with the load they carry (base game reference:
# restLoad 1.4 t -> spring 38, damper 40), so the saucer neither sags nor bounces
# spring/damper follow the load per wheel (base game reference: a 1.4 t wheel
# load uses spring 38 / damper 40), so the saucer neither sags nor bounces
PHYSICS = ('repr="{repr}" radius="0.55" width="{width}" mass="{mass}" '
           'restLoad="{load}" forcePointRatio="0.4" initialCompression="25" '
           'suspTravel="0.15" spring="{spring}" damper="{damper}" '
           'frictionScale="{friction}" maxLongStiffness="30" maxLatStiffness="{lat}" '
           'rotationDamping="0.05" tireType="mud"')

WIDE = dict(width="0.70", mass="0.15", load="0.55", spring="16", damper="18",
            friction="1", lat="40")
STAB = dict(width="0.05", mass="0.01", load="0.05", spring="4", damper="5",
            friction="0.2", lat="6")
BRUSH = dict(width="0.50", mass="0.02", load="0.20", spring="6", damper="7",
             friction="1", lat="40")
STEERING = ' rotMax="30" rotMin="-30" rotSpeed="45" rotSpeedNeg="-45"'


def step(msg):
    print("\n== %s" % msg)


def wheel_block():
    import model_console as mc

    out = []
    for key, save_id, modules in BRUSH_CONFIGS:
        default = ' isDefault="true"' if save_id == DEFAULT_CONFIG else ""
        out.append('            <wheelConfiguration name="$l10n_%s" price="0" saveId="%s"%s>'
                   % (key, save_id, default))
        out.append('                <wheels hasSurfaceSounds="false" autoRotateBackSpeed="1">')
        for node, is_left, steerable in LOAD_WHEELS:
            out.append('                    <wheel isLeft="%s" isCareWheel="true">' % is_left)
            physics = PHYSICS.format(repr=node, **WIDE)
            if steerable:
                physics += STEERING
            out.append("                        <physics %s/>" % physics)
            out.append("                    </wheel>")
        for node, is_left in OUTRIGGERS:
            out.append('                    <wheel isLeft="%s" isCareWheel="true">' % is_left)
            out.append("                        <physics %s/>" % PHYSICS.format(repr=node, **STAB))
            out.append("                    </wheel>")
        for node in mc.brush_module_names(modules):
            out.append('                    <wheel isLeft="true" isCareWheel="false">')
            out.append("                        <physics %s/>"
                       % PHYSICS.format(repr=node, **BRUSH))
            out.append("                    </wheel>")
        out.append("                </wheels>")
        out.append("            </wheelConfiguration>")
    return "\n".join(out)


def build_model():
    step("model + i3d")
    import model_console
    stats, mappings = model_console.write(os.path.join(BUILD, "ufo2500_inline.i3d"))
    print("  %d shapes, %d tris" % (stats["shapes"], stats["tris"]))

    import binarize_i3d
    res = binarize_i3d.binarize(os.path.join(BUILD, "ufo2500_inline.i3d"),
                                os.path.join(MOD, "ufo2500.i3d"))
    print("  wrote %s (%d kB)" % (os.path.basename(res["shapes_path"]), res["size"] // 1024))
    return mappings


def inject_xml(mappings):
    step("i3d mappings + wheels -> ufo2500.xml")
    path = os.path.join(MOD, "ufo2500.xml")
    with open(TEMPLATE, encoding="utf-8") as fh:
        xml = fh.read()

    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in ufo2500.xml")
    block = ("    <i3dMappings>\n" + mappings + "\n    </i3dMappings>")
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)

    if WHEEL_MARKER not in xml:
        sys.exit("wheel marker missing in ufo2500.xml")
    xml = xml.replace(WHEEL_MARKER, wheel_block())

    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  %d mappings, %d wheel configurations"
          % (mappings.count("i3dMapping id="), len(BRUSH_CONFIGS)))


def copy_assets():
    step("textures + sounds")
    copied = 0
    for sub in ("textures", "sounds"):
        src = os.path.join(SOURCE_MOD, sub)
        dst = os.path.join(MOD, sub)
        if not os.path.isdir(src):
            sys.exit("%s is missing - run tools/build_mod.py first" % src)
        os.makedirs(dst, exist_ok=True)
        for name in sorted(os.listdir(src)):
            if not name.lower().endswith((".dds", ".ogg")):
                continue
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
            copied += 1
    print("  %d files" % copied)


def landed_scene(scene=None):
    """The scene as it looks after the landing animation (craft at street level)."""
    import model_console
    root = scene or model_console.build_scene()
    visual = model_console.find(root, "visual")
    x, y, z = model_console._xyz(visual)
    visual.attrs["translation"] = "%s %s %s" % (model_console._fmt([x]),
                                                model_console._fmt([0.95]),
                                                model_console._fmt([z]))
    for i, splay in zip(range(3), (16.0, 16.0, 16.0)):
        leg = model_console.find(root, "leg%d" % i)
        rot = leg.attrs["rotation"].split()
        leg.attrs["rotation"] = "%s %s %s" % (rot[0], rot[1], model_console._fmt([splay]))
    beam = model_console.find(root, "beamNode")
    beam.attrs["scale"] = "0.9 1.0 0.9"
    ring = model_console.find(root, "groundRing")
    ring.attrs["translation"] = "0 -0.88 0"
    ring.attrs["scale"] = "0.9 1 0.9"
    return root


def build_images():
    step("images")
    import model_console
    import render
    import images as ufo_images

    mod = MOD
    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)
    scene = model_console.build_scene()

    # 1) shop / mod icon, 512x512 BC1 with mipmaps - the saucer alone
    craft = model_console.build_scene()
    for name in ("beamNode", "groundRing"):
        node = model_console.find(craft, name)
        if node is not None:
            node.attrs["visibility"] = "false"
    icon = render.render(size=512, eye=(11.0, 24.0, 13.5), target=(0, 19.4, 0), fov=34,
                         ss=2, root=craft)
    p = os.path.join(BUILD, "icon_ufo2500.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(mod, "icon_ufo2500.dds"), "bc1", sys.executable)

    # 2) store picture (RGBA): the whole craft with the beam reaching the ground
    store = render.render(size=512, eye=(20.0, 21.5, 23.0), target=(0, 12.0, 0), fov=40,
                          ss=2, beam=True, return_alpha=True, root=scene)
    store.save(os.path.join(mod, "store_ufo2500.png"))

    # 3) documentation renders
    render.render(size=900, eye=(24.0, 15.0, 27.0), target=(0, 9.8, 0), fov=34, ss=2,
                  beam=True, root=scene).save(os.path.join(docs, "ufo2500_hero.png"))
    render.render(size=760, eye=(14.0, 22.0, 18.0), target=(0, 16.5, 0), fov=38, ss=2,
                  beam=True, root=scene).save(os.path.join(docs, "ufo2500_top.png"))
    render.render(size=760, eye=(9.6, 4.6, 10.2), target=(0, 1.5, 0), fov=40, ss=2,
                  beam=True, root=landed_scene()).save(
        os.path.join(docs, "ufo2500_landed.png"))
    print("  icon, store picture, 3 doc renders")


def validate():
    step("validation")
    rc = subprocess.run([sys.executable, os.path.join(TOOLS, "ufo", "validate2500.py")]).returncode
    if rc != 0:
        sys.exit("validation failed")


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_UFO2500.zip")
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
    with zipfile.ZipFile(out) as z:
        assert "modDesc.xml" in z.namelist(), "modDesc.xml is not at the zip root"
        count = len(z.namelist())
    print("  %s (%.1f MB, %d files)" % (out, os.path.getsize(out) / 1048576.0, count))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-media", action="store_true", help="only rebuild model and xml")
    args = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)
    mappings = build_model()
    inject_xml(mappings)
    if not args.skip_media:
        copy_assets()
        build_images()
    make_zip()
    validate()


if __name__ == "__main__":
    main()
