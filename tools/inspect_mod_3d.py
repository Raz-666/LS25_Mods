#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Offline inspection and preview of packaged GIANTS I3D geometry.

Usage:
    python tools/inspect_mod_3d.py path/to/mod.zip

The report is built directly from the I3D XML and its paired version-10
.i3d.shapes file inside the ZIP. It never extracts files or runs mod code.
"""

import argparse
import html
import math
import os
import posixpath
import re
import sys
import webbrowser
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

# Support both `python tools/inspect_mod_3d.py ...` and importing this file.
TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from i3d import binarize_i3d  # noqa: E402
from i3d.i3d_shapes_reader import ShapesFormatError, read_shapes_file  # noqa: E402


SVG_WIDTH = 1280
SVG_HEIGHT = 900
SVG_MARGIN = 48
DEFAULT_MAX_TRIANGLES = 350_000
FALLBACK_COLORS = (
    "#4d94c8", "#e79b48", "#56a17a", "#b77cbd", "#d45f67", "#8a9e43",
    "#4faeb0", "#d07d52", "#7487c4", "#aa8d5d", "#55a0d5", "#b76d8d",
)


class InspectionError(Exception):
    pass


def _truth(value):
    return str(value or "").strip().lower() in ("true", "1", "yes")


def _int_attr(value, label):
    if value is None:
        raise ValueError("%s fehlt" % label)
    text = value.strip()
    try:
        return int(text, 0) if text.lower().startswith("0x") else int(text)
    except ValueError:
        raise ValueError("%s ist keine gültige Zahl: %r" % (label, value)) from None


def _parse_vector(value, default, label):
    if value is None or not value.strip():
        return tuple(default)
    try:
        result = tuple(float(part) for part in value.split())
    except ValueError:
        raise ValueError("%s ist keine gültige Zahlenliste: %r" % (label, value)) from None
    if len(result) != 3 or not all(math.isfinite(item) for item in result):
        raise ValueError("%s muss drei endliche Zahlen enthalten" % label)
    return result


def _identity3():
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _mat3_mul(a, b):
    return tuple(tuple(sum(a[row][k] * b[k][col] for k in range(3)) for col in range(3))
                 for row in range(3))


def _rotation_matrix(rotation):
    # Match the repository's existing software preview convention: Rz * Rx * Ry.
    rx, ry, rz = (math.radians(value) for value in rotation)
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    mx = ((1.0, 0.0, 0.0), (0.0, cx, -sx), (0.0, sx, cx))
    my = ((cy, 0.0, sy), (0.0, 1.0, 0.0), (-sy, 0.0, cy))
    mz = ((cz, -sz, 0.0), (sz, cz, 0.0), (0.0, 0.0, 1.0))
    return _mat3_mul(_mat3_mul(mz, mx), my)


def _local_transform(element):
    translation = _parse_vector(element.get("translation"), (0.0, 0.0, 0.0), "translation")
    rotation = _parse_vector(element.get("rotation"), (0.0, 0.0, 0.0), "rotation")
    scale = _parse_vector(element.get("scale"), (1.0, 1.0, 1.0), "scale")
    rotation_matrix = _rotation_matrix(rotation)
    # Local transform order is translation * rotation * scale.
    linear = tuple(tuple(rotation_matrix[row][col] * scale[col] for col in range(3))
                   for row in range(3))
    return {"linear": linear, "translation": translation}, {
        "translation": translation, "rotation": rotation, "scale": scale,
    }


def _compose(parent, local):
    linear = _mat3_mul(parent["linear"], local["linear"])
    offset = _mat_vec(parent["linear"], local["translation"])
    translation = tuple(offset[i] + parent["translation"][i] for i in range(3))
    return {"linear": linear, "translation": translation}


def _mat_vec(matrix, vector):
    return tuple(sum(matrix[row][col] * vector[col] for col in range(3)) for row in range(3))


def _transform_point(matrix, point):
    rotated = _mat_vec(matrix["linear"], point)
    return tuple(rotated[i] + matrix["translation"][i] for i in range(3))


def _bbox(points):
    if not points:
        return None
    lo = [min(point[axis] for point in points) for axis in range(3)]
    hi = [max(point[axis] for point in points) for axis in range(3)]
    return tuple(lo), tuple(hi)


def _bbox_size(bounds):
    if bounds is None:
        return None
    lo, hi = bounds
    return tuple(hi[i] - lo[i] for i in range(3))


def _fmt_vec(vector, digits=3):
    if vector is None:
        return "—"
    return "  ".join(("%.*f" % (digits, value)) for value in vector)


def _format_bounds(bounds):
    if bounds is None:
        return "Keine Geometrie"
    lo, hi = bounds
    size = _bbox_size(bounds)
    return "Min (%s) m · Max (%s) m · Größe (%s) m" % (
        _fmt_vec(lo), _fmt_vec(hi), _fmt_vec(size)
    )


def _zip_index(names):
    index = {}
    for name in names:
        normalized = name.replace("\\", "/")
        if normalized.endswith("/"):
            continue
        index.setdefault(normalized.casefold(), normalized)
    return index


def _zip_path_for_reference(i3d_path, filename):
    raw = (filename or "").strip().replace("\\", "/")
    if not raw:
        return "", "missing"
    if raw.startswith("$data/") or raw.startswith("$data\\"):
        return raw, "external"
    if re.match(r"^[A-Za-z]:/", raw) or raw.startswith("/"):
        return raw, "external"
    candidate = posixpath.normpath(posixpath.join(posixpath.dirname(i3d_path), raw))
    if candidate == ".." or candidate.startswith("../"):
        return candidate, "external"
    return candidate, "internal"


def _check_referenced_file(i3d_path, filename, zip_files):
    candidate, kind = _zip_path_for_reference(i3d_path, filename)
    if kind == "missing":
        return {"status": "missing", "path": "(leerer Dateiname)", "note": "Kein Dateiname angegeben"}
    if kind == "external":
        return {"status": "external", "path": candidate, "note": "Außerhalb des ZIPs; nicht geprüft"}
    actual = zip_files.get(candidate.casefold())
    if actual is None:
        return {"status": "missing", "path": candidate, "note": "Datei fehlt im Mod-ZIP"}
    if actual != candidate:
        return {"status": "case", "path": candidate, "actual": actual,
                "note": "Nur mit anderer Groß-/Kleinschreibung vorhanden"}
    return {"status": "ok", "path": candidate, "actual": actual, "note": "Vorhanden"}


def _parse_mod_title(zf):
    try:
        raw = zf.read("modDesc.xml")
        root = ET.fromstring(raw)
    except (KeyError, ET.ParseError, OSError):
        return None
    title = root.find("title")
    if title is None:
        return None
    if title.text and title.text.strip():
        return title.text.strip()
    for child in list(title):
        if child.text and child.text.strip():
            return child.text.strip()
    return None


def _fallback_color(name):
    key = (name or "Material").encode("utf-8", errors="replace")
    return FALLBACK_COLORS[zlib.crc32(key) % len(FALLBACK_COLORS)]


def _hex_rgb(color):
    text = (color or "").strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _parse_diffuse(value):
    try:
        channels = [float(item) for item in value.split()]
    except (AttributeError, ValueError):
        return None
    if len(channels) not in (3, 4) or not all(math.isfinite(item) for item in channels):
        return None
    if len(channels) == 3:
        channels.append(1.0)
    rgba = tuple(max(0.0, min(1.0, channel)) for channel in channels)
    rgb = tuple(int(round(channel * 255)) for channel in rgba[:3])
    return rgb, rgba[3]


def _materials_from_xml(root, issue):
    by_id = {}
    by_name = {}
    files = {}
    for file_element in root.findall("./Files/File"):
        file_id = file_element.get("fileId")
        if file_id is not None:
            if file_id in files:
                issue("warning", "Doppelte fileId %s in <Files>" % file_id)
            files[file_id] = file_element.get("filename", "")

    materials = []
    material_ids = set()
    for element in root.findall("./Materials/Material"):
        name = element.get("name") or ("Material %d" % (len(materials) + 1))
        material_id = element.get("materialId")
        if material_id:
            if material_id in material_ids:
                issue("warning", "Doppelte materialId %s (%s)" % (material_id, name))
            material_ids.add(material_id)
        texture_paths = []
        for child in element.iter():
            if child is element:
                continue
            file_id = child.get("fileId")
            if file_id:
                texture_paths.append(files.get(file_id, "fileId %s (nicht gefunden)" % file_id))
        parsed = _parse_diffuse(element.get("diffuseColor"))
        if parsed:
            rgb, opacity = parsed
            color_source = "diffuseColor aus I3D-XML"
        else:
            fallback = _fallback_color(name)
            rgb = _hex_rgb(fallback)
            opacity = 0.62 if _truth(element.get("alphaBlending")) else 1.0
            color_source = "Ersatzfarbe zur Unterscheidung; Textur nicht gerendert" if texture_paths else "Vorschaufarbe"
        if _truth(element.get("alphaBlending")) and opacity >= 0.99:
            opacity = 0.58
        material = {
            "name": name,
            "material_id": material_id,
            "rgb": rgb or (150, 160, 170),
            "opacity": opacity,
            "color": "#%02x%02x%02x" % tuple(rgb or (150, 160, 170)),
            "source": color_source,
            "textures": texture_paths,
        }
        materials.append(material)
        by_name[name.casefold()] = material
        if material_id is not None:
            by_id[str(material_id)] = material

    return materials, by_id, by_name, files


def _parse_material_ids(value):
    if not value:
        return []
    return [part for part in re.split(r"[\s,;]+", value.strip()) if part]


def _material_for_subset(subset, subset_index, material_ids, by_id, by_name):
    slot_name = (subset.get("material_slot_name") or "").strip()
    if slot_name:
        found = by_name.get(slot_name.casefold())
        if found:
            return found
        return {
            "name": slot_name,
            "material_id": None,
            "rgb": _hex_rgb(_fallback_color(slot_name)),
            "opacity": 1.0,
            "color": _fallback_color(slot_name),
            "source": "Material-Slot; passende <Material>-Definition fehlt",
            "textures": [],
        }
    if material_ids:
        material_id = material_ids[subset_index] if subset_index < len(material_ids) else material_ids[0]
        return by_id.get(material_id, {
            "name": "Material-ID %s" % material_id,
            "material_id": material_id,
            "rgb": _hex_rgb(_fallback_color(material_id)),
            "opacity": 1.0,
            "color": _fallback_color(material_id),
            "source": "Material-ID ohne Definition",
            "textures": [],
        })
    return {
        "name": "Unbekanntes Material",
        "material_id": None,
        "rgb": _hex_rgb(_fallback_color("unbekannt")),
        "opacity": 1.0,
        "color": _fallback_color("unbekannt"),
        "source": "keine Materialzuordnung im I3D",
        "textures": [],
    }


def _issue(scene, level, message):
    scene["issues"].append({"level": level, "message": str(message)})


def _load_i3d_geometry(zf, i3d_path, shapes_element, zip_files, scene):
    external_name = shapes_element.get("externalShapesFile") if shapes_element is not None else None
    inline_children = [child for child in list(shapes_element or []) if isinstance(child.tag, str)]
    if external_name:
        resolved = _check_referenced_file(i3d_path, external_name, zip_files)
        scene["shapes_file"] = resolved["path"]
        scene["shapes_file_status"] = resolved["status"]
        if resolved["status"] not in ("ok", "case"):
            _issue(scene, "error", "Gepaarte .i3d.shapes-Datei fehlt oder liegt außerhalb des ZIPs: %s" % resolved["path"])
            return []
        if resolved["status"] == "case":
            _issue(scene, "warning", "Dateiname der .i3d.shapes-Datei unterscheidet sich in Groß-/Kleinschreibung")
        archive_path = resolved.get("actual", resolved["path"])
        try:
            content = zf.read(archive_path)
            scene["shapes_file_bytes"] = len(content)
            geometry = read_shapes_file(content)
        except (KeyError, OSError, ShapesFormatError, zipfile.BadZipFile) as exc:
            _issue(scene, "error", ".i3d.shapes konnte nicht decodiert werden: %s" % exc)
            scene["shapes_file_status"] = "invalid"
            return []
        scene["geometry_source"] = "Gepackte version-10 .i3d.shapes-Datei"
        return geometry
    if inline_children:
        try:
            geometry = binarize_i3d.parse_inline_shapes(shapes_element)
            scene["shapes_file"] = "Inline-Geometrie in der .i3d"
            scene["shapes_file_status"] = "ok"
            scene["geometry_source"] = "Inline-Geometrie aus der .i3d-XML"
            return geometry
        except (binarize_i3d.I3DError, ValueError) as exc:
            _issue(scene, "error", "Inline-Geometrie konnte nicht gelesen werden: %s" % exc)
            return []
    scene["shapes_file"] = "Nicht vorhanden"
    scene["shapes_file_status"] = "missing"
    _issue(scene, "error", "In der .i3d wurde weder eine externe .i3d.shapes-Datei noch Inline-Geometrie gefunden")
    return []


def _entity_maps(entities):
    by_id = {}
    shapes = []
    splines = []
    for item in entities:
        shape_id = item.get("shape_id")
        if shape_id is not None:
            by_id[shape_id] = item
        if item.get("kind", "shape") == "spline":
            splines.append(item)
        elif item.get("kind", "shape") == "shape":
            shapes.append(item)
    return by_id, shapes, splines


def _check_file_and_material_references(root, i3d_path, zip_files, scene, file_table):
    file_ids = set(file_table)
    for element in root.iter():
        if element.tag == "File":
            continue
        file_id = element.get("fileId")
        if file_id is not None and file_id not in file_ids:
            _issue(scene, "error", "<%s> verweist auf unbekannte fileId %s" % (element.tag, file_id))

    assets = []
    files_element = root.find("./Files")
    if files_element is not None:
        for element in files_element.findall("File"):
            filename = element.get("filename", "")
            result = _check_referenced_file(i3d_path, filename, zip_files)
            result.update({"kind": "Datei", "filename": filename,
                           "file_id": element.get("fileId", "—")})
            assets.append(result)
            if result["status"] == "missing":
                _issue(scene, "warning", "Referenzierte Datei fehlt: %s" % result["path"])
            elif result["status"] == "case":
                _issue(scene, "warning", "Dateireferenz mit abweichender Groß-/Kleinschreibung: %s" % result["path"])
    scene["assets"] = assets


def _scene_walk(scene_element, geometry_by_id, by_material_id, by_material_name, scene):
    instances = []
    node_rows = []
    seen_node_ids = {}
    referenced_shape_ids = set()
    scene_shape_count = 0
    previewable_nodes = 0

    def visit(element, parent_matrix, inherited_visible, parent_path):
        nonlocal scene_shape_count, previewable_nodes
        tag = element.tag if isinstance(element.tag, str) else ""
        try:
            local_matrix, local_values = _local_transform(element)
            world_matrix = _compose(parent_matrix, local_matrix)
        except ValueError as exc:
            _issue(scene, "error", "Ungültiger Transform in <%s> %s: %s" % (
                tag, element.get("name", ""), exc
            ))
            local_matrix = {"linear": _identity3(), "translation": (0.0, 0.0, 0.0)}
            local_values = {"translation": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0)}
            world_matrix = _compose(parent_matrix, local_matrix)

        visible = inherited_visible and element.get("visibility", "true").strip().lower() not in ("false", "0")
        name = element.get("name") or tag or "(unbenannter Knoten)"
        path = parent_path + [name]
        node_id = element.get("nodeId")
        if node_id:
            if node_id in seen_node_ids:
                _issue(scene, "warning", "Doppelte nodeId %s (%s und %s)" % (
                    node_id, seen_node_ids[node_id], " / ".join(path)
                ))
            else:
                seen_node_ids[node_id] = " / ".join(path)

        if tag == "Shape":
            scene_shape_count += 1
            try:
                shape_id = _int_attr(element.get("shapeId"), "shapeId")
            except ValueError as exc:
                _issue(scene, "error", "%s: %s" % (" / ".join(path), exc))
                shape_id = None
            geometry = geometry_by_id.get(shape_id) if shape_id is not None else None
            if shape_id is not None:
                referenced_shape_ids.add(shape_id)
                if geometry is None and scene.get("geometry_loaded"):
                    _issue(scene, "error", "%s verweist auf shapeId %d, die in den Geometriedaten fehlt" % (
                        " / ".join(path), shape_id
                    ))
            is_non_renderable = _truth(element.get("nonRenderable"))
            renderable = visible and not is_non_renderable and geometry is not None and geometry.get("kind", "shape") == "shape"
            material_ids = _parse_material_ids(element.get("materialIds"))
            for material_id in material_ids:
                if material_id not in by_material_id:
                    _issue(scene, "warning", "%s verweist auf unbekannte materialId %s" % (name, material_id))
            row = {
                "name": name,
                "node_id": node_id or "—",
                "shape_id": shape_id,
                "geometry": geometry,
                "visible": visible,
                "non_renderable": is_non_renderable,
                "renderable": renderable,
                "local": local_values,
                "world_translation": world_matrix["translation"],
                "bounds": None,
                "materials": [],
                "path": " / ".join(path),
            }
            if geometry and geometry.get("kind", "shape") == "shape":
                world_positions = [_transform_point(world_matrix, point) for point in geometry.get("positions", [])]
                row["bounds"] = _bbox(world_positions)
                if renderable:
                    subsets = geometry.get("subsets") or [{
                        "first_vertex": 0,
                        "num_vertices": len(world_positions),
                        "first_index": 0,
                        "num_indices": 3 * len(geometry.get("triangles", [])),
                        "material_slot_name": "",
                    }]
                    mapped_subsets = []
                    for subset_index, subset in enumerate(subsets):
                        material = _material_for_subset(
                            subset, subset_index, material_ids, by_material_id, by_material_name
                        )
                        slot_name = (subset.get("material_slot_name") or "").strip()
                        if "collision" in (slot_name or material["name"]).casefold():
                            continue
                        first_index = int(subset.get("first_index", 0))
                        num_indices = int(subset.get("num_indices", 0))
                        first_triangle = first_index // 3
                        triangle_end = (first_index + num_indices) // 3
                        if first_index % 3 or num_indices % 3:
                            _issue(scene, "error", "%s hat einen Subset-Bereich, der nicht an Dreiecksgrenzen liegt" % name)
                            continue
                        mapped_subsets.append({
                            "material": material,
                            "first_triangle": first_triangle,
                            "triangle_end": triangle_end,
                            "triangle_count": max(0, triangle_end - first_triangle),
                        })
                        row["materials"].append(material["name"])
                    triangle_list = geometry.get("triangles", [])
                    usable_subsets = [subset for subset in mapped_subsets
                                      if subset["first_triangle"] <= len(triangle_list)
                                      and subset["triangle_end"] <= len(triangle_list)]
                    if len(usable_subsets) != len(mapped_subsets):
                        _issue(scene, "error", "%s enthält einen Subset-Bereich außerhalb der Dreiecks-Liste" % name)
                    if usable_subsets:
                        previewable_nodes += 1
                        instance = {
                            "name": name,
                            "geometry": geometry,
                            "world_positions": world_positions,
                            "subsets": usable_subsets,
                        }
                        instances.append(instance)
            node_rows.append(row)

        for child in list(element):
            if isinstance(child.tag, str):
                visit(child, world_matrix, visible, path)

    identity = {"linear": _identity3(), "translation": (0.0, 0.0, 0.0)}
    for child in list(scene_element):
        if isinstance(child.tag, str):
            visit(child, identity, True, [])

    scene["scene_shape_count"] = scene_shape_count
    scene["previewable_nodes"] = previewable_nodes
    scene["node_rows"] = node_rows
    scene["instances"] = instances
    scene["referenced_shape_ids"] = referenced_shape_ids
    if scene.get("geometry_loaded"):
        unreferenced = sorted(set(geometry_by_id) - referenced_shape_ids)
        if unreferenced:
            scene["unreferenced_shape_ids"] = unreferenced
            _issue(scene, "info", "%d Geometrie-Eintrag/Einträge sind nicht an einen Shape-Knoten in der Szene gebunden" % len(unreferenced))
    return instances


def _normal(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    n = (ab[1] * ac[2] - ab[2] * ac[1],
         ab[2] * ac[0] - ab[0] * ac[2],
         ab[0] * ac[1] - ab[1] * ac[0])
    length = math.sqrt(sum(value * value for value in n))
    if length <= 1e-12:
        return (0.0, 1.0, 0.0)
    return tuple(value / length for value in n)


def _normalize(vector):
    length = math.sqrt(sum(value * value for value in vector))
    if length <= 1e-12:
        return (0.0, 1.0, 0.0)
    return tuple(value / length for value in vector)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _shade(rgb, shade):
    return tuple(max(0, min(255, int(round(channel * shade)))) for channel in rgb)


def _svg_number(value):
    return "%.2f" % value


def _render_svg(instances, bounds, view, max_triangles):
    eye_vectors = {
        "isometrisch": (1.0, 0.85, 1.2),
        "vorn": (0.0, 0.20, 1.0),
        "seite": (1.0, 0.15, 0.0),
        "oben": (0.0, 1.0, 0.0),
    }
    eye_direction = _normalize(eye_vectors[view])
    forward = tuple(-value for value in eye_direction)
    up_reference = (0.0, 0.0, 1.0) if view == "oben" else (0.0, 1.0, 0.0)
    right = _normalize(_cross(forward, up_reference))
    up = _normalize(_cross(right, forward))
    if bounds is None:
        center = (0.0, 0.0, 0.0)
    else:
        lo, hi = bounds
        center = tuple((lo[i] + hi[i]) * 0.5 for i in range(3))

    projected_instances = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    total_triangles = 0
    for instance in instances:
        world = instance["world_positions"]
        projected = []
        for point in world:
            relative = tuple(point[i] - center[i] for i in range(3))
            coords = (_dot(relative, right), _dot(relative, up), _dot(relative, forward))
            projected.append(coords)
            min_x = min(min_x, coords[0])
            max_x = max(max_x, coords[0])
            min_y = min(min_y, coords[1])
            max_y = max(max_y, coords[1])
        projected_instances.append(projected)
        total_triangles += sum(subset["triangle_count"] for subset in instance["subsets"])

    if total_triangles == 0 or not projected_instances:
        empty = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" role="img" aria-label="Keine renderbaren Dreiecke">'
            '<rect width="100%%" height="100%%" fill="#f2f5f8"/>'
            '<text x="50%%" y="50%%" text-anchor="middle" font-family="sans-serif" '
            'font-size="24" fill="#425466">Keine renderbaren Dreiecke gefunden</text></svg>'
        ) % (SVG_WIDTH, SVG_HEIGHT, SVG_WIDTH, SVG_HEIGHT)
        return empty, 0, total_triangles, 1

    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    drawable_width = SVG_WIDTH - 2 * SVG_MARGIN
    drawable_height = SVG_HEIGHT - 2 * SVG_MARGIN
    scale = min(drawable_width / span_x, drawable_height / span_y)
    drawn_width = span_x * scale
    drawn_height = span_y * scale
    offset_x = SVG_MARGIN + (drawable_width - drawn_width) * 0.5
    offset_y = SVG_MARGIN + (drawable_height - drawn_height) * 0.5

    step = max(1, (total_triangles + max_triangles - 1) // max_triangles)
    faces = []
    sequence = 0
    for instance_index, instance in enumerate(instances):
        projected = projected_instances[instance_index]
        world = instance["world_positions"]
        triangles = instance["geometry"].get("triangles", [])
        for subset in instance["subsets"]:
            material = subset["material"]
            for triangle_index in range(subset["first_triangle"], subset["triangle_end"]):
                if sequence % step == 0:
                    tri = triangles[triangle_index]
                    a, b, c = (world[tri[0]], world[tri[1]], world[tri[2]])
                    pa, pb, pc = (projected[tri[0]], projected[tri[1]], projected[tri[2]])
                    normal = _normal(a, b, c)
                    light = _normalize((0.40, 0.85, 0.45))
                    diffuse = max(0.0, _dot(normal, light))
                    shade = 0.35 + 0.65 * diffuse
                    depth = (pa[2] + pb[2] + pc[2]) / 3.0
                    faces.append((depth, projected, tri, material, shade))
                sequence += 1

    faces.sort(key=lambda item: item[0], reverse=True)
    content = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'role="img" aria-label="Softwarevorschau der gepackten I3D-Geometrie">'
        % (SVG_WIDTH, SVG_HEIGHT, SVG_WIDTH, SVG_HEIGHT),
        '<rect width="100%" height="100%" fill="#f2f5f8"/>',
    ]
    for _depth, projected, tri, material, shade in faces:
        coords = []
        for vertex_index in tri:
            x, y, _z = projected[vertex_index]
            sx = offset_x + (x - min_x) * scale
            sy = offset_y + (max_y - y) * scale
            coords.append(_svg_number(sx) + "," + _svg_number(sy))
        rgb = _shade(material["rgb"], shade)
        color = "#%02x%02x%02x" % rgb
        opacity = material["opacity"]
        opacity_attr = "" if opacity >= 0.995 else ' fill-opacity="%.3f"' % opacity
        content.append('<polygon points="%s %s %s" fill="%s"%s/>' % (
            coords[0], coords[1], coords[2], color, opacity_attr
        ))
    content.append("</svg>")
    return "".join(content), len(faces), total_triangles, step


def _load_scene(zf, i3d_path, zip_files, max_triangles, view):
    scene = {
        "path": i3d_path,
        "issues": [],
        "assets": [],
        "geometry_loaded": False,
        "entities": [],
        "instances": [],
        "node_rows": [],
        "renderable_triangle_count": 0,
        "rendered_triangle_count": 0,
        "bounds": None,
        "svg": None,
    }
    try:
        root = ET.fromstring(zf.read(i3d_path))
    except (KeyError, ET.ParseError, OSError) as exc:
        _issue(scene, "error", "I3D-XML kann nicht gelesen werden: %s" % exc)
        return scene

    scene_element = root.find("Scene")
    if scene_element is None:
        _issue(scene, "error", "Die I3D-Datei enthält kein <Scene>-Element")
    shapes_element = root.find("Shapes")
    if shapes_element is None:
        _issue(scene, "error", "Die I3D-Datei enthält kein <Shapes>-Element")

    materials, by_material_id, by_material_name, file_table = _materials_from_xml(
        root, lambda level, message: _issue(scene, level, message)
    )
    scene["materials"] = materials
    _check_file_and_material_references(root, i3d_path, zip_files, scene, file_table)

    entities = _load_i3d_geometry(zf, i3d_path, shapes_element, zip_files, scene) if shapes_element is not None else []
    scene["entities"] = entities
    scene["geometry_loaded"] = bool(scene.get("geometry_source"))
    geometry_by_id, shape_entities, splines = _entity_maps(entities)
    unknown_entities = [item for item in entities if item.get("kind") == "unknown"]
    for item in unknown_entities:
        _issue(scene, "warning", "Nicht unterstützter shapes-Entity-Typ %s wurde übersprungen" % item.get("entity_type"))
    scene["shape_entities"] = shape_entities
    scene["splines"] = splines
    scene["entity_count"] = len(entities)
    scene["vertex_count"] = sum(len(item.get("positions", [])) for item in shape_entities)
    scene["triangle_count"] = sum(len(item.get("triangles", [])) for item in shape_entities)
    scene["spline_point_count"] = sum(len(item.get("points", [])) for item in splines)

    if scene_element is not None:
        _scene_walk(scene_element, geometry_by_id, by_material_id, by_material_name, scene)
        all_positions = []
        for instance in scene["instances"]:
            all_positions.extend(instance["world_positions"])
        scene["bounds"] = _bbox(all_positions)
        scene["renderable_triangle_count"] = sum(
            subset["triangle_count"] for instance in scene["instances"] for subset in instance["subsets"]
        )
        if scene["renderable_triangle_count"]:
            svg, drawn, total, step = _render_svg(scene["instances"], scene["bounds"], view, max_triangles)
            scene["svg"] = svg
            scene["rendered_triangle_count"] = drawn
            scene["preview_step"] = step
            scene["preview_triangle_count"] = total
            if step > 1:
                _issue(scene, "warning", "Vorschau zur Dateigröße ausgedünnt: jedes %d. Dreieck gezeichnet; Geometrieprüfung bleibt vollständig" % step)
        elif scene["geometry_loaded"]:
            scene["svg"] = _render_svg([], None, view, max_triangles)[0]
            _issue(scene, "warning", "Es gibt keine sichtbaren, renderbaren Dreiecke in der Szene")

    return scene


def _mod_report(zf, zip_name, zip_files, max_triangles, view):
    title = _parse_mod_title(zf) or Path(zip_name).stem
    i3d_paths = sorted(name for name in zip_files.values() if name.lower().endswith(".i3d"))
    scenes = [_load_scene(zf, path, zip_files, max_triangles, view) for path in i3d_paths]
    return {
        "zip_name": zip_name,
        "title": title,
        "scenes": scenes,
        "i3d_count": len(i3d_paths),
        "view": view,
    }


def _css_class_for_status(status):
    return {"ok": "ok", "case": "warning", "warning": "warning", "missing": "error", "invalid": "error", "external": "external"}.get(status, "neutral")


def _render_issue_list(issues):
    if not issues:
        return '<p class="ok-line">Keine strukturellen Warnungen oder Fehler erkannt.</p>'
    chunks = []
    for item in issues:
        level = item["level"]
        label = {"error": "FEHLER", "warning": "HINWEIS", "info": "INFO"}.get(level, level.upper())
        chunks.append('<li class="issue %s"><strong>%s:</strong> %s</li>' % (
            html.escape(level), html.escape(label), html.escape(item["message"])
        ))
    return '<ul class="issues">%s</ul>' % "".join(chunks)


def _scene_html(scene, view):
    issues = _render_issue_list(scene["issues"])
    has_errors = any(item["level"] == "error" for item in scene["issues"])
    has_warnings = any(item["level"] == "warning" for item in scene["issues"])
    status = "Fehler" if has_errors else ("Hinweise" if has_warnings else "OK")
    counts = (
        "<strong>%s</strong> Shapes im Binärfile · <strong>%s</strong> Scene-Knoten · "
        "<strong>%s</strong> sichtbare Dreiecke · <strong>%s</strong> Punkte"
        % (scene.get("entity_count", 0), scene.get("scene_shape_count", 0),
           scene.get("renderable_triangle_count", 0), scene.get("vertex_count", 0))
    )
    svg = scene.get("svg")
    if svg:
        preview = '<figure class="preview"><div class="svg-frame">%s</div><figcaption>Ansicht: %s · Software-Projektion aus den gespeicherten Dreiecken</figcaption></figure>' % (
            svg, html.escape(view)
        )
    else:
        preview = '<div class="no-preview">Für diese Szene konnte keine Geometrie-Vorschau erstellt werden.</div>'

    materials = scene.get("materials", [])
    if materials:
        material_rows = []
        for material in materials:
            texture = ", ".join(material["textures"]) if material["textures"] else "—"
            material_rows.append(
                '<tr><td><span class="swatch" style="background:%s"></span>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                % (html.escape(material["color"], quote=True), html.escape(material["name"]),
                   html.escape(str(material["material_id"] or "—")), html.escape(material["source"]),
                   html.escape(texture))
            )
        material_html = (
            '<details><summary>Materialien und Texturverweise (%d)</summary>'
            '<div class="table-scroll"><table><thead><tr><th>Material</th><th>ID</th><th>Farbherkunft</th><th>Textur(en)</th></tr></thead><tbody>%s</tbody></table></div></details>'
            % (len(materials), "".join(material_rows))
        )
    else:
        material_html = '<p>Keine Materialdefinitionen in der I3D.</p>'

    assets = scene.get("assets", [])
    if assets:
        rows = []
        for asset in assets:
            css = _css_class_for_status(asset["status"])
            shown_path = asset.get("path", "")
            if asset.get("actual") and asset.get("actual") != shown_path:
                shown_path += " → " + asset["actual"]
            rows.append('<tr><td>%s</td><td>%s</td><td><span class="badge %s">%s</span></td><td>%s</td></tr>' % (
                html.escape(str(asset.get("kind", "Datei"))),
                html.escape(str(shown_path)),
                css,
                html.escape(asset["status"]),
                html.escape(asset["note"]),
            ))
        asset_html = (
            '<details open><summary>Referenzierte Dateien aus &lt;Files&gt; (%d)</summary>'
            '<div class="table-scroll"><table><thead><tr><th>Typ</th><th>Pfad im ZIP</th><th>Status</th><th>Ergebnis</th></tr></thead><tbody>%s</tbody></table></div></details>'
            % (len(assets), "".join(rows))
        )
    else:
        asset_html = '<p>Keine Dateien im &lt;Files&gt;-Abschnitt referenziert.</p>'

    rows = []
    for item in scene.get("shape_entities", []):
        subset_names = ", ".join(
            subset.get("material_slot_name", "") or "(ohne Materialslot)"
            for subset in item.get("subsets", [])
        ) or "—"
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            html.escape(str(item.get("shape_id", "—"))),
            html.escape(item.get("name", "")),
            html.escape(str(len(item.get("positions", [])))),
            html.escape(str(len(item.get("triangles", [])))),
            html.escape(subset_names),
        ))
    for item in scene.get("splines", []):
        rows.append('<tr><td>%s</td><td>%s (Spline)</td><td>—</td><td>—</td><td>%s Kontrollpunkte</td></tr>' % (
            html.escape(str(item.get("shape_id", "—"))), html.escape(item.get("name", "")),
            html.escape(str(len(item.get("points", []))))
        ))
    if rows:
        geometry_html = (
            '<details><summary>Geometrie-Einträge (%d)</summary>'
            '<div class="table-scroll"><table><thead><tr><th>shapeId</th><th>Name</th><th>Vertices</th><th>Dreiecke</th><th>Materialslots / Hinweis</th></tr></thead><tbody>%s</tbody></table></div></details>'
            % (len(rows), "".join(rows))
        )
    else:
        geometry_html = '<p>Keine decodierten Shape- oder Spline-Einträge.</p>'

    node_rows = []
    for node in scene.get("node_rows", []):
        local = node["local"]
        transform = "T (%s) · R (%s)° · S (%s)" % (
            _fmt_vec(local["translation"]), _fmt_vec(local["rotation"]), _fmt_vec(local["scale"])
        )
        state = "sichtbar" if node["visible"] and not node["non_renderable"] else "ausgeblendet / nonRenderable"
        bounds = _format_bounds(node.get("bounds"))
        node_rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            html.escape(node["name"]), html.escape(str(node["shape_id"] if node["shape_id"] is not None else "—")),
            html.escape(state), html.escape(transform), html.escape(_fmt_vec(node["world_translation"])),
            html.escape(bounds),
        ))
    if node_rows:
        node_html = (
            '<details><summary>Shape-Knoten, lokale Transformwerte und Welt-Bounds (%d)</summary>'
            '<div class="table-scroll"><table><thead><tr><th>Knoten</th><th>shapeId</th><th>Status</th><th>Lokaler Transform</th><th>Weltposition (m)</th><th>Bounds der Geometrie</th></tr></thead><tbody>%s</tbody></table></div></details>'
            % (len(node_rows), "".join(node_rows))
        )
    else:
        node_html = '<p>Keine &lt;Shape&gt;-Knoten in der Szene.</p>'

    shape_file = scene.get("shapes_file", "Unbekannt")
    shape_status = scene.get("shapes_file_status", "neutral")
    version_text = scene.get("geometry_source", "Keine Geometrie decodiert")
    geometry_status = "ok" if scene.get("geometry_loaded") else "missing"
    badge_status = "invalid" if has_errors or geometry_status != "ok" else ("warning" if has_warnings else "ok")
    scene_bbox = _format_bounds(scene.get("bounds"))
    extra_note = ""
    if scene.get("preview_step", 1) > 1:
        extra_note = '<p class="warning-line">Vorschau vereinfacht: Es wurde für die Anzeige jedes %d. Dreieck gezeichnet. Die Zählung und Dateiprüfung verwenden weiterhin alle gespeicherten Dreiecke.</p>' % scene["preview_step"]

    return (
        '<section class="scene-card"><div class="scene-heading"><div><h2>%s</h2>'
        '<p class="muted">%s · Shapes-Datei: <code>%s</code> · Status: <span class="badge %s">%s</span></p></div></div>'
        '<p class="summary">%s</p><div class="stat-grid">'
        '<div><span>Szene-Bounds</span><strong>%s</strong></div>'
        '<div><span>Quelle der Vorschau</span><strong>%s</strong></div>'
        '</div>%s%s%s%s%s%s%s</section>'
        % (html.escape(scene["path"]), html.escape(version_text), html.escape(shape_file),
           _css_class_for_status(badge_status), html.escape(status),
           counts, html.escape(scene_bbox), html.escape(version_text), preview, extra_note,
           asset_html, material_html, geometry_html, node_html, issues)
    )


def _build_html(report):
    all_issues = [issue for scene in report["scenes"] for issue in scene["issues"]]
    errors = sum(item["level"] == "error" for item in all_issues)
    warnings = sum(item["level"] == "warning" for item in all_issues)
    total_shapes = sum(scene.get("entity_count", 0) for scene in report["scenes"])
    total_triangles = sum(scene.get("renderable_triangle_count", 0) for scene in report["scenes"])
    total_vertices = sum(scene.get("vertex_count", 0) for scene in report["scenes"])
    status = "FEHLER" if errors else ("HINWEISE" if warnings else "GEPRÜFT")
    status_class = "error" if errors else ("warning" if warnings else "ok")
    if not report["scenes"]:
        errors += 1
        status = "KEINE I3D-DATEI"
        status_class = "error"
    scene_sections = "".join(_scene_html(scene, report["view"]) for scene in report["scenes"])
    if not scene_sections:
        scene_sections = '<section class="scene-card"><h2>Keine .i3d-Datei im ZIP gefunden</h2><p>Dieses Archiv enthält keine decodierbare 3D-Szene.</p></section>'
    guidance = (
        '<section class="notice"><h2>Was diese Vorschau zeigt – und was nicht</h2>'
        '<ul><li>Die Dreiecke stammen aus den tatsächlichen Dateien im Mod-ZIP: I3D-XML plus gepaarte <code>.i3d.shapes</code>-Geometrie. Es wurde kein KI-Bild verwendet.</li>'
        '<li>Die Vorschau berücksichtigt die in der I3D gespeicherten Objekt-Transforms und Bounding-Boxen.</li>'
        '<li>Dies ist ein einfacher Software-Renderer, kein GIANTS-Renderer: DDS-Texturen, FS25-Materialshader, Animationen, Beleuchtung und Spielverhalten werden nicht nachgebildet. Bei Texturmaterialien dient die Farbe nur zur Unterscheidung.</li>'
        '<li>Ein erfolgreich decodiertes Modell bestätigt, dass Geometriedaten im ZIP vorhanden und lesbar sind. Es bestätigt nicht, dass FS25 das Mod lädt oder dass XML/Lua im Spiel funktioniert.</li>'
        '<li>Kollisionsflächen und als <code>nonRenderable</code> markierte Knoten werden für die normale Vorschau ausgelassen, aber in der Bestandsliste geführt.</li></ul></section>'
    )
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Offline 3D-Prüfung – %s</title><style>%s</style></head><body>'
        '<main><header><p class="eyebrow">OFFLINE · DIREKT AUS DEM MOD-ZIP</p>'
        '<h1>3D-Prüfbericht: %s</h1><p class="muted">Archiv: <code>%s</code></p>'
        '<p class="result"><span class="badge %s">%s</span> · %d I3D-Szene(n) · %d Geometrie-Einträge · %d sichtbare Dreiecke · %d Vertices · %d Fehler · %d Hinweise</p></header>'
        '%s%s<footer>Erstellt mit dem Offline-I3D-Prüfprogramm. Es wurde nichts aus dem ZIP ausgeführt oder extrahiert. Kein FS25-Laufzeittest.</footer></main></body></html>'
        % (html.escape(report["title"]), _css(), html.escape(report["title"]),
           html.escape(report["zip_name"]), status_class, status, report["i3d_count"],
           total_shapes, total_triangles, total_vertices, errors, warnings,
           guidance, scene_sections)
    )


def _css():
    return """
    :root { color-scheme: light; --ink:#17212b; --muted:#5b6875; --line:#d7dee6; --panel:#fff; --bg:#f3f6f9; --blue:#245f91; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
    main { width:min(1480px,96vw); margin:0 auto; padding:28px 0 56px; }
    header { padding:28px 30px; border-radius:18px; background:#fff; box-shadow:0 4px 18px #17212b0d; }
    h1 { margin:.15rem 0 .4rem; font-size:clamp(1.8rem,4vw,2.7rem); line-height:1.15; }
    h2 { margin:0 0 .4rem; font-size:1.45rem; overflow-wrap:anywhere; }
    h3 { margin:1.2rem 0 .4rem; }
    p { margin:.55rem 0; }
    code { background:#edf2f7; border-radius:5px; padding:.1rem .35rem; overflow-wrap:anywhere; }
    .eyebrow { color:var(--blue); font-size:.78rem; font-weight:800; letter-spacing:.11em; }
    .muted { color:var(--muted); }
    .result { margin-top:1rem; font-weight:650; }
    .badge { display:inline-block; border-radius:999px; padding:.18rem .65rem; font-size:.79rem; font-weight:750; text-transform:uppercase; letter-spacing:.04em; }
    .badge.ok { color:#115c38; background:#dcf5e7; }
    .badge.warning { color:#77510b; background:#fff0c2; }
    .badge.error { color:#8d2525; background:#ffe1e1; }
    .badge.external { color:#465465; background:#e9eef3; }
    .badge.neutral { color:#465465; background:#edf2f7; }
    .notice,.scene-card { margin-top:20px; padding:24px 28px; border:1px solid var(--line); border-radius:16px; background:var(--panel); box-shadow:0 4px 18px #17212b08; }
    .notice { border-left:5px solid #4c8dc0; }
    .notice ul { margin:.5rem 0 0; padding-left:1.25rem; }
    .notice li { margin:.3rem 0; }
    .scene-heading { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }
    .summary { margin:.9rem 0; }
    .stat-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:10px; margin:14px 0 18px; }
    .stat-grid div { background:#f5f8fb; border:1px solid #e2e8ef; border-radius:10px; padding:12px 14px; }
    .stat-grid span { display:block; color:var(--muted); font-size:.84rem; }
    .stat-grid strong { display:block; overflow-wrap:anywhere; }
    figure { margin:14px 0 22px; }
    .svg-frame { width:100%; overflow:auto; border:1px solid var(--line); border-radius:12px; background:#f2f5f8; }
    .svg-frame svg { display:block; width:100%; height:auto; min-width:600px; }
    figcaption { color:var(--muted); font-size:.86rem; padding:.45rem .1rem; }
    .no-preview { padding:22px; color:var(--muted); background:#f5f8fb; border-radius:10px; }
    details { margin:16px 0; border-top:1px solid var(--line); padding-top:12px; }
    summary { cursor:pointer; font-weight:720; }
    .table-scroll { overflow:auto; margin-top:10px; }
    table { width:100%; border-collapse:collapse; font-size:.9rem; }
    th,td { padding:8px 10px; text-align:left; vertical-align:top; border-bottom:1px solid #e7ecf1; }
    th { position:sticky; top:0; background:#f5f8fb; }
    td { overflow-wrap:anywhere; }
    .swatch { display:inline-block; width:14px; height:14px; margin-right:7px; border:1px solid #71809666; border-radius:3px; vertical-align:-2px; }
    .issues { margin:.7rem 0 0; padding:0; list-style:none; }
    .issue { margin:6px 0; padding:9px 12px; border-radius:8px; }
    .issue.error { color:#7d2222; background:#fff0f0; }
    .issue.warning { color:#6b4a0d; background:#fff7df; }
    .issue.info { color:#34495e; background:#edf4fa; }
    .ok-line { color:#17613b; padding:9px 12px; background:#edf9f1; border-radius:8px; }
    .warning-line { color:#77510b; padding:9px 12px; background:#fff7df; border-radius:8px; }
    footer { margin:24px 8px; color:var(--muted); font-size:.88rem; }
    @media(max-width:700px) { main{width:100%;padding:10px;} header,.notice,.scene-card{padding:18px;} .svg-frame svg{min-width:520px;} }
    """


def inspect_zip(zip_path, output_path=None, max_triangles=DEFAULT_MAX_TRIANGLES, view="isometrisch", open_report=False):
    zip_path = os.path.abspath(os.fspath(zip_path))
    if not os.path.isfile(zip_path):
        raise InspectionError("Die ZIP-Datei wurde nicht gefunden: %s" % zip_path)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad_member = zf.testzip()
            if bad_member:
                raise InspectionError("ZIP-Prüfsumme fehlerhaft bei: %s" % bad_member)
            zip_files = _zip_index(zf.namelist())
            report = _mod_report(zf, os.path.basename(zip_path), zip_files, max_triangles, view)
    except zipfile.BadZipFile as exc:
        raise InspectionError("Das ist keine gültige ZIP-Datei: %s" % exc) from None
    except OSError as exc:
        raise InspectionError("ZIP-Datei kann nicht gelesen werden: %s" % exc) from None

    if output_path is None:
        output_path = os.path.splitext(zip_path)[0] + "_3D-Pruefung.html"
    output_path = os.path.abspath(os.fspath(output_path))
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as output:
        output.write(_build_html(report))

    if open_report:
        webbrowser.open(Path(output_path).as_uri())
    report["output_path"] = output_path
    report["error_count"] = sum(
        item["level"] == "error" for scene in report["scenes"] for item in scene["issues"]
    ) + (1 if report["i3d_count"] == 0 else 0)
    report["warning_count"] = sum(
        item["level"] == "warning" for scene in report["scenes"] for item in scene["issues"]
    )
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prüft I3D-Geometrie und Dateiverweise direkt aus einer Mod-ZIP; benötigt kein FS25."
    )
    parser.add_argument("zip", help="Mod-ZIP-Datei, die geprüft werden soll")
    parser.add_argument("--out", help="Ausgabedatei für den selbstständigen HTML-Bericht")
    parser.add_argument("--view", choices=("isometrisch", "vorn", "seite", "oben"), default="isometrisch",
                        help="Ansicht der Softwarevorschau (Standard: isometrisch)")
    parser.add_argument("--max-triangles", type=int, default=DEFAULT_MAX_TRIANGLES,
                        help="Maximale Zahl gezeichneter Dreiecke pro Szene (Standard: %(default)s)")
    parser.add_argument("--open", action="store_true", help="HTML-Bericht nach dem Erstellen öffnen")
    args = parser.parse_args(argv)
    if args.max_triangles < 1:
        parser.error("--max-triangles muss mindestens 1 sein")

    try:
        report = inspect_zip(args.zip, args.out, args.max_triangles, args.view, args.open)
    except InspectionError as exc:
        print("FEHLER: %s" % exc, file=sys.stderr)
        return 2
    print("Mod:       %s" % report["title"])
    print("ZIP:       %s" % report["zip_name"])
    print("I3D:       %d Szene(n)" % report["i3d_count"])
    for scene in report["scenes"]:
        print("  - %s: %d Shapes, %d sichtbare Dreiecke" % (
            scene["path"], scene.get("entity_count", 0), scene.get("renderable_triangle_count", 0)
        ))
    print("Bericht:   %s" % report["output_path"])
    print("Ergebnis:  %d Fehler, %d Hinweise" % (report["error_count"], report["warning_count"]))
    return 1 if report["error_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
