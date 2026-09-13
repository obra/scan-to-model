"""Numerical contracts for reusable drawing geometry helpers."""

import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from drawing import (classify_selected_geometry, clipped, intersect_face,
                     coplanar_boundary_records, coplanar_boundary_segments,
                     line_segments, project)


class DrawingTests(unittest.TestCase):
    def test_classify_selected_geometry_detects_exact_world_point_collapse(self):
        vertices = np.array([[1.0, 2.0, 3.0]] * 4)
        polygons = [[0, 1, 2, 3]]

        result = classify_selected_geometry(vertices, polygons, [0])

        self.assertTrue(result['all_vertices_coincident'])
        self.assertTrue(result['finite'])
        self.assertEqual(result['unique_point_count'], 1)
        self.assertEqual(result['vertex_indices'], [0, 1, 2, 3])

    def test_classify_selected_geometry_ignores_unselected_faces(self):
        vertices = np.array([[1.0, 2.0, 3.0]] * 4 +
                             [[4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [10.0, 11.0, 12.0]])
        polygons = [[0, 1, 2, 3], [4, 5, 6]]

        result = classify_selected_geometry(vertices, polygons, [0])

        self.assertTrue(result['all_vertices_coincident'])
        self.assertEqual(result['unique_point_count'], 1)
        self.assertEqual(result['vertex_indices'], [0, 1, 2, 3])

    def test_classify_selected_geometry_does_not_call_edge_on_or_clipped_geometry_collapsed(self):
        vertices = np.array([[0.0, -1.0, 0.0], [0.0, 1.0, 0.0],
                             [1.0, 1.0, 0.0], [1.0, -1.0, 0.0]])
        polygons = [[0, 1, 2, 3]]

        result = classify_selected_geometry(vertices, polygons, [0])

        self.assertFalse(result['all_vertices_coincident'])
        self.assertTrue(result['finite'])
        self.assertEqual(result['unique_point_count'], 4)

    def test_project_uses_non_axis_aligned_right_and_up_bases(self):
        points = np.array([[1.0, 2.0, 3.0], [-1.0, 0.0, 2.0]])
        right = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)
        up = np.array([0.0, 0.0, 1.0])

        result = project(points, right, up)

        np.testing.assert_allclose(result, [[3.0 / np.sqrt(2.0), 3.0], [-1.0 / np.sqrt(2.0), 2.0]])
        self.assertEqual(result.shape, (2, 2))

    def test_clipped_convex_polygon_keeps_below_side_and_intersection_order(self):
        polygon = np.array([[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0],
                            [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0]])

        result = clipped(polygon, axis=0, value=0.0, keep_below=True)

        np.testing.assert_allclose(result, [[-1.0, -1.0, 0.0], [0.0, -1.0, 0.0],
                                             [0.0, 1.0, 0.0], [-1.0, 1.0, 0.0]])

    def test_clipped_convex_polygon_keeps_above_side(self):
        polygon = np.array([[-1.0, -1.0, 0.0], [1.0, -1.0, 0.0],
                            [1.0, 1.0, 0.0], [-1.0, 1.0, 0.0]])

        result = clipped(polygon, axis=0, value=0.0, keep_below=False)

        np.testing.assert_allclose(result, [[0.0, -1.0, 0.0], [1.0, -1.0, 0.0],
                                             [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]])

    def test_intersect_face_returns_convex_planar_cut_points(self):
        polygon = np.array([[-1.0, -1.0, -1.0], [1.0, -1.0, 1.0],
                            [1.0, 1.0, 1.0], [-1.0, 1.0, -1.0]])

        result = intersect_face(polygon, axis=2, value=0.0)

        self.assertEqual(len(result), 2)
        np.testing.assert_allclose(np.asarray(result), [[0.0, -1.0, 0.0], [0.0, 1.0, 0.0]])

    def test_line_segments_closes_polygon_and_preserves_two_point_segment(self):
        polygon = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])

        result = line_segments(polygon)

        self.assertEqual(len(result), 3)
        np.testing.assert_allclose(result[0], [[0.0, 0.0], [1.0, 0.0]])
        np.testing.assert_allclose(result[-1], [[1.0, 1.0], [0.0, 0.0]])
        segment = np.array([[2.0, 3.0], [4.0, 5.0]])
        self.assertEqual(len(line_segments(segment)), 1)
        np.testing.assert_allclose(line_segments(segment)[0], segment)

    def test_coplanar_boundary_segments_removes_shared_diagonal_from_concave_l(self):
        pieces = [
            np.array([[2, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 0]], float),
            np.array([[2, 0, 0], [2, 2, 0], [1, 2, 0], [1, 1, 0]], float),
        ]

        result = coplanar_boundary_segments(pieces)

        self.assertEqual(len(result), 6)
        self.assertFalse(any(np.allclose(edge, [[2, 0, 0], [1, 1, 0]]) or
                             np.allclose(edge, [[1, 1, 0], [2, 0, 0]])
                             for edge in result))

    def test_coplanar_boundary_segments_preserves_disjoint_patch_edges(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float),
            np.array([[3, 0, 0], [4, 0, 0], [4, 1, 0], [3, 1, 0]], float),
        ]

        self.assertEqual(len(coplanar_boundary_segments(pieces)), 8)

    def test_coplanar_boundary_segments_accepts_rotated_float32_planar_tiles(self):
        rotation = np.array([
            [0.90270109637546, 0.135368930289204, 0.408418882172334],
            [0.182986571299987, 0.738317559743762, -0.649155679092382],
            [-0.389418342308651, 0.660728714137938, 0.641709374239779],
        ])
        local_vertices = np.array([
            [0, 0, 0], [0.02, 0, 0], [0.02, 0.02, 0], [0, 0.02, 0],
            [1.02, 0, 0], [1.02, 0.02, 0],
        ])
        world_vertices = ((local_vertices @ rotation.T) + [8.0, -3.0, 5.0])
        world_vertices = world_vertices.astype(np.float32).astype(float)
        pieces = [world_vertices[[0, 1, 2, 3]], world_vertices[[1, 4, 5, 2]]]

        result = coplanar_boundary_segments(pieces)

        self.assertEqual(len(result), 6)

    def test_coplanar_boundary_records_matches_rotated_float32_adjacent_triangles_with_explicit_tolerance(self):
        rotation = np.array([
            [0.90270109637546, 0.135368930289204, 0.408418882172334],
            [0.182986571299987, 0.738317559743762, -0.649155679092382],
            [-0.389418342308651, 0.660728714137938, 0.641709374239779],
        ])

        def world(points):
            return (((np.asarray(points) @ rotation.T) + [8.0, -3.0, 5.0])
                    .astype(np.float32).astype(float))

        pieces = [
            world([[0, 0, 0], [1, 0, 0], [0, 1, 0]]),
            world([[1 + 2e-6, 0, 0], [1, 1, 0], [0, 1 + 2e-6, 0]]),
        ]
        expected = [
            (0, pieces[0][[0, 1]]),
            (0, pieces[0][[2, 0]]),
            (1, pieces[1][[0, 1]]),
            (1, pieces[1][[1, 2]]),
        ]

        records = coplanar_boundary_records(pieces, tolerance=5e-6)

        self.assertEqual([owner for owner, _ in records], [0, 0, 1, 1])
        for owner, segment in expected:
            self.assertTrue(any(record_owner == owner and
                                np.array_equal(record_segment, segment)
                                for record_owner, record_segment in records))
        self.assertEqual(len(records), 4)
        self.assertEqual(len(coplanar_boundary_segments(pieces, tolerance=5e-6)), 4)

    def test_coplanar_boundary_segments_default_tolerance_keeps_microscopic_real_gap(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float),
            np.array([[1 + 2e-7, 0, 0], [1, 1, 0], [0, 1 + 2e-7, 0]], float),
        ]

        self.assertEqual(len(coplanar_boundary_segments(pieces)), 6)
        self.assertEqual(len(coplanar_boundary_segments(pieces, tolerance=5e-6)), 4)

    def test_coplanar_boundary_segments_keeps_gap_larger_than_requested_tolerance(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float),
            np.array([[1 + 8e-6, 0, 0], [1, 1, 0], [0, 1 + 8e-6, 0]], float),
        ]

        self.assertEqual(len(coplanar_boundary_segments(pieces, tolerance=5e-6)), 6)

    def test_coplanar_boundary_records_preserves_input_owner_after_short_piece_filter(self):
        pieces = [
            np.array([[0, 0, 0]], float),
            np.array([[0, 0, 0], [1e-8, 0, 0]], float),
            np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float),
        ]

        records = coplanar_boundary_records(pieces)

        self.assertEqual(len(records), 4)
        self.assertEqual({owner for owner, _ in records}, {2})

    def test_coplanar_boundary_segments_does_not_split_on_nearby_vertex_from_same_piece(self):
        piece = np.array([
            [-0.002, 0.0007, 0],
            [-0.0044, -0.0005, 0],
            [0.0032, -0.0001, 0],
            [0.003210, -0.000097, 0],
        ], float)

        result = coplanar_boundary_segments([piece], tolerance=5e-6,
                                            line_tolerance=2e-6)

        self.assertEqual(len(result), 4)

    def test_coplanar_boundary_records_uses_explicit_supporting_line_tolerance(self):
        a = np.array([0, 0, 0.], float)
        b = np.array([9e-6, -5.4e-6, 0], float)
        c = np.array([1.3e-6, 2.2e-6, 0], float)
        d = np.array([4943e-6, -1951e-6, 0], float)
        pieces = [
            np.array([
                a, b, [0.01, 0.01, 0], [-0.01, 0.01, 0],
            ]),
            np.array([
                b, c, d, [0, -0.01, 0],
            ]),
        ]

        with self.assertRaisesRegex(ValueError, 'non-manifold'):
            coplanar_boundary_records(pieces, tolerance=5e-6,
                                      line_tolerance=5e-6)

        records = coplanar_boundary_records(
            pieces, tolerance=5e-6, line_tolerance=2e-6)

        self.assertEqual(len(records), 9)
        for owner, segment in records:
            source_edges = line_segments(pieces[owner])
            for point in segment:
                self.assertLessEqual(
                    min(np.linalg.norm(np.cross(point - edge[0], edge[1] - edge[0])) /
                        np.linalg.norm(edge[1] - edge[0]) for edge in source_edges),
                    1e-10)

    def test_coplanar_boundary_segments_rejects_duplicate_edge_from_same_owner(self):
        with self.assertRaisesRegex(ValueError, 'non-manifold'):
            coplanar_boundary_segments([
                np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0]], float),
            ])

    def test_coplanar_boundary_segments_rejects_nonfinite_or_nonpositive_tolerance(self):
        pieces = [np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)]
        for tolerance in (0.0, -1e-7, np.inf, np.nan):
            with self.assertRaisesRegex(ValueError, 'tolerance'):
                coplanar_boundary_segments(pieces, tolerance=tolerance)
        for line_tolerance in (0.0, -1e-7, np.inf, np.nan):
            with self.assertRaisesRegex(ValueError, 'line tolerance'):
                coplanar_boundary_segments(pieces, line_tolerance=line_tolerance)

    def test_coplanar_boundary_segments_preserves_skinny_float32_polygon_coordinates(self):
        rotation = np.array([
            [0.6417093742397794, -0.32151006762371553, 0.6963047863036593],
            [0.2713103718292879, 0.944348152154766, 0.18600335927002182],
            [-0.7173560908995228, 0.06955461119489617, 0.6932260777775765],
        ])
        local_vertices = np.array([
            [0, 0, 0], [0.001, 0, 0], [0.002, 0.001, 0], [1, 1, 0], [0, 1, 0],
        ])
        world_vertices = ((local_vertices @ rotation.T) + [8.0, -3.0, 5.0])
        world_vertices = world_vertices.astype(np.float32).astype(float)
        original_vertices = world_vertices.copy()

        result = coplanar_boundary_segments([world_vertices])

        self.assertEqual(len(result), 5)
        np.testing.assert_array_equal(world_vertices, original_vertices)

    def test_coplanar_boundary_segments_preserves_t_junction_boundary_splits(self):
        pieces = [
            np.array([[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]], float),
            np.array([[.5, 0, 0], [1.5, 0, 0], [1.5, -1, 0], [.5, -1, 0]], float),
        ]

        result = coplanar_boundary_segments(pieces)

        self.assertEqual(len(result), 8)
        self.assertFalse(any(np.allclose(edge, [[.5, 0, 0], [1.5, 0, 0]]) or
                             np.allclose(edge, [[1.5, 0, 0], [.5, 0, 0]])
                             for edge in result))

    def test_coplanar_boundary_segments_matches_rotated_float32_t_junction_with_explicit_tolerance(self):
        rotation = np.array([
            [0.6417093742397794, -0.32151006762371553, 0.6963047863036593],
            [0.2713103718292879, 0.944348152154766, 0.18600335927002182],
            [-0.7173560908995228, 0.06955461119489617, 0.6932260777775765],
        ])

        def world(points):
            return (((np.asarray(points) @ rotation.T) + [8.0, -3.0, 5.0])
                    .astype(np.float32).astype(float))

        pieces = [
            world([[0, 0, 0], [2, 0, 0], [2, 1, 0], [0, 1, 0]]),
            world([[.5 + 2e-6, 0, 0], [1.5 + 2e-6, 0, 0],
                   [1.5, -1, 0], [.5, -1, 0]]),
        ]

        result = coplanar_boundary_segments(pieces, tolerance=5e-6)

        self.assertEqual(len(result), 8)
        self.assertFalse(any(np.linalg.norm(edge[1] - edge[0]) <= 1e-7
                             for edge in result))

    def test_coplanar_boundary_segments_splits_line_at_following_t_junction(self):
        pieces = [
            np.array([[0, 0, 0], [2, 0, 0]], float),
            np.array([[1, 0, 0], [1, 1, 0]], float),
            np.array([[10, 10, 0], [11, 10, 0], [10, 11, 0]], float),
        ]

        result = coplanar_boundary_segments(pieces)

        self.assertEqual(len(result), 6)
        self.assertIn(np.array([[0, 0, 0], [1, 0, 0]]).tolist(), [edge.tolist() for edge in result])
        self.assertIn(np.array([[1, 0, 0], [2, 0, 0]]).tolist(), [edge.tolist() for edge in result])

    def test_coplanar_boundary_segments_rejects_collinear_polygon(self):
        with self.assertRaisesRegex(ValueError, 'non-degenerate'):
            coplanar_boundary_segments([
                np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0]], float),
            ])

    def test_coplanar_boundary_segments_rejects_plane_residual_over_one_micron(self):
        with self.assertRaisesRegex(ValueError, 'one plane'):
            coplanar_boundary_segments([
                np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 5e-6]], float),
            ])

    def test_coplanar_boundary_segments_rejects_non_coplanar_pieces(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float),
            np.array([[0, 1, 0], [1, 1, 0], [1, 2, 1], [0, 2, 1]], float),
        ]

        with self.assertRaisesRegex(ValueError, 'one plane'):
            coplanar_boundary_segments(pieces)

    def test_coplanar_boundary_segments_rejects_non_manifold_edge(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float),
            np.array([[1, 0, 0], [0, 0, 0], [0, -1, 0]], float),
            np.array([[0, 0, 0], [1, 0, 0], [0, -1, 0]], float),
        ]

        with self.assertRaisesRegex(ValueError, 'non-manifold'):
            coplanar_boundary_segments(pieces)

    def test_coplanar_boundary_segments_rejects_non_coplanar_line_piece(self):
        pieces = [
            np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0]], float),
            np.array([[0, 0, 1], [1, 0, 1]], float),
        ]

        with self.assertRaisesRegex(ValueError, 'not on the selected plane'):
            coplanar_boundary_segments(pieces)


if __name__ == '__main__':
    unittest.main()
