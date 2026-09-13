"""Tests for finite multi-view ray intersection diagnostics."""

import importlib.util
from pathlib import Path
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("multiview", ROOT / "scripts" / "multiview.py")
multiview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multiview)


class MultiviewRayTests(unittest.TestCase):
    def test_intersecting_rays_recover_common_point(self):
        point = np.array([1.0, 2.0, 3.0])
        origins = np.array([[0, 0, 0], [2, 2, 0], [1, 0, 3]], dtype=float)
        result = multiview.solve_rays(origins, point - origins)
        np.testing.assert_allclose(result["point"], point, atol=1e-12)
        self.assertEqual(result["status"], "ok")

    def test_skew_rays_report_residuals_and_positive_distances(self):
        origins = np.array([[0, 0, 0], [0, 1, 0], [1, 0, 0]], dtype=float)
        directions = np.array([[1, 0, 1], [1, -0.1, 1], [-0.1, 1, 1]], dtype=float)
        result = multiview.solve_rays(origins, directions)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(all(value > 0 for value in result["along_ray_distances_m"]))
        self.assertTrue(any(value > 0 for value in result["perpendicular_residuals_m"]))

    def test_parallel_rays_are_marked_degenerate(self):
        origins = np.array([[0, 0, 0], [1, 0, 0]], dtype=float)
        directions = np.array([[0, 0, 1], [0, 0, 1]], dtype=float)
        result = multiview.solve_rays(origins, directions)
        self.assertEqual(result["status"], "degenerate")
        self.assertEqual(result["rank"], 2)

    def test_behind_origin_distance_is_visible(self):
        origins = np.array([[0, 0, 0], [1, 0, 2]], dtype=float)
        directions = np.array([[0, 0, 1], [1, 0, 1]], dtype=float)
        result = multiview.solve_rays(origins, directions)
        self.assertLess(result["along_ray_distances_m"][1], 0)
        self.assertEqual(result["status"], "ok")


if __name__ == "__main__":
    unittest.main()
