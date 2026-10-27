#!/usr/bin/env python3
"""Static checks for the venue mods (FS25_Disco, FS25_Autokino).

    python tools/venue/validate.py --mod disco [--zip dist/FS25_Disco.zip]

Checks
  * modDesc: version/descVersion, de+en texts, icon, store items, source files,
    placeable type registration, action keys with l10n and bindings
  * Lua: syntax (via lupa if installed), registered event listeners exist,
    action callbacks exist, sound file references exist
  * placeable XML: i3dMappings resolve into the binarized i3d, all referenced
    nodes have a mapping, areas come as start/width/height triples
  * textures and sounds referenced by the i3d/XML exist and are not empty
  * XSD validation when FS25_MOD_SCHEMA_DIR is set
  * zip layout (flat, modDesc.xml on top)
"""

import argparse
import os
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODS = {
    "disco": dict(folder="FS25_Disco", xml="disco.xml", i3d="disco.i3d",
                  type="disco", lua="scripts/Disco.lua", sounds="sounds/discoSounds.xml",
                  icon="icon_disco.dds"),
    "distillery": dict(folder="FS25_Distillery", xml="distillery.xml",
                       i3d="distillery.i3d", type="distillery",
                       lua="scripts/Distillery.lua",
                       sounds="sounds/distillerySounds.xml",
                       icon="icon_distillery.dds"),
    "autokino": dict(folder="FS25_Autokino", xml="autokino.xml", i3d="autokino.i3d",
                     type="autokino", lua="scripts/Autokino.lua",
                     sounds="sounds/autokinoSounds.xml", icon="icon_autokino.dds"),
}

errors, warnings, notes = [], [], []


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
    for cand in (args.xsd, os.environ.get("FS25_MOD_SCHEMA_DIR")):
        if cand and os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "modDesc.xsd")):
            return cand
    return None


def check_xsd(path, schema_dir, xsd_name):
    if schema_dir is None:
        warn("no schema dir - %s not validated" % xsd_name)
        return
    try:
        from lxml import etree
    except ImportError:
        warn("lxml not installed - %s not validated" % xsd_name)
        return
    schema = etree.XMLSchema(etree.parse(os.path.join(schema_dir, xsd_name)))
    tree = etree.parse(path)
    if schema.validate(tree):
        ok("XSD %-12s OK  (%s)" % (xsd_name, os.path.basename(path)))
    else:
        for e in list(schema.error_log)[:8]:
            err("%s:%d against %s: %s" % (os.path.basename(path), e.line, xsd_name, e.message))


# ---------------------------------------------------------------------------
def check_moddesc(m, moddir):
    path = os.path.join(moddir, "modDesc.xml")
    desc = load(path)
    if desc is None:
        return None
    dv = int(desc.get("descVersion", "0"))
    if not 90 <= dv <= 115:
        err("modDesc descVersion %d outside 90..115" % dv)
    for tag in ("author", "version", "iconFilename", "title", "description",
                "multiplayer"):
        if desc.find(tag) is None:
            err("modDesc.xml: missing <%s>" % tag)
    for tag in ("title", "description"):
        el = desc.find(tag)
        if el is not None and not (el.find("de") is not None and el.find("en") is not None):
            err("modDesc.xml: <%s> needs both <de> and <en>" % tag)

    icon = desc.findtext("iconFilename")
    if icon and not os.path.isfile(os.path.join(moddir, icon)):
        err("iconFilename %s does not exist" % icon)

    sources = [s.get("filename") for s in desc.findall("extraSourceFiles/sourceFile")]
    if m["lua"] not in sources:
        err("modDesc.xml: %s is not in <extraSourceFiles>" % m["lua"])
    for s in sources:
        if not os.path.isfile(os.path.join(moddir, s.replace("$moddir$/", ""))):
            err("sourceFile %s does not exist" % s)

    ptypes = desc.findall("placeableTypes/type")
    if len(ptypes) != 1:
        err("expected exactly one <placeableTypes><type>, found %d" % len(ptypes))
    else:
        t = ptypes[0]
        for attr in ("name", "className", "filename"):
            if not t.get(attr):
                err("placeableTypes/type: missing %s" % attr)
        if t.get("name") != m["type"]:
            err("placeableTypes/type name=%r, expected %r" % (t.get("name"), m["type"]))
        fn = (t.get("filename") or "").replace("$moddir$/", "")
        if fn and not os.path.isfile(os.path.join(moddir, fn)):
            err("placeableTypes/type filename %s does not exist" % fn)
        if t.get("parent") is None:
            warn("placeableTypes/type has no parent; base specializations may be missing")
        ok("placeableTypes: %s (%s, parent=%s)"
           % (t.get("name"), t.get("className"), t.get("parent")))

    actions = {a.get("name") for a in desc.findall("actions/action")}
    if not actions:
        err("modDesc.xml: no <actions>")
    keys = {t.get("name") for t in desc.iter("text")}
    for a in sorted(actions):
        if "input_" + a not in keys:
            err("action %s has no l10n text input_%s" % (a, a))
    bound = {b.get("action") for b in desc.findall("inputBinding/actionBinding")}
    for b in sorted(bound - actions):
        err("inputBinding for unknown action %r" % b)
    for a in sorted(actions - bound):
        warn("action %s has no default key binding" % a)
    devices = {x.get("device") for x in desc.iter("binding")}
    for dev in ("KB", "GAMEPAD"):
        if dev not in devices:
            warn("no %s binding" % dev)
    ok("actions: %d (%d bindings, devices %s)"
       % (len(actions), len(desc.findall("inputBinding/actionBinding/binding")),
          "/".join(sorted(d for d in devices if d))))

    items = [i.get("xmlFilename") for i in desc.findall("storeItems/storeItem")]
    if len(items) != 1:
        err("expected exactly one store item, found %d" % len(items))
    for f in items:
        if not os.path.isfile(os.path.join(moddir, f)):
            err("storeItem %s does not exist" % f)
    return desc


def check_l10n(m, moddir, desc):
    keys = set()
    for t in desc.iter("text"):
        name = t.get("name") or ""
        keys.add(name)
    used = set()
    for name in [m["xml"], "modDesc.xml", m["sounds"], m["lua"]]:
        path = os.path.join(moddir, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        used |= set(re.findall(r"\$l10n_([A-Za-z0-9_]+)", text))
        used |= set(re.findall(r'"(l10n_[A-Za-z0-9_]+)"', text))
    missing = sorted(used - keys)
    if missing:
        err("missing translations: %s" % ", ".join(missing))
    ok("translations: %d keys, %d used" % (len(keys), len(used)))


def check_lua(m, moddir):
    path = os.path.join(moddir, m["lua"])
    if not os.path.isfile(path):
        err("%s is missing" % m["lua"])
        return
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    try:
        import lupa
    except ImportError:
        warn("lupa not installed - Lua syntax not checked")
    else:
        try:
            lupa.LuaRuntime().compile(src)
            ok("Lua: %s compiles (%d lines)" % (os.path.basename(path),
                                                src.count("\n") + 1))
        except Exception as e:  # noqa: BLE001 - lupa raises its own type
            err("Lua syntax error in %s: %s" % (m["lua"], e))
    # every event listener must have a function of that name
    for name in re.findall(r'registerEventListener\([^,]+,\s*"(\w+)"', src):
        if not re.search(r"function\s+\w+[:.]%s\s*\(" % re.escape(name), src):
            err("Lua: listener %r registered but no function defined" % name)
    # every input action in the Lua must exist in modDesc
    desc_path = os.path.join(moddir, "modDesc.xml")
    if os.path.isfile(desc_path):
        with open(desc_path, encoding="utf-8") as fh:
            actions = set(re.findall(r'<action name="([^"]+)"', fh.read()))
    else:
        actions = set()
    for name in set(re.findall(r'action\s*=\s*"(\w+)"', src)):
        if actions and name not in actions:
            err("Lua uses action %r that modDesc does not declare" % name)
    for cb in set(re.findall(r'callback\s*=\s*"(\w+)"', src)):
        if not re.search(r"function\s+\w+[:.]%s\s*\(" % re.escape(cb), src):
            err("Lua: input callback %r has no function" % cb)
    ok("Lua: %d listeners, %d action callbacks"
       % (len(set(re.findall(r'registerEventListener\([^,]+,\s*"(\w+)"', src))),
          len(set(re.findall(r'callback\s*=\s*"(\w+)"', src)))))


def check_sounds(m, moddir):
    path = os.path.join(moddir, m["sounds"])
    if not os.path.isfile(path):
        err("%s is missing" % m["sounds"])
        return
    root = load(path)
    if root is None:
        return
    files = [el.get("file") for el in root.iter() if el.get("file")]
    if not files:
        err("%s: no <... file=...> samples" % m["sounds"])
    total = 0.0
    for f in files:
        full = os.path.join(moddir, f)
        if not os.path.isfile(full):
            err("sound file %s is missing" % f)
            continue
        total += os.path.getsize(full)
        try:
            import soundfile as sf
            info = sf.info(full)
            if info.duration < 4.0:
                err("%s is only %.1f s long" % (f, info.duration))
            if info.format != "OGG":
                err("%s is %s, FS25 needs OGG Vorbis" % (f, info.format))
        except ImportError:
            if os.path.getsize(full) < 30000:
                err("%s is suspiciously small" % f)
        except Exception as e:  # noqa: BLE001
            err("%s cannot be read as audio: %s" % (f, e))
    ok("sounds: %d sample(s), %.1f MB" % (len(files), total / 1e6))


def mappings_of(root):
    out = {}
    for mnode in root.iter("i3dMapping"):
        mid, node = mnode.get("id"), mnode.get("node")
        if mid in out:
            err("duplicate i3dMapping id %r" % mid)
        out[mid] = node
    return out


def resolve(scene, mpath):
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


NODE_ATTRS = ("node", "startNode", "endNode", "widthNode", "heightNode",
              "triggerNode", "rootNode", "shape", "teleportNode", "linkNode",
              "exactFillRootNode", "spawnNode", "parkingNode")


def check_placeable(m, moddir):
    path = os.path.join(moddir, m["xml"])
    root = load(path)
    if root is None:
        return
    if root.tag != "placeable":
        err("%s: root element is <%s>, expected <placeable>" % (m["xml"], root.tag))
    if root.get("type") != m["type"]:
        err("%s: type=%r, expected %r" % (m["xml"], root.get("type"), m["type"]))
    base = root.find("base")
    if base is None or not base.findtext("filename"):
        err("%s: <base><filename> missing" % m["xml"])
    elif not os.path.isfile(os.path.join(moddir, base.findtext("filename"))):
        err("%s: <base><filename> %s missing" % (m["xml"], base.findtext("filename")))
    if root.find("storeData") is None:
        err("%s: <storeData> missing" % m["xml"])

    mappings = mappings_of(root)
    referenced = set()
    for el in root.iter():
        if el.tag in ("i3dMapping", "i3dMappings"):
            continue
        for key in NODE_ATTRS:
            v = el.get(key)
            if v and not v.startswith("$"):
                referenced.add(v)
    unknown = sorted(referenced - set(mappings))
    if unknown:
        err("nodes without i3dMapping: %s" % ", ".join(unknown))
    ok("%d node references, %d mappings" % (len(referenced), len(mappings)))

    # area triples
    for tag in ("clearArea", "levelArea", "paintArea", "indoorArea", "foliageArea"):
        for el in root.iter(tag):
            for key in ("startNode", "widthNode", "heightNode"):
                if not el.get(key):
                    warn("<%s> without %s" % (tag, key))
    for el in root.iter("testArea"):
        if not (el.get("startNode") and el.get("endNode")):
            err("<testArea> needs startNode and endNode")

    i3d_path = os.path.join(moddir, m["i3d"])
    i3d = load(i3d_path)
    if i3d is None:
        return
    scene = i3d.find("Scene")
    if scene is None:
        err("%s has no <Scene>" % m["i3d"])
        return
    ids = [n.get("nodeId") for n in scene.iter() if n.get("nodeId")]
    if len(ids) != len(set(ids)):
        err("%s: duplicate nodeId values" % m["i3d"])
    bad = []
    for mid, p in mappings.items():
        node = resolve(scene, p)
        if node is None:
            bad.append("%s=%s (missing)" % (mid, p))
        elif node.get("name") != mid:
            bad.append("%s=%s points at %r" % (mid, p, node.get("name")))
    if bad:
        err("mapping paths that do not resolve: %s" % ", ".join(bad[:6]))
    else:
        ok("%s: all %d mapping paths resolve" % (m["i3d"], len(mappings)))
    shapes = i3d.find("Shapes")
    ext = shapes.get("externalShapesFile") if shapes is not None else None
    if not ext:
        err("%s is not binarized" % m["i3d"])

    elif not os.path.isfile(os.path.join(moddir, ext)):
        err("shapes file %s is missing" % ext)
    else:
        ok("%s: binarized (%s, %.0f kB)"
           % (m["i3d"], ext, os.path.getsize(os.path.join(moddir, ext)) / 1024.0))
    for f in i3d.iter("File"):
        fn = f.get("filename")
        if fn and not os.path.isfile(os.path.join(moddir, fn)):
            err("texture %s missing" % fn)


def check_media(m, moddir):
    tex = [f for f in os.listdir(os.path.join(moddir, "textures"))
           if f.endswith(".dds")] if os.path.isdir(os.path.join(moddir, "textures")) else []
    if len(tex) < 6:
        err("only %d textures - expected the full material set" % len(tex))
    store = [f for f in os.listdir(moddir) if f.startswith("store_")]
    if not store:
        err("no store_*.png")
    ok("media: %d textures, %d store picture(s)" % (len(tex), len(store)))
    dds = os.path.join(moddir, m["icon"])
    if os.path.isfile(dds) and os.path.getsize(dds) < 1000:
        err("icon %s is too small" % m["icon"])


def check_zip(path, m):
    if not path or not os.path.isfile(path):
        warn("zip not checked")
        return
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    if "modDesc.xml" in names:
        prefix = ""
    else:
        roots = {n.split("/")[0] for n in names}
        prefix = (roots.pop() + "/") if len(roots) == 1 else None
    if prefix is None:
        err("zip has neither a flat layout nor a single mod folder")
        prefix = ""
    for need in ("modDesc.xml", m["xml"], m["i3d"], m["lua"]):
        if prefix + need not in names:
            err("zip: %s is missing" % (prefix + need))
    bad = [n for n in names if n.lower().endswith((".py", ".blend", ".psd"))]
    if bad:
        warn("zip contains non game files: %s" % ", ".join(bad[:5]))
    ok("zip: %d files, %.1f MB" % (len(names), os.path.getsize(path) / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", required=True, choices=sorted(MODS))
    ap.add_argument("--xsd")
    ap.add_argument("--zip")
    args = ap.parse_args()
    m = MODS[args.mod]
    moddir = os.path.join(REPO, m["folder"])
    if not os.path.isdir(moddir):
        print("FAIL mod folder %s missing" % moddir)
        return 1
    print("%s - static validation" % m["folder"])

    schema = xsd_dir(args)
    desc = check_moddesc(m, moddir)
    if desc is None:
        return report()
    check_l10n(m, moddir, desc)
    check_lua(m, moddir)
    check_sounds(m, moddir)
    check_placeable(m, moddir)
    check_media(m, moddir)
    check_xsd(os.path.join(moddir, "modDesc.xml"), schema, "modDesc.xsd")
    check_xsd(os.path.join(moddir, m["xml"]), schema, "placeable.xsd")
    check_xsd(os.path.join(moddir, m["i3d"]), schema, "i3d-1.6.xsd")
    check_zip(args.zip or os.path.join(REPO, "dist", m["folder"] + ".zip"), m)
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


if __name__ == "__main__":
    sys.exit(main())
