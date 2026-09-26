"""Exercise photographic sampling, lighting placement and atlas budgets."""

from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import appearance


class AppearanceTests(unittest.TestCase):
    def source(self):
        return {"camera": {"width": 8, "height": 8, "fx": 4, "fy": 4, "cx": 4, "cy": 4},
                "camera_to_world": np.eye(4).tolist(), "depth_pixels": np.full((4, 4), 2000),
                "confidence_pixels": np.full((4, 4), 255), "rgb": np.full((8, 8, 3), [140, 100, 60], dtype=np.uint8)}

    def test_projection_and_depth_reject_wrong_surface_missing_confidence_and_mask(self):
        source = self.source()
        points = [[0, 0, -2], [1, 1, -2], [0, 0, 1], [0, 0, -3]]
        uv, depth, valid = appearance.project(points, source["camera"], source["camera_to_world"])
        np.testing.assert_allclose(uv[:2], [[4, 4], [6, 2]])
        visible, _ = appearance.depth_visibility(uv, depth, valid, source, .1)
        np.testing.assert_array_equal(visible, [True, True, False, False])
        source["confidence_pixels"][1, 3] = 0
        source["mask_pixels"] = np.full((8, 8), 255)
        source["mask_pixels"][4, 4] = 0
        visible, _ = appearance.depth_visibility(uv, depth, valid, source, .1)
        self.assertFalse(visible.any())

    def test_projected_coverage_excludes_masked_pixels_and_keeps_declared_fallback(self):
        source = self.source()
        source["mask_pixels"] = np.full((8, 8), 255)
        source["mask_pixels"][:, :4] = 0
        material = {"method": "photo-projection", "sources": ["photo"], "color": [50, 60, 70]}
        pixels, record = appearance.bake_face([[-1, -1, -2], [1, -1, -2], [1, 1, -2], [-1, 1, -2]],
                                               material, {"photo": source}, [32, 32])
        self.assertGreater(record["photo_coverage"], .25)
        self.assertLess(record["photo_coverage"], .9)
        colors = set(map(tuple, pixels.reshape(-1, 3)))
        self.assertEqual(colors, {(50, 60, 70), (140, 100, 60)})

    def test_repeated_coordinates_continue_across_separate_faces(self):
        mapping = {"origin": [0, 0, 0], "u": [1, 0, 0], "v": [0, 1, 0], "size_m": [1, 2]}
        uv = appearance.repeated_coordinates([[.25, 1, 0], [1.75, 1, 0], [2.25, 1, 0]], mapping, (21, 11, 3))
        np.testing.assert_allclose(uv, [[2.5, 10]]*3)

    def test_rectification_samples_actual_corners_and_rejects_crossed_quad(self):
        pixels = np.zeros((16, 16, 3))
        pixels[:, :, 0] = np.arange(16)
        pixels[:, :, 1] = np.arange(16)[:, None]
        sample = appearance.rectify_sample(pixels, [[2, 3], [12, 3], [10, 13], [4, 13]], 8)
        np.testing.assert_allclose(sample[0, 0, :2], [2, 3])
        np.testing.assert_allclose(sample[-1, -1, :2], [10, 13])
        with self.assertRaises(ValueError):
            appearance.rectify_sample(pixels, [[2, 3], [10, 13], [12, 3], [4, 13]])

    def test_constant_paint_and_inferred_detail_normalization(self):
        pixels = np.broadcast_to(np.linspace(40, 200, 80)[None, :, None], (80, 80, 3)).copy()
        result = appearance.normalize_detail(pixels, [100, 150, 200], .05)
        self.assertLessEqual(np.max(np.abs(result / [100, 150, 200] - 1)), .050001)

    def test_atlas_reduces_density_before_allocating_and_refuses_impossible_budget(self):
        plan = appearance.plan_atlas([[4, 3]]*8, 128, 16, 512)
        self.assertLess(plan["density"], 128)
        self.assertTrue(plan["attempts"][-1]["fits"])
        for x, y, width, height in plan["rectangles"]:
            self.assertLessEqual(x + width + plan["padding"], plan["size"][0])
            self.assertLessEqual(y + height + plan["padding"], plan["size"][1])
        with self.assertRaises(ValueError):
            appearance.plan_atlas([[100, 100]], 32, 16, 128)

    def test_mixed_face_sizes_keep_density_and_source_order_without_overlap(self):
        extents = [[28, 26], [27, 2], [26, 28], [25, 3], [24, 24], [23, 2]]
        plan = appearance.plan_atlas(extents, 1, 1, 64, padding=1)
        self.assertEqual(plan["density"], 1)
        self.assertEqual([rectangle[2:] for rectangle in plan["rectangles"]], extents)
        occupied = np.zeros((plan["size"][1], plan["size"][0]), dtype=bool)
        for x, y, width, height in plan["rectangles"]:
            self.assertGreaterEqual(min(x, y), 1)
            self.assertLessEqual(x + width + 1, occupied.shape[1])
            self.assertLessEqual(y + height + 1, occupied.shape[0])
            tile = occupied[y-1:y+height+1, x-1:x+width+1]
            self.assertFalse(tile.any())
            tile[:] = True

    def test_light_uses_ceiling_at_its_position_not_lowest_eave(self):
        mesh = {"vertices": [[0, 0, 1], [4, 0, 3], [4, 4, 3], [0, 4, 1]], "faces": [[0, 1, 2, 3]]}
        self.assertAlmostEqual(appearance.ceiling_height_at([mesh], 3, 2, 0), 2.5)
        self.assertIsNone(appearance.ceiling_height_at([mesh], 5, 2, 0))


if __name__ == "__main__":
    unittest.main()
