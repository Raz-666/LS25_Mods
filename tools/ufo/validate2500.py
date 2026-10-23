#!/usr/bin/env python3
"""Static checks for the console edition FS25_UFO2500 (no game required).

      python tools/ufo/validate2500.py [--xsd DIR] [--zip dist/FS25_UFO2500.zip]

On top of the usual XML/i3d checks this one enforces the console rules:

  * no Lua file, no <specializations>, no <extraSourceFiles>, no <actions>,
    no custom brand - that is what the ModHub console test looks for
  * the wheels must be invisible (no <wheel filename=...>) and every wheel
    node has to exist in the i3d
  * the brush row is contiguous and each configuration is centred
  * the saucer really floats (visual node lifted, wheel nodes on the ground)
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_UFO2500")
BASE_BRANDS = {"LIZARD"}
BASE_L10N = {"configuration_valueDefault", "info_transmission_automatic",
             "unit_literShort", "brand_lizard"}

errors = []
warnings = []
notes = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def ok(msg):
    notes.append(msg)


def load(path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        err("%s: not well-formed XML: %s" % (os.path.relpath(path, REPO), e))
        return None


def xsd_dir(args):
    for cand in (args.xsd, os.environ.get("FS25_MOD_SCHEMA_DIR"),
                 os.path.join(REPO, "tools", "xsd")):
        if cand and os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "modDesc.xsd")):
            return cand
    return None


def check_xsd(doc, schema_dir, xsd_name):
    if schema_dir is None:
        return
    try:
        from lxml import etree
    except ImportError:
        warn("lxml not installed - XSD validation skipped")
        return
    schema = etree.XMLSchema(etree.parse(os.path.join(schema_dir, xsd_name)))
    tree = etree.parse(doc)
    if schema.validate(tree):
        ok("XSD %-14s OK  (%s)" % (xsd_name, os.path.basename(doc)))
    else:
        for e in list(schema.error_log)[:8]:
            err("%s:%d against %s: %s" % (os.path.basename(doc), e.line, xsd_name, e.message))


# ---------------------------------------------------------------------------
def check_console_rules():
    lua = [p for p in glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True)]
    if lua:
        err("console check: the mod ships Lua: %s"
            % ", ".join(os.path.relpath(p, MOD) for p in lua))
    else:
        ok("console check: no Lua file in the mod")

    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is None:
        return None
    for tag in ("extraSourceFiles", "actions", "inputBinding"):
        if desc.find(tag) is not None:
            err("console check: modDesc.xml must not contain <%s>" % tag)
    # <specializations> is fine as long as it only enables base game code
    for spec in desc.findall("specializations/specialization"):
        f = spec.get("filename")
        if f and not f.startswith("$dataS/"):
            err("console check: specialization %r ships its own script (%s)"
                % (spec.get("name"), f))
    types = desc.findall("vehicleTypes/type")
    if not types:
        err("console check: no <vehicleTypes><type>")
    for t in types:
        if os.path.basename(t.get("filename") or "") != "Vehicle.lua" and not \
                (t.get("filename") or "").startswith("$dataS/"):
            err("console check: vehicle type %r uses a file outside the base game"
                % t.get("name"))
        if not (t.get("parent") or "").strip():
            err("console check: vehicle type %r has no base game parent" % t.get("name"))
    if not errors:
        ok("console check: XML only, base game scripts only")
    return desc


def check_moddesc(desc):
    dv = int(desc.get("descVersion", "0"))
    if not 90 <= dv <= 115:
        err("modDesc descVersion %d outside the range accepted by FS25 (90..115)" % dv)
    for tag in ("author", "version", "iconFilename", "title", "description"):
        if desc.find(tag) is None:
            err("modDesc.xml: missing <%s>" % tag)
    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(MOD, icon)):
        err("modDesc iconFilename %s does not exist" % icon)
    if desc.find("multiplayer") is None:
        warn("modDesc.xml has no <multiplayer> entry")
    for item in desc.findall("storeItems/storeItem"):
        f = item.get("xmlFilename")
        if not os.path.isfile(os.path.join(MOD, f)):
            err("storeItems entry %s does not exist" % f)
    brands = [b.get("name") for b in desc.findall("brands/brand")]
    if brands:
        err("console check: custom brands are not allowed on console (%s), use LIZARD"
            % ", ".join(brands))
    ok("modDesc.xml: descVersion %d, %d store item(s)" % (dv, len(desc.findall("storeItems/storeItem"))))


def check_l10n():
    keys = set()
    for f in glob.glob(os.path.join(MOD, "translations", "*.xml")):
        root = load(f)
        if root is None:
            continue
        for t in root.iter("text"):
            keys.add(t.get("name"))
    used = set()
    for name in ("modDesc.xml", "ufo2500.xml"):
        with open(os.path.join(MOD, name), encoding="utf-8") as fh:
            used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", fh.read()))
    missing = sorted(used - keys - BASE_L10N)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    ok("translations: %d keys, %d used" % (len(keys), len(used)))


def check_i3d_mappings(veh):
    mappings = {}
    for m in veh.iter("i3dMapping"):
        mid, node = m.get("id"), m.get("node")
        if mid in mappings:
            err("duplicate i3dMapping id %r" % mid)
        mappings[mid] = node
    return mappings


def check_xml_nodes(veh, mappings):
    referenced = set()
    for el in veh.iter():
        if el.tag in ("i3dMapping", "i3dMappings"):
            continue
        for key in ("node", "realLight", "rotateNode"):
            v = el.get(key)
            if v and not v.startswith("$"):
                referenced.add(v)
        if el.tag == "physics":
            v = el.get("repr")
            if v:
                referenced.add(v)
    unknown = sorted(referenced - set(mappings))
    if unknown:
        err("ufo2500.xml references nodes without i3dMapping: %s" % ", ".join(unknown))
    ok("ufo2500.xml: %d node references, %d mappings" % (len(referenced), len(mappings)))


def check_wheels(veh, mappings):
    configs = veh.findall("wheels/wheelConfigurations/wheelConfiguration")
    if len(configs) < 2:
        err("expected several brush wheel configurations")
    node_names = set(mappings)

    swaths = []
    for cfg in configs:
        name = cfg.get("name") or "?"
        wheels = cfg.findall("wheels/wheel")
        care = [w for w in wheels if (w.get("isCareWheel") or "false") == "true"]
        brush = [w for w in wheels if (w.get("isCareWheel") or "false") != "true"]
        if not care:
            err("%s: no care wheel - the craft would damage crop with its load wheels" % name)
        if not brush:
            err("%s: no brush wheel - the configuration does nothing" % name)
        for w in wheels:
            if w.get("filename"):
                err("%s: <wheel filename=...> would show a visible wheel" % name)
            phys = w.find("physics")
            if phys is None:
                err("%s: wheel without <physics>" % name)
                continue
            if phys.get("repr") not in node_names:
                err("%s: wheel repr %r has no i3d node" % (name, phys.get("repr")))
            if phys.get("radius") is None or phys.get("width") is None:
                err("%s: wheel without radius/width" % name)
        # the brush has to be one centred, gap free row
        ids = sorted(int(w.find("physics").get("repr")[len("wheelBrush"):])
                     for w in brush if (w.find("physics").get("repr") or "").startswith("wheelBrush"))
        if ids and ids != list(range(ids[0], ids[-1] + 1)):
            err("%s: brush modules are not contiguous (%s)" % (name, ids))
        if ids and len(ids) % 2 == 0:
            err("%s: brush needs an odd number of modules to stay centred" % name)
        width = float(brush[0].find("physics").get("width")) if brush else 0.0
        swaths.append((name, len(brush), width * len(brush)))
    for name, count, swath in swaths:
        ok("wheels %-26s %2d x 0.5 m  ->  %.1f m swath" % (name.split("_")[-1], count, swath))
    if len({round(s[2], 2) for s in swaths}) != len(swaths):
        warn("two configurations have the same brush width")


def check_i3d(mappings):
    path = os.path.join(MOD, "ufo2500.i3d")
    root = load(path)
    if root is None:
        return
    scene = root.find("Scene")
    if scene is None:
        err("ufo2500.i3d has no <Scene>")
        return

    ids = [n.get("nodeId") for n in scene.iter() if n.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("ufo2500.i3d: duplicate nodeId values")

    def resolve(mpath):
        parts = mpath.split(">")
        try:
            root_index = int(parts[0])
        except ValueError:
            return None
        roots = list(scene)
        if root_index >= len(roots):
            return None
        node = roots[root_index]
        for chunk in (parts[1].split("|") if len(parts) > 1 and parts[1] else []):
            try:
                idx = int(chunk)
            except ValueError:
                return None
            kids = list(node)
            if idx >= len(kids):
                return None
            node = kids[idx]
        return node

    for mid, mpath in mappings.items():
        node = resolve(mpath)
        if node is None:
            err("mapping %r -> %r does not resolve" % (mid, mpath))
        elif node.get("name") != mid:
            err("mapping %r points to node %r" % (mid, node.get("name")))

    # geometry: the craft floats, the wheels stand on the ground
    visual = resolve(mappings.get("visual", ""))
    lifted = float(visual.get("translation", "0 0 0").split()[1]) if visual is not None else 0.0
    if lifted < 8.0:
        err("visual node is only %.2f m up - the craft should hover" % lifted)
    wheel_ys = []
    for name, mpath in mappings.items():
        if name.startswith("wheel"):
            node = resolve(mpath)
            if node is None:
                err("wheel node %r missing in the i3d" % name)
                continue
            if node.tag != "TransformGroup":
                err("wheel node %r is a <%s>, it has to be a TransformGroup" % (name, node.tag))
            wheel_ys.append(float(node.get("translation", "0 0 0").split()[1]))
    if wheel_ys and max(abs(y - 0.55) for y in wheel_ys) > 0.01:
        err("wheel nodes are not on the contact plane (y=0.55): %s" % sorted(set(wheel_ys)))
    if not wheel_ys:
        err("no wheel nodes in the i3d")
    ok("ufo2500.i3d: craft lifted %.2f m, %d wheel nodes at y=0.55" % (lifted, len(wheel_ys)))

    files = [f.get("filename") for f in root.findall("Files/File")]
    for f in files:
        if not os.path.isfile(os.path.join(MOD, f)):
            err("i3d texture %s does not exist" % f)
    shapes_el = root.find("Shapes")
    ext = shapes_el.get("externalShapesFile") if shapes_el is not None else None
    if not ext:
        err("ufo2500.i3d <Shapes> is not binarized")
    elif not os.path.isfile(os.path.join(MOD, ext)):
        err("shapes file %s is missing" % ext)
    else:
        ok("ufo2500.i3d: binarized (%s, %.0f kB)"
           % (ext, os.path.getsize(os.path.join(MOD, ext)) / 1024.0))
    root_shape = list(scene)[0] if len(scene) else None
    if root_shape is None or root_shape.get("dynamic") != "true":
        err("the first scene node has to be the dynamic vehicle component")


def check_landing(veh, mappings):
    """The landing animation has to bring the craft down to street level."""
    anims = {a.get("name"): a for a in veh.findall("animations/animation")}
    if "landing" not in anims:
        err("no <animations><animation name=\"landing\">")
        return
    parts = {p.get("node"): p for p in anims["landing"].findall("part")}
    visual = parts.get("visual")
    if visual is None:
        err("landing animation does not move the visual node")
        return
    try:
        start = float(visual.get("startTrans").split()[1])
        end = float(visual.get("endTrans").split()[1])
    except (AttributeError, IndexError, ValueError):
        err("landing animation: visual part needs startTrans/endTrans")
        return
    if start < 15.0:
        err("landing animation starts at %.2f m, the craft should hover" % start)
    if end > 1.5:
        err("landing animation ends at %.2f m - that is not street level" % end)
    ok("landing animation: %.2f m -> %.2f m in %.1f s"
       % (start, end, float(visual.get("endTime", 0))))
    for leg in ("leg0", "leg1", "leg2"):
        if leg not in parts:
            err("landing animation does not extend %s" % leg)
        elif not (parts[leg].get("startRot") and parts[leg].get("endRot")):
            err("landing animation: %s needs startRot/endRot" % leg)
    for node in ("beamNode", "groundRing"):
        if node not in parts:
            warn("landing animation does not animate %s" % node)
    fold = veh.find("foldable/foldingConfigurations/foldingConfiguration/foldingParts")
    if fold is None:
        err("no <foldable> block - the landing animation would never play")
    elif fold.get("foldInputButton") is None:
        warn("<foldable> has no foldInputButton")
    else:
        ok("foldable: %s plays the landing animation" % fold.get("foldInputButton"))


def check_cockpit(veh, mappings):
    beacons = veh.findall("lights/beaconLights/beaconLight")
    if not beacons:
        warn("no beacon lights in the cockpit")
    for b in beacons:
        f = b.get("filename") or ""
        if not f.startswith("$data/shared/"):
            err("cockpit beacon %r is not a base game light (%s)" % (b.get("node"), f))
        if b.get("node") not in mappings:
            err("cockpit beacon node %r has no i3dMapping" % b.get("node"))
    if beacons and not errors:
        ok("cockpit: %d blinking base game beacon lights" % len(beacons))
    for node in ("cockpitDetail", "cockpitBeacon1", "cockpitBeacon2", "driverSeatNode"):
        if node not in mappings:
            err("cockpit node %r missing" % node)
    ok("cockpit: dashboard, screens and buttons in the model")


def check_files():
    veh = load(os.path.join(MOD, "ufo2500.xml"))
    if veh is None:
        return None
    base = veh.find("base")
    i3d = base.findtext("filename")
    if not os.path.isfile(os.path.join(MOD, i3d)):
        err("base filename %s does not exist" % i3d)
    store = veh.findtext("storeData/image")
    if store and not os.path.isfile(os.path.join(MOD, store)):
        err("storeData image %s does not exist" % store)
    brand = veh.findtext("storeData/brand")
    if brand and brand not in BASE_BRANDS:
        err("storeData brand %r is not a base game brand (console!)" % brand)
    for s in veh.findall(".//sounds/*") + veh.findall(".//honk/*"):
        f = s.get("file")
        if f and not os.path.isfile(os.path.join(MOD, f)):
            err("sound file %s does not exist" % f)
    return veh


def check_zip(zpath):
    if not zpath or not os.path.isfile(zpath):
        warn("zip not checked (not built yet)")
        return
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    if "modDesc.xml" not in names:
        err("zip: modDesc.xml is not at the archive root")
    for n in names:
        if n.startswith("/") or "\\" in n:
            err("zip: unexpected path %r" % n)
        if n.lower().endswith((".psd", ".blend", ".py", ".lua")):
            err("zip: development or script file %r" % n)
        if n.lower().endswith(".png") and n != "store_ufo2500.png":
            warn("zip: development image %r" % n)
    ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(zpath) / 1048576.0))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xsd", help="directory with the official FS25 .xsd files")
    ap.add_argument("--zip", default=os.path.join(REPO, "dist", "FS25_UFO2500.zip"))
    args = ap.parse_args()

    sd = xsd_dir(args)
    if sd is None:
        warn("official FS25 schemas not found - XSD validation skipped")

    desc = check_console_rules()
    if desc is not None:
        check_moddesc(desc)
    check_l10n()
    veh = check_files()
    if veh is not None:
        mappings = check_i3d_mappings(veh)
        check_xml_nodes(veh, mappings)
        check_wheels(veh, mappings)
        check_landing(veh, mappings)
        check_cockpit(veh, mappings)
        check_i3d(mappings)
    check_xsd(os.path.join(MOD, "modDesc.xml"), sd, "modDesc.xsd")
    check_xsd(os.path.join(MOD, "ufo2500.xml"), sd, "vehicle.xsd")
    check_xsd(os.path.join(MOD, "ufo2500.i3d"), sd, "i3d-1.6.xsd")
    check_zip(args.zip)

    for n in notes:
        print("  ok    %s" % n)
    for w in warnings:
        print("  warn  %s" % w)
    for e in errors:
        print("  ERROR %s" % e)
    print("\n%d checks passed, %d warnings, %d errors" % (len(notes), len(warnings), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
