#!/usr/bin/env python3
"""Build FS25_CropHarvester - the retro-comic "UFO 01 CROP HARVESTER".

The blueprint (UFO Harvester Mod Reference Document) asks for a compact saucer
with one huge glass dome, Captain Zorp squeezed in behind the levers, every
field job done by the beam, a virtual tank ("1.000.000 L+") and the five beam
colours of the sheet (green harvest, blue sow/fertilise, purple cultivate,
yellow crop circles, red transport).

The flight, beam and field logic is the proven UFO 2000 specialization; this
mod ships its **own renamed copy** (`CropHarvester.lua`), so both mods can be
installed at the same time without clashing action names or classes.

  1. procedural scene  -> build/crop_inline.i3d  ->  FS25_CropHarvester/crop.i3d
  2. textures          -> textures/ (UFO set + decal/suit/goggle)
  3. sounds            -> sounds/  + crop_sounds.xml
  4. script            -> scripts/CropHarvester.lua  (renamed + blueprint tuning)
  5. vehicle XML       -> crop.xml  (mappings, 1.000.000 L tank, new beams)
  6. modDesc, translations, icon/store picture/brand + doc renders
  7. validate          -> tools/ufo/validate_crop.py
  8. zip               -> dist/FS25_CropHarvester.zip

Usage:  python tools/build_crop_harvester_mod.py [--skip-media] [--skip-renders]
"""

import argparse
import os
import re
import shutil
import subprocess
import math
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_CropHarvester")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")
UFO = os.path.join(TOOLS, "ufo")
SRC_MOD = os.path.join(REPO, "FS25_UFO2000")

sys.path.insert(0, UFO)
sys.path.insert(0, os.path.join(TOOLS, "i3d"))

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt", ".lua")

VEHICLE_XML = "crop.xml"
I3D = "crop.i3d"
LUA = "scripts/CropHarvester.lua"
SOUNDS_XML = "crop_sounds.xml"

# the blueprint: green harvest, blue sow/fertilise, purple cultivate/plow,
# yellow crop circles, red transport (load / unload)
LIGHT_COLOURS = {
    "damage": "1.00, 0.92, 0.20",
    "harvest": "0.30, 1.00, 0.36",
    "cultivate": "0.72, 0.36, 1.00",
    "plow": "0.62, 0.22, 1.00",
    "sow": "0.28, 0.55, 1.00",
    "fertilize": "0.36, 0.72, 1.00",
    "load": "1.00, 0.22, 0.18",
    "unload": "1.00, 0.42, 0.20",
}


def step(msg):
    print("\n== " + msg)


# --------------------------------------------------------------------------
# model + textures
# --------------------------------------------------------------------------
def build_model():
    step("model")
    import binarize_i3d
    import model_crop

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "crop_inline.i3d")
    stats, mappings = model_crop.write(inline)
    res = binarize_i3d.binarize(inline, os.path.join(MOD, I3D))
    print("  %s  %2d shapes, %5d tris, %s %d kB"
          % (I3D, stats["shapes"], stats["tris"], os.path.basename(res["shapes_path"]),
             res["size"] // 1024))
    return mappings


def build_textures():
    step("textures")
    import textures_crop
    os.makedirs(os.path.join(MOD, "textures"), exist_ok=True)
    textures_crop.generate(os.path.join(MOD, "textures"),
                           os.path.join(BUILD, "crop_textures"),
                           png2dds=os.path.join(TOOLS, "png2dds.py"),
                           python=sys.executable, verbose=True)


# --------------------------------------------------------------------------
# script
# --------------------------------------------------------------------------
def build_script():
    step("script")
    with open(os.path.join(SRC_MOD, "scripts", "UFO2000.lua"), encoding="utf-8") as fh:
        lua = fh.read()

    # 1) rename the class, the specialization and every action / l10n key, so
    #    that UFO 2000 and the harvester can be installed side by side
    lua = lua.replace("UFO2000", "CropHarvester").replace("ufo2000", "cropHarvester")
    lua = lua.replace("ufo_", "crop_")

    # 2) blueprint: the beam can open up to 30 m (the sheet's 6 m - 30 m)
    lua = lua.replace("CropHarvester.PEN_MAX_RADIUS = 8.00",
                      "CropHarvester.PEN_MAX_RADIUS = 15.00")
    lua = lua.replace("CropHarvester.PEN_RADIUS_STEP = 0.25",
                      "CropHarvester.PEN_RADIUS_STEP = 0.50")
    # the free-hand pen grows in the same 50 cm steps, so its start value has
    # to be a multiple of the step - otherwise the first key press jumps
    lua = lua.replace("CropHarvester.MANUAL_RADIUS = 0.25",
                      "CropHarvester.MANUAL_RADIUS = 0.50")
    # blueprint: hover height 2 m - 15 m, stepless
    lua = lua.replace("CropHarvester.MAX_ALTITUDE = 120.0",
                      "CropHarvester.MAX_ALTITUDE = 15.0")
    lua = lua.replace("CropHarvester.MIN_ALTITUDE = 1.10",
                      "CropHarvester.MIN_ALTITUDE = 2.00")

    # 3) blueprint: the beam colours
    for key, colour in LIGHT_COLOURS.items():
        lua = re.sub(r'(\{id = \d+, node = "beamNode%s".*?light = \{)[^}]*(\})'
                     % key.capitalize(), r'\g<1>%s\g<2>' % colour, lua,
                     count=1, flags=re.S)

    # 4) Captain Zorp bobs while hovering and disappears as soon as the player
    #    takes the seat (kuppel-animation from the sheet)
    lua = lua.replace("""    CropHarvester.updateCockpit(self)""",
                      """    CropHarvester.updateCockpit(self)
    CropHarvester.updatePilot(self, dt, time)""")

    pilot = '''

-- ---------------------------------------------------------------------------
-- Captain Zorp: he bobs along while the saucer flies and hides as soon as a
-- player takes the seat (then the player's own character sits in the dome).
CropHarvester.PILOT_BOB = 0.055

function CropHarvester.updatePilot(vehicle, dt, time)
    local spec = vehicle.spec_cropHarvester
    if spec.pilotNode == nil then
        return
    end
    local entered = vehicle.getIsEntered ~= nil and vehicle:getIsEntered()
    setVisibility(spec.pilotNode, not entered)
    if entered then
        return
    end
    local hover = spec.isHovering and 1.0 or 0.25
    local bob = CropHarvester.PILOT_BOB * hover * math.sin(time * 4.2)
    local lean = 0.05 * hover * math.sin(time * 2.1)
    setTranslation(spec.pilotNode, lean, 1.22 + bob, 0.30)
    setRotation(spec.pilotNode, 0, 6.0 * lean, 0)
end
'''
    lua = lua.rstrip() + pilot

    # 5) cache the pilot node next to the other nodes
    lua = lua.replace("""    spec.beaconLight = CropHarvester.getNode(self, "beaconLight")""",
                      """    spec.pilotNode = CropHarvester.getNode(self, "pilotNode")
    spec.beaconLight = CropHarvester.getNode(self, "beaconLight")""")

    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    path = os.path.join(MOD, LUA)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(lua)
    print("  %s (%d lines)" % (LUA, lua.count("\n") + 1))


# --------------------------------------------------------------------------
# sounds
# --------------------------------------------------------------------------
def build_sounds():
    step("sounds")
    out = os.path.join(MOD, "sounds")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(SRC_MOD, "sounds")
    count = 0
    for name in sorted(os.listdir(src)):
        if name.endswith(".ogg"):
            shutil.copy2(os.path.join(src, name), os.path.join(out, name))
            count += 1
    # the sound XML gets the new file name, everything else stays
    with open(os.path.join(SRC_MOD, "ufo_sounds.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    with open(os.path.join(MOD, SOUNDS_XML), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  %d ogg files, %s" % (count, SOUNDS_XML))


# --------------------------------------------------------------------------
# vehicle XML + modDesc + translations
# --------------------------------------------------------------------------
def build_xml(mappings):
    step("vehicle XML")
    with open(os.path.join(SRC_MOD, "ufo.xml"), encoding="utf-8") as fh:
        xml = fh.read()

    xml = xml.replace('<vehicle type="UFO2000"', '<vehicle type="CropHarvester"')
    xml = xml.replace("<name>$l10n_ufo_name</name>", "<name>$l10n_crop_name</name>")
    xml = xml.replace("<image>store_ufo.png</image>", "<image>store_crop.png</image>")
    xml = xml.replace("<brand>UFO2000</brand>", "<brand>CropHarvester</brand>")
    xml = xml.replace("<price>42000</price>", "<price>96000</price>")
    xml = xml.replace("<typeDesc>$l10n_typeDesc_ufo</typeDesc>",
                      "<typeDesc>$l10n_typeDesc_crop</typeDesc>")
    xml = xml.replace("<filename>ufo.i3d</filename>", "<filename>%s</filename>" % I3D)
    xml = xml.replace('<sounds filename="ufo_sounds.xml"/>',
                      '<sounds filename="%s"/>' % SOUNDS_XML)
    xml = xml.replace("scripts/UFO2000.lua", LUA)
    # every remaining l10n key (function_ufo, configuration_ufo_motor, ...)
    xml = xml.replace("$l10n_configuration_ufo_", "$l10n_configuration_crop_")
    xml = xml.replace("$l10n_function_ufo", "$l10n_function_crop")
    xml = xml.replace("$l10n_ufo_", "$l10n_crop_")
    # blueprint: "virtually endless" 1,000,000 L grain tank
    xml = xml.replace('fillTypes="WHEAT BARLEY OAT CANOLA MAIZE SUNFLOWER SOYBEAN SORGHUM '
                      'RYE TRITICALE SPELT" capacity="25000"',
                      'fillTypes="WHEAT BARLEY OAT CANOLA MAIZE SUNFLOWER SOYBEAN SORGHUM '
                      'RYE TRITICALE SPELT" capacity="1000000"')

    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in ufo.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)
    with open(os.path.join(MOD, VEHICLE_XML), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(xml)
    print("  %s (%d mappings)" % (VEHICLE_XML, mappings.count("i3dMapping id=")))

    step("modDesc + translations")
    shutil.copy2(os.path.join(UFO, "cropharvester.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    os.makedirs(os.path.join(MOD, "translations"), exist_ok=True)
    for lang in ("de", "en"):
        shutil.copy2(os.path.join(UFO, "cropharvester_translation_%s.xml" % lang),
                     os.path.join(MOD, "translations", "translation_%s.xml" % lang))
    print("  modDesc.xml + translation_de/en.xml")


# --------------------------------------------------------------------------
# images
# --------------------------------------------------------------------------
def scene():
    import model_crop
    return model_crop.build_scene()


def beam_scene(mode="Harvest", altitude=6.0):
    """Documentation scene: hovering high with one beam cone fired."""
    import images as ufo_images
    root = scene()
    radius = max(1.8, altitude * math.tan(math.radians(34.0)))
    tube = ufo_images._find(root, "beamNode" + mode)
    if tube is not None:
        tube.attrs["visibility"] = "true"
        tube.attrs["scale"] = "%.4f %.4f %.4f" % (radius, altitude - 0.22, radius)
    ring = ufo_images._find(root, "groundRing")
    if ring is not None:
        ring.attrs["visibility"] = "true"
        ring.attrs["translation"] = "0 %.3f 0" % (0.08 - altitude)
        ring.attrs["scale"] = "%.4f 1 %.4f" % (radius, radius)
    return root


def build_images():
    step("images")
    import images as ufo_images
    import render

    render.MAT_LOOK.update({
        "collision": None,
        "hullPaint": ((0.74, 0.78, 0.82), 0.62, 0.0, 1.0),
        "hullMetal": ((0.34, 0.37, 0.41), 0.78, 0.0, 1.0),
        "cockpit": ((0.22, 0.24, 0.26), 0.45, 0.0, 1.0),
        "glass": ((0.62, 0.88, 0.95), 0.9, 0.0, 0.32),
        "lensGreen": ((0.35, 1.0, 0.45), 0.4, 0.9, 1.0),
        "lensRed": ((1.0, 0.20, 0.16), 0.4, 0.9, 1.0),
        "lensWhite": ((1.0, 0.96, 0.85), 0.5, 0.8, 1.0),
        "alienSkin": ((0.45, 0.82, 0.33), 0.35, 0.0, 1.0),
        "eyeBlack": ((0.03, 0.05, 0.07), 0.9, 0.0, 1.0),
        "suit": ((0.32, 0.46, 0.25), 0.35, 0.0, 1.0),
        "goggle": ((0.20, 0.21, 0.23), 0.6, 0.0, 1.0),
        "helmet": ((0.88, 0.89, 0.86), 0.45, 0.0, 1.0),
        "helmetTrim": ((0.84, 0.42, 0.12), 0.35, 0.0, 1.0),
        "decal": ((0.88, 0.90, 0.92), 0.4, 0.25, 1.0),
        "beam": ((0.4, 1.0, 0.5), 0.1, 0.9, 0.30),
        "beamGreen": ((0.35, 1.0, 0.40), 0.1, 0.9, 0.34),
        "beamBlue": ((0.30, 0.60, 1.0), 0.1, 0.9, 0.34),
        "beamPurple": ((0.75, 0.40, 1.0), 0.1, 0.9, 0.34),
        "beamYellow": ((1.0, 0.92, 0.30), 0.1, 0.9, 0.34),
        "beamRed": ((1.0, 0.30, 0.22), 0.1, 0.9, 0.34),
    })
    render.load_textures({
        "decal": os.path.join(BUILD, "crop_textures", "decal_diffuse.png"),
        "suit": os.path.join(BUILD, "crop_textures", "suit_diffuse.png"),
        "goggle": os.path.join(BUILD, "crop_textures", "goggle_diffuse.png"),
        "helmet": os.path.join(BUILD, "crop_textures", "helmet_diffuse.png"),
        "helmetTrim": os.path.join(BUILD, "crop_textures", "helmetTrim_diffuse.png"),
    })

    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = render.render(size=512, eye=(6.0, 3.6, 8.8), target=(0, 1.6, 0), fov=36,
                         ss=2, beam=True, root=scene())
    icon = render.add_shadow(icon, strength=0.30)
    p = os.path.join(BUILD, "icon_crop.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_cropharvester.dds"), "bc1", sys.executable)

    store = render.render(size=512, eye=(6.8, 4.0, 9.4), target=(0, 1.5, 0), fov=34,
                          ss=2, return_alpha=True, beam=True, root=scene())
    store = ufo_images._with_shadow(store, cy=0.90, rx=0.34, ry=0.05, strength=0.30)
    store.save(os.path.join(MOD, "store_crop.png"))

    from PIL import Image, ImageDraw
    brand = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    little = render.render(size=256, eye=(0, 2.2, 9.0), target=(0, 1.6, 0), fov=34,
                           ss=2, background=(1, 1, 1), return_alpha=True, beam=True, root=scene())
    brand.alpha_composite(little, (128, 0))
    d = ImageDraw.Draw(brand)
    d.text((256, 224), "UFO 01", anchor="mm", fill=(38, 58, 54, 255))
    p = os.path.join(BUILD, "brand_crop.png")
    brand.save(p)
    ufo_images._dds(p, os.path.join(MOD, "brand_cropharvester.dds"), "bc1", sys.executable)

    render.render(size=1000, eye=(6.4, 3.8, 9.0), target=(0, 1.5, 0), fov=36, ss=2,
                  beam=True, root=scene()).save(os.path.join(docs, "cropharvester_hero.png"))
    render.render(size=900, eye=(2.0, 2.6, 3.4), target=(0, 2.0, 0), fov=44, ss=2,
                  beam=True, root=scene()).save(os.path.join(docs, "cropharvester_pilot.png"))
    # the money shot: the green harvest beam on a field, seen from the ground
    render.render(size=1000, eye=(11.5, 8.2, 13.5), target=(0, 1.0, 0), fov=42, ss=2,
                  beam=True, root=beam_scene("Harvest", 6.0)).save(
                      os.path.join(docs, "cropharvester_beam.png"))
    print("  icon, store picture, brand, cropharvester_hero/pilot/beam.png")


def make_zip():
    step("zip")
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, "FS25_CropHarvester.zip")
    if os.path.exists(out):
        os.remove(out)
    count = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, _dirs, files in os.walk(MOD):
            for name in sorted(files):
                if not name.lower().endswith(ZIP_EXT):
                    continue
                full = os.path.join(root, name)
                zf.write(full, os.path.relpath(full, MOD).replace(os.sep, "/"))
                count += 1
    print("  %s (%.1f MB, %d files)" % (out, os.path.getsize(out) / 1e6, count))


def validate():
    step("validation")
    cmd = [sys.executable, os.path.join(UFO, "validate_crop.py"),
           "--zip", os.path.join(DIST, "FS25_CropHarvester.zip")]
    subprocess.run(cmd, check=True)
    cmd = [sys.executable, os.path.join(UFO, "luatest_crop.py")]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-media", action="store_true")
    ap.add_argument("--skip-renders", action="store_true")
    args = ap.parse_args()

    os.makedirs(MOD, exist_ok=True)
    mappings = build_model()
    if not args.skip_media:
        build_textures()
        build_sounds()
    build_script()
    build_xml(mappings)
    if not args.skip_media and not args.skip_renders:
        build_images()
    make_zip()
    validate()
    print("\nOK - dist/FS25_CropHarvester.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
