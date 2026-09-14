import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'run_surfaces.py'
SCRATCH = Path(os.environ.get('SCAN_TO_MODEL_TEST_SCRATCH', Path.cwd() / '.test-scratch' / 'run-surfaces'))
sys.path.insert(0, str(ROOT / 'scripts'))
import artifact_bindings


def capture(root, name, value=1000):
    base = root / name / 'keyframes'
    for directory in ('images', 'depth', 'confidence', 'cameras'):
        (base / directory).mkdir(parents=True)
    Image.new('RGB', (32, 32), (80, 100, 120)).save(base / 'images/001.jpg')
    Image.fromarray(np.full((32, 32), value, dtype=np.uint16)).save(base / 'depth/001.png')
    Image.fromarray(np.full((32, 32), 255, dtype=np.uint8)).save(base / 'confidence/001.png')
    camera = {'width': 32, 'height': 32, 'fx': 32, 'fy': 32, 'cx': 16, 'cy': 16,
              't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
              't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
              't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0}
    (base / 'cameras/001.json').write_text(json.dumps(camera))


class RunSurfacesTests(unittest.TestCase):
    def test_runs_with_relative_top_level_and_patch_captures(self):
        root = SCRATCH / str(uuid.uuid4()); root.mkdir(parents=True)
        capture(root, 'top', 1000); capture(root, 'patch', 2000)
        spec = {'capture': 'top', 'orientation': 'raw', 'fit': False, 'patches': [
            {'id': 'top_patch', 'frame_id': '001', 'physical_surface': 'top plane', 'fit': False,
             'polygon_px': [[1, 1], [30, 1], [30, 30], [1, 30]]},
            {'id': 'per_patch', 'capture': 'patch', 'frame_id': '001',
             'physical_surface': 'patch plane', 'fit': False, 'polygon_px': [[2, 2], [29, 2], [29, 29], [2, 29]]}],
            'comparisons': []}
        spec_path = root / 'spec.json'; spec_path.write_text(json.dumps(spec))
        output = root / 'output'
        env = os.environ.copy(); env.update({'PYTHONDONTWRITEBYTECODE': '1', 'MPLCONFIGDIR': str(root / 'mpl')})
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--spec', str(spec_path),
                                 '--output', str(output), '--pixel-inspections'],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        measurements = json.loads((output / 'measurements' / 'measurements.json').read_text())
        self.assertEqual(len(measurements['patches']), 2)
        self.assertTrue((output / 'measurements' / 'top_patch.npz').is_file())
        with np.load(output / 'measurements' / 'top_patch.npz') as top, np.load(output / 'measurements' / 'per_patch.npz') as patch:
            self.assertFalse(np.array_equal(top['raw_points'], patch['raw_points']))
            np.testing.assert_allclose(top['raw_points'][:, 2], -1.0)
            np.testing.assert_allclose(patch['raw_points'][:, 2], -2.0)
        self.assertIsNone(measurements['patches'][0]['plane'])
        self.assertIsNone(measurements['patches'][1]['plane'])
        for row in measurements['patches']:
            self.assertTrue((output / 'measurements' / row['pixel_inspection']['patch']['path']).is_file())
            self.assertTrue((output / 'measurements' / row['pixel_inspection']['vertices']['path']).is_file())
        self.assertGreater(measurements['patches'][0]['native_patch_pixels'], 0)
        receipt = json.loads((output / 'run-receipt.json').read_text())
        self.assertEqual(receipt['returncode'], 0)
        self.assertEqual(receipt['argv'][0], sys.executable)
        self.assertTrue(Path(receipt['argv'][2]).is_absolute())
        self.assertEqual(receipt['cwd'], str(output.resolve()))
        self.assertEqual(receipt['original_spec']['sha256'], hashlib.sha256(spec_path.read_bytes()).hexdigest())
        self.assertTrue(receipt['resolved_spec']['path'].endswith('resolved-spec.json'))
        resolved = json.loads((output / 'runtime' / 'resolved-spec.json').read_text())
        self.assertTrue(Path(resolved['capture']).is_absolute())
        self.assertTrue(Path(resolved['patches'][1]['capture']).is_absolute())
        self.assertIn('polycam.py', receipt['helpers'])
        self.assertIn('pixel_inspection.py', receipt['helpers'])
        self.assertTrue(receipt['launcher']['path'].endswith('/run_surfaces.py'))
        self.assertEqual(receipt['launcher']['sha256'], hashlib.sha256(
            Path(receipt['launcher']['path']).read_bytes()).hexdigest())
        self.assertTrue(receipt['source_launcher']['unchanged'])
        self.assertTrue(receipt['original_spec_unchanged'])
        bindings = root / 'bindings.json'
        bindings.write_text(json.dumps({'bindings': receipt['output_files']}))
        self.assertTrue(artifact_bindings.verify(bindings, output)['valid'])
        self.assertTrue(receipt['output_manifest'])

    def test_missing_capture_returns_failure_receipt_without_fake_measurements(self):
        root = SCRATCH / str(uuid.uuid4()); root.mkdir(parents=True)
        spec_path = root / 'spec.json'; spec_path.write_text(json.dumps({
            'capture': 'does-not-exist', 'orientation': 'raw', 'fit': False,
            'patches': [{'id': 'missing', 'frame_id': '001', 'physical_surface': 'unknown',
                         'polygon_px': [[1, 1], [30, 1], [30, 30], [1, 30]]}], 'comparisons': []}))
        output = root / 'output'; env = os.environ.copy(); env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--spec', str(spec_path), '--output', str(output)],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        receipt = json.loads((output / 'run-receipt.json').read_text())
        self.assertNotEqual(receipt['returncode'], 0)
        self.assertFalse((output / 'measurements' / 'measurements.json').exists())
        self.assertTrue((output / 'stderr.log').is_file())

    def test_refuses_existing_output_directory(self):
        root = SCRATCH / str(uuid.uuid4()); root.mkdir(parents=True)
        capture(root, 'top')
        spec_path = root / 'spec.json'; spec_path.write_text(json.dumps({'capture': 'top', 'patches': []}))
        output = root / 'output'; output.mkdir()
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--spec', str(spec_path), '--output', str(output)],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((output / 'run-receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
