"""Check real geometric failure cases without changing the supplied mesh."""

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from mesh_quality import review_meshes


def quad(ident, x=0, z=0):
    return {"id": ident, "vertices": [[x, 0, z], [x+2, 0, z], [x+2, 2, z], [x, 2, z]],
            "faces": [[0, 1, 2, 3]], "triangles": [{"face": 0, "vertices": [0, 1, 2]}, {"face": 0, "vertices": [0, 2, 3]}]}


class MeshQualityTests(unittest.TestCase):
    def test_partial_coplanar_overlap_is_reported_without_mutation(self):
        meshes = [quad("trim-a"), quad("trim-b", x=1)]
        before = copy.deepcopy(meshes)
        result = review_meshes(meshes)
        self.assertFalse(result["passed"])
        finding, = result["findings"]
        self.assertEqual(finding["kind"], "coplanar_overlap")
        self.assertAlmostEqual(finding["area_m2"], 2)
        self.assertEqual(meshes, before)

    def test_shared_edge_open_surfaces_and_separate_planes_are_allowed(self):
        self.assertTrue(review_meshes([quad("left"), quad("right", x=2), quad("above", z=.01)])["passed"])

    def test_degenerate_face_and_wrong_edge_winding_are_reported(self):
        mesh = quad("broken")
        mesh["faces"] += [[0, 1, 2], [0, 0, 1]]
        kinds = {row["kind"] for row in review_meshes([mesh])["findings"]}
        self.assertIn("degenerate_face", kinds)
        self.assertIn("inconsistent_winding_or_nonmanifold", kinds)

    def test_opposed_contact_is_reviewable_without_automatic_geometry_rejection(self):
        first, second = quad("surface"), quad("contact")
        second["faces"] = [list(reversed(face)) for face in second["faces"]]
        for triangle in second["triangles"]:
            triangle["vertices"].reverse()
        result = review_meshes([first, second])
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["contacts_for_review"]), 1)
        self.assertAlmostEqual(result["contacts_for_review"][0]["area_m2"], 4)


if __name__ == "__main__":
    unittest.main()
