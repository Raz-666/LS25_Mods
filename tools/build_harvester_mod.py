#!/usr/bin/env python3
"""Build FS25_UFO4500 - the harvester variant - and zip it.

Two store items in one mod:

  * FS25_UFO4500        - the saucer combine (base game `combine` logic),
  * FS25_UFO4500Header  - the 6 m cutter that feeds it.

Both use nothing but base game specializations, so the mod is console safe.

  1. procedural scenes  -> build/ufo4500_inline.i3d, build/ufo4500header_inline.i3d
  2. binarize           -> FS25_UFO4500/*.i3d(.shapes)
  3. templates          -> ufo4500.xml, ufo4500header.xml (+ i3dMappings, wheels)
  4. media              -> textures/sounds from FS25_UFO2000, icon + store images
  5. validate           -> tools/ufo/validate4500.py
  6. zip                -> dist/FS25_UFO4500.zip

Usage:  python tools/build_harvester_mod.py
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_UFO4500")
SOURCE_MOD = os.path.join(REPO, "FS25_UFO2000")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")

sys.path.insert(0, os.path.join(TOOLS, "ufo"))
sys.path.insert(0, os.path.join(TOOLS, "i3d"))

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
WHEEL_MARKER = "            <!-- WHEELS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt")

# same invisible physics as the console mod: two wide wheels in line plus two
# tiny outriggers, all care wheels so they never destroy crop
LOAD_WHEELS = (("wheelFront", "true", True), ("wheelRear", "false", False))
OUTRIGGERS = (("wheelOutriggerLeft", "true"), ("wheelOutriggerRight", "false"))

PHYSICS = ('repr="{repr}" radius="0.55" width="{width}" mass="{mass}" '
           'restLoad="{load}" forcePointRatio="0.4" initialCompression="25" '
           'suspTravel="0.15" spring="{spring}" damper="{damper}" '
           'frictionScale="{friction}" maxLongStiffness="30" maxLatStiffness="{lat}" '
           'rotationDamping="0.05" tireType="mud"')
WIDE = dict(width="0.70", mass="0.25", load="0.60", spring="18", damper="20",
            friction="1", lat="40")
STAB = dict(width="0.05", mass="0.01", load="0.05", spring="4", damper="5",
            friction="0.2", lat="6")
STEERING = ' rotMax="30" rotMin="-30" rotSpeed="45" rotSpeedNeg="-45"'


def step(msg):
    print("\n== " + msg)


def wheel_block():
    out = ["            <wheelConfiguration name=\"$l10n_ufo4500_wheels\" price=\"0\" saveId=\"DEFAULT\" isDefault=\"true\">",
           '                <wheels hasSurfaceSounds="false" autoRotateBackSpeed="1">']
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
    out.append("                </wheels>")
    out.append("            </wheelConfiguration>")
    return "\n".join(out)


def build_models():
    step("models")
    import binarize_i3d
    import model_harvester
    import model_harvester_header

    result = {}
    for name, module in (("ufo4500", model_harvester),
                         ("ufo4500header", model_harvester_header)):
        inline = os.path.join(BUILD, name + "_inline.i3d")
        stats, mappings = module.write(inline)
        res = binarize_i3d.binarize(inline, os.path.join(MOD, name + ".i3d"))
        print("  %-14s %2d shapes, %5d tris, %s %d kB"
              % (name, stats["shapes"], stats["tris"],
                 os.path.basename(res["shapes_path"]), res["size"] // 1024))
        result[name] = mappings
    return result


def inject(template, out_name, mappings, wheels=False):
    with open(os.path.join(TOOLS, "ufo", template), encoding="utf-8") as fh:
        xml = fh.read()
    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in " + template)
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    if wheels:
        if WHEEL_MARKER not in xml:
            sys.exit("wheel marker missing in " + template)
        xml = xml.replace(WHEEL_MARKER, wheel_block())
    path = os.path.join(MOD, out_name)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  %-20s %d mappings%s" % (out_name, mappings.count("i3dMapping id="),
                                     ", wheels" if wheels else ""))


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


def build_images():
    step("images")
    import images as ufo_images
    import model_harvester
    import model_harvester_header
    import render

    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    craft = model_harvester.build_vehicle_scene()
    header = model_harvester_header.build_scene()
    # hang the header onto the craft for the pictures (the game does the same
    # with the attacher joint)
    craft.add(header)
    header.attrs["translation"] = "0 1.00 2.30"
    craft_scene = craft

    icon = render.render(size=512, eye=(12.0, 6.0, 14.0), target=(0, 1.9, 1.4), fov=38,
                         ss=2, root=craft_scene)
    p = os.path.join(BUILD, "icon_ufo4500.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_ufo4500.dds"), "bc1", sys.executable)

    render.render(size=512, eye=(12.0, 6.0, 14.0), target=(0, 1.9, 1.4), fov=38, ss=2,
                  return_alpha=True, root=craft_scene).save(
        os.path.join(MOD, "store_ufo4500.png"))
    render.render(size=512, eye=(7.5, 2.6, 7.0), target=(0, 0.1, 0.6), fov=40, ss=2,
                  return_alpha=True, root=model_harvester_header.build_scene()).save(
        os.path.join(MOD, "store_ufo4500header.png"))

    render.render(size=900, eye=(11.0, 3.6, 7.5), target=(0, 1.4, 0.8), fov=42, ss=2,
                  root=model_harvester.build_vehicle_scene()).save(
        os.path.join(docs, "ufo4500_hero.png"))
    hero = model_harvester.build_vehicle_scene()
    hero.add(model_harvester_header.build_scene())
    hero.children[-1].attrs["translation"] = "0 1.00 2.30"
    render.render(size=900, eye=(12.0, 3.4, 7.0), target=(0, 1.3, 0.9), fov=42, ss=2,
                  root=hero).save(os.path.join(docs, "ufo4500_header.png"))
    print("  icon, 2 store pictures, 2 doc renders")


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(TOOLS, "ufo", "validate4500.py")]
    subprocess.run(cmd, check=True)


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_UFO4500.zip")
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
    maps = build_models()
    step("vehicle XML")
    inject("ufo4500.template.xml", "ufo4500.xml", maps["ufo4500"], wheels=True)
    inject("ufo4500header.template.xml", "ufo4500header.xml", maps["ufo4500header"])
    copy_assets()
    build_images()
    validate()
    make_zip()
    print("\nOK - dist/FS25_UFO4500.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
