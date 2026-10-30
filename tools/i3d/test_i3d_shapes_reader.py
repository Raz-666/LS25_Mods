# SPDX-License-Identifier: GPL-3.0-or-later
"""Small stdlib-only regression tests for the version-10 shapes decoder."""

import unittest

try:
    from . import i3d_shapes_writer as writer
    from .i3d_shapes_reader import ShapesFormatError, read_shapes_file
except ImportError:  # direct execution from tools/i3d
    import i3d_shapes_writer as writer
    from i3d_shapes_reader import ShapesFormatError, read_shapes_file


class ShapesReaderTests(unittest.TestCase):
    def test_round_trip_shape_channels_and_subset(self):
        positions = [(0, 0, 0), (2, 0, 0), (0, 3, 0), (2, 3, 1)]
        shape = {
            "name": "test_mesh",
            "shape_id": 41,
            "positions": positions,
            "normals": [(0, 0, 1)] * 4,
            "uv0": [(0, 0), (1, 0), (0, 1), (1, 1)],
            "uv1": [(0, 0), (0.5, 0), (0, 0.5), (0.5, 0.5)],
            "colors": [(1, 0.5, 0.25, 1)] * 4,
            "tangents": [(1, 0, 0, 1)] * 4,
            "blend_weights": [(1, 0, 0, 0)] * 4,
            "blend_indices": [(0, 0, 0, 0)] * 4,
            "generic": [0.1, 0.2, 0.3, 0.4],
            "triangles": [(0, 1, 2), (1, 3, 2)],
            "subsets": [{
                "first_vertex": 0,
                "num_vertices": 4,
                "first_index": 0,
                "num_indices": 6,
                "material_slot_name": "paint",
            }],
            "attachments": [
                {"flags": 4, "floats": (1.0, 2.0, 3.0), "data": b"point-a"},
                {"flags": 0, "floats": None, "data": b"point-b"},
            ],
        }
        data, _ = writer.build_shapes_bytes([shape], seed=71, use_numpy=False)
        decoded = read_shapes_file(data)

        self.assertEqual(len(decoded), 1)
        mesh = decoded[0]
        self.assertEqual(mesh["kind"], "shape")
        self.assertEqual(mesh["name"], "test_mesh")
        self.assertEqual(mesh["shape_id"], 41)
        self.assertEqual(mesh["positions"], [tuple(map(float, p)) for p in positions])
        self.assertEqual(mesh["triangles"], [(0, 1, 2), (1, 3, 2)])
        self.assertEqual(mesh["subsets"][0]["material_slot_name"], "paint")
        self.assertTrue(mesh["skinned"])

    def test_round_trip_linear_and_cubic_splines(self):
        items = [
            {"kind": "spline", "name": "linear", "shape_id": 2,
             "points": [(0, 0, 0), (1, 2, 3)], "cubic": False, "closed": False},
            {"kind": "spline", "name": "cubic", "shape_id": 3,
             "points": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 0, 0)],
             "cubic": True, "closed": True},
        ]
        data, _ = writer.build_shapes_bytes(items, seed=11, use_numpy=False)
        decoded = read_shapes_file(data)
        self.assertEqual([item["entity_type"] for item in decoded], [6, 2])
        self.assertEqual(decoded[0]["points"], [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0)])
        self.assertTrue(decoded[1]["closed"])

    def test_empty_shapes_file(self):
        data, _ = writer.build_shapes_bytes([], seed=0, use_numpy=False)
        self.assertEqual(read_shapes_file(data), [])

    def test_rejects_unsupported_version(self):
        data, _ = writer.build_shapes_bytes([], seed=0, use_numpy=False)
        with self.assertRaisesRegex(ShapesFormatError, "unsupported shapes version"):
            read_shapes_file(bytes([9]) + data[1:])

    def test_rejects_truncated_or_trailing_data(self):
        data, _ = writer.build_shapes_bytes([], seed=1, use_numpy=False)
        with self.assertRaises(ShapesFormatError):
            read_shapes_file(data[:-1])
        with self.assertRaisesRegex(ShapesFormatError, "trailing"):
            read_shapes_file(data + b"\0")


if __name__ == "__main__":
    unittest.main()
