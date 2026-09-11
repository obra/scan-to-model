"""Behavior tests for saved architectural presentation contracts."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


def load_presentation():
    path = Path(__file__).resolve().parents[1] / "scripts" / "presentation.py"
    spec = importlib.util.spec_from_file_location("presentation_tested", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_workspace():
    parent = os.environ.get("SCAN_TO_MODEL_TEST_SCRATCH")
    if parent:
        Path(parent).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="presentation-", dir=parent))


def base_documents(root):
    samples = root / "samples"
    samples.mkdir()
    for name, color in (
        ("interior.png", (41, 73, 109)),
        ("upper.png", (131, 89, 47)),
        ("exterior.png", (67, 127, 83)),
    ):
        Image.new("RGB", (4, 3), color).save(samples / name)

    contract = {
        "schema_version": 1,
        "presentation": {
            "mode": "first-person-walkthrough",
            "eye_height_m": {"minimum": 1.45, "maximum": 1.75},
            "objects": [
                {"id": "current-shell", "disposition": "current-eligible"},
                {"id": "upper-furnishing", "disposition": "current-eligible"},
                {"id": "exterior-surface", "disposition": "current-eligible"},
                {"id": "retired-study", "disposition": "retired"},
                {"id": "source-overlay", "disposition": "excluded-source"},
            ],
            "renderer": {
                "allowed_engines": ["BLENDER_EEVEE", "CYCLES"],
                "material_mode": "materials-and-textures",
                "material_overrides": [{
                    "object_id": "current-shell",
                    "original_material_id": "original-glazing",
                    "render_material_id": "render-glazing",
                    "intent": "transparent-glazing",
                }],
                "required_material_ids": [
                    "wall-finish", "picture-surface", "render-glazing",
                ],
                "required_image_ids": ["picture-texture"],
            },
            "required_features": [
                {
                    "id": "interior-envelope",
                    "object_ids": ["current-shell"],
                    "view_intents": ["interior-route"],
                    "finding_id": "enclosure-opaque",
                    "minimum_visible_pixels": 4,
                    "minimum_projected_area_px2": 4,
                },
                {
                    "id": "upper-content",
                    "object_ids": ["upper-furnishing"],
                    "view_intents": ["upward-room-view"],
                    "finding_id": "upper-content-present",
                    "minimum_visible_pixels": 3,
                    "minimum_projected_area_px2": 3,
                },
                {
                    "id": "exterior-context",
                    "object_ids": ["exterior-surface"],
                    "view_intents": ["exterior-view"],
                    "finding_id": "exterior-present",
                    "minimum_visible_pixels": 2,
                    "minimum_projected_area_px2": 2,
                },
            ],
        },
    }

    shots = []
    sample_frames = []
    shot_values = [
        ("shot-interior", "interior-route", "interior.png", "current-shell", 12, "enclosure-opaque"),
        ("shot-upper", "upward-room-view", "upper.png", "upper-furnishing", 9, "upper-content-present"),
        ("shot-exterior", "exterior-view", "exterior.png", "exterior-surface", 7, "exterior-present"),
    ]
    for index, (shot_id, intent, filename, object_id, pixels, finding_id) in enumerate(shot_values):
        shots.append({
            "id": shot_id,
            "intent": intent,
            "scene_id": "presentation-scene",
            "view_layer_id": "presentation-layer",
            "camera_id": f"camera-{index}",
            "floor_reference_id": "entry-datum" if intent == "exterior-view" else f"floor-{index}",
            "eye_height_m": 1.6,
        })
        image_path = samples / filename
        sample_frames.append({
            "id": f"sample-{index}",
            "shot_id": shot_id,
            "frame_index": index * 10,
            "file": f"samples/{filename}",
            "sha256": sha256(image_path),
            "bytes": image_path.stat().st_size,
            "camera_elevation_m": 2.1 + index,
            "floor_elevation_m": 0.5 + index,
            "eye_height_m": 1.6,
            "visible_object_ids": [object_id],
            "material_ids": (
                ["wall-finish", "render-glazing"]
                if index == 0 else ["picture-surface"] if index == 1 else []
            ),
            "image_ids": ["picture-texture"] if index == 1 else [],
            "object_visibility": [{
                "object_id": object_id,
                "projected_bounds_px": [0, 0, 3, 2],
                "visible_pixels": pixels,
                "projected_area_px2": 6,
            }],
            "findings": {finding_id: "pass"},
        })

    coverage = {
        "schema_version": 1,
        "method": {
            "name": "synthetic-object-id-pass",
            "visible_pixels": "raster-count",
            "projected_area": "projected-bounds",
        },
        "sample_frames": sample_frames,
    }
    receipt = {
        "schema_version": 1,
        "contract_sha256": "",
        "run": {
            "command": ["blender", "--background", "--python", "render_presentation.py"],
            "model_sha256": "1" * 64,
            "script_sha256": "2" * 64,
            "blender_version": "Synthetic Blender 1.0",
        },
        "presentation_mode": "first-person-walkthrough",
        "renderer": {
            "engine": "BLENDER_EEVEE",
            "material_mode": "materials-and-textures",
            "material_overrides": copy.deepcopy(
                contract["presentation"]["renderer"]["material_overrides"]
            ),
        },
        "scene_audit": {
            "method": "explicit stable-ID scene traversal",
            "current_eligible_object_ids": [
                "current-shell", "exterior-surface", "upper-furnishing",
            ],
            "included_object_ids": [
                "current-shell", "exterior-surface", "upper-furnishing",
            ],
            "retired_object_ids": ["retired-study"],
            "excluded_source_object_ids": ["source-overlay"],
        },
        "shots": shots,
        "transitions": [
            {"from_shot_id": "shot-interior", "to_shot_id": "shot-upper", "type": "cut"},
            {"from_shot_id": "shot-upper", "to_shot_id": "shot-exterior", "type": "cut"},
        ],
        "coverage_file": {"path": "coverage.json", "sha256": ""},
    }
    return contract, receipt, coverage


def write_documents(root, contract, receipt, coverage):
    contract_path = root / "contract.json"
    coverage_path = root / "coverage.json"
    receipt_path = root / "receipt.json"
    contract_path.write_text(json.dumps(contract, indent=2) + "\n")
    coverage_path.write_text(json.dumps(coverage, indent=2) + "\n")
    receipt["contract_sha256"] = sha256(contract_path)
    receipt["coverage_file"]["sha256"] = sha256(coverage_path)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return contract_path, receipt_path


class PresentationContractTests(unittest.TestCase):
    def setUp(self):
        self.root = make_workspace()
        self.contract, self.receipt, self.coverage = base_documents(self.root)

    def validate(self):
        contract_path, receipt_path = write_documents(
            self.root, self.contract, self.receipt, self.coverage,
        )
        return load_presentation().validate_presentation(contract_path, receipt_path)

    def test_validates_first_person_route_and_rendered_sample_coverage(self):
        result = self.validate()

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["presentation_mode"], "first-person-walkthrough")
        self.assertEqual(result["eligible_objects"], 3)
        self.assertEqual(result["required_features"], 3)
        self.assertEqual(result["sample_frames"], 3)

    def test_accepts_repeated_command_arguments(self):
        self.receipt["run"]["command"] = [
            "blender", "--render-frame", "1", "--render-frame", "2",
        ]

        self.assertEqual(self.validate()["status"], "pass")

    def test_accepts_explicitly_textureless_contract(self):
        self.contract["presentation"]["renderer"]["required_image_ids"] = []
        for frame in self.coverage["sample_frames"]:
            frame["image_ids"] = []

        self.assertEqual(self.validate()["status"], "pass")

    def test_rejects_omitted_current_eligible_object(self):
        self.receipt["scene_audit"]["included_object_ids"].remove("upper-furnishing")

        with self.assertRaisesRegex(ValueError, "included object IDs"):
            self.validate()

    def test_rejects_incorrect_presentation_mode(self):
        self.receipt["presentation_mode"] = "cutaway-orbit"

        with self.assertRaisesRegex(ValueError, "presentation mode"):
            self.validate()

    def test_rejects_camera_outside_floor_relative_eye_height(self):
        self.receipt["shots"][0]["eye_height_m"] = 2.4
        self.coverage["sample_frames"][0]["eye_height_m"] = 2.4
        self.coverage["sample_frames"][0]["camera_elevation_m"] = 2.9

        with self.assertRaisesRegex(ValueError, "eye height"):
            self.validate()

    def test_rejects_negative_eye_height_range(self):
        self.contract["presentation"]["eye_height_m"] = {
            "minimum": -2.0,
            "maximum": -1.0,
        }

        with self.assertRaisesRegex(ValueError, "minimum eye height.*positive"):
            self.validate()

    def test_rejects_missing_required_texture_coverage(self):
        self.coverage["sample_frames"][1]["image_ids"] = []

        with self.assertRaisesRegex(ValueError, "required image IDs"):
            self.validate()

    def test_rejects_missing_required_material_coverage(self):
        self.coverage["sample_frames"][0]["material_ids"].remove("render-glazing")

        with self.assertRaisesRegex(ValueError, "required material IDs"):
            self.validate()

    def test_rejects_material_mode_that_does_not_render_textures(self):
        self.receipt["renderer"]["material_mode"] = "flat-color"

        with self.assertRaisesRegex(ValueError, "material mode"):
            self.validate()

    def test_rejects_renderer_that_cannot_render_textures(self):
        self.contract["presentation"]["renderer"]["allowed_engines"] = [
            "BLENDER_WORKBENCH",
        ]
        self.receipt["renderer"]["engine"] = "BLENDER_WORKBENCH"

        with self.assertRaisesRegex(ValueError, "allowed renderer engines"):
            self.validate()

    def test_rejects_undeclared_material_override(self):
        self.receipt["renderer"]["material_overrides"][0][
            "render_material_id"
        ] = "different-glazing"

        with self.assertRaisesRegex(ValueError, "material overrides"):
            self.validate()

    def test_rejects_material_override_for_noneligible_object(self):
        self.contract["presentation"]["renderer"]["material_overrides"][0][
            "object_id"
        ] = "retired-study"
        self.receipt["renderer"]["material_overrides"][0][
            "object_id"
        ] = "retired-study"

        with self.assertRaisesRegex(ValueError, "material override.*current-eligible"):
            self.validate()

    def test_rejects_empty_sample_coverage(self):
        self.coverage["sample_frames"] = []

        with self.assertRaisesRegex(ValueError, "sample frame"):
            self.validate()

    def test_rejects_crossfade_between_walkthrough_shots(self):
        self.receipt["transitions"][0]["type"] = "crossfade"

        with self.assertRaisesRegex(ValueError, "cut transitions"):
            self.validate()

    def test_rejects_retired_or_source_only_objects_in_render_set(self):
        self.receipt["scene_audit"]["included_object_ids"].append("retired-study")

        with self.assertRaisesRegex(ValueError, "included object IDs"):
            self.validate()

    def test_rejects_visibility_below_required_feature_threshold(self):
        self.coverage["sample_frames"][0]["object_visibility"][0]["visible_pixels"] = 3

        with self.assertRaisesRegex(ValueError, "interior-envelope"):
            self.validate()

    def test_rejects_raster_visibility_over_the_sample_pixel_budget(self):
        self.coverage["sample_frames"][0]["object_visibility"][0][
            "visible_pixels"
        ] = 13

        with self.assertRaisesRegex(ValueError, "sample-0.*pixel budget"):
            self.validate()

    def test_rejects_feature_without_current_eligible_objects(self):
        self.contract["presentation"]["required_features"][0]["object_ids"] = []

        with self.assertRaisesRegex(ValueError, "interior-envelope.*current-eligible"):
            self.validate()

    def test_rejects_feature_that_names_only_an_unmodeled_object(self):
        self.contract["presentation"]["required_features"][0]["object_ids"] = [
            "unmodeled-object",
        ]

        with self.assertRaisesRegex(ValueError, "interior-envelope.*current-eligible"):
            self.validate()

    def test_rejects_non_raster_visible_pixel_claim(self):
        self.coverage["method"]["visible_pixels"] = "ray-sample-estimate"

        with self.assertRaisesRegex(ValueError, "raster-count"):
            self.validate()

    def test_rejects_sample_file_whose_bytes_changed(self):
        (self.root / "samples" / "upper.png").write_bytes(b"not a png")

        with self.assertRaisesRegex(ValueError, "sample-1.*(size|SHA256)"):
            self.validate()

    def test_rejects_hash_bound_sample_that_is_not_decodable(self):
        sample_path = self.root / "samples" / "upper.png"
        sample_path.write_bytes(b"not a png")
        sample = self.coverage["sample_frames"][1]
        sample["bytes"] = sample_path.stat().st_size
        sample["sha256"] = sha256(sample_path)

        with self.assertRaisesRegex(ValueError, "sample-1.*decodable image"):
            self.validate()

    def test_command_writes_machine_readable_validation_receipt(self):
        contract_path, receipt_path = write_documents(
            self.root, self.contract, self.receipt, self.coverage,
        )
        output_path = self.root / "validation.json"
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "presentation.py"

        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script_path),
                "--contract",
                str(contract_path),
                "--receipt",
                str(receipt_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), json.loads(output_path.read_text()))
        self.assertEqual(json.loads(result.stdout)["status"], "pass")

    def test_command_does_not_replace_an_existing_validation_receipt(self):
        contract_path, receipt_path = write_documents(
            self.root, self.contract, self.receipt, self.coverage,
        )
        output_path = self.root / "validation.json"
        output_path.write_text("retained failed attempt\n")
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "presentation.py"

        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script_path),
                "--contract",
                str(contract_path),
                "--receipt",
                str(receipt_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output_path.read_text(), "retained failed attempt\n")

    def test_command_does_not_write_through_dangling_output_symlink(self):
        contract_path, receipt_path = write_documents(
            self.root, self.contract, self.receipt, self.coverage,
        )
        target_path = self.root / "escaped-validation.json"
        output_path = self.root / "validation-link.json"
        output_path.symlink_to(target_path)
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "presentation.py"

        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(script_path),
                "--contract",
                str(contract_path),
                "--receipt",
                str(receipt_path),
                "--output",
                str(output_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(target_path.exists())


if __name__ == "__main__":
    unittest.main(argv=[__file__])
