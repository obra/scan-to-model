"""Write sampled Polycam points as NPZ, PLY, and provenance metadata."""

import argparse
import json
from pathlib import Path

import numpy as np

from polycam import camera_matrix, capture_inventory, digest, frame_paths, read_frame, unproject


def write_ply(path, points, colors):
    points = np.asarray(points)
    colors = np.asarray(colors)
    if points.ndim != 2 or points.shape[1] != 3 or points.shape != colors.shape or not len(points):
        raise ValueError('Expected nonempty matching N by 3 points and colors')
    if not np.isfinite(points).all() or colors.dtype != np.uint8:
        raise ValueError('Expected finite points and uint8 colors')
    rows = np.empty(len(points), dtype=[('p', '<f4', (3,)), ('c', 'u1', (3,))])
    rows['p'], rows['c'] = points, colors
    header = (
        f'ply\nformat binary_little_endian 1.0\nelement vertex {len(rows)}\n'
        'property float x\nproperty float y\nproperty float z\n'
        'property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n'
    )
    with Path(path).open('wb') as stream:
        stream.write(header.encode('ascii'))
        stream.write(rows.tobytes())


def build_reference(source, output, frame_step=20, pixel_step=4, depth_variant='raw', pose_variant='raw'):
    for step in (frame_step, pixel_step):
        if isinstance(step, bool) or not isinstance(step, (int, np.integer)) or step < 1:
            raise ValueError('Sampling steps must be positive integers')
    source, output = Path(source), Path(output)
    if output.suffix != '.npz':
        raise ValueError('Reference output must have an .npz extension')
    inventory = capture_inventory(source)
    if depth_variant not in inventory['variants']['depth'] or pose_variant not in inventory['variants']['pose']:
        raise ValueError('Requested depth or pose variant is unavailable')
    source_manifest = None
    for parent in (source, *source.parents):
        manifest_path = parent / '.source-manifest.json'
        if manifest_path.is_file():
            candidate = json.loads(manifest_path.read_text())
            if (parent / candidate['capture_root']).resolve() == source.resolve():
                source_manifest = candidate
                break
    frame_ids = inventory['frame_ids'][::frame_step]
    positions, colors, pixels, point_frames, hashes = [], [], [], [], []
    for frame_id in frame_ids:
        camera, depth, confidence, rgb = read_frame(source, frame_id, depth_variant, pose_variant)
        points, uv = unproject(depth, confidence, camera)
        eligible_count = len(points)
        points, uv = points[::pixel_step], uv[::pixel_step]
        paths = frame_paths(source, frame_id, depth_variant, pose_variant)
        component_hashes = {key: digest(path) for key, path in paths.items()}
        if source_manifest:
            for key, path in paths.items():
                member = (Path(source_manifest['capture_root']) / path.relative_to(source)).as_posix()
                if source_manifest['members'].get(member) != component_hashes[key]:
                    raise ValueError(f'Source component differs from preserved archive: {path}')
        hashes.append({
            'frame_id': frame_id,
            **component_hashes,
            'component_paths': {key: path.relative_to(source).as_posix() for key, path in paths.items()},
            'depth_variant': depth_variant, 'pose_variant': pose_variant,
            'depth_shape': list(depth.shape), 'rgb_shape': list(rgb.shape),
            'depth_dtype': str(depth.dtype), 'confidence_dtype': str(confidence.dtype),
            'camera_to_world': camera_matrix(camera).tolist(),
            'intrinsics': {key: camera[key] for key in ('width', 'height', 'fx', 'fy', 'cx', 'cy')},
            'eligible_point_count': eligible_count, 'sampled_point_count': len(points),
        })
        if not len(points):
            continue
        u = np.clip(np.rint(uv[:, 0] * rgb.shape[1] / depth.shape[1]).astype(int), 0, rgb.shape[1] - 1)
        v = np.clip(np.rint(uv[:, 1] * rgb.shape[0] / depth.shape[0]).astype(int), 0, rgb.shape[0] - 1)
        positions.append(points)
        colors.append(rgb[v, u])
        pixels.append(uv.astype(np.int32))
        point_frames.extend([frame_id] * len(points))
    if not positions:
        raise ValueError('No eligible reference points')
    points, rgb = np.concatenate(positions), np.concatenate(colors)
    if not np.isfinite(points).all():
        raise ValueError('Reference points must be finite')
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, points=points, colors=rgb, pixels=np.concatenate(pixels), frame_ids=np.asarray(point_frames))
    write_ply(output.with_suffix('.ply'), points, rgb)
    metadata = {
        'source': str(source.resolve()), 'frame_ids': frame_ids,
        'source_archive_sha256': source_manifest['source_sha256'] if source_manifest else None,
        'source_archive': source_manifest['source_archive'] if source_manifest else None,
        'frame_step': int(frame_step), 'pixel_step': int(pixel_step),
        'depth_variant': depth_variant, 'pose_variant': pose_variant,
        'max_depth_m': 5, 'min_depth_m_exclusive': 0, 'confidence_value': 255,
        'depth_units': 'millimetres', 'point_units': 'metres',
        'pixel_coordinates': 'native depth (u, v), origin top left; unrotated',
        'pixel_sampling': 'Every pixel_step-th eligible pixel in row-major order, independently per frame',
        'rgb_sampling': 'Native depth pixel scaled to RGB dimensions and rounded to nearest pixel',
        'point_count': len(points), 'component_hashes': hashes,
        'bounds': [points.min(0).tolist(), points.max(0).tolist()],
        'coordinate_space': 'capture world; metres; ARKit +Y up, -Z forward',
        'output_sha256': {'npz': digest(output), 'ply': digest(output.with_suffix('.ply'))},
    }
    output.with_suffix('.json').write_text(json.dumps(metadata, indent=2) + '\n')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--frame-step', type=int, default=20)
    parser.add_argument('--pixel-step', type=int, default=4)
    parser.add_argument('--depth-variant', choices=['raw', 'clean'], default='raw')
    parser.add_argument('--pose-variant', choices=['raw', 'corrected'], default='raw')
    arguments = parser.parse_args()
    print(json.dumps(build_reference(arguments.capture, arguments.output, arguments.frame_step, arguments.pixel_step, arguments.depth_variant, arguments.pose_variant)))
