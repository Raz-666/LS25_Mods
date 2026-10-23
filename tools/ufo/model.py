# SPDX-License-Identifier: GPL-3.0-or-later
"""Procedural model of the FS25 UFO 2000.

Builds the whole `<Scene>` of ``ufo.i3d`` (body, glass dome, alien pilot, rim
lights, landing gear, tractor beam) plus the collision compound and the nodes
the vehicle XML refers to (cameras, sound, enter/exit points, animation pivots).

The scene is written with inline `<IndexedTriangleSet>` geometry which
``tools/i3d/binarize_i3d.py`` turns into the FS25 ``.i3d.shapes`` file.
"""

import math

from meshlib import (Mesh, box, cylinder, disc, lathe, open_cone, place,
                     sphere, torus, TAU)

MATERIALS = [
    # name, textures (diffuse, gloss/specular), flags
    {"name": "collision", "diffuse": None, "gloss": None, "color": "0.6 0.1 0.6 1", "specular": "0.1 0.1 0.1"},
    {"name": "hullPaint", "diffuse": "hullPaint_diffuse.dds", "gloss": "hullPaint_specular.dds"},
    {"name": "hullMetal", "diffuse": "hullMetal_diffuse.dds", "gloss": "hullMetal_specular.dds"},
    {"name": "cockpit", "diffuse": "cockpit_diffuse.dds", "gloss": "cockpit_specular.dds"},
    {"name": "glass", "diffuse": "glass_diffuse.dds", "gloss": "glass_specular.dds", "alpha": True},
    {"name": "lensGreen", "diffuse": "lensGreen_diffuse.dds", "gloss": None},
    {"name": "lensRed", "diffuse": "lensRed_diffuse.dds", "gloss": None},
    {"name": "lensWhite", "diffuse": "lensWhite_diffuse.dds", "gloss": None},
    {"name": "alienSkin", "diffuse": "alienSkin_diffuse.dds", "gloss": "alienSkin_specular.dds"},
    {"name": "eyeBlack", "diffuse": "eyeBlack_diffuse.dds", "gloss": None},
    {"name": "beam", "diffuse": "beam_diffuse.dds", "gloss": None, "alpha": True},
]
MAT_INDEX = {m["name"]: i + 1 for i, m in enumerate(MATERIALS)}

HULL_R = 2.35            # outer radius of the saucer
DOME_R = 0.98
RIM_Y = 0.93
HULL_Y = 0.30            # belly centre height


LEG_SPLAY = "16"          # degrees the legs are splayed out at rest


def _fmt(values):
    out = []
    for v in values:
        s = ("%.6g" % v)
        out.append("0" if s == "-0" else s)
    return " ".join(out)


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def hull_mesh():
    m = Mesh()
    # underside: dark metal, from the centre out to the rim
    m.add("hullMetal", *lathe([
        (0.06, HULL_Y), (0.45, 0.32), (0.95, 0.26), (1.45, 0.30),
        (1.90, 0.46), (2.10, 0.60),
    ], 56, close_ends=False))
    # rim lip: painted band that catches the light
    m.add("hullPaint", *lathe([
        (2.10, 0.60), (2.27, 0.67), (2.35, 0.79), (2.26, 0.93),
    ], 56, close_ends=False))
    # upper shell, gently domed towards the cockpit
    m.add("hullPaint", *lathe([
        (2.26, 0.93), (2.00, 1.02), (1.62, 1.10), (1.22, 1.155), (DOME_R, 1.17),
    ], 56, close_ends=False))
    # cockpit floor (visible through the glass dome)
    m.add("cockpit", *lathe([
        (DOME_R, 1.17), (0.66, 1.12), (0.34, 1.06), (0.06, 1.02),
    ], 40, close_ends=True))

    # accent rings
    m.add("hullMetal", *torus(2.24, 0.06, 0.935, 56, 10))
    m.add("hullMetal", *torus(1.02, 0.055, 1.175, 40, 10))
    m.add("hullMetal", *torus(0.62, 0.045, 1.075, 32, 8))

    # rim light pods: 12 around the saucer
    for i in range(12):
        a = TAU * i / 12
        geom = sphere((0, 0, 0), 0.10, 14, 8, scale=(1.0, 0.55, 1.7))
        m.add("lensGreen", *place(geom, translation=(2.245 * math.cos(a), 0.86, 2.245 * math.sin(a)),
                                  rot=(0, -math.degrees(a), 0)))
    # front head lamp
    m.add("lensWhite", *place(sphere((0, 0, 0), 0.12, 16, 8, scale=(1.0, 0.8, 0.5)),
                              translation=(0, 0.72, 2.315)))
    m.add("hullMetal", *place(torus(0.14, 0.026, 0, 20, 8), rot=(90, 0, 0),
                              translation=(0, 0.72, 2.28)))

    # tractor beam emitter under the belly
    m.add("hullMetal", *place(torus(0.50, 0.05, 0, 36, 8), translation=(0, 0.30, 0)))
    m.add("lensGreen", *place(disc(0.47, 0.245, 32, up=False)))

    # antenna mast
    m.add("hullMetal", *cylinder(0.018, 1.92, 2.22, 10, caps=True))
    return m


def antenna_beacon_mesh():
    m = Mesh()
    m.add("lensRed", *sphere((0, 0, 0), 0.082, 16, 10, scale=(1, 1.05, 1)))
    return m


def dome_mesh():
    m = Mesh()
    m.add("glass", *lathe([
        (DOME_R, 1.175), (0.97, 1.30), (0.90, 1.48), (0.76, 1.65),
        (0.53, 1.79), (0.27, 1.88), (0.06, 1.915),
    ], 48, close_ends=True))
    return m


def leg_mesh_local():
    """One landing leg in local space (+Y up, pivot at the hull attachment)."""
    m = Mesh()
    m.add("hullMetal", *cylinder(0.062, -0.36, 0.05, 12, caps=True, top_radius=0.10))
    m.add("hullMetal", *place(torus(0.125, 0.032, 0, 20, 8), translation=(0, -0.36, 0)))
    m.add("hullMetal", *place(disc(0.155, -0.385, 20, up=False)))
    m.add("lensGreen", *place(sphere((0, 0, 0), 0.032, 10, 6), translation=(0, 0.0, 0.085)))
    return m


LEG_ANGLES = (30, 150, 270)      # degrees around the hull, 270 = rear


def leg_nodes(parent):
    """Three separately animatable legs.

    Each node sits on the hull, rotated so its local +X points outwards and its
    local Z is tangential; rotating the node around Z splays / retracts the leg.
    The first rotation value (splay) is also baked into the node transform.
    """
    nodes = []
    for i, deg in enumerate(LEG_ANGLES):
        a = math.radians(deg)
        pos = (1.72 * math.cos(a), 0.375, 1.72 * math.sin(a))
        node = Node("TransformGroup", "leg%d" % i, translation="%s" % _fmt(pos),
                    rotation="0 %s %s" % (_fmt([-deg]), LEG_SPLAY))
        m = Mesh()
        src = leg_mesh_local()
        for mat in src.order:
            v, n, uv, t = src.parts[mat]
            m.add(mat, v, n, uv, t)
        node.add(Node("Shape", "leg%dMesh" % i, m))
        parent.add(node)
        nodes.append(node)
    return nodes


def alien_mesh():
    """Cute little pilot; local origin is the seat."""
    m = Mesh()
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.20, 20, 12, scale=(1.0, 1.15, 0.85)),
                              translation=(0, 0.22, 0)))
    m.add("alienSkin", *place(sphere((0, 0, 0), 0.19, 20, 12, scale=(1.0, 1.05, 0.95)),
                              translation=(0, 0.53, 0.01)))
    # big shiny eyes
    for sx in (-1, 1):
        m.add("eyeBlack", *place(sphere((0, 0, 0), 0.065, 14, 10, scale=(1.0, 1.3, 0.55)),
                                 translation=(0.075 * sx, 0.55, 0.155)))
        m.add("lensWhite", *place(sphere((0, 0, 0), 0.016, 8, 6),
                                  translation=(0.093 * sx, 0.585, 0.205)))
    # tiny smile
    m.add("eyeBlack", *place(sphere((0, 0, 0), 0.035, 10, 6, scale=(1.7, 0.35, 0.5)),
                             translation=(0, 0.455, 0.175)))
    # antennae
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.009, 0.0, 0.12, 8, caps=True),
                                  rot=(0, 0, -18 * sx), translation=(0.055 * sx, 0.66, 0)))
        m.add("lensGreen", *place(sphere((0, 0, 0), 0.024, 10, 6),
                                  translation=(0.092 * sx, 0.775, 0)))
    # arms
    for sx in (-1, 1):
        m.add("alienSkin", *place(cylinder(0.045, 0, 0.20, 10, caps=True, top_radius=0.032),
                                  rot=(70, 0, 30 * sx), translation=(0.17 * sx, 0.30, 0.02)))
        m.add("alienSkin", *place(sphere((0, 0, 0), 0.045, 10, 6),
                                  translation=(0.245 * sx, 0.22, 0.20)))
    return m


def cockpit_console_mesh():
    m = Mesh()
    for i in range(3):
        a = TAU * i / 3 + math.pi / 2
        m.add("hullMetal", *place(box((0, 0, 0), (0.26, 0.16, 0.06)),
                                  rot=(0, -math.degrees(a), 0),
                                  translation=(0.64 * math.cos(a), 1.13, 0.64 * math.sin(a))))
        m.add("lensGreen", *place(box((0, 0, 0), (0.18, 0.09, 0.02)),
                                  rot=(0, -math.degrees(a), 0),
                                  translation=(0.64 * math.cos(a), 1.17, 0.62 * math.sin(a))))
    return m


def beam_mesh():
    m = Mesh()
    m.add("beam", *open_cone(0.02, 0.40, -3.20, 1.95, 40))
    return m


def collision_meshes():
    """(name, geometry) pairs for the compound collision; the first one is the
    main rigid body shape (node 0>, "ufo_main_component1")."""
    return [
        ("ufo_main_component1", cylinder(2.02, 0.0, 0.80, 16, caps=True)),
        ("collisionDome", cylinder(0.92, 0.80, 1.90, 12, caps=True)),
    ]


# --------------------------------------------------------------------------
# i3d scene tree
# --------------------------------------------------------------------------
class Node:
    def __init__(self, kind, name, mesh=None, materials=None, **attrs):
        self.kind = kind
        self.name = name
        self.mesh = mesh
        self.materials = materials or []
        self.attrs = attrs
        self.children = []

    def add(self, child):
        self.children.append(child)
        return child


def build_scene():
    """Return (root Node, mapping list)."""
    main_mesh = Mesh()
    main_mesh.add("collision", *collision_meshes()[0][1])
    body = Node("Shape", "ufo_main_component1", mesh=main_mesh, materials=["collision"], **{
        "dynamic": "true", "compound": "true", "collisionFilterGroup": "0x10004",
        "collisionFilterMask": "0xfe3ffb83", "clipDistance": "300",
        "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
    })

    visual = body.add(Node("TransformGroup", "visual"))
    visual.add(Node("Shape", "hullMesh", hull_mesh()))
    visual.add(Node("Shape", "domeGlass", dome_mesh(),
                    materials=["glass"], castsShadows="false", receiveShadows="true"))
    leg_nodes(visual)

    alien = visual.add(Node("TransformGroup", "alienNode", translation="0 1.02 0", scale="1.12 1.12 1.12"))
    alien.add(Node("Shape", "alienMesh", alien_mesh()))
    visual.add(Node("Shape", "consoleMesh", cockpit_console_mesh()))

    beacon = visual.add(Node("TransformGroup", "beaconNode", translation="0 2.26 0"))
    beacon.add(Node("Shape", "beaconMesh", antenna_beacon_mesh(), materials=["lensRed"]))

    beam = visual.add(Node("TransformGroup", "beamNode", translation="0 0.25 0", visibility="false"))
    beam.add(Node("Shape", "beamMesh", beam_mesh(), materials=["beam"],
                  castsShadows="false", receiveShadows="false"))

    collisions = body.add(Node("TransformGroup", "collisions"))
    for name, geom in collision_meshes()[1:]:
        m = Mesh()
        m.add("collision", *geom)
        collisions.add(Node("Shape", name, m, materials=["collision"], **{
            "compoundChild": "true", "collisionFilterGroup": "0x10004",
            "collisionFilterMask": "0xfe3ffb83", "density": "0.001",
            "castsShadows": "false", "receiveShadows": "false", "nonRenderable": "true",
        }))

    lights = body.add(Node("TransformGroup", "lights"))
    lights.add(Node("Light", "headLightLeft", translation="0.62 0.66 1.95", rotation="-8 180 0",
                    type="spot", color="0.85 1.0 0.92", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="45", coneAngle="72", dropOff="3"))
    lights.add(Node("Light", "headLightRight", translation="-0.62 0.66 1.95", rotation="-8 180 0",
                    type="spot", color="0.85 1.0 0.92", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="45", coneAngle="72", dropOff="3"))
    lights.add(Node("Light", "workLight", translation="0 0.30 0", rotation="-90 0 0",
                    type="spot", color="0.65 1.0 0.85", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="60", coneAngle="88", dropOff="2"))
    lights.add(Node("Light", "beamLight", translation="0 0.22 0", rotation="-90 0 0",
                    type="spot", color="0.55 1.0 0.95", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="42", coneAngle="52", dropOff="1.5"))
    lights.add(Node("Light", "beaconLight", translation="0 2.30 0",
                    type="point", color="1 0.18 0.12", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="26"))
    lights.add(Node("Light", "tailLight", translation="0 0.72 -2.20",
                    type="point", color="1 0.25 0.15", emitDiffuse="true", emitSpecular="true",
                    castShadowMap="false", range="8"))

    fill = Mesh()
    fill.add("collision", *cylinder(0.16, -0.05, 0.05, 10, caps=True))
    body.add(Node("Shape", "exactFillRootNode", mesh=fill, materials=["collision"], **{
        "kinematic": "true", "compound": "true", "collisionFilterGroup": "0x40000000",
        "collisionFilterMask": "0x20000000", "castsShadows": "false",
        "receiveShadows": "false", "nonRenderable": "true",
    }))

    body.add(Node("TransformGroup", "enterReferenceNode", translation="0 1.0 2.45"))
    body.add(Node("TransformGroup", "exitPoint", translation="2.7 0.05 0.0"))
    body.add(Node("TransformGroup", "soundMotor", translation="0 1.0 0.0"))

    cam_target = body.add(Node("TransformGroup", "outdoorCameraTarget", translation="0 1.15 0"))
    cam_target.add(Node("Camera", "outdoorCamera", translation="0 0 -9", rotation="0 180 0",
                        fov="45", nearClip="0.05", farClip="5000"))
    inside_target = body.add(Node("TransformGroup", "indoorCameraTarget", translation="0 1.42 0.12"))
    inside_target.add(Node("Camera", "indoorCamera", rotation="0 180 0", fov="60",
                           nearClip="0.03", farClip="5000"))

    return body


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------
class Writer:
    def __init__(self, materials):
        self.materials = materials
        self.files = []
        self.shape_xml = []
        self.node_id = 0
        self.shape_id = 0
        self.mappings = []
        self.stats = {"tris": 0, "verts": 0, "shapes": 0}

    # -- files / materials -------------------------------------------------
    def file_id(self, rel):
        if rel not in self.files:
            self.files.append(rel)
        return self.files.index(rel) + 1

    def material_id(self, name):
        return MAT_INDEX[name]

    # -- geometry ----------------------------------------------------------
    def write_shape(self, node):
        self.shape_id += 1
        sid = self.shape_id
        mesh = node.mesh
        mats = node.materials or [m for m in mesh.order if m != "collision"]
        if not mats:
            mats = list(mesh.order)

        verts, normals, uvs, tris = [], [], [], []
        subsets = []
        for mat in mats:
            if mat not in mesh.parts:
                continue
            pv, pn, puv, pt = mesh.parts[mat]
            first_vertex = len(verts)
            first_index = 3 * len(tris)
            verts.extend(pv)
            normals.extend(pn)
            uvs.extend(puv)
            tris.extend(pt)
            subsets.append((first_vertex, len(pv), first_index, 3 * len(pt), mat))

        self.stats["tris"] += len(tris)
        self.stats["verts"] += len(verts)
        self.stats["shapes"] += 1

        attr = [("name", node.name), ("shapeId", str(sid))]
        for k in ("dynamic", "compound", "compoundChild", "collisionFilterGroup",
                  "collisionFilterMask", "density", "clipDistance", "castsShadows",
                  "receiveShadows", "nonRenderable"):
            if k in node.attrs:
                attr.append((k, node.attrs[k]))
        mid_list = [self.material_id(m) for m in mats if m in mesh.parts]
        attr.append(("materialIds", " ".join(str(m) for m in mid_list)))

        lines = ["      <IndexedTriangleSet %s>" % _attrs(attr)]
        lines.append('        <Vertices normal="true" uv0="true" count="%d">' % len(verts))
        for v, n, uv in zip(verts, normals, uvs):
            lines.append('          <v p="%s" n="%s" t0="%s"/>' % (_fmt(v), _fmt(n), _fmt(uv)))
        lines.append("        </Vertices>")
        lines.append('        <Triangles count="%d">' % len(tris))
        for t in tris:
            lines.append('          <t vi="%d %d %d"/>' % t)
        lines.append("        </Triangles>")
        lines.append("        <Subsets>")
        for fv, nv, fi, ni, mat in subsets:
            lines.append('          <Subset firstVertex="%d" numVertices="%d" firstIndex="%d" '
                         'numIndices="%d" materialSlotName="%s"/>' % (fv, nv, fi, ni, mat))
        lines.append("        </Subsets>")
        lines.append("      </IndexedTriangleSet>")
        self.shape_xml.extend(lines)
        return sid

    # -- scene -------------------------------------------------------------
    def write_node(self, node, depth, path):
        self.node_id += 1
        nid = self.node_id
        self.mappings.append((node.name, path))
        indent = "    " * depth
        attrs = [("name", node.name)]
        if node.kind == "Shape":
            sid = self.write_shape(node)
            attrs.append(("shapeId", str(sid)))
        for k, v in node.attrs.items():
            attrs.append((k, v))
        attrs.append(("nodeId", str(nid)))
        if not node.children:
            return ["%s<%s %s/>" % (indent, node.kind, _attrs(attrs))]
        lines = ["%s<%s %s>" % (indent, node.kind, _attrs(attrs))]
        for i, child in enumerate(node.children):
            child_path = ("0>%d" % i) if path == "0>" else ("%s|%d" % (path, i))
            lines.extend(self.write_node(child, depth + 1, child_path))
        lines.append("%s</%s>" % (indent, node.kind))
        return lines


def _attrs(pairs):
    return " ".join('%s="%s"' % (k, v) for k, v in pairs)


def write_i3d(root, out_path, materials=MATERIALS):
    w = Writer(materials)
    scene_lines = w.write_node(root, 3, "0>")
    # materials first: they register the texture files
    mat_lines = []
    for mat in materials:
        attrs = [("name", mat["name"]), ("materialId", str(MAT_INDEX[mat["name"]]))]
        if mat.get("alpha"):
            attrs.append(("alphaBlending", "true"))
        children = []
        if mat.get("diffuse") is None:
            attrs.append(("diffuseColor", mat.get("color", "0.5 0.5 0.5 1")))
            attrs.append(("specularColor", mat.get("specular", "0.2 0.2 0.2")))
        else:
            children.append(('      <Texture fileId="%d"/>' % w.file_id(mat["diffuse"])))
        if mat.get("gloss"):
            children.append(('      <Glossmap fileId="%d"/>' % w.file_id(mat["gloss"])))
        if children:
            mat_lines.append("    <Material %s>" % _attrs(attrs))
            mat_lines.extend(children)
            mat_lines.append("    </Material>")
        else:
            mat_lines.append("    <Material %s/>" % _attrs(attrs))

    lines = ['<?xml version="1.0" encoding="iso-8859-1"?>',
             '<i3D name="ufo" version="1.6" '
             'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
             'xsi:noNamespaceSchemaLocation="http://i3d.giants.ch/schema/i3d-1.6.xsd">',
             "  <Asset>",
             '    <Export program="tools/ufo/model.py (procedural FS25 pipeline)" version="1.0"/>',
             "  </Asset>",
             "  <Files>"]
    for i, f in enumerate(w.files, start=1):
        lines.append('    <File fileId="%d" filename="textures/%s"/>' % (i, f))
    lines.append("  </Files>")
    lines.append("  <Materials>")
    lines.extend(mat_lines)
    lines.append("  </Materials>")
    lines.append("  <Shapes>")
    lines.extend(w.shape_xml)
    lines.append("  </Shapes>")
    lines.append("  <Dynamics>")
    lines.append("  </Dynamics>")
    lines.append("  <Scene>")
    lines.extend(scene_lines)
    lines.append("  </Scene>")
    lines.append("</i3D>")
    with open(out_path, "w", encoding="iso-8859-1", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")

    mappings = "\n".join('        <i3dMapping id="%s" node="%s"/>' % (n, p) for n, p in w.mappings)
    return w.stats, mappings
