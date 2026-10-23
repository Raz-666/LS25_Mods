#!/usr/bin/env python3
"""Static checks for the FS25_Alien mod (placeable).

      python tools/alien/validate.py [--xsd DIR]

Checks modDesc.xml and alien.xml against the official FS25 schemas (if found),
that every referenced file exists, all l10n keys are translated, the i3d is well
formed and the zip (if built) has modDesc.xml at its root.
"""

import argparse
import glob
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_Alien")

errors, notes, warnings = [], [], []


def err(m):
    errors.append(m)


def warn(m):
    warnings.append(m)


def ok(m):
    notes.append(m)


def load(path):
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as e:
        err("%s: not well-formed XML: %s" % (os.path.basename(path), e))
        return None


def find_xsd(args):
    for cand in (args.xsd, os.environ.get("FS25_MOD_SCHEMA_DIR"), os.path.join(REPO, "tools", "xsd")):
        if cand and os.path.isfile(os.path.join(cand, "modDesc.xsd")):
            return cand
    return None


def check_xsd(doc, schema_dir, name):
    if schema_dir is None:
        return
    try:
        from lxml import etree
    except ImportError:
        warn("lxml not installed - XSD checks skipped")
        return
    schema = etree.XMLSchema(etree.parse(os.path.join(schema_dir, name)))
    tree = etree.parse(doc)
    if schema.validate(tree):
        ok("XSD %-12s OK (%s)" % (name, os.path.basename(doc)))
    else:
        for e in list(schema.error_log)[:8]:
            err("%s:%d against %s: %s" % (os.path.basename(doc), e.line, name, e.message))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xsd")
    ap.add_argument("--zip", default=os.path.join(REPO, "dist", "FS25_Alien.zip"))
    args = ap.parse_args()
    sd = find_xsd(args)

    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is None:
        print("  ERROR modDesc.xml missing")
        return 1
    ok("modDesc.xml: descVersion %s" % desc.get("descVersion"))
    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(MOD, icon)):
        err("iconFilename %s does not exist" % icon)
    for item in desc.findall("storeItems/storeItem"):
        f = os.path.join(MOD, item.get("xmlFilename"))
        if not os.path.isfile(f):
            err("store item %s does not exist" % item.get("xmlFilename"))
    check_xsd(os.path.join(MOD, "modDesc.xml"), sd, "modDesc.xsd")

    place = load(os.path.join(MOD, "alien.xml"))
    check_xsd(os.path.join(MOD, "alien.xml"), sd, "placeable.xsd")
    if place is not None:
        # every file=""/texture reference must exist
        base = MOD
        images = place.findall(".//image")
        for img in images:
            if img.text and not os.path.isfile(os.path.join(base, img.text)):
                err("store image %s is missing" % img.text)
        i3d = place.findtext("base/filename")
        if i3d is None or not os.path.isfile(os.path.join(base, i3d)):
            err("base/filename %s does not exist" % i3d)
        else:
            scene = load(os.path.join(base, i3d))
            shapes = 0 if scene is None else len(list(scene.iter("Shape")))
            ok("alien.i3d: %d shapes" % shapes)
            files = [] if scene is None else [f.get("filename") for f in scene.iter("File")]
            for f in files:
                if not os.path.isfile(os.path.join(base, f)):
                    err("i3d texture %s is missing" % f)
            if files:
                ok("alien.i3d: %d textures present" % len(files))
            check_xsd(os.path.join(base, i3d), sd, "i3d-1.6.xsd")

    # l10n
    keys = set()
    for f in glob.glob(os.path.join(MOD, "translations", "*.xml")):
        root = load(f)
        if root is None:
            continue
        for t in root.findall("text"):
            keys.add(t.get("name"))
    used = set()
    for f in glob.glob(os.path.join(MOD, "**", "*.xml"), recursive=True):
        try:
            used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", open(f, encoding="utf-8").read()))
        except (OSError, UnicodeDecodeError):
            pass
    missing = sorted(used - keys)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    else:
        ok("translations: %d keys, all used keys present" % len(keys))

    if os.path.isfile(args.zip):
        with zipfile.ZipFile(args.zip) as z:
            names = z.namelist()
        if "modDesc.xml" not in names:
            err("zip: modDesc.xml not at the archive root")
        ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(args.zip) / 1048576.0))
    else:
        warn("zip not built yet")

    for n in notes:
        print("  ok    " + n)
    for w in warnings:
        print("  warn  " + w)
    for e in errors:
        print("  ERROR " + e)
    print("\n%d checks passed, %d warnings, %d errors" % (len(notes), len(warnings), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
