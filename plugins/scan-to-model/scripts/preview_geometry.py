"""Export source-local mesh geometry and camera overlays for review."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from polycam import project_model_points


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_geometry(spec):
    vertices = np.asarray(spec.get('vertices'), dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
        raise ValueError('vertices must be a finite Nx3 array')
    faces = spec.get('faces')
    if not isinstance(faces, list) or not faces:
        raise ValueError('faces must be a nonempty list')
    checked = []
    for face in faces:
        if (not isinstance(face, list) or len(face) < 3
                or any(isinstance(i, bool) or not isinstance(i, int) or i < 0 or i >= len(vertices)
                       for i in face)):
            raise ValueError('faces must contain valid vertex indices')
        checked.append(face)
    return vertices, checked


def _clip(a, b, width, height):
    x0, y0 = a; x1, y1 = b
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0., 1.
    for p, q in ((-dx, x0), (dx, width - 1 - x0), (-dy, y0), (dy, height - 1 - y0)):
        if p == 0:
            if q < 0: return None
        else:
            t = q / p
            if p < 0: t0 = max(t0, t)
            else: t1 = min(t1, t)
            if t0 > t1: return None
    return [(x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)]


def _write_obj(path, vertices, faces):
    with path.open('w') as out:
        for point in vertices:
            out.write('v %.17g %.17g %.17g\n' % tuple(point))
        for face in faces:
            out.write('f ' + ' '.join(str(i + 1) for i in face) + '\n')


def generate(spec_path, output):
    spec_path = Path(spec_path).resolve()
    spec = json.loads(spec_path.read_text())
    if output.exists():
        raise ValueError('output directory must be new')
    output.mkdir(parents=True)
    vertices, faces = _load_geometry(spec)
    labels = spec.get('face_labels', [None] * len(faces))
    colors = spec.get('face_colors', [(255, 40, 40)] * len(faces))
    if len(labels) != len(faces) or len(colors) != len(faces):
        raise ValueError('face_labels and face_colors must match faces')
    _write_obj(output / 'geometry.obj', vertices, faces)
    result = {'spec_sha256': _hash(spec_path), 'geometry_obj': 'geometry.obj', 'frames': []}
    for frame in spec.get('frames', []):
        orientation = frame.get('orientation', 'raw')
        camera_path = (spec_path.parent / frame['camera']).resolve()
        rgb_path = (spec_path.parent / frame['rgb']).resolve()
        camera = json.loads(camera_path.read_text())
        with Image.open(rgb_path) as image:
            image = image.convert('RGB')
            if image.size != (camera['width'], camera['height']):
                raise ValueError('RGB dimensions must match camera calibration')
            if orientation == 'upright90cw':
                image = image.transpose(Image.Transpose.ROTATE_270)
            elif orientation != 'raw':
                raise ValueError("orientation must be 'raw' or 'upright90cw'")
            draw = ImageDraw.Draw(image)
            projected, depths, front = project_model_points(vertices, camera,
                                                             frame['raw_to_model4x4'], orientation)
            face_results = []
            for index, face in enumerate(faces):
                if not bool(np.all(front[face])):
                    face_results.append({'index': index, 'status': 'skipped', 'reason': 'behind-camera vertex'})
                    continue
                segments = []
                for start, end in zip(face, face[1:] + face[:1]):
                    clipped = _clip(projected[start], projected[end], image.width, image.height)
                    if clipped:
                        draw.line([(round(x), round(y)) for x, y in clipped], fill=tuple(colors[index]), width=2)
                        segments.append(clipped)
                face_results.append({'index': index, 'label': labels[index], 'color': colors[index], 'status': 'drawn', 'segments': segments,
                                     'pixels': projected[face].tolist(), 'depths': depths[face].tolist()})
            image_name = f"{frame['id']}.png"
            image = ImageOps.expand(image, border=(0, 0, 0, 24), fill=(255, 255, 255))
            ImageDraw.Draw(image).text((4, image.height - 20),
                                       'PROVISIONAL WIRES; INCLUDES OCCLUDED GEOMETRY',
                                       fill=(80, 20, 20))
            image.save(output / image_name)
        result['frames'].append({'id': frame['id'], 'camera': str(camera_path), 'rgb': str(rgb_path),
                                 'camera_sha256': _hash(camera_path), 'rgb_sha256': _hash(rgb_path),
                                 'orientation': orientation, 'overlay': image_name,
                                 'faces': face_results})
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    generate(Path(args.spec), Path(args.output))


if __name__ == '__main__':
    main()
