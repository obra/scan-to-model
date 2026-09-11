"""Synthetic Blender inventory contracts."""

import importlib.util
import math
from pathlib import Path
import unittest

try:
    import bpy
except ImportError:
    bpy = None


def load_review():
    path = Path(__file__).resolve().parents[1] / "scripts" / "blender_review.py"
    spec = importlib.util.spec_from_file_location("blender_review_tested", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matrix_max_delta(left, right):
    return max(abs(a - b) for row, expected_row in zip(left, right)
               for a, b in zip(row, expected_row))


@unittest.skipIf(bpy is None, "requires Blender's Python")
class BlenderReviewTests(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.scene = bpy.context.scene
        self.scene.view_layers[0].name = "Layer A"
        self.scene.view_layers.new("Layer B")

        zulu = bpy.data.collections.new("Zulu")
        alpha = bpy.data.collections.new("Alpha")
        nested = bpy.data.collections.new("Nested")
        self.scene.collection.children.link(zulu)
        self.scene.collection.children.link(alpha)
        alpha.children.link(nested)

        hidden_a = bpy.data.objects.new("Hidden A", None)
        hidden_b = bpy.data.objects.new("Hidden B", None)
        visible = bpy.data.objects.new("Visible", None)
        for obj in (hidden_a, hidden_b, visible):
            self.scene.collection.objects.link(obj)

        layer_a, layer_b = self.scene.view_layers
        alpha_a = layer_a.layer_collection.children["Alpha"]
        zulu_a = layer_a.layer_collection.children["Zulu"]
        alpha_b = layer_b.layer_collection.children["Alpha"]
        zulu_b = layer_b.layer_collection.children["Zulu"]
        alpha_a.hide_viewport = True
        alpha_a.children["Nested"].holdout = True
        zulu_a.exclude = True
        alpha_b.exclude = True
        zulu_b.indirect_only = True
        hidden_a.hide_set(True, view_layer=layer_a)
        hidden_b.hide_set(True, view_layer=layer_b)

    def test_view_layer_snapshots_preserve_sorted_tree_and_per_layer_flags(self):
        review = load_review()

        snapshots = review.view_layer_snapshots(self.scene)

        self.assertEqual(snapshots, [
            {
                "name": "Layer A",
                "collections": {
                    "name": "Scene Collection", "exclude": False, "hide_viewport": False,
                    "holdout": False, "indirect_only": False,
                    "children": [
                        {
                            "name": "Alpha", "exclude": False, "hide_viewport": True,
                            "holdout": False, "indirect_only": False,
                            "children": [{
                                "name": "Nested", "exclude": False, "hide_viewport": False,
                                "holdout": True, "indirect_only": False, "children": [],
                            }],
                        },
                        {
                            "name": "Zulu", "exclude": True, "hide_viewport": False,
                            "holdout": False, "indirect_only": False, "children": [],
                        },
                    ],
                },
                "hidden_objects": ["Hidden A"],
            },
            {
                "name": "Layer B",
                "collections": {
                    "name": "Scene Collection", "exclude": False, "hide_viewport": False,
                    "holdout": False, "indirect_only": False,
                    "children": [
                        {
                            "name": "Alpha", "exclude": True, "hide_viewport": False,
                            "holdout": False, "indirect_only": False,
                            "children": [{
                                "name": "Nested", "exclude": True, "hide_viewport": False,
                                "holdout": False, "indirect_only": False, "children": [],
                            }],
                        },
                        {
                            "name": "Zulu", "exclude": False, "hide_viewport": False,
                            "holdout": False, "indirect_only": True, "children": [],
                        },
                    ],
                },
                "hidden_objects": ["Hidden B"],
            },
        ])

    def test_evaluated_world_matrices_reject_excluded_and_wrong_scene_objects(self):
        review = load_review()
        excluded = bpy.data.objects.new("Excluded matrix", None)
        bpy.data.collections["Zulu"].objects.link(excluded)
        other_scene = bpy.data.scenes.new("Other scene")
        wrong_scene = bpy.data.objects.new("Wrong scene matrix", None)
        other_scene.collection.objects.link(wrong_scene)
        bpy.context.window.scene = self.scene
        bpy.context.window.view_layer = self.scene.view_layers["Layer A"]
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()

        for obj in (excluded, wrong_scene):
            with self.subTest(obj=obj.name):
                with self.assertRaisesRegex(ValueError, obj.name):
                    review.evaluated_world_matrices([obj], graph)

    def test_evaluated_world_matrices_copy_included_rotated_parent_transform(self):
        from mathutils import Euler, Matrix, Vector

        review = load_review()
        parent = bpy.data.objects.new("Rotated parent", None)
        child = bpy.data.objects.new("Included child", None)
        self.scene.collection.objects.link(parent)
        self.scene.collection.objects.link(child)
        child.parent = parent
        parent.location = (2.0, -1.0, 3.0)
        parent.rotation_euler = (0.0, 0.0, math.pi / 2)
        child.location = (1.0, 0.0, 0.0)
        child.rotation_euler = (0.0, 0.0, math.pi / 6)
        expected = (
            Matrix.Translation(Vector(parent.location))
            @ Euler(parent.rotation_euler).to_matrix().to_4x4()
            @ Matrix.Translation(Vector(child.location))
            @ Euler(child.rotation_euler).to_matrix().to_4x4()
        )
        bpy.context.window.scene = self.scene
        bpy.context.window.view_layer = self.scene.view_layers["Layer A"]
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()

        self.assertEqual(review.evaluated_world_matrices([], graph), {})
        matrices = review.evaluated_world_matrices([child], graph)

        self.assertEqual(list(matrices), [child.name])
        self.assertLess(matrix_max_delta(matrices[child.name], expected), 1e-8)
        child.location.x = 4.0
        bpy.context.view_layer.update()
        self.assertLess(matrix_max_delta(matrices[child.name], expected), 1e-8)

    def test_inventory_compares_nested_object_mesh_and_image_properties(self):
        review = load_review()
        mesh = bpy.data.meshes.new("Tagged mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
        obj = bpy.data.objects.new("Tagged object", mesh)
        self.scene.collection.objects.link(obj)
        image = bpy.data.images.new("Tagged image", width=2, height=2, alpha=True)
        image.pack()
        for owner in (obj, mesh, image):
            owner["review"] = {"threshold": 0.25, "note": "synthetic baseline"}

        baseline = review.inventory()
        legacy = dict(baseline, schema_version=1)
        with self.assertRaisesRegex(ValueError, "helper schema"):
            review.compare_inventory(legacy, baseline)
        for group, name in (("objects", obj.name), ("meshes", mesh.name), ("images", image.name)):
            with self.subTest(group=group):
                row = next(item for item in baseline[group] if item["name"] == name)
                self.assertEqual(row["tags"]["review"], {
                    "threshold": 0.25,
                    "note": "synthetic baseline",
                })

        tracked = {"objects": obj, "meshes": mesh, "images": image}
        unchanged = review.compare_inventory(baseline, review.inventory())
        self.assertTrue(all(not unchanged[group]["changed"] for group in tracked))

        for changed_group, owner in tracked.items():
            with self.subTest(changed_group=changed_group):
                owner["review"]["threshold"] = 1.25
                comparison = review.compare_inventory(baseline, review.inventory())
                self.assertEqual(comparison[changed_group]["changed"], [owner.name])
                self.assertTrue(all(not comparison[group]["changed"]
                                    for group in tracked if group != changed_group))
                owner["review"]["threshold"] = 0.25


if __name__ == "__main__":
    unittest.main(argv=[__file__])
