"""Tests for pure plane and planar-polygon comparison helpers."""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))


class SurfaceGeometryTests(unittest.TestCase):
    def test_rigid_plane_transform_preserves_signed_equation_residuals(self):
        from surfaces import transform_plane

        normal = np.array([1., 2., 3.])
        offset = 0.7
        angle = .37
        rotation = np.array([
            [np.cos(angle), -np.sin(angle), 0.],
            [np.sin(angle), np.cos(angle), 0.],
            [0., 0., 1.],
        ])
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = [2., -1., .5]
        points = np.array([[.2, 1.4, -.7], [3., -2., 1.], [-1., .5, 4.]])
        transformed_normal, transformed_offset = transform_plane(normal, offset, transform)
        transformed_points = points @ rotation.T + transform[:3, 3]
        np.testing.assert_allclose(
            transformed_points @ transformed_normal - transformed_offset,
            points @ normal - offset,
            atol=1e-12,
        )

    def test_concave_polygon_uses_orthogonal_projection_and_retains_points(self):
        from surfaces import compare_points_to_planar_polygons

        polygon = np.array([
            [0., 0., 0.], [4., 0., 0.], [4., 1., 0.],
            [1., 1., 0.], [1., 4., 0.], [0., 4., 0.],
        ])
        points = np.array([[.5, .5, .2], [2., 2., .2], [8., .5, .2]])
        result = compare_points_to_planar_polygons(points, [polygon])
        np.testing.assert_array_equal(result['overlap_mask'], [True, False, False])
        np.testing.assert_array_equal(result['overlap_indices'], [0])
        np.testing.assert_allclose(result['residuals'][0], .2)
        self.assertTrue(np.isnan(result['residuals'][1:]).all())
        self.assertEqual(result['statistics'], {'median': .2, 'p95': .2, 'max': .2})
        self.assertEqual(result['supporting_polygon'].tolist(), [0, -1, -1])

    def test_union_assigns_each_point_once_to_closest_supporting_plane(self):
        from surfaces import compare_points_to_planar_polygons

        lower = np.array([[0., 0., 0.], [2., 0., 0.], [2., 2., 0.], [0., 2., 0.]])
        upper = lower + [0., 0., .5]
        points = np.array([[1., 1., .1], [1., 1., .45]])
        result = compare_points_to_planar_polygons(points, [lower, upper])
        np.testing.assert_array_equal(result['overlap_mask'], [True, True])
        np.testing.assert_array_equal(result['supporting_polygon'], [0, 1])
        np.testing.assert_allclose(result['residuals'], [.1, -.05], atol=1e-12)
        self.assertEqual(result['overlap_count'], 2)
        self.assertEqual(result['normal_convention'], 'vertex-winding')
        self.assertEqual(result['statistics'], {'median': .075, 'p95': .0975, 'max': .1})

    def test_source_aligned_signs_override_polygon_winding(self):
        from surfaces import compare_points_to_planar_polygons

        clockwise = np.array([[0., 0., 0.], [0., 2., 0.], [2., 2., 0.], [2., 0., 0.]])
        result = compare_points_to_planar_polygons(
            np.array([[1., 1., .25]]), [clockwise], source_normal=[0., 0., 1.])
        self.assertEqual(result['normal_convention'], 'source-aligned')
        np.testing.assert_allclose(result['residuals'], [.25])

    def test_collinear_boundary_vertices_remain_valid(self):
        from surfaces import compare_points_to_planar_polygons

        polygon = np.array([
            [0., 0., 0.], [1., 0., 0.], [2., 0., 0.],
            [2., 2., 0.], [0., 2., 0.],
        ])
        result = compare_points_to_planar_polygons(
            np.array([[.5, .5, .1]]), [polygon])
        self.assertEqual(result['overlap_count'], 1)

        notched = np.array([
            [0., 0., 0.], [1., 0., 0.], [1., 1., 0.],
            [2., 1., 0.], [2., 0., 0.], [3., 0., 0.],
            [3., 2., 0.], [0., 2., 0.],
        ])
        result = compare_points_to_planar_polygons(
            np.array([[.5, .5, .1], [1.5, .5, .1], [2.5, .5, .1]]), [notched])
        np.testing.assert_array_equal(result['overlap_mask'], [True, False, True])

    def test_non_simple_ring_and_ambiguous_source_normal_are_rejected(self):
        from surfaces import _segments_intersect, compare_points_to_planar_polygons

        self.assertTrue(_segments_intersect(
            np.array([0., 0.]), np.array([2., 0.]),
            np.array([2., 0.]), np.array([3., 1.]), 1e-9))
        self.assertTrue(_segments_intersect(
            np.array([0., 0.]), np.array([3., 0.]),
            np.array([1., 0.]), np.array([2., 0.]), 1e-9))

        non_simple = np.array([
            [0., 0., 0.], [4., 0., 0.], [0., 4., 0.],
            [4., 4., 0.], [2., 1., 0.],
        ])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(np.zeros((1, 3)), [non_simple])
        touching = np.array([
            [0., 0., 0.], [4., 0., 0.], [4., 4., 0.], [0., 4., 0.],
            [0., 2., 0.], [2., 2., 0.], [2., 0., 0.],
            [2., -1., 0.], [0., 0., 0.],
        ])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(np.zeros((1, 3)), [touching])
        overlapping = np.array([
            [0., 0., 0.], [4., 0., 0.], [4., 4., 0.], [0., 4., 0.],
            [0., 0., 0.], [2., 0., 0.], [0., 0., 0.],
        ])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(np.zeros((1, 3)), [overlapping])
        square = np.array([
            [0., 0., 0.], [2., 0., 0.], [2., 2., 0.], [0., 2., 0.],
        ])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(
                np.array([[1., 1., .1]]), [square], source_normal=[1., 0., 0.])

    def test_zero_overlap_has_null_statistics(self):
        from surfaces import compare_points_to_planar_polygons

        polygon = np.array([[0., 0., 0.], [1., 0., 0.], [1., 1., 0.], [0., 1., 0.]])
        result = compare_points_to_planar_polygons(np.array([[4., 4., 2.]]), [polygon])
        self.assertEqual(result['overlap_count'], 0)
        self.assertIsNone(result['statistics'])
        self.assertTrue(np.isnan(result['residuals'][0]))
        empty = compare_points_to_planar_polygons(np.empty((0, 3)), [])
        self.assertEqual(empty['polygon_normals'].shape, (0, 3))
        self.assertEqual(empty['overlap_count'], 0)

    def test_invalid_plane_transform_points_and_polygons_are_rejected(self):
        from surfaces import compare_points_to_planar_polygons, transform_plane

        with self.assertRaises(ValueError):
            transform_plane([0., 0., 1.], 0., np.eye(3))
        nonrigid = np.eye(4)
        nonrigid[0, 0] = 2.
        with self.assertRaises(ValueError):
            transform_plane([0., 0., 1.], 0., nonrigid)
        with self.assertRaises(ValueError):
            transform_plane([np.nan, 0., 1.], 0., np.eye(4))
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(np.zeros((2, 2)), [])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(np.array([[np.inf, 0., 0.]]), [])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(
                np.zeros((1, 3)), [np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]])])
        with self.assertRaises(ValueError):
            compare_points_to_planar_polygons(
                np.zeros((1, 3)), [np.array([[0., 0., 0.], [1., 0., 0.],
                                              [1., 1., .1], [0., 1., 0.]])])


if __name__ == '__main__':
    unittest.main()
