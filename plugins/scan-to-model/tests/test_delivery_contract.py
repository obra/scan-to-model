"""Validate delivery intent, source closure and reusable frozen helper identities."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from delivery_contract import check_inputs, digest, load_job, validate
from delivery_runtime import freeze_helpers


def job():
    return {"schema_version": 1, "title": "Synthetic room", "deliverables": ["native"],
            "intent": {"interpolation_authorized": True, "basis": "Make a rendered approximation",
                       "geometry_status": "tentative", "metric_status": "synthetic dimensions"},
            "objects": [{"id": "floor", "name": "Floor", "room": "room", "level": "lower", "role": "floor"}],
            "sources": [], "materials": [], "views": []}


class DeliveryContractTests(unittest.TestCase):
    def test_geometry_only_request_does_not_require_presentation(self):
        data = job()
        data["intent"]["interpolation_authorized"] = False
        self.assertEqual(validate(data)["deliverables"], ["native"])
        self.assertEqual(data["views"], [])

    def test_unknown_sources_and_unauthorized_inference_are_rejected(self):
        data = job()
        data["materials"] = [{"id": "paint", "method": "inferred", "color": [200, 200, 200], "basis": "unknown paint"}]
        data["intent"]["interpolation_authorized"] = False
        with self.assertRaises(ValueError):
            validate(data)
        data["intent"]["interpolation_authorized"] = True
        data["materials"][0].update(method="matched-color", sources=["absent"])
        with self.assertRaises(ValueError):
            validate(data)

    def test_view_requires_real_subjects_and_native_camera(self):
        data = job()
        data["deliverables"] = ["viewer"]
        with self.assertRaises(ValueError):
            validate(data)
        data["views"] = [{"id": "room", "camera": "Camera", "required_objects": ["absent"]}]
        with self.assertRaises(ValueError):
            validate(data)
        data["views"][0]["required_objects"] = ["floor"]
        validate(data)

    def test_source_hashes_are_resolved_relative_to_job_and_rechecked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "model.blend").write_bytes(b"fixture identity only")
            (root / "source.png").write_bytes(b"fixture source identity only")
            data = job()
            data.update(model="model.blend", model_sha256=digest(root / "model.blend"))
            data["sources"] = [{"id": "source", "image": "source.png", "image_sha256": digest(root / "source.png")}]
            path = root / "job.json"
            path.write_text(json.dumps(data))
            resolved, inputs = load_job(path)
            self.assertEqual(resolved["model"], str(root / "model.blend"))
            check_inputs(inputs)
            (root / "source.png").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                check_inputs(inputs)
            with self.assertRaises(ValueError):
                load_job(path)

    def test_distinct_outputs_are_explicit_and_duplicate_names_fail(self):
        data = job()
        data["deliverables"] = ["native", "sources"]
        validate(data)
        data["objects"].append({**copy.deepcopy(data["objects"][0]), "id": "second"})
        with self.assertRaises(ValueError):
            validate(data)

    def test_helpers_are_deduplicated_by_bytes_and_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            helper = root / "helper.py"
            helper.write_text("value = 1\n")
            first, hashes = freeze_helpers(root / "frozen", [helper])
            second, _ = freeze_helpers(root / "frozen", [helper])
            self.assertEqual(first, second)
            helper.write_text("value = 2\n")
            third, _ = freeze_helpers(root / "frozen", [helper])
            self.assertNotEqual(first, third)
            (third / helper.name).write_text("tampered\n")
            with self.assertRaises(ValueError):
                freeze_helpers(root / "frozen", [helper])


if __name__ == "__main__":
    unittest.main()
