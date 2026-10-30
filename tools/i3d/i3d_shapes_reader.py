# SPDX-License-Identifier: GPL-3.0-or-later
"""Read GIANTS version-10 ``.i3d.shapes`` files (FS25 / GIANTS Editor 10).

This module reads the packaged binary geometry without FS25.  It deliberately
returns the stored bind-pose vertex positions and triangle indices; it does not
emulate GIANTS materials, shader effects, animation, or skinning.

The binary layout and cipher are the inverse of ``i3d_shapes_writer.py``.  The
keystream is reused from that module so the decoder and encoder stay aligned.
"""

import math
import struct

try:
    from . import i3d_shapes_writer as _writer
except ImportError:  # direct execution from tools/i3d
    import i3d_shapes_writer as _writer


SHAPES_VERSION = 10
OPTION_NORMALS = 0x001
OPTION_UV = (0x002, 0x004, 0x008, 0x010)
OPTION_COLOR = 0x020
OPTION_SKINNING = 0x040
OPTION_TANGENTS = 0x080
OPTION_SINGLE_BLEND_WEIGHTS = 0x100
OPTION_GENERIC = 0x200


class ShapesFormatError(ValueError):
    """The input is not a valid supported version-10 shapes file."""


class _Cursor:
    def __init__(self, data, label):
        self.data = data
        self.pos = 0
        self.label = label

    def require(self, size, what):
        if size < 0 or self.pos + size > len(self.data):
            raise ShapesFormatError(
                "%s: truncated while reading %s (offset %d, need %d bytes, entity size %d)"
                % (self.label, what, self.pos, size, len(self.data))
            )

    def take(self, size, what="data"):
        self.require(size, what)
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result

    def unpack(self, fmt, what):
        size = struct.calcsize(fmt)
        self.require(size, what)
        result = struct.unpack_from(fmt, self.data, self.pos)
        self.pos += size
        return result

    def align(self, boundary):
        self.pos = (self.pos + boundary - 1) // boundary * boundary
        self.require(0, "alignment")

    def finish(self):
        if self.pos != len(self.data):
            raise ShapesFormatError(
                "%s: %d unexpected trailing byte(s) in entity"
                % (self.label, len(self.data) - self.pos)
            )


def _read_part_header(cursor):
    (name_size,) = cursor.unpack("<i", "name length")
    if name_size < 0 or name_size > 1_000_000:
        raise ShapesFormatError("%s: invalid name length %d" % (cursor.label, name_size))
    name = cursor.take(name_size, "entity name").decode("latin-1")
    cursor.align(4)
    (shape_id,) = cursor.unpack("<I", "shape id")
    return name, shape_id


def _read_shape(entity_type, payload):
    cursor = _Cursor(payload, "shape entity")
    name, shape_id = _read_part_header(cursor)
    bounds = cursor.unpack("<4f", "bounding sphere")
    corners, subset_count, vertex_count, options = cursor.unpack("<4I", "shape counts and options")
    (compression_range,) = cursor.unpack("<f", "vertex compression range")

    if corners % 3:
        raise ShapesFormatError("shape %r: corner count %d is not a multiple of 3" % (name, corners))
    if subset_count > 1_000_000 or vertex_count > 20_000_000 or corners > 60_000_000:
        raise ShapesFormatError("shape %r: unreasonable geometry counts" % name)

    uv_count = sum(1 for bit in OPTION_UV if options & bit)
    subsets = []
    for subset_index in range(subset_count):
        first_vertex, num_vertices, first_index, num_indices = cursor.unpack(
            "<4I", "subset %d ranges" % subset_index
        )
        densities = cursor.unpack("<%df" % uv_count, "subset UV density") if uv_count else ()
        if first_vertex + num_vertices > vertex_count:
            raise ShapesFormatError("shape %r subset %d: vertex range is outside the mesh" % (name, subset_index))
        if first_index + num_indices > corners or first_index % 3 or num_indices % 3:
            raise ShapesFormatError("shape %r subset %d: invalid triangle-index range" % (name, subset_index))
        subsets.append({
            "first_vertex": first_vertex,
            "num_vertices": num_vertices,
            "first_index": first_index,
            "num_indices": num_indices,
            "uv_densities": tuple(densities),
            "material_slot_name": "",
        })

    for subset_index, subset in enumerate(subsets):
        (name_size,) = cursor.unpack("<H", "subset %d material-name length" % subset_index)
        subset["material_slot_name"] = cursor.take(
            name_size, "subset %d material name" % subset_index
        ).decode("latin-1")
        cursor.align(2)
    cursor.align(4)

    index_width = 2 if vertex_count <= 0x10000 else 4
    index_data = cursor.take(corners * index_width, "triangle indices")
    index_format = "<H" if index_width == 2 else "<I"
    flat_indices = [item[0] for item in struct.iter_unpack(index_format, index_data)]
    if any(index >= vertex_count for index in flat_indices):
        raise ShapesFormatError("shape %r: a triangle index is outside the vertex array" % name)
    cursor.align(4)
    triangles = [tuple(flat_indices[i:i + 3]) for i in range(0, corners, 3)]

    position_data = cursor.take(vertex_count * 12, "vertex positions")
    positions = [tuple(row) for row in struct.iter_unpack("<3f", position_data)]

    # The remaining vertex channels do not change the stored triangle geometry.
    if options & OPTION_NORMALS:
        cursor.take(vertex_count * 12, "vertex normals")
    if options & OPTION_TANGENTS:
        cursor.take(vertex_count * 16, "vertex tangents")
    for bit in OPTION_UV:
        if options & bit:
            cursor.take(vertex_count * 8, "vertex UV channel")
    if options & OPTION_COLOR:
        cursor.take(vertex_count * 16, "vertex colors")
    if options & OPTION_SKINNING:
        if not options & OPTION_SINGLE_BLEND_WEIGHTS:
            cursor.take(vertex_count * 16, "skin weights")
        cursor.take(vertex_count * (1 if options & OPTION_SINGLE_BLEND_WEIGHTS else 4), "skin indices")
    if options & OPTION_GENERIC:
        cursor.take(vertex_count * 4, "generic vertex channel")

    (attachment_count,) = cursor.unpack("<I", "attachment count")
    if attachment_count > 1_000_000:
        raise ShapesFormatError("shape %r: unreasonable attachment count" % name)
    for attachment_index in range(attachment_count):
        (flags,) = cursor.unpack("<I", "attachment %d flags" % attachment_index)
        if flags & 4:
            cursor.take(12, "attachment %d position" % attachment_index)
        (data_size,) = cursor.unpack("<i", "attachment %d data length" % attachment_index)
        if data_size < 0 or data_size > len(payload):
            raise ShapesFormatError("shape %r: invalid attachment data length" % name)
        cursor.take(data_size, "attachment %d data" % attachment_index)
    cursor.finish()

    if not all(math.isfinite(value) for point in positions for value in point):
        raise ShapesFormatError("shape %r: non-finite vertex position" % name)
    if not all(math.isfinite(value) for value in bounds) or not math.isfinite(compression_range):
        raise ShapesFormatError("shape %r: non-finite bounding data" % name)

    return {
        "kind": "shape",
        "entity_type": entity_type,
        "name": name,
        "shape_id": shape_id,
        "bounds": tuple(bounds),
        "vertex_compression_range": compression_range,
        "options": options,
        "positions": positions,
        "triangles": triangles,
        "subsets": subsets,
        "skinned": bool(options & OPTION_SKINNING),
    }


def _read_spline(entity_type, payload):
    cursor = _Cursor(payload, "spline entity")
    name, shape_id = _read_part_header(cursor)
    (closed,) = cursor.unpack("<I", "spline closed flag")
    (point_count,) = cursor.unpack("<i", "spline point count")
    if point_count < 0 or point_count > 20_000_000:
        raise ShapesFormatError("spline %r: invalid point count %d" % (name, point_count))
    point_data = cursor.take(point_count * 12, "spline points")
    points = [tuple(row) for row in struct.iter_unpack("<3f", point_data)]
    (attribute_flags,) = cursor.unpack("<I", "spline attribute flags")
    cursor.finish()
    if not all(math.isfinite(value) for point in points for value in point):
        raise ShapesFormatError("spline %r: non-finite control-point position" % name)
    return {
        "kind": "spline",
        "entity_type": entity_type,
        "name": name,
        "shape_id": shape_id,
        "closed": bool(closed),
        "attribute_flags": attribute_flags,
        "points": points,
    }


class _EncryptedReader:
    """Decrypt the separately encrypted writes used by ``CipherStream``."""

    def __init__(self, data, seed):
        self.data = data
        self.key = _writer.seed_key(seed)
        self.offset = 4
        self.block = 0

    def read(self, size, label):
        if size < 0 or self.offset + size > len(self.data):
            raise ShapesFormatError("truncated encrypted stream while reading %s" % label)
        block_count = (size + 63) // 64
        stream = _writer.keystream(self.key, self.block, block_count)
        encrypted = self.data[self.offset:self.offset + size]
        plain = bytes(left ^ right for left, right in zip(encrypted, stream))
        self.offset += size
        self.block += block_count
        return plain


def read_shapes_file(data):
    """Decode bytes from a version-10 ``.i3d.shapes`` file.

    Returns a list of dictionaries. Shape dictionaries include actual vertices,
    triangle indices, and subset names; spline dictionaries include control
    points. Unsupported entity types are returned as metadata-only entries so
    the caller can report them rather than silently discarding them.
    """
    if len(data) < 4:
        raise ShapesFormatError("file is shorter than its four-byte header")
    version, reserved_a, seed, reserved_b = data[:4]
    if version != SHAPES_VERSION:
        raise ShapesFormatError("unsupported shapes version %d (this tool supports version 10)" % version)
    if reserved_a != 0 or reserved_b != 0:
        raise ShapesFormatError("unexpected reserved header bytes")

    encrypted = _EncryptedReader(data, seed)
    (entity_count,) = struct.unpack("<i", encrypted.read(4, "entity count"))
    if entity_count < 0 or entity_count > 1_000_000:
        raise ShapesFormatError("invalid entity count %d" % entity_count)

    shapes = []
    seen_ids = set()
    for entity_index in range(entity_count):
        (entity_type,) = struct.unpack("<i", encrypted.read(4, "entity %d type" % entity_index))
        (entity_size,) = struct.unpack("<i", encrypted.read(4, "entity %d size" % entity_index))
        if entity_size < 0 or entity_size > len(data):
            raise ShapesFormatError("entity %d has invalid size %d" % (entity_index, entity_size))
        payload = encrypted.read(entity_size, "entity %d data" % entity_index)
        if entity_type == 1:
            item = _read_shape(entity_type, payload)
        elif entity_type in (2, 6):
            item = _read_spline(entity_type, payload)
        else:
            item = {"kind": "unknown", "entity_type": entity_type, "name": "", "shape_id": None}
        shape_id = item.get("shape_id")
        if shape_id is not None:
            if shape_id in seen_ids:
                raise ShapesFormatError("duplicate shape id %d" % shape_id)
            seen_ids.add(shape_id)
        shapes.append(item)

    if encrypted.offset != len(data):
        raise ShapesFormatError("%d unexpected trailing byte(s)" % (len(data) - encrypted.offset))
    return shapes
