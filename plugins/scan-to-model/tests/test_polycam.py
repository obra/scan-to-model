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
from polycam import digest, read_frame, unproject, validate_depth


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
