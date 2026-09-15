"""Native image decoding and calibrated depth contracts using synthetic files.

Run with --output /path/to/review/polycam-fixtures; the directory must be new.
All input fixtures and the test result are retained there.
Unittest discovery retains fixtures under SCAN_TO_MODEL_TEST_SCRATCH or
.test-scratch/polycam in the working directory.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import unittest
import uuid
import zlib

import numpy as np
from PIL import Image, __version__ as pillow_version

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from polycam import (clip_camera_segment, digest, pixel_ray,
                     project_display_points, project_points, read_frame,
                     unproject, validate_depth)


def write_png(path, values, bit_depth, color_type):
    """Write explicit sample bytes, avoiding encoder mode or scaling choices."""
    height, width = values.shape[:2]
    samples = values.astype('>u2' if bit_depth == 16 else 'u1')
    rows = b''.join(b'\0' + row.tobytes() for row in samples)

    def chunk(kind, data):
        return (struct.pack('>I', len(data)) + kind + data
                + struct.pack('>I', zlib.crc32(kind + data)))

    header = struct.pack('>IIBBBBB', width, height, bit_depth, color_type, 0, 0, 0)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header)
                     + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def frame_fixture(root):
    for directory in ('images', 'depth', 'confidence', 'cameras'):
        (root / 'keyframes' / directory).mkdir(parents=True)
    camera = {'width': 6, 'height': 4, 'fx': 6, 'fy': 4, 'cx': 2, 'cy': 0,
              't_00': 1, 't_01': 0, 't_02': 0, 't_03': 2,
              't_10': 0, 't_11': 1, 't_12': 0, 't_13': 3,
              't_20': 0, 't_21': 0, 't_22': 1, 't_23': 4}
    (root / 'keyframes/cameras/001.json').write_text(json.dumps(camera))
    Image.new('RGB', (6, 4), (80, 120, 160)).save(root / 'keyframes/images/001.jpg')
    write_png(root / 'keyframes/confidence/001.png',
              np.array([[255, 255, 0], [255, 255, 255]]), 8, 0)
    return root / 'keyframes/depth/001.png', camera


class PolycamTests(unittest.TestCase):
    output = None

    def setUp(self):
        if self.output is None:
            scratch = Path(os.environ.get('SCAN_TO_MODEL_TEST_SCRATCH',
                                          Path.cwd() / '.test-scratch' / 'polycam'))
            self.root = scratch / f'{self._testMethodName}-{uuid.uuid4()}'
        else:
            self.root = self.output / self._testMethodName
        self.root.mkdir(parents=True)

    def test_depth_samples_and_source_hashes_survive_decoding(self):
        path, _ = frame_fixture(self.root)
        expected = [[0, 1, 255], [256, 65535, 1000]]
        write_png(path, np.array(expected), 16, 0)
        before = {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        with Image.open(path) as image:
            decoder = {'mode': image.mode, 'dtype': str(np.array(image).dtype)}
        camera, depth, confidence, rgb = read_frame(self.root, '001')
        self.assertEqual(depth.dtype, np.dtype('uint16'))
        np.testing.assert_array_equal(depth, expected)
        np.testing.assert_array_equal(confidence, [[255, 255, 0], [255, 255, 255]])
        self.assertEqual(rgb.shape, (4, 6, 3))
        self.assertEqual(before, {name: digest(self.root / name) for name in before})
        (self.root / 'decoding.json').write_text(json.dumps({
            'pillow': pillow_version, 'decoder': decoder, 'depth': depth.tolist(),
            'depth_dtype': str(depth.dtype), 'source_hashes': before,
        }, indent=2) + '\n')

    def test_decoded_samples_unproject_with_confidence_and_range_limits(self):
        path, _ = frame_fixture(self.root)
        write_png(path, np.array([[0, 1, 255], [256, 65535, 1000]]), 16, 0)
        camera, depth, confidence, _ = read_frame(self.root, '001')
        points, pixels = unproject(depth, confidence, camera, max_depth_m=70)
        np.testing.assert_array_equal(pixels, [[1, 0], [0, 1], [1, 1], [2, 1]])
        expected = [[2, 3, 3.999], [2 - .256/3, 2.872, 3.744],
                    [2, -29.7675, -61.535], [2 + 1/3, 2.5, 3]]
        np.testing.assert_allclose(points, expected, atol=1e-12, rtol=0)
        points, pixels = unproject(depth, confidence, camera)
        np.testing.assert_array_equal(pixels, [[1, 0], [0, 1], [2, 1]])
        np.testing.assert_allclose(points, np.array(expected)[[0, 1, 3]], atol=1e-12, rtol=0)

    def test_project_points_round_trips_rotated_translated_camera(self):
        angle = np.deg2rad(23)
        rotation = np.array([[np.cos(angle), 0, np.sin(angle)],
                             [0, 1, 0],
                             [-np.sin(angle), 0, np.cos(angle)]])
        camera = {'width': 640, 'height': 480, 'fx': 500, 'fy': 510,
                  'cx': 311, 'cy': 229}
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = [2, -1, 4]
        for i in range(3):
            for j in range(4):
                camera[f't_{i}{j}'] = transform[i, j]
        camera_points = np.array([[-.7, .4, -2], [.2, -.3, -3], [1, .8, -1.5]])
        world = camera_points @ rotation.T + transform[:3, 3]
        pixels, depths, front = project_points(world, camera)
        expected_pixels = np.column_stack((500 * camera_points[:, 0] / -camera_points[:, 2] + 311,
                                            229 - 510 * camera_points[:, 1] / -camera_points[:, 2]))
        np.testing.assert_allclose(pixels, expected_pixels, atol=1e-12)
        np.testing.assert_allclose(depths, -camera_points[:, 2], atol=1e-12)
        np.testing.assert_array_equal(front, [True, True, True])

    def test_project_display_points_round_trips_raw_and_upright_non_square(self):
        _, camera = frame_fixture(self.root)
        raw_pixels = np.array([[1.25, 2.5], [4.5, 1.25]])
        points = []
        for pixel in raw_pixels:
            origin, direction = pixel_ray(camera, pixel, orientation='raw')
            points.append(origin + 3.0 * direction)
        points = np.asarray(points)
        expected_upright = np.column_stack((camera['height'] - 1 - raw_pixels[:, 1],
                                            raw_pixels[:, 0]))
        raw, raw_depths, raw_front = project_display_points(points, camera, 'raw')
        upright, upright_depths, upright_front = project_display_points(
            points, camera, 'upright90cw')
        np.testing.assert_allclose(raw, raw_pixels, atol=1e-12)
        np.testing.assert_allclose(upright, expected_upright, atol=1e-12)
        np.testing.assert_allclose(upright_depths, raw_depths, atol=1e-12)
        np.testing.assert_array_equal(raw_front, [True, True])
        np.testing.assert_array_equal(upright_front, [True, True])

    def test_project_display_points_rejects_unknown_orientation(self):
        _, camera = frame_fixture(self.root)
        with self.assertRaises(ValueError):
            project_display_points(np.array([[0., 0., -1.]]), camera, 'rotated')

    def test_project_points_inverts_rounded_camera_rotation(self):
        angle = np.deg2rad(23)
        rotation = np.array([[np.cos(angle), 0, np.sin(angle)],
                             [0, 1, 0],
                             [-np.sin(angle), 0, np.cos(angle)]])
        rotation = np.round(rotation, decimals=6)
        camera = {'width': 640, 'height': 480, 'fx': 500, 'fy': 510,
                  'cx': 311, 'cy': 229}
        transform = np.eye(4)
        transform[:3, :3] = rotation
        transform[:3, 3] = [2, -1, 4]
        for i in range(3):
            for j in range(4):
                camera[f't_{i}{j}'] = transform[i, j]
        camera_points = np.array([[-.7, .4, -2], [.2, -.3, -3], [1, .8, -1.5]])
        world = camera_points @ rotation.T + transform[:3, 3]
        old_camera_points = (world - transform[:3, 3]) @ rotation
        old_pixels = np.column_stack((500 * old_camera_points[:, 0] / -old_camera_points[:, 2] + 311,
                                      229 - 510 * old_camera_points[:, 1] / -old_camera_points[:, 2]))
        expected_pixels = np.column_stack((500 * camera_points[:, 0] / -camera_points[:, 2] + 311,
                                            229 - 510 * camera_points[:, 1] / -camera_points[:, 2]))
        self.assertGreater(np.max(np.abs(old_pixels - expected_pixels)), 1e-5)
        pixels, depths, front = project_points(world, camera)
        np.testing.assert_allclose(pixels, expected_pixels, atol=1e-9, rtol=0)
        np.testing.assert_allclose(depths, -camera_points[:, 2], atol=1e-9, rtol=0)
        np.testing.assert_array_equal(front, [True, True, True])

    def test_pixel_ray_returns_analytic_world_ray_without_depth(self):
        angle = np.deg2rad(27)
        rotation = np.array([[np.cos(angle), 0, np.sin(angle)],
                             [0, 1, 0],
                             [-np.sin(angle), 0, np.cos(angle)]])
        camera = {'width': 640, 'height': 480, 'fx': 500, 'fy': 510,
                  'cx': 311, 'cy': 229,
                  't_00': rotation[0, 0], 't_01': rotation[0, 1],
                  't_02': rotation[0, 2], 't_03': 2,
                  't_10': rotation[1, 0], 't_11': rotation[1, 1],
                  't_12': rotation[1, 2], 't_13': -1,
                  't_20': rotation[2, 0], 't_21': rotation[2, 1],
                  't_22': rotation[2, 2], 't_23': 4}
        origin, direction = pixel_ray(camera, (411, 329))
        np.testing.assert_allclose(origin, [2, -1, 4], atol=1e-12)
        expected = rotation @ np.array([100 / 500, -100 / 510, -1.0])
        expected /= np.linalg.norm(expected)
        np.testing.assert_allclose(direction, expected, atol=1e-12)
        self.assertAlmostEqual(np.linalg.norm(direction), 1.0, places=12)

    def test_pixel_ray_raw_and_upright_90cw_are_equivalent(self):
        _, camera = frame_fixture(self.root)
        raw_pixel = (1.25, 2.5)
        upright_pixel = (camera['height'] - 1 - raw_pixel[1], raw_pixel[0])
        raw_origin, raw_direction = pixel_ray(camera, raw_pixel, orientation='raw')
        upright_origin, upright_direction = pixel_ray(
            camera, upright_pixel, orientation='upright90cw')
        np.testing.assert_allclose(upright_origin, raw_origin, atol=1e-12)
        np.testing.assert_allclose(upright_direction, raw_direction, atol=1e-12)

    def test_pixel_ray_intersects_projected_point_round_trip(self):
        _, camera = frame_fixture(self.root)
        point = np.array([2.5, 2.25, 1.0])
        pixel, _, front = project_points(point[None], camera)
        self.assertTrue(front[0])
        origin, direction = pixel_ray(camera, pixel[0])
        distance = np.dot(point - origin, direction)
        np.testing.assert_allclose(origin + distance * direction, point, atol=1e-12)

    def test_pixel_ray_does_not_require_depth_files(self):
        camera = {'width': 4, 'height': 3, 'fx': 4, 'fy': 3, 'cx': 2, 'cy': 1,
                  't_00': 1, 't_01': 0, 't_02': 0, 't_03': 0,
                  't_10': 0, 't_11': 1, 't_12': 0, 't_13': 0,
                  't_20': 0, 't_21': 0, 't_22': 1, 't_23': 0}
        origin, direction = pixel_ray(camera, (2, 1))
        np.testing.assert_allclose(origin, [0, 0, 0])
        np.testing.assert_allclose(direction, [0, 0, -1])

    def test_pixel_ray_rejects_invalid_coordinates_and_orientation(self):
        _, camera = frame_fixture(self.root)
        for pixel in ((-0.1, 1), (camera['width'], 1), (1, -0.1),
                      (1, camera['height']), (float('nan'), 1), (1, float('inf'))):
            with self.subTest(pixel=pixel), self.assertRaises(ValueError):
                pixel_ray(camera, pixel)
        for orientation in ('upright', 'Upright90CW', '', None):
            with self.subTest(orientation=orientation), self.assertRaises(ValueError):
                pixel_ray(camera, (1, 1), orientation=orientation)

    def test_pixel_ray_uses_upright_image_dimensions_for_non_square_bounds(self):
        camera = {'width': 1024, 'height': 768, 'fx': 900, 'fy': 900,
                  'cx': 512, 'cy': 384,
                  't_00': 1, 't_01': 0, 't_02': 0, 't_03': 2,
                  't_10': 0, 't_11': 1, 't_12': 0, 't_13': 3,
                  't_20': 0, 't_21': 0, 't_22': 1, 't_23': 4}
        origin, direction = pixel_ray(camera, (620, 1008),
                                      orientation='upright90cw')
        self.assertEqual(origin.tolist(), [2.0, 3.0, 4.0])
        self.assertTrue(np.isfinite(direction).all())
        with self.assertRaises(ValueError):
            pixel_ray(camera, (800, 200), orientation='upright90cw')

    def test_project_points_marks_camera_plane_and_behind_without_infinities(self):
        _, camera = frame_fixture(self.root)
        pixels, depths, front = project_points(np.array([[2, 3, 2], [2, 3, 4], [2, 3, 5.0]]), camera)
        np.testing.assert_array_equal(front, [True, False, False])
        self.assertTrue(np.isfinite(pixels[0]).all())
        self.assertTrue(np.isfinite(depths[0]))
        self.assertTrue(np.isnan(pixels[1:]).all())
        self.assertTrue(np.isnan(depths[1:]).all())
        with self.assertRaises(ValueError):
            project_points([[0, 0, float('nan')]], camera)

    def test_project_points_round_trips_scaled_depth_pixels_to_native_rgb(self):
        _, camera = frame_fixture(self.root)
        depth = np.array([[1000, 0, 2000], [0, 1500, 0]], dtype=np.uint16)
        confidence = np.full((2, 3), 255, dtype=np.uint8)
        points, depth_pixels = unproject(depth, confidence, camera)
        rgb_pixels, depths, front = project_points(points, camera)
        np.testing.assert_allclose(rgb_pixels, depth_pixels * 2, atol=1e-12)
        np.testing.assert_allclose(depths, [1, 2, 1.5], atol=1e-12)
        np.testing.assert_array_equal(front, [True, True, True])

    def test_rejects_png_samples_that_are_not_16_bit_grayscale(self):
        for bits, color_type, channels in [(8, 0, 1), (8, 2, 3), (16, 2, 3),
                                            (8, 4, 2), (16, 4, 2), (16, 6, 4)]:
            with self.subTest(bits=bits, color_type=color_type):
                root = self.root / f'bits-{bits}-color-{color_type}'
                path, _ = frame_fixture(root)
                shape = (2, 3) if channels == 1 else (2, 3, channels)
                write_png(path, np.full(shape, 128), bits, color_type)
                with self.assertRaises(ValueError):
                    read_frame(root, '001')

    def test_rejects_non_png_even_with_uint16_samples_and_png_suffix(self):
        path, _ = frame_fixture(self.root)
        Image.fromarray(np.array([[0, 1, 255], [256, 65535, 1000]], dtype=np.uint16)).save(path, format='TIFF')
        with self.assertRaises(ValueError):
            read_frame(self.root, '001')

    def test_array_contract_still_rejects_non_uint16_and_invalid_shapes(self):
        _, camera = frame_fixture(self.root)
        confidence = np.full((2, 3), 255, dtype=np.uint8)
        invalid = [np.full((2, 3), value, dtype=dtype)
                   for dtype, value in [(np.int32, 1), (np.int32, -1), (np.int32, 65536),
                                        (np.uint8, 1), (np.float64, 1), (np.float64, np.nan)]]
        invalid.extend([np.zeros((0, 0), dtype=np.uint16), np.zeros((2, 3, 1), dtype=np.uint16)])
        for depth in invalid:
            with self.subTest(dtype=depth.dtype, shape=depth.shape), self.assertRaises(ValueError):
                validate_depth(depth, confidence, camera)

    def test_camera_segment_with_positive_depth_is_preserved(self):
        result = clip_camera_segment([0, 0, -2], [1, 1, -3], near_depth_m=0.1)

        self.assertTrue(result['visible'])
        self.assertFalse(result['camera_plane_clipped'])
        self.assertEqual(result['original_camera_depth_m'], [2.0, 3.0])
        self.assertEqual(result['original_camera_points_m'], [[0.0, 0.0, -2.0], [1.0, 1.0, -3.0]])
        self.assertEqual(result['clip_parameters'], [0.0, 1.0])
        np.testing.assert_allclose(result['camera_points_m'], [[0, 0, -2], [1, 1, -3]])

    def test_camera_segment_wholly_behind_is_excluded_with_audit_record(self):
        result = clip_camera_segment([0, 0, 1], [1, 1, 0.2], near_depth_m=0.1)

        self.assertFalse(result['visible'])
        self.assertFalse(result['camera_plane_clipped'])
        self.assertEqual(result['original_camera_depth_m'], [-1.0, -0.2])
        self.assertIsNone(result['clip_parameters'])
        self.assertIsNone(result['camera_points_m'])

    def test_camera_segment_forward_crossing_clips_at_positive_near_depth(self):
        result = clip_camera_segment([0, 0, 0.5], [1, 1, -2], near_depth_m=0.1)

        self.assertTrue(result['visible'])
        self.assertTrue(result['camera_plane_clipped'])
        self.assertAlmostEqual(result['clip_parameters'][0], 0.24)
        self.assertEqual(result['clip_parameters'][1], 1.0)
        np.testing.assert_allclose(result['camera_points_m'][0], [0.24, 0.24, -0.1])
        self.assertEqual(result['original_camera_depth_m'], [-0.5, 2.0])
        self.assertAlmostEqual(result['safe_camera_depth_m'][0], 0.1)

    def test_camera_segment_reverse_crossing_clips_at_positive_near_depth(self):
        result = clip_camera_segment([0, 0, -2], [1, 1, 0.5], near_depth_m=0.1)

        self.assertTrue(result['visible'])
        self.assertTrue(result['camera_plane_clipped'])
        self.assertEqual(result['clip_parameters'][0], 0.0)
        self.assertAlmostEqual(result['clip_parameters'][1], 0.76)
        np.testing.assert_allclose(result['camera_points_m'][1], [0.76, 0.76, -0.1])
        self.assertEqual(result['original_camera_depth_m'], [2.0, -0.5])
        self.assertAlmostEqual(result['safe_camera_depth_m'][1], 0.1)

    def test_camera_segment_on_camera_plane_is_clipped_forward(self):
        result = clip_camera_segment([0, 0, 0], [1, 1, -1], near_depth_m=0.1)

        self.assertTrue(result['visible'])
        self.assertTrue(result['camera_plane_clipped'])
        self.assertAlmostEqual(result['clip_parameters'][0], 0.1)
        np.testing.assert_allclose(result['camera_points_m'][0], [0.1, 0.1, -0.1])
        self.assertEqual(result['original_camera_depth_m'], [0.0, 1.0])

    def test_camera_segment_rejects_nonfinite_endpoints_and_invalid_near_depth(self):
        for start, end in (([float('nan'), 0, -1], [0, 0, -1]),
                           ([0, 0, -1], [float('inf'), 0, -1])):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                clip_camera_segment(start, end, near_depth_m=0.1)
        for near_depth in (0, -0.1, float('nan'), float('inf')):
            with self.subTest(near_depth=near_depth), self.assertRaises(ValueError):
                clip_camera_segment([0, 0, -1], [0, 0, -2], near_depth_m=near_depth)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output directory must not exist; retain previous fixtures separately')
    args.output.mkdir(parents=True)
    PolycamTests.output = args.output
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PolycamTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    (args.output / 'result.json').write_text(json.dumps({
        'pillow': pillow_version, 'numpy': np.__version__, 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'passed': result.wasSuccessful(),
    }, indent=2) + '\n')
    sys.exit(0 if result.wasSuccessful() else 1)
