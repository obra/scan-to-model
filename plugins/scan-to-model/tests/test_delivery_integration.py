"""Run real Blender, npm and offline Chromium on invented public geometry.

The generated pass notes authorize fixture assertions only. They are not a substitute
for source comparison or visual review of production deliverables.
"""

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from delivery import read
from delivery_contract import digest, write_json
from delivery_runtime import run_worker
from glb_delivery import check_glb


def fixture_review(template, destination):
    review = read(template)
    for row in [review["geometry"], *review["views"]]:
        row.update(finding="pass", note="Automated synthetic fixture contract only; not a visual or metric acceptance.")
    write_json(destination, review)
    return review


def rewrite_glb(source, destination, mutate):
    payload = source.read_bytes()
    size, = struct.unpack_from("<I", payload, 12)
    data = json.loads(payload[20:20+size])
    mutate(data)
    encoded = json.dumps(data, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary_chunk = payload[20+size:]
    destination.write_bytes(struct.pack("<4sII", b"glTF", 2, 20+len(encoded)+len(binary_chunk)) +
                            struct.pack("<II", len(encoded), 0x4E4F534A) + encoded + binary_chunk)


@unittest.skipUnless(os.environ.get("SCAN_TO_MODEL_DELIVERY_BLENDER"), "set SCAN_TO_MODEL_DELIVERY_BLENDER for the full delivery fixture")
class DeliveryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blender = os.environ["SCAN_TO_MODEL_DELIVERY_BLENDER"]
        retained = os.environ.get("SCAN_TO_MODEL_DELIVERY_TEST_OUTPUT")
        cls.temporary = None if retained else tempfile.TemporaryDirectory(prefix="stm-delivery-tests-")
        cls.root = Path(retained or cls.temporary.name).resolve()
        cls.root.mkdir(parents=True, exist_ok=not retained)

    @classmethod
    def tearDownClass(cls):
        if cls.temporary:
            cls.temporary.cleanup()

    def fixture(self, name, case="clean"):
        root = self.root / name
        run_worker(self.blender, ROOT / "tests/delivery_fixture.py", ["--output", root, "--case", case],
                   self.root / (name + "-creation"))
        return root

    def cli(self, *arguments, success=True):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/delivery.py"), *map(str, arguments)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def test_complete_delivery_is_portable_and_reuses_unchanged_work(self):
        source = self.fixture("clean")
        original = {file: digest(file) for file in source.iterdir() if file.is_file()}
        prepared, output = self.root / "prepared", self.root / "delivered"
        self.cli("prepare", "--job", source / "job.json", "--output", prepared, "--blender", self.blender)
        self.assertTrue(read(prepared / "readback/checks.json")["passed"])
        appearance = read(prepared / "appearance.json")
        photo = next(row for row in appearance["faces"] if row["object"] == "poster")
        self.assertGreater(photo["photo_coverage"], .5)
        self.assertLess(photo["photo_coverage"], 1)
        self.assertAlmostEqual(appearance["lights"][0]["position"][2], 2.65, places=5)
        review = prepared / "fixture-review.json"
        fixture_review(prepared / "review-template.json", review)
        self.cli("finish", "--prepared", prepared, "--review", review, "--output", output, "--blender", self.blender)
        self.assertEqual(read(output / "glb-checks.json")["object_count"], 17)
        self.assertEqual({row["id"] for row in read(output / "sources.json")}, {"synthetic-photo", "grain"})
        self.assertTrue((output / "viewer.bundle.js.LEGAL.txt").is_file())
        final = output / "fixture-review.json"
        fixture_review(output / "final-review-template.json", final)
        self.cli("verify", "--output", output, "--review", final)
        checks = read(output / "delivery-checks.json")
        browser = checks["browser"]
        self.assertTrue(browser["network_disabled"] and browser["copied_delivery_tested"])
        self.assertEqual(browser["object_count"], 17)
        self.assertEqual(browser["tour_images_loaded"], ["studio", "washroom"])
        self.assertEqual(browser["external_requests"], [])
        self.assertGreater(browser["flight_distance_m"], .01)
        self.assertGreater(browser["touch_distance_m"], .01)
        reused = self.cli("verify", "--output", output, "--review", final)
        self.assertTrue(reused["reused_unchanged_checks"])
        self.assertEqual(len(list(output.glob("browser-check*"))), 1)

        receipts = [*prepared.glob("*-receipt.json"), *prepared.glob("viewer-build/*/viewer-build.json")]
        timestamps = {file: file.stat().st_mtime_ns for file in receipts}
        self.cli("finish", "--prepared", prepared, "--review", review, "--output", self.root / "repackaged", "--blender", self.blender)
        self.assertEqual({file: file.stat().st_mtime_ns for file in receipts}, timestamps)
        self.assertEqual(len(list((prepared / "runs/helpers").iterdir())), 1)
        self.assertEqual({file: digest(file) for file in original}, original)

        # Remove every input image from its original location before reopening the copy.
        hidden = source / "hidden-images"
        hidden.mkdir()
        images = list(source.glob("*.png"))
        try:
            for file in images:
                file.rename(hidden / file.name)
            run_worker(self.blender, ROOT / "scripts/blender_delivery.py",
                       ["--phase", "readback", "--job", prepared / "job.json", "--appearance", prepared / "appearance.json",
                        "--native", prepared / "apply/native.json", "--output", self.root / "portable-readback"],
                       self.root / "portable-runtime", blend=output / "model.blend", helpers=[ROOT / "scripts/delivery_contract.py"])
        finally:
            for file in images:
                (hidden / file.name).rename(file)
        self.assertTrue(read(self.root / "portable-readback/checks.json")["passed"])
        run_worker(self.blender, ROOT / "tests/blender_delivery_checks.py",
                   ["--job", prepared / "job.json", "--appearance", prepared / "appearance.json", "--native", prepared / "apply/native.json",
                    "--output", self.root / "native-rejections.json"], self.root / "native-rejections-runtime", blend=output / "model.blend",
                   helpers=[ROOT / "scripts/delivery_contract.py", ROOT / "scripts/blender_delivery.py"])
        self.assertTrue(all(read(self.root / "native-rejections.json").values()))

        scene, job = read(prepared / "inspect/scene.json"), read(prepared / "job.json")
        def photo_primitive(gltf):
            node = next(row for row in gltf["nodes"] if row.get("extras", {}).get("stm_id") == "poster")
            return gltf["meshes"][node["mesh"]]["primitives"][0]
        def omit_object(gltf):
            index = next(index for index, row in enumerate(gltf["nodes"]) if row.get("extras", {}).get("stm_id") == "poster")
            gltf["scenes"][gltf.get("scene", 0)]["nodes"].remove(index)
        def omit_face(gltf):
            gltf["accessors"][photo_primitive(gltf)["indices"]]["count"] -= 3
        def lose_photo_binding(gltf):
            photo_primitive(gltf)["material"] = next(index for index, row in enumerate(gltf["materials"]) if row["name"] == "STM paint")
        def change_source(gltf):
            next(row for row in gltf["nodes"] if row.get("extras", {}).get("stm_id") == "poster")["extras"]["source_ids"] = ["wrong"]
        for name, mutate in [("missing-object", omit_object), ("missing-face", omit_face), ("wrong-texture", lose_photo_binding), ("wrong-source", change_source)]:
            damaged = self.root / (name + ".glb")
            rewrite_glb(output / "model.glb", damaged, mutate)
            with self.subTest(damage=name), self.assertRaises(ValueError):
                check_glb(damaged, scene, job, appearance)
        self.assertEqual({file: digest(file) for file in original}, original)
        with (output / "model.glb").open("ab") as stream:
            stream.write(b"changed")
        self.cli("verify", "--output", output, "--review", final, success=False)
        shutil.copyfile(prepared / "export/model.glb", output / "model.glb")

    def test_overlapping_trim_stops_before_baking(self):
        source = self.fixture("overlap", "overlap")
        prepared = self.root / "overlap-prepared"
        self.cli("prepare", "--job", source / "job.json", "--output", prepared, "--blender", self.blender, success=False)
        self.assertFalse(read(prepared / "mesh-quality.json")["passed"])
        self.assertFalse((prepared / "appearance").exists())

    def test_native_only_scope_needs_no_render_or_web_producer(self):
        source = self.fixture("geometry-only")
        job = read(source / "job.json")
        job["deliverables"] = ["native"]
        job["intent"].update(basis="Preserve the tentative geometry only", interpolation_authorized=False)
        job.update(materials=[], views=[])
        job.pop("lighting")
        for row in job["objects"]:
            row.pop("material")
        write_json(source / "job.json", job)
        prepared, output = self.root / "geometry-prepared", self.root / "geometry-delivered"
        self.cli("prepare", "--job", source / "job.json", "--output", prepared, "--blender", self.blender)
        review = prepared / "fixture-review.json"
        fixture_review(prepared / "review-template.json", review)
        self.cli("finish", "--prepared", prepared, "--review", review, "--output", output, "--blender", self.blender)
        self.cli("verify", "--output", output, "--review", review)
        self.assertEqual(read(output / "delivery.json")["requested_deliverables"], ["native"])
        self.assertTrue((output / "model.blend").is_file())
        for relative in ["probe", "render", "export", "viewer-build"]:
            self.assertFalse((prepared / relative).exists())
        self.assertFalse((output / "browser-check").exists())

    def test_closed_door_cannot_pass_a_room_view(self):
        source = self.fixture("blocked", "blocked")
        prepared = self.root / "blocked-prepared"
        self.cli("prepare", "--job", source / "job.json", "--output", prepared, "--blender", self.blender)
        state = read(prepared / "prepared.json")
        doorway = next(row for row in state["coverage"] if row["id"] == "doorway")
        self.assertFalse(doorway["passed"])
        self.assertEqual(doorway["actual_raster_pixels"]["object"], {"door": 76800})
        review = prepared / "fixture-review.json"
        fixture_review(prepared / "review-template.json", review)
        self.cli("finish", "--prepared", prepared, "--review", review, "--output", self.root / "blocked-delivery",
                 "--blender", self.blender, success=False)
        self.assertFalse((self.root / "blocked-delivery").exists())


if __name__ == "__main__":
    unittest.main()
