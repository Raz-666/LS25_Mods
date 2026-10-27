#!/usr/bin/env python3
"""Build FS25_UFO4500 - the big beam-only mother ship - and zip it.

The 4500 does **everything with the tractor beam**: harvest, cultivate,
plow, sow, fertilise, load and unload, plus the crop-circle patterns from
the reference document.  There is no cutter, no attacher joint, no grain
pipe and no header any more - one store item, one ship.

  * model      : model_beam4500.py (scaled UFO 01 hull + turbines + emitter)
  * script     : scripts/UFO4500.lua (own renaming of the UFO 2000 logic, so
                 all three saucers can be installed side by side)
  * vehicle XML: FS25_UFO2000/ufo.xml with the 4500 values
  * media      : textures + sounds from FS25_CropHarvester (the beam set)
  * pictures   : icon, two store pictures, documentation renders
  * validate   : structural checks in this file
  * zip        : dist/FS25_UFO4500.zip

Usage:  python tools/build_harvester_mod.py [--skip-media] [--skip-renders]
"""

import argparse
import os
import re
import shutil
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(REPO, "FS25_UFO4500")
BUILD = os.path.join(REPO, "build")
DIST = os.path.join(REPO, "dist")
TOOLS = os.path.join(REPO, "tools")
UFO = os.path.join(TOOLS, "ufo")
SRC_MOD = os.path.join(REPO, "FS25_UFO2000")          # ufo.xml + UFO2000.lua
MEDIA_MOD = os.path.join(REPO, "FS25_CropHarvester")  # beam textures + suits

sys.path.insert(0, UFO)
sys.path.insert(0, os.path.join(TOOLS, "i3d"))

MAP_START = "    <!-- I3D_MAPPINGS -->"
MAP_END = "    <!-- /I3D_MAPPINGS -->"
ZIP_EXT = (".xml", ".i3d", ".shapes", ".dds", ".png", ".ogg", ".txt", ".lua")

I3D = "ufo4500.i3d"
LUA = "scripts/UFO4500.lua"
SOUNDS_XML = "ufo4500_sounds.xml"

# the sheet's beam colours, identical to the UFO 01 harvester
LIGHT_COLOURS = {
    "damage": "1.00, 0.92, 0.20",
    "harvest": "0.30, 1.00, 0.36",
    "cultivate": "0.72, 0.36, 1.00",
    "plow": "0.72, 0.36, 1.00",
    "sow": "0.30, 0.62, 1.00",
    "fertilize": "0.30, 0.62, 1.00",
    "load": "1.00, 0.30, 0.22",
    "unload": "1.00, 0.30, 0.22",
}

# 4500 tuning: roughly twice the working width of the UFO 01, and it can
# hover high enough to draw the 30 m patterns from the reference document
LUA_TUNING = (
    ("UFO4500.PEN_MAX_RADIUS = 8.00", "UFO4500.PEN_MAX_RADIUS = 30.00"),
    ("UFO4500.PEN_RADIUS_STEP = 0.25", "UFO4500.PEN_RADIUS_STEP = 1.00"),
    ("UFO4500.MANUAL_RADIUS = 0.25", "UFO4500.MANUAL_RADIUS = 1.00"),
    ("UFO4500.MAX_ALTITUDE = 120.0", "UFO4500.MAX_ALTITUDE = 30.0"),
    ("UFO4500.MIN_ALTITUDE = 1.10", "UFO4500.MIN_ALTITUDE = 3.00"),
    ("UFO4500.MAX_SPEED = 8.5", "UFO4500.MAX_SPEED = 7.0"),
    ("UFO4500.MAX_CIRCLE_RADIUS = 70.0", "UFO4500.MAX_CIRCLE_RADIUS = 90.0"),
)


def step(msg):
    print("\n== " + msg)


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------
def build_model():
    step("model")
    import binarize_i3d
    import model_beam4500

    os.makedirs(BUILD, exist_ok=True)
    inline = os.path.join(BUILD, "ufo4500_inline.i3d")
    stats, mappings = model_beam4500.write(inline)
    res = binarize_i3d.binarize(inline, os.path.join(MOD, I3D))
    print("  %-14s %2d shapes, %5d tris, %s %d kB"
          % (os.path.basename(I3D), stats["shapes"], stats["tris"],
             os.path.basename(res["shapes_path"]), res["size"] // 1024))
    return mappings


# --------------------------------------------------------------------------
# script
# --------------------------------------------------------------------------
def build_script():
    step("script")
    with open(os.path.join(SRC_MOD, "scripts", "UFO2000.lua"), encoding="utf-8") as fh:
        lua = fh.read()

    # own class, own specialization, own action and l10n keys, so that
    # UFO 2000, UFO 01 and UFO 4500 can all be installed together
    lua = lua.replace("UFO2000", "UFO4500").replace("ufo2000", "ufo4500")
    lua = lua.replace("ufo_", "ufo4500_")

    for old, new in LUA_TUNING:
        if old not in lua:
            sys.exit("tuning anchor missing: " + old)
        lua = lua.replace(old, new)

    # the sheet's beam colours
    for key, colour in LIGHT_COLOURS.items():
        lua = re.sub(r'(\{id = \d+, node = "beamNode%s".*?light = \{)[^}]*(\})'
                     % key.capitalize(), r'\g<1>%s\g<2>' % colour, lua,
                     count=1, flags=re.S)

    # Captain Zorp bobs along while the ship hovers and disappears as soon as
    # the player takes the seat
    lua = lua.replace("""    UFO4500.updateCockpit(self)""",
                      """    UFO4500.updateCockpit(self)
    UFO4500.updatePilot(self, dt, time)""")
    lua = lua.replace("""    spec.beaconLight = UFO4500.getNode(self, "beaconLight")""",
                      """    spec.pilotNode = UFO4500.getNode(self, "pilotNode")
    spec.beaconLight = UFO4500.getNode(self, "beaconLight")""")
    lua = lua.rstrip() + PILOT_LUA

    os.makedirs(os.path.join(MOD, "scripts"), exist_ok=True)
    with open(os.path.join(MOD, LUA), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(lua)
    print("  %s (%d lines)" % (LUA, lua.count("\n") + 1))


PILOT_LUA = '''


-- ---------------------------------------------------------------------------
-- Captain Zorp: he bobs along while the ship flies and hides as soon as a
-- player takes the seat (then the player's own character sits in the dome).
UFO4500.PILOT_BOB = 0.05

function UFO4500.updatePilot(vehicle, dt, time)
    local spec = vehicle.spec_ufo4500
    if spec.pilotNode == nil then
        return
    end
    local entered = vehicle.getIsEntered ~= nil and vehicle:getIsEntered()
    setVisibility(spec.pilotNode, not entered)
    if entered then
        return
    end
    local hover = spec.isHovering and 1.0 or 0.25
    local bob = UFO4500.PILOT_BOB * hover * math.sin(time * 4.2)
    setTranslation(spec.pilotNode, 0.0, 1.22 + bob, 0.30)
end
'''


# --------------------------------------------------------------------------
# media
# --------------------------------------------------------------------------
def copy_assets():
    step("textures + sounds")
    if not os.path.isdir(MEDIA_MOD):
        sys.exit("%s is missing - run tools/build_crop_harvester_mod.py first"
                 % MEDIA_MOD)
    copied = 0
    for sub in ("textures", "sounds"):
        src = os.path.join(MEDIA_MOD, sub)
        dst = os.path.join(MOD, sub)
        os.makedirs(dst, exist_ok=True)
        for name in sorted(os.listdir(src)):
            if not name.lower().endswith((".dds", ".ogg")):
                continue
            shutil.copy2(os.path.join(src, name), os.path.join(dst, name))
            copied += 1
    # the extra sound bank (beam loops, mode beep) is shared with the UFO 01
    src_xml = os.path.join(MEDIA_MOD, "crop_sounds.xml")
    if os.path.isfile(src_xml):
        shutil.copy2(src_xml, os.path.join(MOD, SOUNDS_XML))
        copied += 1
    print("  %d files" % copied)


# --------------------------------------------------------------------------
# XML + modDesc + translations
# --------------------------------------------------------------------------
def build_xml(mappings):
    step("vehicle XML")
    with open(os.path.join(SRC_MOD, "ufo.xml"), encoding="utf-8") as fh:
        xml = fh.read()

    xml = xml.replace('<vehicle type="UFO2000"', '<vehicle type="UFO4500"')
    xml = xml.replace("$l10n_ufo_", "$l10n_ufo4500_")
    xml = xml.replace("$l10n_configuration_ufo_", "$l10n_configuration_ufo4500_")
    xml = xml.replace("$l10n_function_ufo", "$l10n_function_ufo4500")
    xml = xml.replace("$l10n_typeDesc_ufo", "$l10n_typeDesc_ufo4500")
    xml = xml.replace("<image>store_ufo.png</image>", "<image>store_ufo4500.png</image>")
    xml = xml.replace("<price>42000</price>", "<price>185000</price>")
    xml = xml.replace("<power>113</power>", "<power>300</power>")
    xml = xml.replace("<maxSpeed>32</maxSpeed>", "<maxSpeed>25</maxSpeed>")
    xml = xml.replace('<size width="4.7" length="4.7" height="3.15"/>',
                      '<size width="6.3" length="6.3" height="4.3"/>')
    xml = xml.replace('<speedLimit value="32"/>', '<speedLimit value="25"/>')
    xml = xml.replace('hp="113"', 'hp="300"')
    xml = xml.replace('maxForwardSpeed="32" maxBackwardSpeed="18"',
                      'maxForwardSpeed="25" maxBackwardSpeed="12"')
    xml = xml.replace('<forwardGear maxSpeed="32" name="D"/>',
                      '<forwardGear maxSpeed="25" name="D"/>')
    xml = xml.replace('<backwardGear maxSpeed="18" name="R"/>',
                      '<backwardGear maxSpeed="12" name="R"/>')
    xml = xml.replace('mass="1450"', 'mass="4200"')
    xml = xml.replace("<filename>ufo.i3d</filename>", "<filename>%s</filename>" % I3D)
    xml = xml.replace('<sounds filename="ufo_sounds.xml"/>',
                      '<sounds filename="%s"/>' % SOUNDS_XML)
    xml = xml.replace("scripts/UFO2000.lua", LUA)
    # the sheet asks for a "virtually endless" tank; the 4500 gets the big one
    xml = xml.replace('capacity="25000"', 'capacity="2000000"')

    pattern = re.compile(re.escape(MAP_START) + r".*?" + re.escape(MAP_END), re.S)
    if not pattern.search(xml):
        sys.exit("mapping markers missing in ufo.xml")
    block = "    <i3dMappings>\n" + mappings + "\n    </i3dMappings>"
    xml = pattern.sub(lambda _: MAP_START + "\n" + block + "\n" + MAP_END, xml, count=1)

    for banned in ("<attacherJoints", 'jointType="cutter"', "<combine ",
                   "<pipe ", "<workAreas>\n        <workArea"):
        if banned in xml:
            sys.exit("the 4500 must not contain %r - it works with the beam only"
                     % banned)
    with open(os.path.join(MOD, "ufo4500.xml"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(xml)
    print("  ufo4500.xml (%d mappings)" % mappings.count("i3dMapping id="))

    step("modDesc + translations")
    shutil.copy2(os.path.join(UFO, "ufo4500.modDesc.xml"),
                 os.path.join(MOD, "modDesc.xml"))
    os.makedirs(os.path.join(MOD, "translations"), exist_ok=True)
    for lang in ("de", "en"):
        with open(os.path.join(UFO, "cropharvester_translation_%s.xml" % lang),
                  encoding="utf-8") as fh:
            text = fh.read()
        text = text.replace("crop_", "ufo4500_")
        text = text.replace("brand_crop", "brand_ufo4500")
        text = text.replace("brand_ufo4500", "brand_ufo4500")
        text = text.replace("function_crop", "function_ufo4500")
        text = text.replace("typeDesc_crop", "typeDesc_ufo4500")
        text = text.replace("<de>UFO 01 – Crop Harvester</de>",
                            "<de>UFO 4500 – Mutterschiff</de>")
        text = text.replace("<en>UFO 01 - Crop Harvester</en>",
                            "<en>UFO 4500 - Mother Ship</en>")
        text = text.replace("<de>UFO 01 – Erntemaschine mit Glaskuppel und Traktorstrahl</de>",
                            "<de>UFO 4500 – großes Strahl-Ernteschiff mit Glaskuppel</de>")
        text = text.replace("<en>UFO 01 - harvester with a glass dome and a tractor beam</en>",
                            "<en>UFO 4500 - large beam harvester with a glass dome</en>")
        text = re.sub(r'<text name="ufo4500_description">.*?</text>',
                      DESCRIPTION[lang], text, count=1, flags=re.S)
        with open(os.path.join(MOD, "translations", "translation_%s.xml" % lang),
                  "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    brand_src = os.path.join(MEDIA_MOD, "brand_cropharvester.dds")
    if os.path.isfile(brand_src):
        shutil.copy2(brand_src, os.path.join(MOD, "brand_ufo4500.dds"))
    print("  modDesc.xml + translation_de/en.xml")


DESCRIPTION = {
    "de": '<text name="ufo4500_description"><de><![CDATA[Das große Mutterschiff der '
          'UFO-Reihe: anderthalbmal so groß wie die UFO 01, 300 PS, vier Hover-Turbinen '
          'am Rumpf. Jede Feldarbeit macht ausschließlich der Strahl unter dem '
          'Schiff - kein Schneidwerk, kein Anbaugerät, kein Anhänger nötig.\n\n'
          '* Strahlbreite 2 m bis 30 m (Taste J/L), Arbeitshöhe 3 m bis 30 m\n'
          '* Acht Funktionen in fünf Farben: GRÜN ernten, BLAU säen/düngen, '
          'VIOLETT grubbern/pflügen, GELB Kornkreise, ROT aufnehmen/abgeben\n'
          '* Korntank 2.000.000 L, mit Taste I auf unendlich gestellt\n'
          '* Kornkreise: neun Presets per Tastenrad sowie ein freier 1-m-Stift, '
          'mit dem du mit der Maus bzw. dem Stick selbst zeichnest\n'
          '* Weiches Schweben mit Spielsound, Innenraum wie ein Fahrzeug, '
          'Cockpit mit Hebeln, Hologramm und Captain Zorp\n'
          '* Eigene Tastenbelegung (ufo4500_*), läuft parallel zu UFO 2000 und UFO 01\n\n'
          'Bedienung: V abheben/landen, Bild auf/ab Höhe, Z Strahl, K Modus, '
          'J/L Strahlbreite, U abgeben, I Tank endlos, M Muster-Menü.]]></de>'
          '<en><![CDATA[The big mother ship of the UFO family: one and a half times '
          'the UFO 01, 300 hp, four hover turbines on the hull. Every field job is '
          'done by the beam alone - no cutter, no implement, no trailer needed.\n\n'
          '* Beam width 2 m to 30 m (key J/L), working height 3 m to 30 m\n'
          '* Eight functions in five colours: GREEN harvest, BLUE sow/fertilise, '
          'PURPLE cultivate/plow, YELLOW crop circles, RED load/unload\n'
          '* 2,000,000 l grain tank, press I for an endless tank\n'
          '* Crop circles: nine presets on the key wheel plus a free 1 m pen to '
          'draw your own pattern while flying\n'
          '* Smooth hovering with in-game sound, a proper vehicle interior and a '
          'cockpit with levers, hologram and Captain Zorp\n'
          '* Own key bindings (ufo4500_*), runs next to UFO 2000 and UFO 01\n\n'
          'Controls: V take off/land, Page Up/Down altitude, Z beam, K mode, '
          'J/L beam width, U unload, I endless tank, M pattern menu.]]></en></text>',
    "en": '<text name="ufo4500_description"><de><![CDATA[Das große Mutterschiff der '
          'UFO-Reihe: anderthalbmal so groß wie die UFO 01, 300 PS, vier Hover-Turbinen '
          'am Rumpf. Jede Feldarbeit macht ausschließlich der Strahl unter dem '
          'Schiff - kein Schneidwerk, kein Anbaugerät, kein Anhänger nötig.\n\n'
          '* Strahlbreite 2 m bis 30 m (Taste J/L), Arbeitshöhe 3 m bis 30 m\n'
          '* Acht Funktionen in fünf Farben: GRÜN ernten, BLAU säen/düngen, '
          'VIOLETT grubbern/pflügen, GELB Kornkreise, ROT aufnehmen/abgeben\n'
          '* Korntank 2.000.000 L, mit Taste I auf unendlich gestellt\n'
          '* Kornkreise: neun Presets per Tastenrad sowie ein freier 1-m-Stift\n'
          '* Weiches Schweben mit Spielsound, Innenraum wie ein Fahrzeug\n'
          '* Eigene Tastenbelegung (ufo4500_*), läuft parallel zu UFO 2000 und UFO 01\n\n'
          'Bedienung: V abheben/landen, Bild auf/ab Höhe, Z Strahl, K Modus, '
          'J/L Strahlbreite, U abgeben, I Tank endlos, M Muster-Menü.]]></de>'
          '<en><![CDATA[The big mother ship of the UFO family: one and a half times '
          'the UFO 01, 300 hp, four hover turbines on the hull. Every field job is '
          'done by the beam alone - no cutter, no implement, no trailer needed.]]></en></text>',
}


# --------------------------------------------------------------------------
# pictures
# --------------------------------------------------------------------------
def scene(mode="Harvest", altitude=6.0):
    import images as ufo_images
    import math
    import model_beam4500

    root = model_beam4500.build_scene()
    radius = max(2.0, altitude * math.tan(math.radians(34.0)))
    tube = ufo_images._find(root, "beamNode" + mode)
    if tube is not None:
        tube.attrs["visibility"] = "true"
        tube.attrs["scale"] = "%.4f %.4f %.4f" % (radius, altitude - 0.22, radius)
    ring = ufo_images._find(root, "groundRing")
    if ring is not None:
        ring.attrs["visibility"] = "true"
        # the beam node lives under the scaled root, so the ring has to sink
        # by the scaled altitude
        ring.attrs["translation"] = "0 %.3f 0" % (0.08 - altitude * 1.30)
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

    docs = os.path.join(REPO, "docs", "renders")
    os.makedirs(docs, exist_ok=True)

    icon = render.render(size=512, eye=(9.5, 5.0, 9.5), target=(0, 1.6, 0),
                         fov=40, ss=2, beam=True, root=scene())
    p = os.path.join(BUILD, "icon_ufo4500.png")
    icon.save(p)
    ufo_images._dds(p, os.path.join(MOD, "icon_ufo4500.dds"), "bc1", sys.executable)

    render.render(size=512, eye=(9.5, 5.0, 9.5), target=(0, 1.6, 0), fov=40, ss=2,
                  return_alpha=True, beam=True, root=scene()).save(
        os.path.join(MOD, "store_ufo4500.png"))
    render.render(size=512, eye=(8.0, 6.5, 8.5), target=(0, 1.4, 0), fov=40, ss=2,
                  return_alpha=True, beam=True, root=scene(altitude=9.0)).save(
        os.path.join(MOD, "store_ufo4500_beam.png"))

    render.render(size=900, eye=(9.5, 5.0, 9.5), target=(0, 1.6, 0), fov=40, ss=2,
                  beam=True, root=scene()).save(os.path.join(docs, "ufo4500_hero.png"))
    render.render(size=900, eye=(0.5, -3.8, 9.5), target=(0, 1.0, 0), fov=42, ss=2,
                  beam=True, root=scene()).save(os.path.join(docs, "ufo4500_below.png"))
    render.render(size=900, eye=(8.5, 7.0, 8.0), target=(0, 1.2, 0), fov=42, ss=2,
                  beam=True, root=scene(altitude=12.0)).save(
        os.path.join(docs, "ufo4500_beam.png"))
    print("  icon, 2 store pictures, 3 doc renders")


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------
def validate_zip():
    """Structural checks - catches the mistakes that break a mod before the
    game ever loads it."""
    import xml.etree.ElementTree as ET

    step("validation")
    problems = []

    def check(cond, msg):
        if not cond:
            problems.append(msg)

    for name in ("modDesc.xml", "ufo4500.xml", SOUNDS_XML, I3D,
                 os.path.join("translations", "translation_de.xml"),
                 os.path.join("translations", "translation_en.xml"), LUA):
        check(os.path.isfile(os.path.join(MOD, name)), "missing: " + name)

    desc = ET.parse(os.path.join(MOD, "modDesc.xml")).getroot()
    check(desc.find("multiplayer") is not None, "modDesc: multiplayer missing")
    l10n = desc.find("l10n")
    check(l10n is not None and l10n.get("filenamePrefix") == "translations/translation",
          "modDesc: external translations are not registered")
    spec = desc.find("specializations/specialization")
    check(spec is not None and spec.get("filename") == LUA,
          "modDesc: specialization path")
    check(desc.find("vehicleTypes/type") is not None, "modDesc: vehicleTypes missing")

    veh = ET.parse(os.path.join(MOD, "ufo4500.xml")).getroot()
    check(veh.get("type") == "UFO4500", "vehicle type")
    check(veh.find("base/filename").text == I3D, "base filename")
    check(veh.find("attacherJoints") is None, "attacher joints must not exist")
    check(veh.find("combine") is None, "combine logic must not exist")
    check(veh.find("pipe") is None, "grain pipe must not exist")
    check(veh.find("workAreas/workArea") is None, "no work area / cutter")
    mappings = {m.get("id") for m in veh.iter("i3dMapping")}
    with open(os.path.join(MOD, LUA), encoding="utf-8") as fh:
        lua = fh.read()
    for node in re.findall(r'getNode\(self, "([A-Za-z0-9_]+)"\)', lua):
        check(node in mappings, "Lua node without mapping: " + node)
    # every l10n key used in the XML has to exist in both translations
    keys = set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", open(
        os.path.join(MOD, "ufo4500.xml"), encoding="utf-8").read()))
    for lang in ("de", "en"):
        have = {t.get("name") for t in ET.parse(os.path.join(
            MOD, "translations", "translation_%s.xml" % lang)).getroot().iter("text")}
        missing = sorted(keys - have - {"unit_literShort", "info_transmission_automatic",
                                        "configuration_valueDefault"})
        check(not missing, "%s: missing l10n keys %s" % (lang, ", ".join(missing)))

    for problem in problems:
        print("  FAIL " + problem)
    if problems:
        sys.exit("%d problem(s) found" % len(problems))
    print("  all checks passed")


# --------------------------------------------------------------------------
# zip
# --------------------------------------------------------------------------
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
                zf.write(full, os.path.relpath(full, MOD).replace(os.sep, "/"))
                count += 1
    print("  %s (%.1f MB, %d files)" % (out, os.path.getsize(out) / 1e6, count))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-media", action="store_true")
    parser.add_argument("--skip-renders", action="store_true")
    args = parser.parse_args()

    os.makedirs(MOD, exist_ok=True)
    # the header ship is gone - remove what an older build left behind
    for stale in ("ufo4500header.xml", "ufo4500header.i3d",
                  "ufo4500header.i3d.shapes", "store_ufo4500header.png"):
        path = os.path.join(MOD, stale)
        if os.path.isfile(path):
            os.remove(path)

    mappings = build_model()
    build_script()
    build_xml(mappings)
    if not args.skip_media:
        copy_assets()
    if not args.skip_renders:
        build_images()
    validate_zip()
    make_zip()
    print("\nOK - dist/FS25_UFO4500.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
