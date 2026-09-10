"""Preserve a Polycam ZIP and create a validated, traceable capture."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile

from PIL import Image, ImageDraw

from polycam import capture_inventory, digest, frame_paths, read_frame


GENERATED = {'all', 'overview', '.source-manifest.json'}


def reject_symlinks(path):
    """Check the supplied path and its existing ancestors without resolving links."""
    path = Path(os.path.abspath(path))
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            raise ValueError(f'Output symlink is not allowed: {ancestor}')
    return path


def _members(archive):
    members = archive.infolist()
    if not members:
        raise ValueError('Archive is empty')
    aliases = {}
    names = set()
    files = set()
    directories = set()
    roots = set()
    for member in members:
        name = member.filename
        parts = name.rstrip('/').split('/')
        mode = member.external_attr >> 16
        if (not name or name != member.orig_filename or '\\' in name or
                name.startswith('/') or re.match(r'^[A-Za-z]:', name) or
                any(part in ('', '.', '..') for part in parts) or
                name != '/'.join(parts) + ('/' if member.is_dir() else '')):
            raise ValueError(f'Unsafe ZIP path: {name!r}')
        if stat.S_ISLNK(mode):
            raise ValueError(f'ZIP symlinks are not allowed: {name}')
        if stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f'Unsupported ZIP member type: {name}')
        if unicodedata.normalize('NFC', parts[0]).casefold() in GENERATED:
            raise ValueError(f'ZIP path is reserved for generated output: {name}')
        normalized = '/'.join(unicodedata.normalize('NFC', part).casefold() for part in parts)
        if normalized in names:
            raise ValueError(f'Duplicate or normalized ZIP alias: {name}')
        names.add(normalized)
        for length in range(1, len(parts) + 1):
            prefix = '/'.join(parts[:length])
            alias = '/'.join(normalized.split('/')[:length])
            if alias in aliases and aliases[alias] != prefix:
                raise ValueError(f'Normalized ZIP path alias: {name}')
            aliases[alias] = prefix
        if member.is_dir():
            directories.add(normalized)
        else:
            files.add(normalized)
        directories.update('/'.join(normalized.split('/')[:i]) for i in range(1, len(parts)))
        for index, part in enumerate(parts):
            if part == 'keyframes':
                roots.add('/'.join(parts[:index]))
    if files & directories:
        raise ValueError('ZIP file/directory path conflict')
    if len(roots) != 1:
        raise ValueError(f'Expected one keyframes root, found {len(roots)}')
    return members, next(iter(roots))


def _tree(path, skip_generated=False):
    """List files and directories while rejecting links, including dangling links."""
    files, directories = set(), set()
    for directory, child_dirs, child_files in os.walk(path, followlinks=False):
        for name in child_dirs + child_files:
            entry = Path(directory) / name
            reject_symlinks(entry)
            relative = entry.relative_to(path).as_posix()
            if skip_generated and relative.split('/')[0] in GENERATED:
                continue
            if entry.is_dir():
                directories.add(relative)
            elif entry.is_file():
                files.add(relative)
            else:
                raise ValueError(f'Unsupported extracted file type: {entry}')
    return files, directories


def _verify_extraction(capture, manifest):
    files, directories = _tree(capture, skip_generated=True)
    expected = manifest['members']
    if files != set(expected) or directories != set(manifest['directories']):
        raise ValueError('Existing extraction has missing or stale members')
    for name, checksum in expected.items():
        if digest(capture / name) != checksum:
            raise ValueError(f'Existing extracted member differs: {name}')


def _audit(root, capture):
    inventory = capture_inventory(root)
    rows = []
    for index, frame_id in enumerate(inventory['frame_ids']):
        camera, depth, confidence, rgb = read_frame(root, frame_id)
        for depth_variant in inventory['variants']['depth']:
            for pose_variant in inventory['variants']['pose']:
                if (depth_variant, pose_variant) != ('raw', 'raw'):
                    read_frame(root, frame_id, depth_variant, pose_variant)
        paths = frame_paths(root, frame_id)
        hashes = {key: digest(path) for key, path in paths.items()}
        if 'clean' in inventory['variants']['depth']:
            clean = frame_paths(root, frame_id, 'clean')
            hashes.update({f'clean_{key}': digest(clean[key]) for key in ('depth', 'confidence')})
        if 'corrected' in inventory['variants']['pose']:
            hashes['corrected_camera'] = digest(frame_paths(root, frame_id, pose_variant='corrected')['camera'])
        rows.append({
            'index': index, 'frame_id': frame_id,
            'file': paths['rgb'].relative_to(capture).as_posix(),
            'sha256': hashes['rgb'], 'component_hashes': hashes,
            'depth_shape': list(depth.shape), 'rgb_shape': list(rgb.shape),
        })
    return inventory, rows


def _sheets(rows, output, step, capture):
    chosen = rows[::step]
    output.mkdir(parents=True, exist_ok=True)
    for start in range(0, len(chosen), 80):
        batch = chosen[start:start + 80]
        canvas = Image.new('RGB', (1600, 1870), 'white')
        draw = ImageDraw.Draw(canvas)
        for index, row in enumerate(batch):
            x, y = index % 10 * 160 + 4, index // 10 * 230 + 4
            with Image.open(capture / row['file']) as image:
                upright = image.transpose(Image.Transpose.ROTATE_270)
                upright.thumbnail((152, 202))
                canvas.paste(upright, (x, y + 24))
            draw.text((x, y + 2), row['frame_id'][:20], fill='black')
        canvas.save(output / f'{start // 80 + 1:02d}.jpg')


def ingest(archive, project, capture_id=None):
    archive = Path(archive)
    project = reject_symlinks(project)
    checksum = digest(archive)
    capture_id = capture_id or archive.stem.lower().replace(' ', '-') + '-' + checksum[:8]
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', capture_id) or capture_id in ('.', '..'):
        raise ValueError('Invalid capture ID')
    source = reject_symlinks(project / 'sources' / archive.name)
    capture = reject_symlinks(project / 'derived' / 'scan-to-model' / 'captures' / capture_id)
    documents = reject_symlinks(project / 'docs' / 'scan-to-model' / 'captures' / capture_id)
    if documents.exists():
        _tree(documents)
    with zipfile.ZipFile(archive) as incoming:
        _members(incoming)
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        if not source.is_file() or digest(source) != checksum:
            raise FileExistsError(f'Source archive differs: {source}')
    else:
        with tempfile.NamedTemporaryFile(dir=source.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
        try:
            shutil.copyfile(archive, temporary_path)
            if digest(temporary_path) != checksum:
                raise ValueError('Source archive changed during preservation')
            temporary_path.replace(source)
        finally:
            temporary_path.unlink(missing_ok=True)
    if digest(source) != checksum:
        raise ValueError('Preserved archive hash mismatch')
    capture.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as preserved:
        members, relative_root = _members(preserved)
        manifest = {'source_sha256': checksum, 'source_archive': archive.name, 'capture_root': relative_root, 'members': {}, 'directories': []}
        directories = set()
        for member in members:
            path = Path(member.filename.rstrip('/'))
            directories.update(parent.as_posix() for parent in path.parents if parent != Path('.'))
            if member.is_dir():
                directories.add(path.as_posix())
            else:
                with preserved.open(member) as stream:
                    manifest['members'][member.filename] = hashlib.file_digest(stream, 'sha256').hexdigest()
        manifest['directories'] = sorted(directories)
        if capture.exists():
            _tree(capture)
            manifest_path = capture / '.source-manifest.json'
            if not manifest_path.is_file() or json.loads(manifest_path.read_text()) != manifest:
                raise ValueError('Existing extraction lacks matching source provenance')
            _verify_extraction(capture, manifest)
            inventory, rows = _audit(capture / relative_root, capture)
            _sheets(rows, capture / 'all', 1, capture)
            _sheets(rows, capture / 'overview', 20, capture)
        else:
            with tempfile.TemporaryDirectory(prefix=f'.{capture_id}-', dir=capture.parent) as temporary:
                stage = Path(temporary) / 'capture'
                stage.mkdir()
                for member in members:
                    output = stage / member.filename
                    if member.is_dir():
                        output.mkdir(parents=True, exist_ok=True)
                    else:
                        output.parent.mkdir(parents=True, exist_ok=True)
                        with preserved.open(member) as reader, output.open('xb') as writer:
                            shutil.copyfileobj(reader, writer)
                _verify_extraction(stage, manifest)
                inventory, rows = _audit(stage / relative_root, stage)
                _sheets(rows, stage / 'all', 1, stage)
                _sheets(rows, stage / 'overview', 20, stage)
                (stage / '.source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
                stage.rename(capture)
    root = capture / relative_root
    report = {
        'capture_id': capture_id, 'source': source.relative_to(project).as_posix(),
        'sha256': checksum, 'source_sha256': checksum,
        'capture_root': root.relative_to(project).as_posix(),
        'frames': len(rows), 'valid_frames': len(rows), 'errors': [],
        'component_counts': inventory['component_counts'], 'variants': inventory['variants'],
        'variant_validation': 'All present depth and pose combinations validated for every frame',
        'contact_sheet_rotation': '90 degrees clockwise from native RGB',
    }
    documents.mkdir(parents=True, exist_ok=True)
    (documents / 'index.json').write_text(json.dumps(rows, indent=2) + '\n')
    (documents / 'inventory.json').write_text(json.dumps(report, indent=2) + '\n')
    return {**report, 'capture_root': str(root)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--capture-id')
    arguments = parser.parse_args()
    print(json.dumps(ingest(arguments.archive, arguments.project, arguments.capture_id), indent=2))
