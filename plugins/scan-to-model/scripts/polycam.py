"""Read Polycam native keyframes and unproject calibrated depth."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


def digest(path):
    """Return the full SHA-256 of a source file."""
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def frame_paths(root, frame_id, depth_variant='raw', pose_variant='raw'):
    if depth_variant not in ('raw', 'clean'):
        raise ValueError("depth_variant must be 'raw' or 'clean'")
    if pose_variant not in ('raw', 'corrected'):
        raise ValueError("pose_variant must be 'raw' or 'corrected'")
    frame_id = str(frame_id)
    if not frame_id or frame_id in ('.', '..') or any(c in frame_id for c in '/\\\0'):
        raise ValueError('Invalid frame ID')
    base = Path(root) / 'keyframes'
    suffix = '' if depth_variant == 'raw' else '.Clean'
    camera_dir = 'cameras' if pose_variant == 'raw' else 'corrected_cameras'
    return {
        'rgb': base / 'images' / f'{frame_id}.jpg',
        'depth': base / 'depth' / f'{frame_id}{suffix}.png',
        'confidence': base / 'confidence' / f'{frame_id}{suffix}.png',
        'camera': base / camera_dir / f'{frame_id}.json',
    }


def camera_matrix(camera):
    """Validate and return a complete proper rigid camera-to-world transform."""
    try:
        transform = np.eye(4)
        transform[:3] = [[camera[f't_{i}{j}'] for j in range(4)] for i in range(3)]
        if any(f't_3{j}' in camera for j in range(4)):
            transform[3] = [camera[f't_3{j}'] for j in range(4)]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Camera requires a complete numeric pose') from error
    if not np.isfinite(transform).all() or not np.allclose(transform[3], [0, 0, 0, 1], atol=1e-7, rtol=0):
        raise ValueError('Camera pose must be finite and homogeneous')
    rotation = transform[:3, :3]
    if not np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-4, rtol=0) or not np.isclose(np.linalg.det(rotation), 1, atol=1e-4, rtol=0):
        raise ValueError('Camera pose must contain a proper rigid rotation')
    return transform


def validate_camera(camera):
    if not isinstance(camera, dict):
        raise ValueError('Camera must be a JSON object')
    for key in ('width', 'height', 'fx', 'fy', 'cx', 'cy'):
        value = camera.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f'Camera {key} must be finite')
        if key in ('width', 'height', 'fx', 'fy') and value <= 0:
            raise ValueError(f'Camera {key} must be positive')
        if key in ('width', 'height') and int(value) != value:
            raise ValueError(f'Camera {key} must be an integer')
    camera_matrix(camera)


def validate_depth(depth, confidence, camera):
    if depth.ndim != 2 or not depth.size or depth.dtype != np.uint16:
        raise ValueError('Depth must be a nonempty uint16 2-D array')
    if confidence.ndim != 2 or confidence.dtype != np.uint8 or confidence.shape != depth.shape:
        raise ValueError('Confidence must be a matching uint8 2-D array')
    height, width = depth.shape
    if width * camera['height'] != height * camera['width']:
        raise ValueError('Depth and camera aspect ratios differ')


def read_depth(path):
    """Decode unsigned 16-bit grayscale PNG samples without changing their values."""
    with Path(path).open('rb') as stream:
        header = stream.read(26)
        # IHDR records the source bit depth and color type, independent of Pillow's mode.
        if (header[:16] != b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR'
                or header[24:26] != b'\x10\x00'):
            raise ValueError('Depth image must be a 16-bit grayscale PNG')
        stream.seek(0)
        with Image.open(stream) as image:
            return np.array(image, dtype=np.uint16)


def read_frame(root, frame_id, depth_variant='raw', pose_variant='raw'):
    """Read the requested variants without replacing missing calibration or data."""
    paths = frame_paths(root, frame_id, depth_variant, pose_variant)
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(f'Missing frame component: {path}')
    camera = json.loads(paths['camera'].read_text())
    validate_camera(camera)
    depth = read_depth(paths['depth'])
    with Image.open(paths['confidence']) as image:
        confidence = np.array(image)
    with Image.open(paths['rgb']) as image:
        rgb = np.array(image.convert('RGB'))
    validate_depth(depth, confidence, camera)
    if (camera['width'], camera['height']) != (rgb.shape[1], rgb.shape[0]):
        raise ValueError('RGB/camera dimensions mismatch')
    return camera, depth, confidence, rgb


def capture_inventory(root):
    """Require matching component IDs and complete optional variant sets."""
    base = Path(root) / 'keyframes'

    def ids(directory, extension, clean=False):
        result = set()
        for path in (base / directory).glob(f'*{extension}'):
            stem = path.name[:-len(extension)]
            if extension == '.png':
                if stem.endswith('.Clean') != clean:
                    continue
                if clean:
                    stem = stem[:-len('.Clean')]
            if not stem or not path.is_file():
                raise ValueError(f'Invalid frame component: {path}')
            result.add(stem)
        return result

    components = {
        'rgb': ids('images', '.jpg'),
        'raw_camera': ids('cameras', '.json'),
        'raw_depth': ids('depth', '.png'),
        'raw_confidence': ids('confidence', '.png'),
        'clean_depth': ids('depth', '.png', clean=True),
        'clean_confidence': ids('confidence', '.png', clean=True),
        'corrected_camera': ids('corrected_cameras', '.json'),
    }
    expected = components['rgb']
    if not expected:
        raise ValueError('Capture contains no RGB keyframes')
    optional = {
        'clean': bool(components['clean_depth'] or components['clean_confidence']),
        'corrected': (base / 'corrected_cameras').exists(),
    }
    for component, found in components.items():
        required = component.startswith('raw_') or component == 'rgb'
        required |= component.startswith('clean_') and optional['clean']
        required |= component == 'corrected_camera' and optional['corrected']
        if required and found != expected:
            raise ValueError(f'{component} IDs differ: missing={sorted(expected - found)}, orphan={sorted(found - expected)}')
    frame_ids = sorted(expected, key=lambda value: (not value.isdigit(), int(value) if value.isdigit() else value))
    return {
        'frame_ids': frame_ids,
        'component_counts': {key: len(value) for key, value in components.items()},
        'variants': {
            'depth': ['raw', 'clean'] if optional['clean'] else ['raw'],
            'pose': ['raw', 'corrected'] if optional['corrected'] else ['raw'],
        },
    }


def unproject(depth, confidence, camera, max_depth_m=5, confidence_value=255):
    """Return world points and their native (u, v) depth pixels."""
    depth = np.asarray(depth)
    confidence = np.asarray(confidence)
    validate_camera(camera)
    validate_depth(depth, confidence, camera)
    if not np.isfinite(max_depth_m) or max_depth_m <= 0:
        raise ValueError('Maximum depth must be finite and positive')
    if not isinstance(confidence_value, (int, np.integer)) or not 0 <= confidence_value <= 255:
        raise ValueError('Confidence value must be an integer from 0 to 255')
    height, width = depth.shape
    sx, sy = width / camera['width'], height / camera['height']
    fx, fy = camera['fx'] * sx, camera['fy'] * sy
    cx, cy = camera['cx'] * sx, camera['cy'] * sy
    v, u = np.nonzero((confidence == confidence_value) & (depth > 0) & (depth <= max_depth_m * 1000))
    z = depth[v, u].astype(float) / 1000
    points = np.column_stack(((u - cx) * z / fx, -(v - cy) * z / fy, -z))
    transform = camera_matrix(camera)
    return points @ transform[:3, :3].T + transform[:3, 3], np.column_stack((u, v))
