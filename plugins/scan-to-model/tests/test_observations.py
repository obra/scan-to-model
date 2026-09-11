"""Behavior tests for reproducible source-photo annotation sheets."""

import base64
import copy
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
import xml.etree.ElementTree as ET

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
SCRATCH_ROOT = Path(os.environ.get(
    "SCAN_TO_MODEL_TEST_SCRATCH",
    Path.cwd() / ".test-scratch" / "observations",
))


def make_workspace():
    root = SCRATCH_ROOT / str(uuid.uuid4())
    images = root / "images"
    images.mkdir(parents=True)
    Image.new("RGB", (3, 2), (19, 41, 73)).save(images / "raw.png")
    Image.new("RGB", (3, 2), (91, 37, 11)).save(images / "turned.jpg", quality=87)
    return root


def valid_spec(root):
    raw_hash = hashlib.sha256((root / "images/raw.png").read_bytes()).hexdigest()
    return {
        "sources": [
            {
                "id": "photo.raw",
                "path": "images/./raw.png",
                "sha256": raw_hash,
                "orientation": "raw",
                "metadata": {"caption": "Invented <source> & fixture"},
            },
            {
                "id": "photo-turned",
                "path": "images/turned.jpg",
                "orientation": "upright90cw",
                "metadata": {"capture_clock": "unknown"},
            },
        ],
        "observations": [
            {
                "id": "obs-point",
                "label": "A < B > C & \"quoted\" café 🧱",
                "source_id": "photo.raw",
                "marks": {
                    "type": "point",
                    "meaning": "locator",
                    "coordinates": [[0, 0]],
                },
                "endpoints": [],
                "qualification": {"status": "visible", "basis": "invented fixture"},
                "metadata": {"label": "A < B & C"},
            },
            {
                "id": "obs-turned-corners",
                "source_id": "photo-turned",
                "marks": {
                    "type": "polyline",
                    "meaning": "visible centerline",
                    "coordinates": [[0, 0], [2, 0], [0, 1], [2, 1]],
                },
                "endpoints": [
                    {"index": 0, "kind": "image boundary", "basis": "fixture corner"},
                    {"index": -1, "kind": "annotation boundary", "basis": "fixture corner"},
                ],
                "qualification": {"identity": "unresolved"},
                "metadata": {"nested": [1, {"kept": True}]},
            },
            {
                "id": "obs-polygon",
                "source_id": "photo.raw",
                "marks": {
                    "type": "polygon",
                    "meaning": "visible face",
                    "coordinates": [[0, 0], [2, 0], [2, 1]],
                },
                "endpoints": [],
                "qualification": {"boundary": "partly occluded"},
            },
        ],
        "features": [
            {
                "id": "feature-candidate",
                "observation_ids": ["obs-point", "obs-turned-corners"],
                "qualification": {"status": "candidate", "basis": "invented relation"},
                "metadata": {"physical_scope": "one invented item"},
            }
        ],
        "metadata": {"review_scope": ["points", "spans", "faces"]},
    }


def write_spec(root, data, name="observations.json"):
    path = root / name
    path.write_text(json.dumps(data, indent=2, allow_nan=True) + "\n")
    return path


def svg_root(path):
    return ET.fromstring(path.read_bytes())


def embedded_bytes(root):
    image = root.find(f"{SVG}image")
    href = image.attrib.get("href") or image.attrib[f"{XLINK}href"]
    return base64.b64decode(href.split(",", 1)[1])


class ObservationSheetTests(unittest.TestCase):
    def generate(self, spec_path, output, **options):
        from observations import generate_evidence
        return generate_evidence(spec_path, output, **options)

    def test_preserves_inputs_and_embeds_exact_source_bytes(self):
        root = make_workspace()
        data = valid_spec(root)
        before = copy.deepcopy(data)
        spec_path = write_spec(root, data)
        spec_bytes = spec_path.read_bytes()
        source_bytes = {
            row["id"]: (root / row["path"]).read_bytes()
            for row in data["sources"]
        }

        record = self.generate(spec_path, root / "evidence")

        self.assertEqual(data, before)
        self.assertEqual(record["input"], before)
        self.assertEqual(spec_path.read_bytes(), spec_bytes)
        self.assertTrue(record["input_proof"]["unchanged"])
        self.assertEqual(record["input_proof"]["sha256_before"], hashlib.sha256(spec_bytes).hexdigest())
        for source in record["sources"]:
            self.assertEqual(source["declared_path"], before["sources"][source["input_index"]]["path"])
            self.assertEqual(source["sha256_before"], hashlib.sha256(source_bytes[source["id"]]).hexdigest())
            self.assertEqual(source["sha256_after"], source["sha256_before"])
            self.assertTrue(source["unchanged"])
            sheet = root / "evidence" / source["sheet"]["path"]
            self.assertEqual(embedded_bytes(svg_root(sheet)), source_bytes[source["id"]])
            self.assertEqual(source["sheet"]["sha256"], hashlib.sha256(sheet.read_bytes()).hexdigest())

    def test_maps_native_centers_to_raw_and_clockwise_display_coordinates(self):
        root = make_workspace()
        record = self.generate(write_spec(root, valid_spec(root)), root / "evidence")
        annotations = {row["id"]: row for row in record["annotations"]}

        self.assertEqual(annotations["obs-point"]["display_coordinates"], [[0, 0]])
        self.assertEqual(
            annotations["obs-turned-corners"]["display_coordinates"],
            [[1, 0], [1, 2], [0, 0], [0, 2]],
        )
        self.assertTrue(all(row["coordinate_round_trip_verified"] for row in annotations.values()))

        raw_svg = svg_root(root / "evidence/photo.raw.svg")
        point = raw_svg.find(f".//{SVG}circle[@data-observation-id='obs-point']")
        self.assertEqual((point.attrib["cx"], point.attrib["cy"]), ("0.5", "0.5"))
        turned_svg = svg_root(root / "evidence/photo-turned.svg")
        self.assertEqual(turned_svg.attrib["viewBox"], "0 0 2 3")
        image = turned_svg.find(f"{SVG}image")
        self.assertEqual(image.attrib["transform"], "matrix(0 1 -1 0 2 0)")
        polyline = turned_svg.find(f".//{SVG}polyline[@data-observation-id='obs-turned-corners']")
        self.assertEqual(polyline.attrib["points"], "1.5,0.5 1.5,2.5 0.5,0.5 0.5,2.5")
        turned_label = turned_svg.find(f".//{SVG}text[@data-observation-id='obs-turned-corners']")
        self.assertEqual(turned_label.attrib["text-anchor"], "end")
        self.assertEqual(turned_label.attrib["dx"], "-6")
        labels = [node.text for node in raw_svg.findall(f".//{SVG}text")]
        self.assertIn("A < B > C & \"quoted\" café 🧱", labels)

    def test_writes_native_scale_assertion_and_endpoint_review_crops(self):
        root = make_workspace()
        Image.new("RGB", (160, 120), (36, 72, 108)).save(root / "images/review.png")
        Image.new("RGB", (160, 120), (108, 72, 36)).save(root / "images/review-turned.png")
        data = {
            "sources": [
                {"id": "review-raw", "path": "images/review.png", "orientation": "raw"},
                {"id": "review-turned", "path": "images/review-turned.png",
                 "orientation": "upright90cw"},
            ],
            "observations": [
                {
                    "id": "obs-locator",
                    "label": "invented locator",
                    "source_id": "review-raw",
                    "marks": {"type": "point", "meaning": "locator",
                              "coordinates": [[80, 60]]},
                    "endpoints": [],
                    "qualification": {"identity": "invented"},
                },
                {
                    "id": "obs-span",
                    "label": "invented span",
                    "source_id": "review-raw",
                    "marks": {"type": "polyline", "meaning": "visible centerline",
                              "coordinates": [[10, 10], [150, 110]]},
                    "endpoints": [
                        {"index": 0, "kind": "occlusion", "basis": "Invented start."},
                        {"index": -1, "kind": "annotation boundary", "basis": "Invented end."},
                    ],
                    "qualification": {"identity": "invented"},
                },
                {
                    "id": "obs-turned",
                    "label": "invented turned locator",
                    "source_id": "review-turned",
                    "marks": {"type": "point", "meaning": "locator",
                              "coordinates": [[20, 30]]},
                    "endpoints": [],
                    "qualification": {"identity": "invented"},
                },
            ],
            "features": [],
            "metadata": {"fixture": "native-scale review crops"},
        }
        source_bytes = {
            source["id"]: (root / source["path"]).read_bytes()
            for source in data["sources"]
        }

        record = self.generate(write_spec(root, data), root / "evidence")

        self.assertEqual(record["schema_version"], 3)
        annotations = {row["id"]: row for row in record["annotations"]}
        expected = {
            "obs-locator": ([48, 28, 113, 93], []),
            "obs-span": ([0, 0, 160, 120], [
                (0, "occlusion", [0, 0, 43, 43]),
                (-1, "annotation boundary", [118, 78, 160, 120]),
            ]),
            "obs-turned": ([57, 0, 120, 53], []),
        }
        for observation_id, (bounds, endpoints) in expected.items():
            review = annotations[observation_id]["review"]
            self.assertEqual(review["status"], "pending visual review")
            self.assertEqual(review["assertion"]["display_bounds"], bounds)
            self.assertEqual(review["assertion"]["scale"], "1 SVG unit per displayed source pixel")
            self.assertEqual(
                [(row["index"], row["kind"], row["display_bounds"])
                 for row in review["endpoints"]],
                endpoints,
            )
            for artifact in [review["assertion"], *review["endpoints"]]:
                artifact_path = root / "evidence" / artifact["path"]
                artifact_root = svg_root(artifact_path)
                left, top, right, bottom = artifact["display_bounds"]
                self.assertEqual(artifact_root.attrib["viewBox"],
                                 f"{left} {top} {right-left} {bottom-top}")
                self.assertEqual(artifact_root.attrib["width"], str(right-left))
                self.assertEqual(artifact_root.attrib["height"], str(bottom-top))
                self.assertEqual(embedded_bytes(artifact_root),
                                 source_bytes[annotations[observation_id]["source_id"]])
                self.assertIsNotNone(artifact_root.find(f"{SVG}title"))
                self.assertIsNone(artifact_root.find(f".//{SVG}text"))
                self.assertEqual(artifact["sha256"], hashlib.sha256(artifact_path.read_bytes()).hexdigest())
        end_crop = svg_root(root / "evidence/review/obs-span/endpoint-0.svg")
        endpoint_mark = end_crop.find(f".//{SVG}circle[@data-observation-id='obs-span']")
        self.assertEqual((endpoint_mark.attrib["cx"], endpoint_mark.attrib["cy"]), ("10.5", "10.5"))

    def test_coordinate_inspections_show_exact_raw_and_rotated_pixels_without_covering_them(self):
        root = make_workspace()
        pixels = Image.new("RGB", (5, 4))
        pixels.putdata([
            (u * 40 + 5, v * 50 + 7, u * 10 + v)
            for v in range(4)
            for u in range(5)
        ])
        pixels.save(root / "images/grid-raw.png")
        pixels.save(root / "images/grid-turned.png")
        coordinates = [[0, 0], [2.49, 1.51], [4, 3]]
        data = {
            "sources": [
                {"id": "grid-raw", "path": "images/grid-raw.png", "orientation": "raw"},
                {"id": "grid-turned", "path": "images/grid-turned.png",
                 "orientation": "upright90cw"},
            ],
            "observations": [
                {
                    "id": "raw-points",
                    "source_id": "grid-raw",
                    "marks": {"type": "polygon", "meaning": "fixture", "coordinates": coordinates},
                    "endpoints": [],
                    "qualification": {"status": "synthetic"},
                },
                {
                    "id": "turned-points",
                    "source_id": "grid-turned",
                    "marks": {"type": "polygon", "meaning": "fixture", "coordinates": coordinates},
                    "endpoints": [],
                    "qualification": {"status": "synthetic"},
                },
            ],
            "features": [],
        }
        source_bytes = {
            source["id"]: (root / source["path"]).read_bytes()
            for source in data["sources"]
        }

        record = self.generate(
            write_spec(root, data), root / "evidence", coordinate_inspections=True
        )

        self.assertEqual(record["schema_version"], 3)
        self.assertTrue(record["generator"]["coordinate_inspections"])
        annotations = {row["id"]: row for row in record["annotations"]}
        expected_display = {
            "raw-points": [[0, 0], [2.49, 1.51], [4, 3]],
            "turned-points": [[3, 0], [1.49, 2.49], [0, 4]],
        }
        expected_nearest_display = {
            "raw-points": [[0, 0], [2, 2], [4, 3]],
            "turned-points": [[3, 0], [1, 2], [0, 4]],
        }
        source_pixels = pixels.load()
        for observation_id in ("raw-points", "turned-points"):
            inspection = annotations[observation_id]["review"]["coordinate_inspection"]
            artifact = root / "evidence" / inspection["path"]
            self.assertEqual(inspection["sha256"], hashlib.sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(inspection["media_type"], "image/png")
            self.assertEqual(inspection["resampling"], "nearest")
            self.assertEqual(inspection["context_radius_display_pixels"], 128)
            self.assertEqual(inspection["context_magnification"], 1)
            self.assertEqual(inspection["detail_radius_display_pixels"], 4)
            self.assertEqual(inspection["detail_magnification"], 12)
            self.assertEqual(
                [row["display"] for row in inspection["coordinates"]],
                expected_display[observation_id],
            )
            self.assertEqual(
                [row["nearest_display_pixel"] for row in inspection["coordinates"]],
                expected_nearest_display[observation_id],
            )
            with Image.open(artifact) as sheet:
                sheet.load()
                for index, row in enumerate(inspection["coordinates"]):
                    native_u, native_v = row["nearest_native_pixel"]
                    expected_color = (*source_pixels[native_u, native_v], 255)
                    for panel_name in ("unmarked_context_bounds", "located_context_bounds"):
                        left, top, _, _ = row[panel_name]
                        self.assertEqual(sheet.getpixel((left + 128, top + 128)), expected_color)

                    left, top, _, _ = row["detail_bounds"]
                    selected = sheet.crop((
                        left + 4 * 12,
                        top + 4 * 12,
                        left + 5 * 12,
                        top + 5 * 12,
                    ))
                    self.assertEqual(set(selected.getdata()), {expected_color})

                    left, top, _, _ = row["unmarked_context_bounds"]
                    if index == 1 and observation_id == "raw-points":
                        right_color = sheet.getpixel((left + 129, top + 128))
                        down_color = sheet.getpixel((left + 128, top + 129))
                        self.assertEqual(right_color, (*source_pixels[3, 2], 255))
                        self.assertEqual(down_color, (*source_pixels[2, 3], 255))
                    if index == 1 and observation_id == "turned-points":
                        right_color = sheet.getpixel((left + 129, top + 128))
                        down_color = sheet.getpixel((left + 128, top + 129))
                        self.assertEqual(right_color, (*source_pixels[2, 1], 255))
                        self.assertEqual(down_color, (*source_pixels[3, 2], 255))

        self.assertEqual(source_bytes, {
            source["id"]: (root / source["path"]).read_bytes()
            for source in data["sources"]
        })
        repeated = self.generate(
            root / "observations.json", root / "evidence-repeated",
            coordinate_inspections=True,
        )
        for annotation in repeated["annotations"]:
            repeated_inspection = annotation["review"]["coordinate_inspection"]
            first_inspection = annotations[annotation["id"]]["review"]["coordinate_inspection"]
            self.assertEqual(repeated_inspection, first_inspection)
            self.assertEqual(
                (root / "evidence-repeated" / repeated_inspection["path"]).read_bytes(),
                (root / "evidence" / first_inspection["path"]).read_bytes(),
            )

    def test_coordinate_inspections_require_a_boolean_option(self):
        root = make_workspace()
        with self.assertRaisesRegex(ValueError, "coordinate_inspections must be a boolean"):
            self.generate(
                write_spec(root, valid_spec(root)),
                root / "evidence",
                coordinate_inspections="yes",
            )

    def test_coordinate_inspections_balance_many_coordinates_across_columns(self):
        root = make_workspace()
        data = valid_spec(root)
        data["observations"] = [data["observations"][2]]
        data["observations"][0]["marks"]["coordinates"] = [
            [index % 3, (index // 3) % 2]
            for index in range(10)
        ]
        data["features"] = []

        record = self.generate(
            write_spec(root, data), root / "evidence", coordinate_inspections=True
        )

        coordinates = record["annotations"][0]["review"]["coordinate_inspection"]["coordinates"]
        panel_rows = {row["unmarked_context_bounds"][1] for row in coordinates}
        panel_columns = {row["unmarked_context_bounds"][0] for row in coordinates}
        self.assertEqual(len(panel_rows), 5)
        self.assertEqual(len(panel_columns), 2)

    def test_coordinate_inspection_columns_differ_by_at_most_one_item(self):
        root = make_workspace()
        data = valid_spec(root)
        data["observations"] = [data["observations"][2]]
        data["observations"][0]["marks"]["coordinates"] = [
            [index % 3, (index // 3) % 2]
            for index in range(57)
        ]
        data["features"] = []

        record = self.generate(
            write_spec(root, data), root / "evidence", coordinate_inspections=True
        )

        coordinates = record["annotations"][0]["review"]["coordinate_inspection"]["coordinates"]
        column_sizes = {}
        for row in coordinates:
            column = row["unmarked_context_bounds"][0]
            column_sizes[column] = column_sizes.get(column, 0) + 1
        self.assertEqual(len(column_sizes), 8)
        self.assertLessEqual(max(column_sizes.values()) - min(column_sizes.values()), 1)

    def test_coordinate_inspections_preserve_transparent_source_pixels(self):
        root = make_workspace()
        source = Image.new("RGBA", (3, 2), (20, 40, 60, 255))
        source.putpixel((1, 0), (255, 0, 0, 0))
        source.putpixel((2, 0), (0, 0, 255, 96))
        source.save(root / "images/transparent.png")
        data = {
            "sources": [
                {"id": "transparent", "path": "images/transparent.png", "orientation": "raw"},
            ],
            "observations": [
                {
                    "id": "transparent-point",
                    "source_id": "transparent",
                    "marks": {"type": "point", "meaning": "fixture", "coordinates": [[1, 0]]},
                    "endpoints": [],
                    "qualification": {"status": "synthetic"},
                },
            ],
            "features": [],
        }

        record = self.generate(
            write_spec(root, data), root / "evidence", coordinate_inspections=True
        )

        inspection = record["annotations"][0]["review"]["coordinate_inspection"]
        row = inspection["coordinates"][0]
        with Image.open(root / "evidence" / inspection["path"]) as sheet:
            self.assertEqual(sheet.mode, "RGBA")
            for panel_name in ("unmarked_context_bounds", "located_context_bounds"):
                left, top, _, _ = row[panel_name]
                self.assertEqual(sheet.getpixel((left + 128, top + 128)), (255, 0, 0, 0))
            left, top, _, _ = row["detail_bounds"]
            selected = sheet.crop((
                left + 4 * 12,
                top + 4 * 12,
                left + 5 * 12,
                top + 5 * 12,
            ))
            self.assertEqual(set(selected.getdata()), {(255, 0, 0, 0)})
            left, top, _, _ = row["unmarked_context_bounds"]
            adjacent = sheet.getpixel((left + 129, top + 128))
            self.assertEqual(adjacent, (0, 0, 255, 96))

    def test_review_artifact_paths_cannot_collide_with_observation_ids(self):
        root = make_workspace()
        data = {
            "sources": [
                {"id": "source", "path": "images/raw.png", "orientation": "raw"},
            ],
            "observations": [
                {
                    "id": "span",
                    "source_id": "source",
                    "marks": {"type": "polyline", "meaning": "visible centerline",
                              "coordinates": [[0, 0], [2, 1]]},
                    "endpoints": [
                        {"index": 0, "kind": "unknown", "basis": "Invented start."},
                        {"index": -1, "kind": "annotation boundary", "basis": "Invented end."},
                    ],
                    "qualification": {"identity": "invented"},
                },
                {
                    "id": "span-endpoint-0",
                    "source_id": "source",
                    "marks": {"type": "point", "meaning": "locator",
                              "coordinates": [[1, 1]]},
                    "endpoints": [],
                    "qualification": {"identity": "invented"},
                },
            ],
            "features": [],
        }

        record = self.generate(write_spec(root, data), root / "evidence")

        artifacts = []
        for annotation in record["annotations"]:
            artifacts.append((annotation["id"], annotation["review"]["assertion"]))
            artifacts.extend(
                (annotation["id"], endpoint)
                for endpoint in annotation["review"]["endpoints"]
            )
        paths = [artifact["path"] for _, artifact in artifacts]
        self.assertEqual(len(paths), len(set(paths)))
        for observation_id, artifact in artifacts:
            artifact_path = root / "evidence" / artifact["path"]
            self.assertEqual(artifact["sha256"], hashlib.sha256(artifact_path.read_bytes()).hexdigest())
            self.assertIsNotNone(
                svg_root(artifact_path).find(
                    f".//*[@data-observation-id='{observation_id}']"
                )
            )

    def test_rejects_invalid_mark_coordinates_and_cardinality(self):
        cases = [
            {"type": "point", "coordinates": [[0, 0], [1, 1]]},
            {"type": "polyline", "coordinates": [[0, 0]]},
            {"type": "polygon", "coordinates": [[0, 0], [1, 0]]},
            {"type": "point", "coordinates": [[3, 0]]},
            {"type": "point", "coordinates": [[0, 2]]},
            {"type": "point", "coordinates": [[float("nan"), 0]]},
            {"type": "point", "coordinates": [[float("inf"), 0]]},
            {"type": "circle", "coordinates": [[0, 0]]},
        ]
        for index, marks in enumerate(cases):
            root = make_workspace()
            data = valid_spec(root)
            data["observations"] = [{
                "id": "invalid-mark",
                "source_id": "photo.raw",
                "marks": {"meaning": "test", **marks},
                "endpoints": [],
                "qualification": {},
            }]
            data["features"] = []
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.generate(write_spec(root, data), root / "evidence")

    def test_rejects_invalid_ids_references_and_endpoints(self):
        def duplicate_source(data):
            data["sources"].append(copy.deepcopy(data["sources"][0]))

        def duplicate_source_path(data):
            row = copy.deepcopy(data["sources"][0])
            row.update(id="second-id", path="images/raw.png")
            data["sources"].append(row)

        def missing_source(data):
            data["observations"][0]["source_id"] = "missing"

        def duplicate_observation(data):
            data["observations"].append(copy.deepcopy(data["observations"][0]))

        def duplicate_feature(data):
            data["features"].append(copy.deepcopy(data["features"][0]))

        def missing_observation(data):
            data["features"][0]["observation_ids"] = ["missing"]

        def invalid_id(data):
            data["observations"][0]["id"] = "../unsafe"

        def bad_endpoint(data):
            data["observations"][1]["endpoints"][1]["kind"] = "continues somehow"

        changes = [
            duplicate_source, duplicate_source_path, missing_source,
            duplicate_observation, duplicate_feature, missing_observation,
            invalid_id, bad_endpoint,
        ]
        for change in changes:
            root = make_workspace()
            data = valid_spec(root)
            change(data)
            with self.subTest(change=change.__name__), self.assertRaises(ValueError):
                self.generate(write_spec(root, data), root / "evidence")

    def test_rejects_hash_mismatch_non_image_and_invalid_image(self):
        cases = []
        root = make_workspace()
        data = valid_spec(root)
        data["sources"][0]["sha256"] = "0" * 64
        cases.append((root, data))

        root = make_workspace()
        (root / "images/not-image.txt").write_text("invented text")
        data = valid_spec(root)
        data["sources"][0]["path"] = "images/not-image.txt"
        data["sources"][0].pop("sha256")
        cases.append((root, data))

        root = make_workspace()
        (root / "images/broken.png").write_bytes(b"not a png")
        data = valid_spec(root)
        data["sources"][0]["path"] = "images/broken.png"
        data["sources"][0].pop("sha256")
        cases.append((root, data))

        for index, (root, data) in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.generate(write_spec(root, data), root / "evidence")

    def test_rejects_truncated_jpeg_before_creating_output(self):
        root = make_workspace()
        complete = (root / "images/turned.jpg").read_bytes()
        truncated = complete[:-8]
        with Image.open(BytesIO(truncated)) as image:
            image.verify()
        with self.assertRaises(OSError), Image.open(BytesIO(truncated)) as image:
            image.load()
        (root / "images/truncated.jpg").write_bytes(truncated)
        data = valid_spec(root)
        data["sources"] = [{
            "id": "truncated",
            "path": "images/truncated.jpg",
            "orientation": "raw",
        }]
        data["observations"] = []
        data["features"] = []
        output = root / "evidence"

        with self.assertRaises(ValueError):
            self.generate(write_spec(root, data), output)
        self.assertFalse(output.exists())

    def test_rejects_xml_invalid_label_before_creating_output(self):
        root = make_workspace()
        data = valid_spec(root)
        data["observations"][0]["label"] = "invalid\0label"
        output = root / "evidence"

        with self.assertRaises(ValueError):
            self.generate(write_spec(root, data), output)
        self.assertFalse(output.exists())

    def test_reads_sibling_absolute_and_symlink_sources_without_mutation(self):
        root = make_workspace()
        docs = root / "docs"
        sources = root / "shared-sources"
        docs.mkdir()
        sources.mkdir()
        paths = {
            "sibling": sources / "sibling.png",
            "absolute": sources / "absolute.png",
            "linked": sources / "linked-target.png",
        }
        for index, path in enumerate(paths.values()):
            Image.new("RGB", (4, 3), (20 + index, 40, 60)).save(path)
        link = docs / "source-link.png"
        link.symlink_to(paths["linked"])
        declared = [
            "../shared-sources/sibling.png",
            str(paths["absolute"]),
            "source-link.png",
        ]
        data = {
            "sources": [
                {"id": source_id, "path": source_path, "orientation": "raw"}
                for source_id, source_path in zip(paths, declared)
            ],
            "observations": [],
            "features": [],
            "metadata": {"fixture": "local path resolution"},
        }
        before = {name: path.read_bytes() for name, path in paths.items()}
        link_target = os.readlink(link)
        spec_path = write_spec(docs, data)
        output = root / "evidence"

        record = self.generate(spec_path, output)

        rows = {row["id"]: row for row in record["sources"]}
        for source_id, declared_path in zip(paths, declared):
            self.assertEqual(rows[source_id]["declared_path"], declared_path)
            self.assertEqual(rows[source_id]["resolved_path"], str(paths[source_id].resolve()))
            self.assertEqual(rows[source_id]["sha256_before"], hashlib.sha256(before[source_id]).hexdigest())
            self.assertEqual(rows[source_id]["sha256_after"], rows[source_id]["sha256_before"])
            self.assertEqual(paths[source_id].read_bytes(), before[source_id])
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), link_target)
        with self.assertRaises(FileExistsError):
            self.generate(spec_path, output)
        self.assertEqual({name: path.read_bytes() for name, path in paths.items()}, before)

    def test_requires_fresh_output_and_is_deterministic(self):
        root = make_workspace()
        spec_path = write_spec(root, valid_spec(root))
        first = root / "first"
        second = root / "second"
        first_record = self.generate(spec_path, first)
        second_record = self.generate(spec_path, second)

        self.assertFalse(first_record["generator"]["coordinate_inspections"])
        self.assertTrue(all(
            annotation["review"]["coordinate_inspection"] is None
            for annotation in first_record["annotations"]
        ))
        self.assertFalse(any(first.rglob("coordinates.png")))
        self.assertEqual(first_record, second_record)
        self.assertEqual((first / "evidence.json").read_bytes(), (second / "evidence.json").read_bytes())
        for source in first_record["sources"]:
            path = source["sheet"]["path"]
            self.assertEqual((first / path).read_bytes(), (second / path).read_bytes())
        before = sorted(first.iterdir())
        with self.assertRaises(FileExistsError):
            self.generate(spec_path, first)
        self.assertEqual(sorted(first.iterdir()), before)

    def test_cli_writes_packet_and_refuses_an_existing_output(self):
        root = make_workspace()
        spec_path = write_spec(root, valid_spec(root))
        script = Path(__file__).resolve().parents[1] / "scripts" / "observations.py"
        output = root / "cli-output"

        completed = subprocess.run(
            [sys.executable, str(script), "--spec", str(spec_path), "--output", str(output),
             "--coordinate-inspections"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue((output / "evidence.json").is_file())
        cli_record = json.loads((output / "evidence.json").read_text())
        self.assertTrue(cli_record["generator"]["coordinate_inspections"])
        self.assertTrue(all(
            (output / annotation["review"]["coordinate_inspection"]["path"]).is_file()
            for annotation in cli_record["annotations"]
        ))
        refused = subprocess.run(
            [sys.executable, str(script), "--spec", str(spec_path), "--output", str(output)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(refused.returncode, 0)


if __name__ == "__main__":
    unittest.main()
