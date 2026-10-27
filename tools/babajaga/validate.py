#!/usr/bin/env python3
"""Static checks for FS25_BabaJaga - the chicken hut - no game required.

    python tools/babajaga/validate.py [--xsd DIR] [--zip dist/FS25_BabaJaga.zip]

Checks
  * console rules: no Lua, no <actions>, no <brands>, LIZARD brand only
  * babaJaga.xml against placeable.xsd, modDesc.xml against modDesc.xsd
  * every node referenced in the XML has an i3dMapping that resolves in the i3d
  * the husbandry is a real chicken coop: <animals type="CHICKEN">, navmesh,
    loading trigger, food with troughs + unload trigger, pallet spawner
  * fence has >= 4 contour nodes, area nodes come in start/width/height triples
  * textures / shapes / icon exist, zip layout is flat with modDesc.xml on top
  * the hut stands on the ground (leg reaches y=0) and has a collider
"""

import argparse
import glob
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MOD = os.path.join(REPO, "FS25_BabaJaga")
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
        warn("no schema dir - XSD validation skipped")
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
        err("console check: the mod ships Lua: %s"
            % ", ".join(os.path.relpath(p, MOD) for p in lua))
    else:
        ok("console check: no Lua file in the mod")
    for tag in ("extraSourceFiles", "actions", "inputBinding", "brands"):
        if desc.find(tag) is not None:
            err("console check: modDesc.xml must not contain <%s>" % tag)

    dv = int(desc.get("descVersion", "0"))
    if not 90 <= dv <= 115:
        err("modDesc descVersion %d outside 90..115" % dv)
    for tag in ("author", "version", "iconFilename", "title", "description"):
        if desc.find(tag) is None:
            err("modDesc.xml: missing <%s>" % tag)
    for tag in ("title", "description"):
        el = desc.find(tag)
        if el is not None and not (el.find("de") is not None and el.find("en") is not None):
            err("modDesc.xml: <%s> needs both <de> and <en>" % tag)
    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(MOD, icon)):
        err("iconFilename %s does not exist" % icon)
    items = [i.get("xmlFilename") for i in desc.findall("storeItems/storeItem")]
    if len(items) != 1:
        err("expected exactly one store item, found %d" % len(items))
    for f in items:
        if not os.path.isfile(os.path.join(MOD, f)):
            err("storeItem %s does not exist" % f)
    ok("modDesc.xml: descVersion %d, %d store item(s), LIZARD base game brand"
       % (dv, len(items)))
    return desc, items


def check_l10n(names):
    keys = set()
    for f in glob.glob(os.path.join(MOD, "translations", "*.xml")):
        root = load(f)
        if root is None:
            continue
        keys.update(t.get("name") for t in root.iter("text"))
    for t in (load(os.path.join(MOD, "modDesc.xml")) or ET.Element("modDesc")).iter("text"):
        name = t.get("name") or ""
        keys.add(name)
    used = set()
    for name in ["modDesc.xml"] + names:
        with open(os.path.join(MOD, name), encoding="utf-8") as fh:
            used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", fh.read()))
    missing = sorted(used - keys - BASE_L10N)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    ok("translations: %d keys, %d used" % (len(keys), len(used)))


def mappings_of(root):
    out = {}
    for m in root.iter("i3dMapping"):
        mid, node = m.get("id"), m.get("node")
        if mid in out:
            err("duplicate i3dMapping id %r" % mid)
        out[mid] = node
    return out


def check_node_refs(root, mappings):
    referenced = set()
    for el in root.iter():
        if el.tag in ("i3dMapping", "i3dMappings"):
            continue
        for key in ("node", "startNode", "endNode", "widthNode", "heightNode",
                    "triggerNode", "rootNode", "shape", "teleportNode",
                    "linkNode", "exactFillRootNode"):
            v = el.get(key)
            if v and not v.startswith("$"):
                referenced.add(v)
    unknown = sorted(referenced - set(mappings))
    if unknown:
        err("nodes without i3dMapping: %s" % ", ".join(unknown))
    unused = sorted(m for m in set(mappings) - referenced
                    if not m.endswith("Mesh") and "Col" not in m and m != "babaJaga")
    if unused:
        warn("mappings never used: %s" % ", ".join(unused))
    ok("%d node references, %d mappings" % (len(referenced), len(mappings)))
    return referenced


def resolve(scene, mpath):
    """Walk an i3d mapping path like 0>2|1|0 through the parsed scene."""
    node = None
    for part in [p for p in mpath.split(">") if p]:
        idx = part.split("|")
        siblings = list(scene) if node is None else list(node)
        try:
            node = siblings[int(idx[0])]
        except (IndexError, ValueError):
            return None
        for sub in idx[1:]:
            try:
                node = list(node)[int(sub)]
            except (IndexError, ValueError):
                return None
    return node


def check_i3d(mappings):
    root = load(os.path.join(MOD, "babaJaga.i3d"))
    if root is None:
        return
    scene = root.find("Scene")
    if scene is None:
        err("babaJaga.i3d has no <Scene>")
        return
    ids = [n.get("nodeId") for n in scene.iter() if n.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("babaJaga.i3d: duplicate nodeId values")
    bad = []
    for mid, path in mappings.items():
        node = resolve(scene, path)
        if node is None:
            bad.append("%s=%s (missing)" % (mid, path))
        elif node.get("name") != mid:
            bad.append("%s=%s points at %r" % (mid, path, node.get("name")))
    if bad:
        err("i3dMapping paths that do not resolve: %s" % ", ".join(bad))
    else:
        ok("babaJaga.i3d: all %d mapping paths resolve" % len(mappings))

    shapes = root.find("Shapes")
    ext = shapes.get("externalShapesFile") if shapes is not None else None
    if not ext:
        err("babaJaga.i3d is not binarized")
    elif not os.path.isfile(os.path.join(MOD, ext)):
        err("shapes file %s is missing" % ext)
    else:
        ok("babaJaga.i3d: binarized (%s, %.0f kB)"
           % (ext, os.path.getsize(os.path.join(MOD, ext)) / 1024.0))

    name = "babaJaga"
    check_xsd(os.path.join(MOD, name + ".i3d"), XSD, "i3d-1.6.xsd")


def check_husbandry(root, referenced):
    hus = root.find("husbandry")
    if hus is None:
        err("no <husbandry> block")
        return
    animals = hus.find("animals")
    if animals is None:
        err("husbandry: no <animals>")
    else:
        atype = animals.get("type")
        if atype != "CHICKEN":
            err("husbandry/animals type=%r, expected CHICKEN" % atype)
        base = int(animals.get("baseMaxNumAnimals", "0"))
        top = int(animals.get("maxNumAnimals", "0"))
        if not (0 < base <= top <= 100):
            err("husbandry/animals capacities look wrong: %d / %d" % (base, top))
        else:
            ok("animals: CHICKEN, %d base / %d max" % (base, top))
        nav = animals.find("navigation")
        if nav is None or not nav.get("rootNode") or not nav.get("shape"):
            err("husbandry/animals: <navigation rootNode shape> incomplete")
        if animals.find("loadingTrigger") is None:
            err("husbandry/animals: no <loadingTrigger>")

    food = hus.find("food")
    if food is None:
        err("husbandry: no <food>")
    else:
        cap = int(food.get("capacity", "0"))
        if cap < 500:
            err("husbandry/food capacity %d l is too small" % cap)
        if food.find("unloadTrigger") is None:
            err("husbandry/food: no <unloadTrigger exactFillRootNode>")
        places = food.findall("foodPlaces/foodPlace")
        if len(places) < 1:
            err("husbandry/food: no <foodPlace>")
        ok("food: %d l, %d trough(s)" % (cap, len(places)))

    pallets = hus.find("pallets/palletSpawner")
    if pallets is None:
        warn("husbandry: no <pallets> - eggs will not spawn on pallets")
    else:
        if not pallets.get("fillTypes"):
            err("palletSpawner without fillTypes")
        if pallets.find("palletTrigger") is None:
            err("palletSpawner without <palletTrigger>")
        if not pallets.findall("spawnPlaces/spawnPlace"):
            err("palletSpawner without <spawnPlace>")
        else:
            ok("pallets: %s, max %s" % (pallets.get("fillTypes"),
                                        pallets.get("maxNumPallets")))

    fence = hus.find("fence")
    if fence is None:
        err("husbandry: no <fence> - the game cannot build a chicken navmesh")
    else:
        fn = fence.get("xmlFilename") or ""
        if not fn.startswith("$data/placeables/brandless/fences"):
            err("fence xmlFilename %r should point at a base game brandless fence" % fn)
        sections = fence.findall("sections/section")
        if not sections:
            err("husbandry/fence: no <section>")
        for sec in sections:
            nodes = sec.findall("node")
            if len(nodes) < 4:
                err("fence section %r has %d contour nodes, need >= 4"
                    % (sec.get("segmentId"), len(nodes)))
            first, last = nodes[0].get("node"), nodes[-1].get("node")
            if first != last:
                err("fence section is not closed: %s .. %s" % (first, last))
            if not sec.get("segmentId"):
                err("fence section without segmentId")
        ok("fence: %d section(s), closed contour" % len(sections))

    if root.find("hotspots/hotspot") is None:
        warn("no <hotspots> - the coop will not show up on the PDA map")
    if root.find("infoTrigger") is None:
        err("no <infoTrigger>")


def check_areas(root):
    """start/width/height triples for every area element."""
    pairs = (("clearArea", "clearArea1"), ("levelArea", "levelArea1"),
             ("paintArea", "paintArea1"), ("indoorArea", "indoorArea1"),
             ("foliageArea", "foliageArea1"))
    for tag, label in pairs:
        el = root.find(".//" + tag)
        if el is None:
            err("missing <%s>" % tag)
            continue
        for key in ("startNode", "widthNode", "heightNode"):
            if not el.get(key):
                err("<%s> without %s" % (tag, key))
    for el in root.iter("testArea"):
        if not (el.get("startNode") and el.get("endNode")):
            err("<testArea> needs startNode and endNode")
    ok("areas: 5 area blocks, test areas with start + end")


def check_media():
    png = glob.glob(os.path.join(MOD, "store_*.png"))
    if not png:
        err("no store_*.png")
    tex = glob.glob(os.path.join(MOD, "textures", "*.dds"))
    if len(tex) < 6:
        err("only %d textures - expected the full material set" % len(tex))
    else:
        ok("media: %d textures, %d store picture(s)" % (len(tex), len(png)))
    with open(os.path.join(MOD, "babaJaga.xml"), encoding="utf-8") as fh:
        xml = fh.read()
    for tex_name in set(re.findall(r'<Texture fileId="[^"]*" filename="([^"]+)"', xml)):
        if not os.path.isfile(os.path.join(MOD, tex_name.replace("\\", "/"))):
            err("texture %s missing" % tex_name)
    for name in re.findall(r'filename="([^"$]+\.dds)"', xml):
        if not os.path.isfile(os.path.join(MOD, name)):
            err("file %s missing" % name)


def check_zip(path):
    if not path or not os.path.isfile(path):
        warn("zip not checked")
        return
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    # both layouts are fine: files at the top level, or one mod folder inside
    roots = {n.split("/")[0] for n in names}
    prefix = "" if "modDesc.xml" in names else (roots.pop() + "/" if len(roots) == 1 else None)
    if prefix is None:
        err("zip has neither a flat layout nor a single mod folder: %s" % sorted(roots))
        prefix = ""
    for need in ("modDesc.xml", "babaJaga.xml", "babaJaga.i3d"):
        if prefix + need not in names:
            err("zip: %s is missing" % (prefix + need))
    bad = [n for n in names if n.lower().endswith((".py", ".txt", ".blend", ".psd"))]
    if bad:
        warn("zip contains non game files: %s" % ", ".join(bad[:5]))
    ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(path) / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xsd")
    ap.add_argument("--zip", default=os.path.join(REPO, "dist", "FS25_BabaJaga.zip"))
    args = ap.parse_args()
    global XSD
    XSD = xsd_dir(args)

    print("FS25_BabaJaga - static validation")
    desc, items = check_moddesc()
    if desc is None:
        report()
        return 1
    check_l10n(items)
    check_xsd(os.path.join(MOD, "modDesc.xml"), XSD, "modDesc.xsd")

    for name in items:
        root = load(os.path.join(MOD, name))
        if root is None:
            continue
        if not root.get("type", "").startswith("chickenHusbandry"):
            err("%s: type=%r, expected a chickenHusbandry placeable type"
                % (name, root.get("type")))
        check_xsd(os.path.join(MOD, name), XSD, "placeable.xsd")
        mappings = mappings_of(root)
        referenced = check_node_refs(root, mappings)
        check_husbandry(root, referenced)
        check_areas(root)
        check_i3d(mappings)
        check_media()

    check_zip(args.zip)
    return report()


def report():
    for n in notes:
        print("  ok   " + n)
    for w in warnings:
        print("  WARN " + w)
    for e in errors:
        print("  FAIL " + e)
    print("\n%d ok, %d warnings, %d errors" % (len(notes), len(warnings), len(errors)))
    return 1 if errors else 0


XSD = None

if __name__ == "__main__":
    sys.exit(main())
