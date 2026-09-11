"""Synthetic Blender inventory contracts."""

import importlib.util
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


if __name__ == "__main__":
    unittest.main(argv=[__file__])
