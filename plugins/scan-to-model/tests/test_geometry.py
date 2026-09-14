"""Focused contracts for explicit planar manufactured geometry."""

import unittest
from itertools import combinations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class GeometryTests(unittest.TestCase):
    def test_plane_point_uses_outward_depth_and_local_tangent_coordinates(self):
        from geometry import plane_point

        point = plane_point(
            tangent=(0.0, 1.0),
            normal=(-1.0, 0.0),
            plane_constant=2.0,
            u=3.0,
            z=4.0,
            depth=0.25,
        )

        self.assertEqual(point, (-2.25, 3.0, 4.0))

    def test_solid_bar_has_outward_front_and_positive_volume(self):
        from geometry import solid_bar

        shape = solid_bar(
            tangent=(1.0, 0.0),
            normal=(0.0, 1.0),
            plane_constant=0.0,
            u_bounds=(1.0, 2.0),
            z_bounds=(3.0, 4.0),
            depth=0.1,
        )

        self.assertGreater(shape["volume"], 0.0)
        self.assertEqual(shape["front_normal"], (0.0, 1.0, 0.0))
        centroid = tuple(sum(vertex[axis] for vertex in shape["vertices"]) / len(shape["vertices"]) for axis in range(3))
        signed_volume = 0.0
        for face in shape["faces"]:
            points = [shape["vertices"][index] for index in face]
            edge_a = [points[1][axis] - points[0][axis] for axis in range(3)]
            edge_b = [points[2][axis] - points[0][axis] for axis in range(3)]
            normal = (
                edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
                edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
                edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
            )
            face_centroid = tuple(sum(point[axis] for point in points) / len(points) for axis in range(3))
            self.assertGreater(sum(normal[axis] * (face_centroid[axis] - centroid[axis]) for axis in range(3)), 0.0)
            for index in range(1, len(points) - 1):
                cross = (
                    points[index][1] * points[index + 1][2] - points[index][2] * points[index + 1][1],
                    points[index][2] * points[index + 1][0] - points[index][0] * points[index + 1][2],
                    points[index][0] * points[index + 1][1] - points[index][1] * points[index + 1][0],
                )
                signed_volume += sum(points[0][axis] * cross[axis] for axis in range(3)) / 6.0
        self.assertAlmostEqual(signed_volume, shape["volume"], places=12)

    def test_panel_quad_rejects_wrong_handed_basis(self):
        from geometry import panel_quad

        with self.assertRaisesRegex(ValueError, "handed"):
            panel_quad((1.0, 0.0), (0.0, -1.0), 0.0, (0.0, 1.0), (0.0, 1.0))

    def test_four_bars_are_disjoint_and_outside_aperture(self):
        from geometry import aperture_bars

        width = 0.08
        bars = aperture_bars(
            aperture_u=(5.0, 7.0),
            aperture_z=(2.0, 4.0),
            width=width,
            outer_u=(4.5, 7.5),
            outer_z=(1.5, 4.5),
        )

        self.assertEqual([bar["id"] for bar in bars], ["left", "right", "sill", "head"])
        self.assertEqual(bars[0]["u_bounds"], (4.92, 5.0))
        self.assertEqual(bars[1]["u_bounds"], (7.0, 7.08))
        self.assertEqual(bars[2]["u_bounds"], (4.92, 7.08))
        self.assertEqual(bars[3]["u_bounds"], (4.92, 7.08))
        self.assertEqual([bar["margin_m"] for bar in bars], [0.5, 0.5, 0.5, 0.5])
        for left, right in combinations(bars, 2):
            u_overlap = max(0.0, min(left["u_bounds"][1], right["u_bounds"][1]) - max(left["u_bounds"][0], right["u_bounds"][0]))
            z_overlap = max(0.0, min(left["z_bounds"][1], right["z_bounds"][1]) - max(left["z_bounds"][0], right["z_bounds"][0]))
            self.assertEqual(u_overlap * z_overlap, 0.0)

        area = sum((bar["u_bounds"][1] - bar["u_bounds"][0]) * (bar["z_bounds"][1] - bar["z_bounds"][0]) for bar in bars)
        self.assertAlmostEqual(area, (2.0 + 2 * width) * (2.0 + 2 * width) - 2.0 * 2.0)

        with self.assertRaisesRegex(ValueError, "outer margin"):
            aperture_bars((5.0, 7.0), (2.0, 4.0), width, (4.95, 7.05), (1.5, 4.5))

        with self.assertRaisesRegex(ValueError, "outer margin"):
            aperture_bars((5.0, 7.0), (2.0, 4.0), width, (4.5, 7.5), (1.5, 4.05))

        with self.assertRaisesRegex(ValueError, "outer margin"):
            aperture_bars((5.0, 7.0), (2.0, 4.0), width, (4.5, 7.5), (1.95, 4.5))


if __name__ == "__main__":
    unittest.main()
