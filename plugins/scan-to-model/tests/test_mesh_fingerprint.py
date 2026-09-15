import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


def reference_digest(values, format_code):
    payload = struct.pack('<' + format_code * len(values), *values)
    return hashlib.sha256(payload).hexdigest()


class MeshFingerprintTests(unittest.TestCase):
    def test_quad_matches_independent_little_endian_buffers(self):
        from mesh_fingerprint import geometry_fingerprints

        vertices = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        polygons = [(0, 1, 2, 3)]
        result = geometry_fingerprints(vertices, polygons)
        self.assertEqual(result, {
            'coordinates': reference_digest([value for vertex in vertices for value in vertex], 'f'),
            'corners': reference_digest([0, 1, 2, 3], 'i'),
            'face_starts': reference_digest([0], 'i'),
            'face_sizes': reference_digest([4], 'i'),
        })

    def test_coordinate_and_face_order_changes_are_detected(self):
        from mesh_fingerprint import geometry_fingerprints

        vertices = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        original = geometry_fingerprints(vertices, [(0, 1, 2, 3)])
        moved = geometry_fingerprints([(0, 0, 0), (1, 0, 0), (1, 1, 0.1), (0, 1, 0)],
                                      [(0, 1, 2, 3)])
        reordered = geometry_fingerprints(vertices, [(0, 3, 2, 1)])
        self.assertNotEqual(original['coordinates'], moved['coordinates'])
        self.assertNotEqual(original['corners'], reordered['corners'])

    def test_rejects_nonfinite_coordinates_and_invalid_indices(self):
        from mesh_fingerprint import geometry_fingerprints

        with self.assertRaisesRegex(ValueError, 'finite'):
            geometry_fingerprints([(0, 0, 0), (1, 0, 0), (float('nan'), 1, 0)], [(0, 1, 2)])
        with self.assertRaisesRegex(ValueError, 'indices'):
            geometry_fingerprints([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 3)])


if __name__ == '__main__':
    unittest.main()
