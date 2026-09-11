"""Synthetic geometry and input contracts for manufactured rectangles."""

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def spec(controls, **overrides):
    result = {
        "frame_id": "synthetic-plane",
        "units": "uncalibrated",
        "frame": {"origin": [0, 0], "u_axis": [1, 0]},
        "rectangles": [{"id": "front", "controls": controls,
                        "evidence": {"shape": "invented", "scale": "unknown"}}],
    }
    result.update(overrides)
    return result


class ManufacturedTests(unittest.TestCase):
    def fit(self, data):
        self.assertIsNotNone(importlib.util.find_spec("manufactured"),
                             "Reusable rectangle fit is not implemented")
        from manufactured import fit_rectangles
        return fit_rectangles(data)

    def test_fixed_frame_removes_skew_and_preserves_controls(self):
        data = spec([[0, 0], [4, 1], [5, 3], [1, 2]])
        before = copy.deepcopy(data)
        result = self.fit(data)
        row = result["rectangles"][0]
        np.testing.assert_allclose(row["corners"], [[.5, .5], [4.5, .5], [4.5, 2.5], [.5, 2.5]])
        self.assertEqual((row["width"], row["height"]), (4, 2))
        np.testing.assert_allclose(row["residuals"], [[.5, .5], [.5, -.5], [-.5, -.5], [-.5, .5]])
        np.testing.assert_allclose(row["errors"], [2**-.5]*4)
        self.assertEqual(result["input"], before)
        self.assertEqual(row["controls"], before["rectangles"][0]["controls"])
        self.assertEqual(data, before)
        result["input"]["rectangles"][0]["evidence"]["scale"] = "changed"
        self.assertEqual(data, before)

    def test_fitted_orientation_and_fixed_frame_reuse(self):
        # A 3-4-5 rotation with independently sized and positioned rectangles.
        data = spec([[0, 0], [3.2, 2.4], [2, 4], [-1.2, 1.6]], fit_orientation=True)
        data["rectangles"].append({"id": "plate", "controls": [[8, 6], [9.6, 7.2], [7.8, 9.6], [6.2, 8.4]]})
        result = self.fit(data)
        np.testing.assert_allclose(result["frame"]["u_axis"], [.8, .6], atol=1e-12)
        np.testing.assert_allclose(result["frame"]["v_axis"], [-.6, .8], atol=1e-12)
        for row, expected in zip(result["rectangles"], [(4, 2), (2, 3)]):
            np.testing.assert_allclose([row["width"], row["height"]], expected, atol=1e-12)
            np.testing.assert_allclose(row["errors"], 0, atol=1e-12)
        reused = self.fit(spec(data["rectangles"][1]["controls"], frame=result["frame"]))
        np.testing.assert_allclose(reused["rectangles"][0]["corners"], data["rectangles"][1]["controls"], atol=1e-12)

    def test_translation_and_units_do_not_change_shape(self):
        data = spec([[100, -80], [108, -80], [108, -76], [100, -76]],
                    frame={"origin": [99, -81], "u_axis": [1, 0]}, units="mm")
        row = self.fit(data)["rectangles"][0]
        self.assertEqual(row["local_bounds"], [[1, 1], [9, 5]])
        self.assertEqual((row["width"], row["height"]), (8, 4))
        np.testing.assert_allclose(row["errors"], 0)

    def test_rejects_invalid_specs(self):
        valid = spec([[0, 0], [4, 0], [4, 2], [0, 2]])
        cases = [None, {}, spec([]), spec([[0, 0]]*4),
                 spec([[0, 0], [4, 0], [4, 0], [0, 0]]),
                 spec([[0, 0], [4, 2], [4, 0], [0, 2]]),
                 spec([[0, 0], [0, 2], [4, 2], [4, 0]]),
                 spec([[0, 0], [4, 0], [1, .1], [0, 2]]),
                 spec([[0, 0], [4, 0], [4, float("nan")], [0, 2]]),
                 spec([[0, 0], [4, 0], [4, float("inf")], [0, 2]])]
        for changes in [{"frame_id": ""}, {"units": ""}, {"fit_orientation": "yes"},
                        {"frame": {"origin": [0, 0], "u_axis": [0, 0]}},
                        {"frame": {"origin": [0, 0], "u_axis": [2, 0]}},
                        {"frame": {"origin": [0, float("inf")], "u_axis": [1, 0]}},
                        {"rectangles": []}, {"rectangles": [valid["rectangles"][0]]*2}]:
            cases.append({**valid, **changes})
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.fit(data)


if __name__ == "__main__":
    unittest.main()
