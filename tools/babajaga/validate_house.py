#!/usr/bin/env python3
"""Static checks for the separate FS25_BabaJagaHouse residence.

    python tools/babajaga/validate_house.py [--xsd SCHEMA_DIR] [--zip PATH]

Validates native farmhouse/sleep/wardrobe/animated-door XML, walkable collision
assets and mapping paths. It also rejects Lua/custom actions so the mod remains
console compatible. An FS25 XSD directory may be supplied for schema checks.
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_BabaJagaHouse")
BASE_L10N = {"configuration_valueDefault", "info_transmission_automatic",
             "unit_literShort", "brand_lizard"}

errors = []
warnings = []
notes = []


def err(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def ok(message):
    notes.append(message)


def load(path):
    try:
        return ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        err("%s: cannot parse XML: %s" % (os.path.relpath(path, REPO), exc))
        return None


def check_xsd(path, schema_dir, schema_name):
    if schema_dir is None:
        return
    schema_path = os.path.join(schema_dir, schema_name)
    if not os.path.isfile(schema_path):
        warn("XSD not found: %s" % schema_path)
        return
    try:
        from lxml import etree
    except ImportError:
        warn("lxml is unavailable; XSD check skipped")
        return
    schema = etree.XMLSchema(etree.parse(schema_path))
    document = etree.parse(path)
    if schema.validate(document):
        ok("XSD %-14s OK (%s)" % (schema_name, os.path.basename(path)))
    else:
        for issue in list(schema.error_log)[:10]:
            err("%s:%d XSD %s: %s" % (os.path.basename(path), issue.line,
                                        schema_name, issue.message))


def check_moddesc():
    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is None:
        return None
    for tag in ("author", "version", "iconFilename", "title", "description", "storeItems"):
        if desc.find(tag) is None:
            err("modDesc.xml is missing <%s>" % tag)
    for tag in ("extraSourceFiles", "actions", "inputBinding", "brands"):
        if desc.find(tag) is not None:
            err("console compatibility: modDesc.xml must not contain <%s>" % tag)
    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(MOD, icon)):
        err("icon file does not exist: %s" % icon)
    items = [node.get("xmlFilename") for node in desc.findall("storeItems/storeItem")]
    if items != ["babaJagaHouse.xml"]:
        err("expected one separate residential store item babaJagaHouse.xml")
    for item in items:
        if not os.path.isfile(os.path.join(MOD, item)):
            err("store item XML is missing: %s" % item)
    if os.path.isfile(os.path.join(MOD, "babaJagaHouse.xml")):
        store_image = load(os.path.join(MOD, "babaJagaHouse.xml"))
        image = store_image.findtext("storeData/image") if store_image is not None else None
        if image and not os.path.isfile(os.path.join(MOD, image)):
            err("store image does not exist: %s" % image)
    if glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True):
        err("console compatibility: the residential mod must not package Lua")
    else:
        ok("console compatibility: no Lua, custom actions, or brand override")
    return desc


def check_l10n(desc, placeable):
    keys = set()
    for text in (desc.findall("l10n/text") if desc is not None else []):
        name = text.get("name", "")
        keys.add(name)
    used = set()
    for path in (os.path.join(MOD, "modDesc.xml"), os.path.join(MOD, "babaJagaHouse.xml")):
        try:
            with open(path, encoding="utf-8") as fh:
                used.update(re.findall(r"\$l10n_([A-Za-z0-9_]+)", fh.read()))
        except OSError:
            pass
    missing = sorted(used - keys - BASE_L10N)
    if missing:
        err("missing l10n entries: %s" % ", ".join(missing))
    else:
        ok("translations: all %d referenced l10n keys exist" % len(used))


def mappings_of(placeable):
    mappings = {}
    for node in placeable.iter("i3dMapping"):
        mapping_id, path = node.get("id"), node.get("node")
        if not mapping_id or not path:
            err("i3dMapping requires both id and node")
        elif mapping_id in mappings:
            err("duplicate i3dMapping id %r" % mapping_id)
        else:
            mappings[mapping_id] = path
    return mappings


def check_native_features(placeable, mappings):
    if placeable.get("type") != "simplePlaceable":
        err("residential home should use native simplePlaceable type")
    if placeable.find("husbandry") is not None:
        err("residential home must remain separate from the chicken husbandry")
    farmhouse = placeable.find("farmhouse")
    sleeping = farmhouse.find("sleeping") if farmhouse is not None else None
    wardrobe = placeable.find("wardrobe")
    if farmhouse is None or farmhouse.get("spawnNode") != "spawnNode":
        err("native <farmhouse> needs the mapped spawnNode")
    if sleeping is None or sleeping.get("triggerNode") != "sleepTrigger" \
            or sleeping.get("cameraNode") != "sleepingCamera":
        err("native <farmhouse><sleeping> needs trigger and camera nodes")
    if wardrobe is None or wardrobe.get("triggerNode") != "wardrobeTrigger":
        err("native <wardrobe> needs its triggerNode")

    animated = placeable.find("animatedObjects/animatedObject")
    part = animated.find("animation/part") if animated is not None else None
    controls = animated.find("controls") if animated is not None else None
    if part is None or part.get("node") != "doorPivot":
        err("animated front door must animate the doorPivot node")
    if controls is None or controls.get("triggerNode") != "doorTrigger":
        err("animated front door must have a player trigger")
    if controls is not None and controls.get("posAction") != "ACTIVATE_HANDTOOL":
        err("door must use the base-game ACTIVATE_HANDTOOL action")

    ref_attrs = ("node", "startNode", "endNode", "widthNode", "heightNode",
                 "triggerNode", "rootNode", "shape", "cameraNode", "spawnNode")
    referenced = set()
    for element in placeable.iter():
        if element.tag in ("i3dMapping", "i3dMappings"):
            continue
        for attr in ref_attrs:
            value = element.get(attr)
            if value and not value.startswith("$"):
                referenced.add(value)
    unknown = sorted(referenced - set(mappings))
    if unknown:
        err("placeable nodes lack i3dMappings: %s" % ", ".join(unknown))
    else:
        ok("native house features: sleep, wardrobe, animated door; %d node references mapped"
           % len(referenced))
    return mappings


def resolve_node(scene, path):
    parts = path.split(">")
    try:
        node = list(scene)[int(parts[0])]
    except (ValueError, IndexError):
        return None
    if len(parts) > 1 and parts[1]:
        for index in parts[1].split("|"):
            try:
                node = list(node)[int(index)]
            except (ValueError, IndexError):
                return None
    return node


def check_i3d(placeable, mappings, schema_dir):
    path = os.path.join(MOD, "babaJagaHouse.i3d")
    root = load(path)
    if root is None:
        return
    scene = root.find("Scene")
    if scene is None:
        err("babaJagaHouse.i3d has no Scene")
        return
    ids = [node.get("nodeId") for node in scene.iter() if node.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("babaJagaHouse.i3d has duplicate nodeId values")
    bad = []
    for mapping_id, mapping_path in mappings.items():
        node = resolve_node(scene, mapping_path)
        if node is None or node.get("name") != mapping_id:
            bad.append("%s -> %s" % (mapping_id, mapping_path))
    if bad:
        err("I3D mappings do not resolve: %s" % ", ".join(bad))
    else:
        ok("I3D: all %d mappings resolve" % len(mappings))

    shapes = root.find("Shapes")
    external = shapes.get("externalShapesFile") if shapes is not None else None
    if not external or not os.path.isfile(os.path.join(MOD, external)):
        err("babaJagaHouse.i3d external shapes file is missing")

    node_names = {node.get("name") for node in scene.iter() if node.get("name")}
    required = {"residenceFloorCol", "residenceBalconyCol", "residenceStairsCol",
                "doorPivot", "sleepTrigger", "wardrobeTrigger", "doorTrigger",
                "spawnNode", "sleepingCamera", "stairMesh"}
    missing = sorted(required - node_names)
    if missing:
        err("walkability/interaction scene nodes are missing: %s" % ", ".join(missing))
    else:
        ok("I3D contains interior, balcony and stair collisions plus all interaction nodes")

    base = placeable.findtext("base/filename")
    if base and not os.path.isfile(os.path.join(MOD, base)):
        err("base model does not exist: %s" % base)
    for file_node in root.findall("Files/File"):
        name = file_node.get("filename")
        if name and not os.path.isfile(os.path.join(MOD, name)):
            err("I3D texture does not exist: %s" % name)
    check_xsd(path, schema_dir, "i3d-1.6.xsd")


def check_zip(path):
    if not path or not os.path.isfile(path):
        return
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            required = {"modDesc.xml", "babaJagaHouse.xml", "babaJagaHouse.i3d"}
            if not required.issubset(set(names)):
                err("zip root is missing: %s" % ", ".join(sorted(required - set(names))))
            if any(name.startswith("FS25_BabaJagaHouse/") for name in names):
                err("zip must have modDesc.xml at its root, not in a nested directory")
            if any(name.lower().endswith(".lua") for name in names):
                err("console compatibility: zip must not contain Lua")
            bad = archive.testzip()
            if bad:
                err("corrupt zip entry: %s" % bad)
            else:
                ok("zip: flat console-safe package with %d files" % len(names))
    except (OSError, zipfile.BadZipFile) as exc:
        err("cannot read zip: %s" % exc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xsd", help="schema directory containing placeable.xsd, modDesc.xsd and i3d-1.6.xsd")
    parser.add_argument("--zip", help="optional built mod zip to inspect")
    args = parser.parse_args()
    schema_dir = args.xsd or os.environ.get("FS25_MOD_SCHEMA_DIR")

    desc = check_moddesc()
    placeable = load(os.path.join(MOD, "babaJagaHouse.xml"))
    if placeable is not None:
        mappings = mappings_of(placeable)
        check_native_features(placeable, mappings)
        check_i3d(placeable, mappings, schema_dir)
        check_l10n(desc, placeable)
        check_xsd(os.path.join(MOD, "babaJagaHouse.xml"), schema_dir, "placeable.xsd")
    if desc is not None:
        check_xsd(os.path.join(MOD, "modDesc.xml"), schema_dir, "modDesc.xsd")
    check_zip(args.zip)

    for message in notes:
        print("  OK: " + message)
    for message in warnings:
        print("  WARN: " + message)
    for message in errors:
        print("  ERROR: " + message)
    if errors:
        print("FAILED: %d error(s), %d warning(s)" % (len(errors), len(warnings)))
        return 1
    print("OK: Baba Jaga residence is statically valid (%d warning(s))" % len(warnings))
    return 0


if __name__ == "__main__":
    sys.exit(main())
