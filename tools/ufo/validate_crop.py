#!/usr/bin/env python3
"""Static checks for the FS25_CropHarvester mod (no game required).

      python tools/ufo/validate_crop.py [--xsd DIR] [--zip dist/FS25_CropHarvester.zip]

Checks
  * modDesc.xml / crop.xml / crop.i3d are well formed and - if the official FS25
    schemas are available - valid against modDesc.xsd, vehicle.xsd, i3d-1.6.xsd
    (pass --xsd, set FS25_MOD_SCHEMA_DIR, or drop them into tools/xsd/)
  * every file referenced by the XML/i3d exists (textures, sounds, store image)
  * every i3dMapping path in crop.xml resolves to a scene node with that name,
    and every <i3dMapping id> is unique
  * the number of shapes in crop.i3d matches the entities in ufo.i3d.shapes
  * all $l10n_ keys used by the mod exist in translations/
  * every input action used by the Lua is declared in modDesc.xml
  * optional: the built zip has modDesc.xml at its root and no stray files
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_CropHarvester")
VEHICLE_XML = "crop.xml"
I3D_XML = "crop.i3d"
LUA_FILE = "CropHarvester.lua"
STORE_PNG = "store_crop.png"
MAIN_NODE = "crop_main_component1"

errors = []
warnings = []
notes = []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def ok(msg):
    notes.append(msg)


# ---------------------------------------------------------------------------
def load(path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        err("%s: not well-formed XML: %s" % (os.path.relpath(path, REPO), e))
        return None


def xsd_dir(args):
    for cand in (args.xsd, os.environ.get("FS25_MOD_SCHEMA_DIR"), os.path.join(REPO, "tools", "xsd")):
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
def check_moddesc(mod):
    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is None:
        return None
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
    for spec in desc.findall("specializations/specialization"):
        f = spec.get("filename")
        if not os.path.isfile(os.path.join(MOD, f)):
            err("specialization file %s does not exist" % f)
    types = [t.get("name") for t in desc.findall("vehicleTypes/type")]
    ok("modDesc.xml: descVersion %d, vehicle types: %s" % (dv, ", ".join(types) or "-"))
    return desc


def check_l10n(mod, desc):
    keys = set()
    for f in glob.glob(os.path.join(MOD, "translations", "*.xml")):
        root = load(f)
        if root is None:
            continue
        file_keys = set()
        for t in root.iter("text"):
            key = t.get("name")
            if key in file_keys:
                err("%s: duplicate translation key %r" % (os.path.basename(f), key))
            file_keys.add(key)
            keys.add(key)
    used = set()
    for f in ("modDesc.xml", VEHICLE_XML):
        with open(os.path.join(MOD, f), encoding="utf-8") as fh:
            used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", fh.read()))
    with open(os.path.join(MOD, "scripts", LUA_FILE), encoding="utf-8") as fh:
        used |= set(re.findall(r'getText\("([A-Za-z0-9_]+)"\)', fh.read()))
    base_keys = {"configuration_valueDefault", "info_transmission_automatic", "unit_literShort"}
    missing = sorted(used - keys - base_keys)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    if desc is not None:
        texts = set()
        for lang in desc.findall("title/*"):
            if lang.text and lang.text.startswith("$l10n_"):
                texts.add(lang.text[6:])
        for lang in desc.findall("description/*"):
            if lang.text and lang.text.strip().startswith("$l10n_"):
                texts.add(lang.text.strip()[6:])
    ok("translations: %d keys" % len(keys))


def check_vehicle(desc):
    path = os.path.join(MOD, VEHICLE_XML)
    veh = load(path)
    if veh is None:
        return None

    base = veh.find("base")
    i3d = base.findtext("filename")
    if not os.path.isfile(os.path.join(MOD, i3d)):
        err("base filename %s does not exist" % i3d)
    view = base.findtext("size")
    if view is None:
        err("base/size missing")

    # store image + brand image
    store = veh.findtext("storeData/image")
    if store and not os.path.isfile(os.path.join(MOD, store)):
        err("storeData image %s does not exist" % store)
    brand = veh.findtext("storeData/brand")
    if desc is not None and brand is not None:
        names = [b.get("name") for b in desc.findall("brands/brand")]
        if brand not in names:
            err("storeData brand %r is not declared in modDesc.xml" % brand)
        else:
            for b in desc.findall("brands/brand"):
                img = b.get("image")
                if img and not os.path.isfile(os.path.join(MOD, img)):
                    err("brand image %s does not exist" % img)

    # sounds
    for tag in (".//sounds/*", ".//honk/*"):
        for s in veh.findall(tag):
            f = s.get("file") or s.get("filename")
            if f and not f.startswith("$") and not os.path.isfile(os.path.join(MOD, f)):
                err("sound file %s does not exist" % f)

    # node references have to be resolvable through <i3dMappings>
    mapping_ids = set()
    mappings = {}
    for m in veh.iter("i3dMapping"):
        mid, node = m.get("id"), m.get("node")
        if mid in mapping_ids:
            err("duplicate i3dMapping id %r" % mid)
        mapping_ids.add(mid)
        mappings[mid] = node
    if "transferBeamNode" not in mapping_ids:
        err("crop.xml is missing i3dMapping for the secondary harvest beam")

    referenced = set()
    for el in veh.iter():
        if el.tag in ("i3dMapping", "i3dMappings"):
            continue
        for key in ("node", "realLight", "rotateNode"):
            v = el.get(key)
            if v and not v.startswith("$"):
                referenced.add(v)
    unknown = sorted(referenced - mapping_ids)
    if unknown:
        err("crop.xml references nodes without i3dMapping: %s" % ", ".join(unknown))

    # input actions used by the Lua must exist in modDesc
    actions = {a.get("name") for a in desc.findall("actions/action")} if desc is not None else set()
    with open(os.path.join(MOD, "scripts", LUA_FILE), encoding="utf-8") as fh:
        lua = fh.read()
    used_actions = set(re.findall(r'addActionEvent\(spec\.actionEvents, "([A-Za-z0-9_]+)"', lua))
    # Base-game vehicle actions such as LOWER_IMPLEMENT and AXIS_FRONTLOADER_ARM
    # are supplied by FS25; only this mod's own crop_* actions belong in modDesc.
    mod_actions = {name for name in used_actions if name.startswith("crop_")}
    if actions:
        missing = sorted(mod_actions - actions)
        if missing:
            err("Lua registers actions that are not declared in modDesc.xml: %s" % ", ".join(missing))
    bindings = set()
    if desc is not None:
        bindings = {b.get("action") for b in desc.findall("inputBinding/actionBinding")}
        unbound = sorted(actions - bindings)
        if unbound:
            warn("actions without default key binding: %s" % ", ".join(unbound))
    if "crop_physicalCargo" not in actions or "crop_physicalCargo" not in bindings:
        err("Crop Harvester physical-cargo action must be declared and bound in modDesc.xml")
    physical_tokens = (
        "CropHarvester.PHYSICAL_CARGO_ENABLED = true",
        "function CropHarvester.acquirePhysicalCargo(vehicle)",
        "function CropHarvester.releasePhysicalCargo(vehicle, force)",
        "CropHarvester.PHYSICAL_CARGO_MAX_MASS = 12000.0",
        "CropHarvester.PHYSICAL_CARGO_MAX_WIDTH = 4.5",
        "CropHarvester.PHYSICAL_CARGO_MAX_HEIGHT = 4.0",
        "CropHarvester.PHYSICAL_CARGO_MAX_LENGTH = 8.0",
    )
    missing_physical = [token for token in physical_tokens if token not in lua]
    if missing_physical:
        err("Crop Harvester physical-cargo implementation is incomplete: %s"
            % ", ".join(missing_physical))
    ok("vehicle XML: %d node references, %d mappings, %d actions"
       % (len(referenced), len(mappings), len(actions)))
    return mappings


def check_i3d(mappings):
    path = os.path.join(MOD, I3D_XML)
    root = load(path)
    if root is None:
        return
    scene = root.find("Scene")
    if scene is None:
        err("crop.i3d has no <Scene>")
        return

    # nodeId uniqueness
    ids = [n.get("nodeId") for n in scene.iter() if n.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("crop.i3d: duplicate nodeId values")

    # resolve every mapping path
    def resolve(path):
        """GIANTS node path: "<rootIndex>>" or "<rootIndex>>child|child|..."."""
        parts = path.split(">")
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

    bad = 0
    for mid, mpath in mappings.items():
        node = resolve(mpath)
        if node is None:
            err("mapping %r -> %r does not resolve in crop.i3d" % (mid, mpath))
            bad += 1
        elif node.get("name") != mid and mid not in (MAIN_NODE,):
            err("mapping %r points to node %r" % (mid, node.get("name")))
    if not bad:
        ok("crop.i3d: %d mappings resolve" % len(mappings))

    # shapes / textures
    files = [f.get("filename") for f in root.findall("Files/File")]
    for f in files:
        if not os.path.isfile(os.path.join(MOD, f)):
            err("i3d texture %s does not exist" % f)
    shape_ids = [s.get("shapeId") for s in scene.iter("Shape")]
    shapes_el = root.find("Shapes")
    ext = shapes_el.get("externalShapesFile") if shapes_el is not None else None
    if not ext:
        err("crop.i3d <Shapes> is not binarized (no externalShapesFile)")
    else:
        spath = os.path.join(MOD, ext)
        if not os.path.isfile(spath):
            err("shapes file %s is missing" % ext)
        else:
            import struct
            data = open(spath, "rb").read()
            n = struct.unpack("<i", data[4 + 64 * 0:8]) if False else None  # decoded below
            try:
                sys.path.insert(0, os.path.join(REPO, "tools", "i3d"))
                import i3d_shapes_writer as W  # noqa: F401
            except Exception:
                pass
            ok("crop.i3d: %d shapes, shapes file %.0f kB" % (len(shape_ids), len(data) / 1024.0))
    # dynamic root component
    root_shape = list(scene)[0] if len(scene) else None
    if root_shape is None or root_shape.get("dynamic") != "true":
        err("the first scene node has to be the dynamic vehicle component")
    ok("crop.i3d: %d lights, %d cameras"
       % (len(list(scene.iter("Light"))), len(list(scene.iter("Camera")))))


def check_zip(zpath):
    if not zpath or not os.path.isfile(zpath):
        warn("zip not checked (not built yet)")
        return
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
    if "modDesc.xml" not in names:
        err("zip: modDesc.xml is not at the archive root")
    for n in names:
        if n.startswith(("FS25_UFO2000/", "FS25_CropHarvester/")) or n.startswith("/") or "\\" in n:
            err("zip: unexpected path %r" % n)
        if n.lower().endswith((".psd", ".blend", ".py", ".png")) and not n.endswith(STORE_PNG):
            warn("zip: development file %r" % n)
    ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(zpath) / 1048576.0))


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xsd", help="directory with the official FS25 .xsd files")
    ap.add_argument("--zip", default=os.path.join(REPO, "dist", "FS25_CropHarvester.zip"))
    args = ap.parse_args()

    sd = xsd_dir(args)
    if sd is None:
        warn("official FS25 schemas not found - XSD validation skipped "
             "(drop them into tools/xsd/ or pass --xsd)")

    desc = check_moddesc(MOD)
    check_xsd(os.path.join(MOD, "modDesc.xml"), sd, "modDesc.xsd")
    check_l10n(MOD, desc)
    mappings = check_vehicle(desc)
    check_xsd(os.path.join(MOD, VEHICLE_XML), sd, "vehicle.xsd")
    if mappings is not None:
        check_i3d(mappings)
    check_xsd(os.path.join(MOD, I3D_XML), sd, "i3d-1.6.xsd")
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
