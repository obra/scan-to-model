"""Retain selected Polycam RGB frames and their source records."""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from pixel_inspection import display_dimensions
from polycam import capture_inventory, digest, frame_paths, validate_camera


def _resolved_file(value, label):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"{label} must be a file: {path}")
    return path


def _source_manifest(capture):
    for parent in (capture, *capture.parents):
        path = parent / '.source-manifest.json'
        if not path.is_file():
            continue
        contents = path.read_bytes()
        manifest = json.loads(contents)
        if not isinstance(manifest, dict) or not isinstance(manifest.get('members'), dict):
            raise ValueError(f'Source manifest is invalid: {path}')
        capture_root = manifest.get('capture_root')
        if isinstance(capture_root, str) and (parent / capture_root).resolve() == capture:
            return path, manifest, contents
    return None, None, None


def _copy_binding(contents, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)
    return {'path': str(destination), 'sha256': digest(destination), 'bytes': destination.stat().st_size}


def retain_frames(capture, frame_ids, orientation, records, output):
    capture = Path(capture).expanduser().resolve(strict=True)
    output = Path(output).expanduser().resolve()
    if not capture.is_dir():
        raise ValueError(f'capture must be a directory: {capture}')
    if orientation not in ('raw', 'upright90cw'):
        raise ValueError('orientation must be raw or upright90cw')
    if output.exists():
        raise ValueError(f'output must be a new directory: {output}')
    inventory = capture_inventory(capture)
    unknown = sorted(set(frame_ids) - set(inventory['frame_ids']))
    if unknown:
        raise ValueError(f'Unknown frame ID(s): {", ".join(unknown)}')
    if len(set(frame_ids)) != len(frame_ids):
        raise ValueError('frame IDs must be unique')
    record_paths = [_resolved_file(record, 'record') for record in records]
    if len({path.name for path in record_paths}) != len(record_paths):
        raise ValueError('record basenames must be unique')

    manifest_path, manifest, manifest_bytes = _source_manifest(capture)
    prepared = []
    for ordinal, frame_id in enumerate(inventory['frame_ids']):
        if frame_id not in frame_ids:
            continue
        paths = {key: path for key, path in frame_paths(capture, frame_id).items()
                 if key in ('rgb', 'camera')}
        contents = {key: path.read_bytes() for key, path in paths.items()}
        hashes = {key: hashlib.sha256(value).hexdigest() for key, value in contents.items()}
        camera = json.loads(contents['camera'])
        validate_camera(camera)
        with Image.open(BytesIO(contents['rgb'])) as image:
            if image.format != 'JPEG':
                raise ValueError(f'RGB source must be a JPEG: {paths["rgb"]}')
            image.load()
            dimensions = image.size
        if dimensions != (camera['width'], camera['height']):
            raise ValueError(f'RGB dimensions differ from camera: {frame_id}')
        bindings = {}
        if manifest is not None:
            for key, path in paths.items():
                member = (Path(manifest['capture_root']) / path.relative_to(capture)).as_posix()
                bindings[key] = {'member': member, 'sha256': hashes[key],
                                 'matches_manifest': manifest['members'].get(member) == hashes[key]}
            if not all(binding['matches_manifest'] for binding in bindings.values()):
                raise ValueError(f'Source component differs from preserved archive: {frame_id}')
        prepared.append((ordinal, frame_id, paths, contents, hashes, dimensions, bindings))
    record_contents = [(path, path.read_bytes()) for path in record_paths]

    output.mkdir(parents=True)
    source_manifest_binding = None
    if manifest_path is not None:
        source_manifest_binding = {
            'path': str(manifest_path), 'sha256': hashlib.sha256(manifest_bytes).hexdigest(),
            'retained': _copy_binding(manifest_bytes, output / 'source-manifest.json'),
            'source_archive_sha256': manifest.get('source_sha256'),
        }
    retained = []
    for ordinal, frame_id, paths, contents, hashes, dimensions, bindings in prepared:
        native = _copy_binding(contents['rgb'], output / 'frames' / frame_id / 'native.jpg')
        camera = _copy_binding(contents['camera'], output / 'frames' / frame_id / 'camera.json')
        with Image.open(BytesIO(contents['rgb'])) as image:
            image = image.convert('RGB')
            width, height = dimensions
            source = {'orientation': orientation, 'width': width, 'height': height}
            if orientation == 'upright90cw':
                image = image.transpose(Image.Transpose.ROTATE_270)
            display_path = output / 'frames' / frame_id / f'display-{orientation}.png'
            image.save(display_path, format='PNG')
        display = {'path': str(display_path), 'sha256': digest(display_path),
                   'bytes': display_path.stat().st_size, 'source_sha256': hashes['rgb']}
        frame_record = {
            'frame_id': frame_id,
            'native_ordinal': ordinal,
            'source_paths': {
                'rgb': str(paths['rgb']), 'camera': str(paths['camera']),
            },
            'source_sha256': hashes,
            'native': native,
            'camera': camera,
            'display': display,
            'native_dimensions': [width, height],
            'display_dimensions': list(display_dimensions(source)),
            'orientation': orientation,
            'pixel_coordinates': 'zero-based pixel centers; origin top left; u right, v down',
            'mapping': ('raw native pixel centers map directly to display pixel centers'
                        if orientation == 'raw' else
                        'native (u, v) maps to display (H - 1 - v, u)'),
        }
        if manifest is not None:
            frame_record['source_manifest_binding'] = bindings
        retained.append(frame_record)

    retained_records = []
    for record_path, contents in record_contents:
        destination = output / 'records' / record_path.name
        binding = _copy_binding(contents, destination)
        parsed = None
        if record_path.suffix.lower() == '.json':
            try:
                candidate = json.loads(contents)
                if isinstance(candidate, dict):
                    parsed = candidate
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
        retained_records.append({
            'original_record': {'path': str(record_path), 'sha256': hashlib.sha256(contents).hexdigest()},
            'retained': binding,
            'model_sha256': parsed.get('model_sha256') if parsed else None,
        })
    record = {
        'schema_version': 1,
        'capture': str(capture),
        'requested_frame_ids': frame_ids,
        'orientation': orientation,
        'inventory': inventory,
        'index_basis': {'source': 'polycam.capture_inventory(capture)["frame_ids"]', 'ordinal_base': 0},
        'source_manifest': source_manifest_binding,
        'frames': retained,
        'records': retained_records,
        'limits': 'Retains selected RGB/camera/record bytes and display derivatives; it does not copy depth, fit alignment or infer physical identity.',
    }
    (output / 'frame-retention.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--frame-id', action='append', required=True)
    parser.add_argument('--orientation', choices=('raw', 'upright90cw'), required=True)
    parser.add_argument('--record', action='append', default=[])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    retain_frames(args.capture, args.frame_id, args.orientation, args.record, args.output)


if __name__ == '__main__':
    main()
