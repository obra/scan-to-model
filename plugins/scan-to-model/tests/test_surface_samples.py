"""Exercise staged native sample review using the existing per-patch fit switch."""

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


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'surfaces.py'
SCRATCH_ROOT = Path(os.environ.get('SCAN_TO_MODEL_TEST_SCRATCH', Path.cwd() / '.test-scratch' / 'surface-samples'))


class SurfaceSampleTests(unittest.TestCase):
    def test_pixel_inspections_show_whole_patch_and_vertices_without_changing_samples(self):
        root = SCRATCH_ROOT / str(uuid.uuid4())
        capture = root / 'capture'
        for directory in ('images', 'depth', 'confidence', 'cameras'):
            (capture / 'keyframes' / directory).mkdir(parents=True)
        grid = np.array([[(u * 2, v * 3, (u + v) % 256) for u in range(96)]
                         for v in range(64)], dtype=np.uint8)
        Image.fromarray(grid).save(capture / 'keyframes/images/001.jpg')
        Image.fromarray(np.full((32, 48), 2000, dtype=np.uint16)).save(
            capture / 'keyframes/depth/001.png')
        Image.fromarray(np.full((32, 48), 255, dtype=np.uint8)).save(
            capture / 'keyframes/confidence/001.png')
        camera = {
            'width': 96, 'height': 64, 'fx': 96, 'fy': 96, 'cx': 48, 'cy': 32,
            't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
            't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
            't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0,
        }
        (capture / 'keyframes/cameras/001.json').write_text(json.dumps(camera))
        source_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in capture.rglob('*') if path.is_file()}
        environment = os.environ.copy()
        for key, directory in [('TMPDIR', 'tmp'), ('MPLCONFIGDIR', 'matplotlib')]:
            path = root / directory
            path.mkdir()
            environment[key] = str(path)
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        cases = [
            ('raw', [[0, 0], [18.5, 3.5], [19, 47], [3, 47]],
             [[0, 0], [18.5, 3.5], [19, 47], [3, 47]], [0, 0, 52, 64], [19, 4]),
            ('upright90cw', [[0, 0], [20.5, 3.5], [21, 70], [3, 70]],
             [[0, 63], [3.5, 42.5], [70, 42], [70, 60]], [0, 0, 54, 96], [20, 4]),
            ('raw', [[0, 0], [95.75, 63.75], [0, 63]],
             [[0, 0], [95.75, 63.75], [0, 63]], [0, 0, 96, 64], None),
            ('upright90cw', [[0, 0], [63.75, 95.75], [0, 95]],
             [[0, 63], [95.75, -.75], [95, 63]], [0, 0, 64, 96], None),
        ]
        with Image.open(capture / 'keyframes/images/001.jpg') as image:
            decoded = image.convert('RGBA')
        for case_index, (orientation, polygon, native, crop_edges, nearest_display) in enumerate(cases):
            for fitting in (False, True):
                with self.subTest(orientation=orientation, fitting=fitting):
                    spec = {'capture': 'capture', 'orientation': orientation, 'patches': [{
                        'id': 'patch', 'frame_id': '001', 'physical_surface': 'synthetic plane',
                        'fit': fitting, 'polygon_px': polygon,
                    }], 'comparisons': []}
                    spec_path = root / f'{case_index}-{orientation}-{fitting}.json'
                    spec_path.write_text(json.dumps(spec))
                    results = []
                    outputs = []
                    for enabled in (False, True):
                        output = root / f'{case_index}-{orientation}-{fitting}-{enabled}'
                        command = [sys.executable, str(SCRIPT), '--spec', str(spec_path),
                                   '--output', str(output)]
                        if enabled:
                            command.append('--pixel-inspections')
                        process = subprocess.run(command, env=environment, capture_output=True, text=True)
                        (root / f'{output.name}.log').write_text(process.stdout + process.stderr)
                        self.assertEqual(process.returncode, 0, process.stderr)
                        results.append(json.loads((output / 'measurements.json').read_text()))
                        outputs.append(output)
                    baseline = results[0]['patches'][0]
                    inspected = results[1]['patches'][0]
                    self.assertNotIn('pixel_inspection', baseline)
                    inspection = inspected.pop('pixel_inspection')
                    self.assertEqual(results[0], results[1])
                    self.assertEqual(inspection['status'], 'pending visual review')
                    self.assertEqual(inspection['polygon_native_pixel_centers'], native)
                    self.assertEqual(inspection['polygon_display_pixel_centers'], polygon)
                    self.assertEqual(inspection['source_rgb'], baseline['sources']['rgb'])
                    self.assertEqual((outputs[0] / baseline['figure']).read_bytes(),
                                     (outputs[1] / baseline['figure']).read_bytes())
                    with np.load(outputs[0] / baseline['samples']) as original, np.load(
                            outputs[1] / baseline['samples']) as extra:
                        for key in original.files:
                            np.testing.assert_array_equal(original[key], extra[key])
                        if not fitting:
                            self.assertFalse(extra['inlier_mask'].any())
                            self.assertIsNone(inspected['plane'])
                    crop = inspection['patch']
                    self.assertEqual(crop['display_bounds_pixel_edges'], crop_edges)
                    self.assertEqual(crop['resampling'], 'nearest')
                    shown = decoded if orientation == 'raw' else decoded.transpose(Image.Transpose.ROTATE_270)
                    expected = shown.crop(crop_edges)
                    expected = expected.resize((expected.width * 3, expected.height * 3), Image.Resampling.NEAREST)
                    for artifact in (crop, inspection['vertices']):
                        path = outputs[1] / artifact['path']
                        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), artifact['sha256'])
                    with Image.open(outputs[1] / crop['path']) as sheet:
                        np.testing.assert_array_equal(np.asarray(sheet.crop(crop['unmarked_bounds'])), np.asarray(expected))
                        self.assertNotEqual(sheet.crop(crop['marked_bounds']).tobytes(), expected.tobytes())
                    coordinates = inspection['vertices']['coordinates']
                    self.assertEqual([row['native'] for row in coordinates], native)
                    self.assertEqual([row['display'] for row in coordinates], polygon)
                    self.assertEqual(coordinates[1]['nearest_display_pixel'], nearest_display)
                    if nearest_display is None:
                        self.assertIsNone(coordinates[1]['nearest_native_pixel'])
                        self.assertEqual(coordinates[1]['source_pixel_status'], 'outside image')
                        self.assertEqual(coordinates[1]['outside_image_nearest_native_center'],
                                         [96, 64] if orientation == 'raw' else [96, -1])
                        self.assertEqual(coordinates[1]['outside_image_nearest_display_center'],
                                         [96, 64] if orientation == 'raw' else [64, 96])
                    with Image.open(outputs[1] / inspection['vertices']['path']) as sheet:
                        for row in coordinates:
                            if row['nearest_native_pixel'] is None:
                                continue
                            left, top, _, _ = row['unmarked_context_bounds']
                            self.assertEqual(sheet.getpixel((left + 128, top + 128)),
                                             decoded.getpixel(tuple(row['nearest_native_pixel'])))
        self.assertEqual(source_hashes, {path: hashlib.sha256(path.read_bytes()).hexdigest()
                                        for path in source_hashes})

    def test_tracking_segment_scope_rejects_mismatch_and_preserves_unknown(self):
        missing = object()

        def run_case(label, camera_segment=missing, declared_segment=missing,
                     patch_segment=missing, corrected=False, translated=False):
            root = SCRATCH_ROOT / str(uuid.uuid4()) / label
            capture = root / 'capture'
            for directory in ('images', 'depth', 'confidence', 'cameras'):
                (capture / 'keyframes' / directory).mkdir(parents=True)
            if corrected:
                (capture / 'keyframes/corrected_cameras').mkdir()
            Image.fromarray(np.full((4, 4), 2000, dtype=np.uint16)).save(
                capture / 'keyframes/depth/001.png')
            Image.fromarray(np.full((4, 4), 255, dtype=np.uint8)).save(
                capture / 'keyframes/confidence/001.png')
            Image.new('RGB', (8, 8), (31, 63, 95)).save(
                capture / 'keyframes/images/001.jpg')
            camera = {
                'width': 8, 'height': 8, 'fx': 8, 'fy': 8, 'cx': 4, 'cy': 4,
                't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
                't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
                't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0,
            }
            if camera_segment is not missing:
                camera['tracking_segment'] = camera_segment
            (capture / 'keyframes/cameras/001.json').write_text(json.dumps(camera))
            if corrected:
                corrected_camera = {key: value for key, value in camera.items()
                                    if key != 'tracking_segment'}
                (capture / 'keyframes/corrected_cameras/001.json').write_text(
                    json.dumps(corrected_camera))
            spec = {
                'capture': 'capture', 'orientation': 'raw',
                'analysis_frame': 'synthetic raw capture',
                'patches': [{
                    'id': 'sample', 'frame_id': '001', 'physical_surface': 'synthetic plane',
                    'fit': False, 'polygon_px': [[0, 0], [7, 0], [7, 7], [0, 7]],
                }],
                'comparisons': [],
            }
            if declared_segment is not missing:
                spec['tracking_segment'] = declared_segment
            if patch_segment is not missing:
                spec['patches'][0]['tracking_segment'] = patch_segment
            if corrected:
                spec['pose_variant'] = 'corrected'
            if translated:
                spec['transform'] = [
                    [1, 0, 0, 10], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1],
                ]
            spec_path = root / 'spec.json'
            spec_path.write_text(json.dumps(spec))
            source_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in capture.rglob('*') if path.is_file()}
            environment = os.environ.copy()
            for name, directory in [('MPLCONFIGDIR', 'matplotlib'), ('TMPDIR', 'tmp')]:
                path = root / directory
                path.mkdir()
                environment[name] = str(path)
            environment['PYTHONDONTWRITEBYTECODE'] = '1'
            output = root / 'output'
            process = subprocess.run(
                [sys.executable, str(SCRIPT), '--spec', str(spec_path), '--output', str(output)],
                env=environment, capture_output=True, text=True,
            )
            (root / 'process.log').write_text(process.stdout + process.stderr)
            self.assertEqual(source_hashes, {
                path: hashlib.sha256(path.read_bytes()).hexdigest() for path in source_hashes
            })
            return process, output

        mismatch, mismatch_output = run_case('mismatch', camera_segment=7, declared_segment=8)
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn('tracking segment', mismatch.stderr.lower())
        self.assertFalse((mismatch_output / 'measurements.json').exists())

        unavailable, unavailable_output = run_case('unavailable', declared_segment=7)
        self.assertNotEqual(unavailable.returncode, 0)
        self.assertIn('tracking segment', unavailable.stderr.lower())
        self.assertFalse((unavailable_output / 'measurements.json').exists())

        cleared, cleared_output = run_case(
            'cleared', camera_segment=8, declared_segment=7,
            patch_segment=None, translated=True)
        self.assertNotEqual(cleared.returncode, 0)
        self.assertIn('tracking segment', cleared.stderr.lower())
        self.assertFalse(any(cleared_output.iterdir()))

        matching, matching_output = run_case('matching', camera_segment=7, declared_segment=7)
        self.assertEqual(matching.returncode, 0, matching.stderr)
        matching_row = json.loads((matching_output / 'measurements.json').read_text())['patches'][0]
        self.assertEqual(matching_row['declared_tracking_segment'], 7)
        self.assertEqual(matching_row['camera_tracking_segment'], 7)

        corrected, corrected_output = run_case(
            'corrected', camera_segment=7, declared_segment=7, corrected=True)
        self.assertEqual(corrected.returncode, 0, corrected.stderr)
        corrected_row = json.loads(
            (corrected_output / 'measurements.json').read_text())['patches'][0]
        self.assertEqual(corrected_row['declared_tracking_segment'], 7)
        self.assertEqual(corrected_row['camera_tracking_segment'], 7)

        unknown, unknown_output = run_case('unknown')
        self.assertEqual(unknown.returncode, 0, unknown.stderr)
        unknown_row = json.loads((unknown_output / 'measurements.json').read_text())['patches'][0]
        self.assertIsNone(unknown_row['declared_tracking_segment'])
        self.assertIsNone(unknown_row['camera_tracking_segment'])

    def test_fit_switch_preserves_eligible_samples_and_source_review_figures(self):
        root = SCRATCH_ROOT / str(uuid.uuid4())
        capture = root / 'capture'
        for directory in ('images', 'depth', 'confidence', 'cameras'):
            (capture / 'keyframes' / directory).mkdir(parents=True)
        depth = np.full((8, 8), 2000, dtype=np.uint16)
        depth[1, 1] = 0
        depth[2, 2] = 6000
        confidence = np.full((8, 8), 255, dtype=np.uint8)
        confidence[3, 3] = 0
        confidence[0, 0] = 128
        Image.fromarray(depth).save(capture / 'keyframes/depth/001.png')
        Image.fromarray(confidence).save(capture / 'keyframes/confidence/001.png')
        Image.new('RGB', (16, 16), (140, 160, 180)).save(capture / 'keyframes/images/001.jpg')
        camera = {'width': 16, 'height': 16, 'fx': 16, 'fy': 16, 'cx': 8, 'cy': 8,
                  't_00': 1, 't_01': 0, 't_02': 0, 't_03': 1,
                  't_10': 0, 't_11': 1, 't_12': 0, 't_13': 2,
                  't_20': 0, 't_21': 0, 't_22': 1, 't_23': 3}
        (capture / 'keyframes/cameras/001.json').write_text(json.dumps(camera))
        source_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in capture.rglob('*') if p.is_file()}
        spec = {
            'capture': 'capture', 'orientation': 'raw', 'max_depth_m': 5,
            'confidence_value': 255, 'analysis_frame': 'synthetic transformed metres',
            'transform': [[0, -1, 0, 3], [1, 0, 0, -1], [0, 0, 1, 2], [0, 0, 0, 1]],
            'patches': [
                {'id': 'wide', 'frame_id': '001', 'physical_surface': 'synthetic plane',
                 'polygon_px': [[2, 2], [12, 2], [12, 12], [2, 12]]},
                {'id': 'small', 'frame_id': '001', 'physical_surface': 'synthetic plane',
                 'polygon_px': [[2, 2], [4, 2], [4, 4], [2, 4]]},
                {'id': 'confidence-excluded', 'frame_id': '001', 'physical_surface': 'synthetic plane',
                 'polygon_px': [[0, 0], [1, 0], [1, 1], [0, 1]]},
            ],
            'comparisons': [],
        }
        environment = os.environ.copy()
        for name, directory in [('MPLCONFIGDIR', 'matplotlib'), ('TMPDIR', 'tmp')]:
            path = root / directory
            path.mkdir()
            environment[name] = str(path)
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        outputs = {}
        for fitting in (False, True):
            mode = 'fit' if fitting else 'samples'
            for patch in spec['patches']:
                patch['fit'] = fitting
            spec_path = root / f'{mode}.json'
            spec_path.write_text(json.dumps(spec))
            spec_hash = hashlib.sha256(spec_path.read_bytes()).hexdigest()
            output = root / mode
            process = subprocess.run([sys.executable, str(SCRIPT), '--spec', str(spec_path),
                                      '--output', str(output)], env=environment, capture_output=True, text=True)
            (root / f'{mode}.log').write_text(process.stdout + process.stderr)
            self.assertEqual(process.returncode, 0, process.stderr)
            result = json.loads((output / 'measurements.json').read_text())
            self.assertEqual(result['comparisons'], [])
            self.assertEqual(result['spec']['sha256'], spec_hash)
            self.assertEqual(hashlib.sha256(spec_path.read_bytes()).hexdigest(), spec_hash)
            outputs[mode] = {row['id']: row for row in result['patches']}

        for name, selected in [
            ('wide', [(u, v) for v in range(1, 7) for u in range(1, 7)
                      if (u, v) not in {(1, 1), (2, 2), (3, 3)}]),
            ('small', [(2, 1), (1, 2)]),
            ('confidence-excluded', []),
        ]:
            with self.subTest(patch=name):
                row = outputs['samples'][name]
                self.assertEqual(row['eligible_pixels'], len(selected))
                self.assertEqual(row['native_patch_pixels'], {'wide': 36, 'small': 4, 'confidence-excluded': 1}[name])
                self.assertIsNone(row['plane'])
                self.assertEqual(row['fit_status'], 'not fitted')
                with np.load(root / 'samples' / row['samples']) as samples, np.load(root / 'fit' / outputs['fit'][name]['samples']) as fitted:
                    np.testing.assert_array_equal(samples['pixels'], np.asarray(selected).reshape(-1, 2))
                    expected_raw = [[1 + (u - 4) / 4, 2 - (v - 4) / 4, 1] for u, v in selected]
                    expected_points = [[1 + (v - 4) / 4, (u - 4) / 4, 3] for u, v in selected]
                    np.testing.assert_allclose(samples['raw_points'], np.asarray(expected_raw).reshape(-1, 3), atol=1e-12, rtol=0)
                    np.testing.assert_allclose(samples['points'], np.asarray(expected_points).reshape(-1, 3), atol=1e-12, rtol=0)
                    self.assertEqual(samples['inlier_mask'].shape, (len(selected),))
                    self.assertEqual(samples['inlier_mask'].dtype, np.dtype(bool))
                    self.assertFalse(samples['inlier_mask'].any())
                    for key in ('pixels', 'raw_points', 'points'):
                        np.testing.assert_array_equal(samples[key], fitted[key])
                    if name == 'wide':
                        self.assertTrue(fitted['inlier_mask'].all())
                for source in row['sources'].values():
                    self.assertEqual(source['sha256'], source_hashes[Path(source['path'])])
                self.assertEqual((root / 'samples' / row['figure']).read_bytes(),
                                 (root / 'fit' / outputs['fit'][name]['figure']).read_bytes())
        self.assertEqual(outputs['fit']['wide']['plane']['inlier_count'], 33)
        self.assertIsNone(outputs['fit']['small']['plane'])
        self.assertNotEqual(outputs['fit']['small']['fit_status'], 'not fitted')
        self.assertEqual(source_hashes, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_hashes})


if __name__ == '__main__':
    unittest.main()
