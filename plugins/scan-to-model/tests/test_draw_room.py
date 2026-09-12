"""Behavioral tests for the generic declared room drawing producer."""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PRODUCER = PLUGIN_ROOT / 'scripts' / 'draw_room.py'
MATH_HELPER = PLUGIN_ROOT / 'scripts' / 'drawing.py'


class DrawRoomTests(unittest.TestCase):
    def test_declared_views_draw_selected_faces_and_write_review_outputs(self):
        native_data = {
            'schema_version': 1,
            'status': 'ok',
            'all_visible_guard': True,
            'model_sha256': 'model-fixture-sha',
            'objects': [{
                'name': 'fixture-mesh',
                'vertices_world_m': [[0, 0, 0], [2, 0, 1], [2, 2, 1], [0, 2, 0]],
                'polygons': [[0, 1, 2, 3]],
                'loop_triangles': [
                    {'polygon_index': 0, 'vertex_indices': [0, 1, 2]},
                    {'polygon_index': 0, 'vertex_indices': [0, 2, 3]},
                ],
            }],
        }
        base_view = {
            'subjects': [{
                'object_id': 'fixture-mesh',
                'style': 'architecture',
                'face_indices': [0],
            }],
            'bounds_frame': [-1, 3, -1, 3],
            'axis_labels': ['horizontal', 'vertical'],
            'annotations': [],
        }
        views = [
            dict(base_view, id='P1', kind='plan', title='Plan', note='Plan fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 1, 0],
                 cut={'axis': 2, 'value_m': 0.5, 'keep_below': True}),
            dict(base_view, id='R1', kind='reflected_ceiling', title='RCP', note='RCP fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 1, 0],
                 cut={'axis': 2, 'value_m': 0.5, 'keep_below': False}),
            dict(base_view, id='E1', kind='elevation', title='Elevation', note='Elevation fixture',
                 right_frame=[1, 0, 0], up_frame=[0, 0, 1]),
            dict(base_view, id='S1', kind='section', title='Section', note='Section fixture',
                 right_frame=[0, 1, 0], up_frame=[0, 0, 1],
                 cut={'axis': 0, 'value_m': 1.0}),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            native_path = root / 'native.json'
            native_path.write_text(json.dumps(native_data, indent=2) + '\n')
            specification = {
                'model_sha256': native_data['model_sha256'],
                'native_sha256': hashlib.sha256(native_path.read_bytes()).hexdigest(),
                'room_id': 'fixture-room',
                'frame_axes_world': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'frame_source': 'fixture',
                'frame_source_sha256': 'fixture-sha',
                'styles': {'architecture': {'color': '#566573'}},
                'section_marks': [],
                'views': views,
            }
            views_path = root / 'views.json'
            views_path.write_text(json.dumps(specification, indent=2) + '\n')
            output = root / 'output'

            result = subprocess.run([
                sys.executable, '-B', str(PRODUCER),
                '--native', str(native_path),
                '--views', str(views_path),
                '--math-helper', str(MATH_HELPER),
                '--title', 'Fixture Room',
                '--output-stem', 'fixture-room',
                '--output', str(output),
            ], capture_output=True, text=True, check=True)

            self.assertEqual(json.loads(result.stdout)['geometry_pages'], 4)
            manifest = json.loads((output / 'drawing-manifest.json').read_text())
            self.assertEqual(
                [record['view_id'] for record in manifest['rendered_selections']],
                ['P1', 'R1', 'E1', 'S1'],
            )
            for record in manifest['rendered_selections']:
                self.assertEqual(record['drawn_faces'], {'fixture-mesh': [0]})
            detail_images = sorted(output.glob('P*.png')) + sorted(output.glob('R*.png')) + sorted(output.glob('E*.png')) + sorted(output.glob('S*.png'))
            self.assertEqual(len(detail_images), 4)
            self.assertTrue((output / 'fixture-room-geometry.pdf').is_file())
            self.assertTrue((output / 'fixture-room-overview.png').is_file())
            self.assertTrue(all(path.stat().st_size > 0 for path in detail_images))


if __name__ == '__main__':
    unittest.main()
