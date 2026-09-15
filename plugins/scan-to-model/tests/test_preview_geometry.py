import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from preview_geometry import generate


class PreviewGeometryTests(unittest.TestCase):
    def test_exports_obj_and_skips_behind_camera_face(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            camera = {'width': 8, 'height': 6, 'fx': 6, 'fy': 6, 'cx': 4, 'cy': 3,
                      't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
                      't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
                      't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0}
            (root / 'camera.json').write_text(json.dumps(camera))
            photo = Image.new('RGB', (8, 6), 'white')
            photo.putpixel((0, 0), (12, 34, 56))
            photo.save(root / 'photo.png')
            spec = {'vertices': [[-1, -1, -3], [1, -1, -3], [0, 1, -3],
                                  [0, 0, 2], [1, 0, 2], [0, 1, 2]],
                    'faces': [[0, 1, 2], [3, 4, 5]],
                    'frames': [{'id': 'view', 'camera': 'camera.json', 'rgb': 'photo.png',
                                'raw_to_model4x4': np.eye(4).tolist(), 'orientation': 'upright90cw'}]}
            spec_path = root / 'spec.json'; spec_path.write_text(json.dumps(spec))
            output = root / 'output'
            generate(spec_path, output)
            result = json.loads((output / 'result.json').read_text())
            self.assertEqual(result['frames'][0]['faces'][0]['status'], 'drawn')
            self.assertEqual(result['frames'][0]['faces'][1]['reason'], 'behind-camera vertex')
            obj_lines = (output / 'geometry.obj').read_text().splitlines()
            self.assertEqual(sum(line.startswith('v ') for line in obj_lines), 6)
            self.assertIn('f 1 2 3', obj_lines)
            self.assertIn('f 4 5 6', obj_lines)
            with Image.open(output / 'view.png') as overlay:
                self.assertEqual(overlay.getpixel((5, 0)), (12, 34, 56))
                self.assertEqual(overlay.size, (6, 8 + 24))

    def test_rejects_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); spec = root / 'spec.json'
            spec.write_text(json.dumps({'vertices': [[0, 0, 0]], 'faces': []}))
            output = root / 'output'; output.mkdir()
            with self.assertRaisesRegex(ValueError, 'new'):
                generate(spec, output)

    def test_rejects_malformed_face(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); spec = root / 'spec.json'
            spec.write_text(json.dumps({'vertices': [[0, 0, 0]], 'faces': [[0, 1, 0]]}))
            with self.assertRaisesRegex(ValueError, 'valid vertex'):
                generate(spec, root / 'output')
