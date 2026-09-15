"""Behavior tests for bounded Polycam frame retention."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN_ROOT / 'scripts' / 'retain_frames.py'


def capture_fixture(root):
    capture = root / 'capture'
    for directory in ('images', 'cameras', 'depth', 'confidence'):
        (capture / 'keyframes' / directory).mkdir(parents=True)
    for frame_id, color in (('002', (20, 40, 80)), ('3', (40, 80, 20)), ('010', (120, 60, 30))):
        image = Image.new('RGB', (2, 3), color)
        image.putpixel((0, 0), (255, 0, 0))
        image.save(capture / 'keyframes' / 'images' / f'{frame_id}.jpg', quality=95)
        camera = {
            'width': 2, 'height': 3, 'fx': 2, 'fy': 3, 'cx': 1, 'cy': 1,
            't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
            't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
            't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0,
        }
        (capture / 'keyframes' / 'cameras' / f'{frame_id}.json').write_text(json.dumps(camera))
        Image.new('L', (2, 3), 0).save(capture / 'keyframes' / 'depth' / f'{frame_id}.png')
        Image.new('L', (2, 3), 255).save(capture / 'keyframes' / 'confidence' / f'{frame_id}.png')
    members = {}
    for path in sorted(capture.rglob('*')):
        if path.is_file():
            members[path.relative_to(capture).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    (capture / '.source-manifest.json').write_text(json.dumps({
        'capture_root': '.', 'source_sha256': 'archive-sha', 'members': members,
    }))
    record = root / 'selection.json'
    record.write_text(json.dumps({'model_sha256': 'model-hash', 'selection': ['002', '010']}))
    return capture, record


class RetainFramesTests(unittest.TestCase):
    def test_retains_exact_frames_orientation_ordinals_records_and_bindings(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture, record = capture_fixture(root)
            other_record = root / 'finding.bin'
            other_record.write_bytes(b'\x00\xffsource finding\n')
            output = root / 'retained'
            completed = subprocess.run([
                sys.executable, str(RUNNER), '--capture', str(capture), '--frame-id', '010',
                '--frame-id', '002', '--orientation', 'upright90cw', '--record', str(record),
                '--record', str(other_record),
                '--output', str(output),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            packet = json.loads((output / 'frame-retention.json').read_text())
            self.assertEqual([frame['frame_id'] for frame in packet['frames']], ['002', '010'])
            self.assertEqual(packet['inventory']['frame_ids'], ['002', '3', '010'])
            self.assertEqual([frame['native_ordinal'] for frame in packet['frames']], [0, 2])
            self.assertEqual(packet.get('index_basis', {}).get('ordinal_base'), 0)
            for frame in packet['frames']:
                source = capture / 'keyframes' / 'images' / f"{frame['frame_id']}.jpg"
                retained = Path(frame['native']['path'])
                self.assertEqual(retained.read_bytes(), source.read_bytes())
                for component, retained_key in (('rgb', 'native'), ('camera', 'camera')):
                    original = Path(frame['source_paths'][component])
                    self.assertEqual(Path(frame[retained_key]['path']).read_bytes(), original.read_bytes())
                    self.assertEqual(frame['source_sha256'][component],
                                     hashlib.sha256(original.read_bytes()).hexdigest())
                    self.assertEqual(frame[retained_key]['sha256'], frame['source_sha256'][component])
                self.assertEqual(frame['native_dimensions'], [2, 3])
                self.assertEqual(frame['display_dimensions'], [3, 2])
                self.assertEqual(frame['display']['source_sha256'], frame['native']['sha256'])
                self.assertTrue(all(binding['matches_manifest'] for binding in frame['source_manifest_binding'].values()))
                with Image.open(source) as image, Image.open(frame['display']['path']) as display:
                    expected = [image.getpixel(point) for point in
                                ((0, 2), (0, 1), (0, 0), (1, 2), (1, 1), (1, 0))]
                    self.assertEqual(display.size, (3, 2))
                    self.assertEqual(list(display.getdata()), expected)
            self.assertEqual(sorted(path.name for path in (output / 'frames').iterdir()), ['002', '010'])
            manifest = packet['source_manifest']
            self.assertEqual(Path(manifest['retained']['path']).read_bytes(),
                             (capture / '.source-manifest.json').read_bytes())
            self.assertEqual(manifest['sha256'], manifest['retained']['sha256'])
            self.assertEqual(packet['records'][0]['original_record']['sha256'],
                             hashlib.sha256(record.read_bytes()).hexdigest())
            self.assertEqual(packet['records'][0]['model_sha256'], 'model-hash')
            self.assertEqual(Path(packet['records'][0]['retained']['path']).read_bytes(), record.read_bytes())
            self.assertEqual(packet['records'][0]['retained']['sha256'],
                             packet['records'][0]['original_record']['sha256'])
            self.assertEqual(Path(packet['records'][1]['retained']['path']).read_bytes(), other_record.read_bytes())
            self.assertEqual(packet['records'][1]['original_record']['sha256'],
                             hashlib.sha256(other_record.read_bytes()).hexdigest())
            self.assertIsNone(packet['records'][1]['model_sha256'])
            self.assertFalse(any('depth' in path.parts or 'confidence' in path.parts
                                 for path in output.rglob('*')))
            receipt = json.loads((output / 'run-receipt.json').read_text())
            self.assertEqual(receipt['status'], 'pass')
            self.assertEqual(receipt['returncode'], 0)
            runtime = Path(receipt['runtime'])
            preflight = json.loads((runtime / 'preflight.json').read_text())
            self.assertEqual(preflight['helpers'], receipt['helpers'])
            self.assertEqual(Path(receipt['argv'][2]).parent, runtime)
            for name, binding in receipt['helpers'].items():
                self.assertEqual(Path(binding['path']).read_bytes(), (PLUGIN_ROOT / 'scripts' / name).read_bytes())
                self.assertEqual(binding['sha256'], hashlib.sha256(Path(binding['path']).read_bytes()).hexdigest())

    def test_rejects_invalid_selected_source_before_retaining_any_frames(self):
        for invalid in ('jpeg', 'camera', 'dimensions', 'manifest'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                capture, _ = capture_fixture(root)
                if invalid == 'jpeg':
                    (capture / 'keyframes/images/010.jpg').write_bytes(b'not a JPEG')
                elif invalid == 'camera':
                    (capture / 'keyframes/cameras/010.json').write_text('{}')
                elif invalid == 'dimensions':
                    camera_path = capture / 'keyframes/cameras/010.json'
                    camera = json.loads(camera_path.read_text())
                    camera['width'] = 5
                    camera_path.write_text(json.dumps(camera))
                else:
                    (capture / 'keyframes/cameras/010.json').write_text(
                        (capture / 'keyframes/cameras/010.json').read_text() + '\n')
                if invalid != 'manifest':
                    (capture / '.source-manifest.json').unlink()
                output = root / 'retained'
                completed = subprocess.run([
                    sys.executable, str(RUNNER), '--capture', str(capture), '--frame-id', '002',
                    '--frame-id', '010', '--orientation', 'upright90cw', '--output', str(output),
                ], capture_output=True, text=True, check=False)
                self.assertNotEqual(completed.returncode, 0)
                self.assertFalse((output / 'frames').exists())
                self.assertFalse((output / 'frame-retention.json').exists())
                receipt = json.loads((output / 'run-receipt.json').read_text())
                self.assertEqual(receipt['status'], 'fail')
                self.assertNotEqual(receipt['returncode'], 0)
                self.assertTrue((output / receipt['stderr']).read_text())

    def test_rejects_unknown_frame_and_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            capture, record = capture_fixture(root)
            unknown_output = root / 'unknown'
            unknown = subprocess.run([
                sys.executable, str(RUNNER), '--capture', str(capture), '--frame-id', '999',
                '--orientation', 'upright90cw', '--record', str(record), '--output', str(unknown_output),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(unknown.returncode, 0)
            self.assertEqual(json.loads((unknown_output / 'run-receipt.json').read_text())['status'], 'fail')
            self.assertFalse((unknown_output / 'frames').exists())
            output = root / 'retained'
            first = subprocess.run([
                sys.executable, str(RUNNER), '--capture', str(capture), '--frame-id', '002',
                '--orientation', 'upright90cw', '--output', str(output),
            ], capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            existing = {path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()}
            refused = subprocess.run([
                sys.executable, str(RUNNER), '--capture', str(capture), '--frame-id', '002',
                '--orientation', 'upright90cw', '--output', str(output),
            ], capture_output=True, text=True, check=False)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual({path.relative_to(output): path.read_bytes() for path in output.rglob('*') if path.is_file()},
                             existing)


if __name__ == '__main__':
    unittest.main()
