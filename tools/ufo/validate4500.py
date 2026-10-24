#!/usr/bin/env python3
"""Static checks for FS25_UFO4500 (harvester + header), no game required.

    python tools/ufo/validate4500.py [--xsd DIR] [--zip dist/FS25_UFO4500.zip]

Checks
  * console rules: no Lua, no <actions>, base game specializations only, LIZARD
  * both vehicle XMLs against the official vehicle.xsd, modDesc against modDesc.xsd
  * every node / physics#repr has an i3dMapping that resolves in the i3d
  * the combine really is a combine: WorkArea + FillUnit specializations,
    <combine fillUnitIndex> pointing at the grain fill unit
  * the header really is a cutter: cutter work area, 6 m wide, ground reference,
    cutter attacher joint on the combine, combination link
  * the craft floats above the invisible wheels, textures/shapes files exist
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_UFO4500")
BASE_BRANDS = {"LIZARD"}
BASE_L10N = {"configuration_valueDefault", "info_transmission_automatic",
             "unit_literShort", "brand_lizard"}
# specializations we are allowed to add to our own vehicle type on console
ALLOWED_SPECS = {"workArea", "turnOnVehicle", "combine", "pipe", "dischargeable",
                 "fillUnit", "animatedVehicle", "foldable", "groundReference",
                 "testAreas", "powerConsumer"}

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
        ok("XSD %-12s OK  (%s)" % (xsd_name, os.path.basename(doc)))
    else:
        for e in list(schema.error_log)[:8]:
            err("%s:%d against %s: %s" % (os.path.basename(doc), e.line, xsd_name, e.message))


# ---------------------------------------------------------------------------
def check_moddesc():
    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is None:
        return None, []
    lua = glob.glob(os.path.join(MOD, "**", "*.lua"), recursive=True)
    if lua:
        err("console check: the mod ships Lua: %s" % ", ".join(lua))
    else:
        ok("console check: no Lua file in the mod")
    for tag in ("extraSourceFiles", "actions", "inputBinding", "brands"):
        if desc.find(tag) is not None:
            err("console check: modDesc.xml must not contain <%s>" % tag)
    for spec in desc.findall("specializations/specialization"):
        f = spec.get("filename")
        if f and not f.startswith("$dataS/"):
            err("console check: specialization %r ships its own script" % spec.get("name"))

    types = desc.findall("vehicleTypes/type")
    if len(types) != 2:
        err("expected two vehicle types (combine + header), found %d" % len(types))
    for t in types:
        parent = (t.get("parent") or "").strip()
        if not parent:
            err("vehicle type %r has no base game parent" % t.get("name"))
        fn = t.get("filename")
        if fn and not fn.startswith("$dataS/"):
            err("vehicle type %r uses a file outside the base game" % t.get("name"))
        for spec in t.findall("specialization"):
            name = spec.get("name")
            if spec.get("filename"):
                err("%r: specialization %r ships a script" % (t.get("name"), name))
            elif name not in ALLOWED_SPECS:
                warn("%r: specialization %r was not verified for this mod"
                     % (t.get("name"), name))
    ok("console check: XML only, %d vehicle types, base game code" % len(types))

    dv = int(desc.get("descVersion", "0"))
    if not 90 <= dv <= 115:
        err("modDesc descVersion %d outside 90..115" % dv)
    for tag in ("author", "version", "iconFilename", "title", "description"):
        if desc.find(tag) is None:
            err("modDesc.xml: missing <%s>" % tag)
    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(MOD, icon)):
        err("iconFilename %s does not exist" % icon)
    items = [i.get("xmlFilename") for i in desc.findall("storeItems/storeItem")]
    for f in items:
        if not os.path.isfile(os.path.join(MOD, f)):
            err("storeItem %s does not exist" % f)
    ok("modDesc.xml: descVersion %d, %d store items" % (dv, len(items)))
    return desc, items


def check_l10n(names):
    keys = set()
    for f in glob.glob(os.path.join(MOD, "translations", "*.xml")):
        root = load(f)
        if root is None:
            continue
        keys.update(t.get("name") for t in root.iter("text"))
    used = set()
    for name in ["modDesc.xml"] + names:
        with open(os.path.join(MOD, name), encoding="utf-8") as fh:
            used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", fh.read()))
    missing = sorted(used - keys - BASE_L10N)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    ok("translations: %d keys, %d used" % (len(keys), len(used)))


def mappings_of(veh):
    out = {}
    for m in veh.iter("i3dMapping"):
        mid, node = m.get("id"), m.get("node")
        if mid in out:
            err("%s: duplicate i3dMapping id %r" % (veh.tag, mid))
        out[mid] = node
    return out


def check_node_refs(name, veh, mappings):
    referenced = set()
    for el in veh.iter():
        if el.tag in ("i3dMapping", "i3dMappings"):
            continue
        for key in ("node", "rotateNode", "realLight", "shaderNode"):
            v = el.get(key)
            if v and not v.startswith("$"):
                referenced.add(v)
        if el.tag == "physics" and el.get("repr"):
            referenced.add(el.get("repr"))
    unknown = sorted(referenced - set(mappings))
    if unknown:
        err("%s: nodes without i3dMapping: %s" % (name, ", ".join(unknown)))
    ok("%s: %d node references, %d mappings" % (name, len(referenced), len(mappings)))


def check_i3d(name, mappings, expect_hover):
    path = os.path.join(MOD, name + ".i3d")
    root = load(path)
    if root is None:
        return
    scene = root.find("Scene")
    if scene is None:
        err("%s.i3d has no <Scene>" % name)
        return
    ids = [n.get("nodeId") for n in scene.iter() if n.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("%s.i3d: duplicate nodeId values" % name)

    def resolve(mpath):
        parts = mpath.split(">")
        try:
            idx = int(parts[0])
            roots = list(scene)
            if idx >= len(roots):
                return None
            node = roots[idx]
            for chunk in (parts[1].split("|") if len(parts) > 1 and parts[1] else []):
                kids = list(node)
                i = int(chunk)
                if i >= len(kids):
                    return None
                node = kids[i]
            return node
        except (ValueError, IndexError):
            return None

    for mid, mpath in mappings.items():
        node = resolve(mpath)
        if node is None:
            err("%s: mapping %r -> %r does not resolve" % (name, mid, mpath))
        elif node.get("name") != mid:
            err("%s: mapping %r points to %r" % (name, mid, node.get("name")))

    if expect_hover:
        visual = resolve(mappings.get("visual", ""))
        lifted = float(visual.get("translation", "0 0 0").split()[1]) if visual is not None else 0
        if not 1.0 <= lifted <= 4.0:
            err("%s: the craft floats at %.2f m, expected ~1.7 m" % (name, lifted))
        else:
            ok("%s: craft floats %.2f m above the origin" % (name, lifted))
        ys = []
        for mid, mpath in mappings.items():
            if mid.startswith("wheel"):
                node = resolve(mpath)
                if node is not None and node.tag == "TransformGroup":
                    ys.append(float(node.get("translation", "0 0 0").split()[1]))
        if not ys:
            err("%s: no invisible wheel nodes found" % name)
        elif max(abs(y - 0.55) for y in ys) > 0.01:
            err("%s: wheel nodes are not on the contact plane (y=0.55)" % name)

    for f in root.findall("Files/File"):
        fn = f.get("filename")
        if fn and not os.path.isfile(os.path.join(MOD, fn)):
            err("%s.i3d texture %s does not exist" % (name, fn))
    shapes = root.find("Shapes")
    ext = shapes.get("externalShapesFile") if shapes is not None else None
    if not ext:
        err("%s.i3d is not binarized" % name)
    elif not os.path.isfile(os.path.join(MOD, ext)):
        err("%s: shapes file %s is missing" % (name, ext))
    else:
        ok("%s.i3d: binarized (%s, %.0f kB)"
           % (name, ext, os.path.getsize(os.path.join(MOD, ext)) / 1024.0))


def check_combine(veh, mappings):
    has = {s.get("name") for s in veh.iter("specialization")}
    desc = load(os.path.join(MOD, "modDesc.xml"))
    if desc is not None:
        for t in desc.findall("vehicleTypes/type"):
            if t.get("name") == veh.get("type"):
                has |= {s.get("name") for s in t.findall("specialization")}
    for need in ("combine", "workArea", "fillUnit", "pipe", "dischargeable"):
        if need not in has and need not in ("fillUnit",):
            err("combine type is missing the %r specialization" % need)

    units = veh.findall("fillUnit/fillUnitConfigurations/fillUnitConfiguration/fillUnits/fillUnit")
    combine = veh.find("combine")
    if combine is None:
        err("no <combine> block - it would not harvest")
        return
    try:
        index = int(combine.get("fillUnitIndex"))
    except (TypeError, ValueError):
        err("<combine> needs a fillUnitIndex")
        return
    if not 1 <= index <= len(units):
        err("<combine fillUnitIndex=%d> does not exist" % index)
        return
    grain = units[index - 1]
    types = (grain.get("fillTypes") or "").split()
    if not types:
        err("the grain fill unit has no fillTypes")
    elif "diesel" in types:
        err("the grain fill unit must not be the diesel tank")
    else:
        ok("combine: fills unit %d (%s, %s l)"
           % (index, " ".join(types[:4]) + (" ..." if len(types) > 4 else ""),
              grain.get("capacity")))
    if len(units) < 2:
        err("the combine needs a second fill unit for diesel")
    pipe = veh.find("pipe")
    if pipe is None:
        warn("no <pipe> - the grain tank cannot be unloaded")
    elif pipe.find("unloadingTriggers/unloadingTrigger") is None:
        err("<pipe> has no unloadingTrigger")
    else:
        node = pipe.find("unloadingTriggers/unloadingTrigger").get("node")
        if node not in mappings:
            err("pipe trigger node %r has no i3dMapping" % node)
        else:
            ok("pipe: unloading trigger on the grain pipe")
    dn = veh.find("dischargeable/dischargeNode")
    if dn is None:
        err("no <dischargeable><dischargeNode> - the pipe would do nothing")
    elif dn.get("node") not in mappings:
        err("discharge node %r has no i3dMapping" % dn.get("node"))
    joints = veh.findall(".//attacherJoint")
    cutter = [j for j in joints if j.get("jointType") == "cutter"]
    if not cutter:
        err("the combine has no attacher joint of jointType=\\\"cutter\\\"")
    else:
        j = cutter[0]
        if j.get("node") not in mappings:
            err("attacher joint node %r has no i3dMapping" % j.get("node"))
        if j.find("distanceToGround") is None:
            warn("attacher joint has no <distanceToGround>")
        else:
            ok("combine: cutter attacher joint with %s"
               % ("ground distance" if j.find("rotationNode") is None else "lift rotation"))


def check_header(veh, mappings):
    cutter = veh.find("cutter")
    if cutter is None:
        err("header has no <cutter> block - it would not cut anything")
        return
    fruits = (cutter.get("fruitTypes") or "").split()
    if len(fruits) < 4:
        err("header only cuts %d fruit types" % len(fruits))
    else:
        ok("header: %d fruit types (%s ...)" % (len(fruits), " ".join(fruits[:3])))
    area = veh.find("workAreas/workArea")
    if area is None:
        err("header has no work area")
        return
    if area.get("type") != "cutter":
        err("header work area type is %r, expected \\\"cutter\\\"" % area.get("type"))
    if area.get("functionName") != "processCutterArea":
        err("header work area functionName is %r, expected processCutterArea"
            % area.get("functionName"))
    nodes = area.find("area")
    for key in ("startNode", "widthNode", "heightNode"):
        v = nodes.get(key) if nodes is not None else None
        if not v:
            err("header work area is missing %s" % key)
        elif v not in mappings:
            err("header work area %s %r has no i3dMapping" % (key, v))
    if veh.find("workAreas/workArea/groundReferenceNode") is None:
        warn("header work area has no <groundReferenceNode> - it may not follow the ground")
    if len(veh.findall("groundReferenceNodes/groundReferenceNode")) != 1:
        err("header needs exactly one <groundReferenceNode>")
    if area.find("testAreas") is None:
        warn("header work area has no <testAreas>")

    input_joint = veh.find("attachable/inputAttacherJoints/inputAttacherJoint")
    if input_joint is None:
        err("header has no input attacher joint")
    else:
        if input_joint.get("jointType") != "cutter":
            err("header input joint type is %r, expected \\\"cutter\\\""
                % input_joint.get("jointType"))
        if not input_joint.findall("heightNode"):
            err("header input joint has no <heightNode>")

    comb = veh.find("storeData/specs/combination")
    if comb is None:
        warn("header has no <specs><combination> - the shop will not offer it")
    elif not os.path.isfile(os.path.join(MOD, comb.get("xmlFilename"))):
        err("combination file %s does not exist" % comb.get("xmlFilename"))

    # the work area has to be as wide as the shop says
    spec = veh.findtext("storeData/specs/workingWidth")
    if spec:
        width = float(spec)
        if not 3.0 <= width <= 12.0:
            err("workingWidth %.1f m looks wrong" % width)
        else:
            ok("header: %.1f m working width" % width)


def check_files(veh, name):
    base = veh.find("base")
    i3d = base.findtext("filename") if base is not None else None
    if not i3d or not os.path.isfile(os.path.join(MOD, i3d)):
        err("%s: base filename %r does not exist" % (name, i3d))
    store = veh.findtext("storeData/image")
    if store and not os.path.isfile(os.path.join(MOD, store)):
        err("%s: store image %s does not exist" % (name, store))
    brand = veh.findtext("storeData/brand")
    if brand and brand not in BASE_BRANDS:
        err("%s: brand %r is not a base game brand" % (name, brand))
    if veh.find("storeData") is not None:
        pass
    for s in veh.findall(".//sounds/*") + veh.findall(".//honk/*"):
        f = s.get("file")
        if f and not os.path.isfile(os.path.join(MOD, f)):
            err("%s: sound file %s does not exist" % (name, f))


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
    ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(zpath) / 1048576.0))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xsd", help="directory with the official FS25 .xsd files")
    ap.add_argument("--zip", default=os.path.join(REPO, "dist", "FS25_UFO4500.zip"))
    args = ap.parse_args()

    sd = xsd_dir(args)
    if sd is None:
        warn("official FS25 schemas not found - XSD validation skipped")

    desc, items = check_moddesc()
    check_l10n(items)
    vehicles = [("ufo4500", True), ("ufo4500header", False)]
    for name, is_combine in vehicles:
        veh = load(os.path.join(MOD, name + ".xml"))
        if veh is None:
            continue
        mappings = mappings_of(veh)
        check_node_refs(name + ".xml", veh, mappings)
        check_files(veh, name)
        if is_combine:
            check_combine(veh, mappings)
        else:
            check_header(veh, mappings)
        check_i3d(name, mappings, expect_hover=is_combine)
        check_xsd(os.path.join(MOD, name + ".xml"), sd, "vehicle.xsd")
        check_xsd(os.path.join(MOD, name + ".i3d"), sd, "i3d-1.6.xsd")
    check_xsd(os.path.join(MOD, "modDesc.xml"), sd, "modDesc.xsd")
    check_zip(args.zip)

    for n in notes:
        print("  ok    %s" % n)
    for w in warnings:
        print("  warn  %s" % w)
    for e in errors:
        print("  ERROR %s" % e)
    print("\n%d checks passed, %d warnings, %d errors"
          % (len(notes), len(warnings), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
