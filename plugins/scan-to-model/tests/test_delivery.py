"""Check raster material use and review identity against actual saved data."""

import copy
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from delivery import audit_rasters, validate_review
from delivery_contract import digest, write_json


class DeliveryTests(unittest.TestCase):
    def test_required_object_with_wrong_render_material_fails_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "view"
            folder.mkdir()
            Image.new("RGB", (4, 4), "white").save(folder / "view.png")
            job = {"views": [{"id": "view", "required_objects": ["wall"], "minimum_pixels": 8}]}
            assignments = [{"object": "wall", "material": "Photo wall"}]
            for material, expected in [(2, False), (1, True)]:
                np.savez_compressed(folder / "raster.npz", object=np.ones((4, 4), dtype=np.int32),
                                    material=np.full((4, 4), material, dtype=np.int32))
                write_json(folder / "render.json", {"resolution": [4, 4], "object_ids": {"1": "wall"},
                    "material_ids": {"1": "Photo wall", "2": "Override"}, "model_sha256": "model",
                    "image_sha256": digest(folder / "view.png"), "raster_sha256": digest(folder / "raster.npz")})
                coverage, = audit_rasters(root, job, assignments)
                self.assertEqual(coverage["passed"], expected)
                self.assertEqual(coverage["object_material_pixels"]["wall"], 16 if expected else 0)

    def test_visual_review_cannot_accept_changed_image_or_missing_subject(self):
        views = [{"id": "view", "image_sha256": "image", "passed": True}]
        review = {"model_sha256": "model", "geometry": {"finding": "pass", "note": "Inspected fixture"},
                  "views": [{"id": "view", "image_sha256": "image", "finding": "pass", "note": "Subject visible"}]}
        validate_review(review, "model", views)
        for key, value in [("image_sha256", "changed"), ("finding", "pending"), ("note", "")]:
            candidate = copy.deepcopy(review)
            candidate["views"][0][key] = value
            with self.assertRaises(ValueError):
                validate_review(candidate, "model", views)
        with self.assertRaises(ValueError):
            validate_review(review, "model", [{**views[0], "passed": False}])

    def test_mixed_geometry_status_does_not_claim_survey_acceptance(self):
        review = {"model_sha256": "model", "geometry": {"finding": "pending", "note": "File hashes pass"}, "views": []}
        with self.assertRaises(ValueError):
            validate_review(review, "model", [])


if __name__ == "__main__":
    unittest.main()
