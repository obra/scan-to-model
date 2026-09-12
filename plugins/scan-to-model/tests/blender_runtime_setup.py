"""Verify Blender runtime setup before importing a review helper.

Run after scripts/blender_runtime.py with --output /new/review/directory.
"""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

import bpy


def contained(path, parent):
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    output = args.output.expanduser().resolve()
    try:
        output.mkdir(parents=True)
    except FileExistsError:
        parser.error(f'Output already exists: {output}')

    runtime_root = Path(os.environ['SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT']).resolve()
    temporary = runtime_root / 'tmp'
    module_root = output / 'module-source'
    module_root.mkdir()
    module_path = module_root / 'synthetic_review_helper.py'
    module_path.write_text('VALUE = "loaded"\n')
    sys.path.insert(0, str(module_root))
    imported = importlib.import_module('synthetic_review_helper')
    cached = Path(imported.__cached__)
    preferences = bpy.context.preferences.filepaths
    result = {
        'blender_version': bpy.app.version_string,
        'module_loaded': imported.VALUE == 'loaded',
        'dont_write_bytecode': sys.dont_write_bytecode,
        'cached_path': str(cached),
        'cached_exists': cached.exists(),
        'bytecode_files': sorted(str(path.relative_to(output)) for path in output.rglob('*.pyc')),
        'bpy_tempdir': bpy.app.tempdir,
        'bpy_tempdir_contained': contained(Path(bpy.app.tempdir), temporary),
        'temporary_directory': preferences.temporary_directory,
        'temporary_directory_matches': Path(preferences.temporary_directory).resolve() == temporary,
        'save_version': preferences.save_version,
        'use_auto_save_temporary_files': preferences.use_auto_save_temporary_files,
    }
    result['passed'] = all((
        result['module_loaded'],
        result['dont_write_bytecode'],
        not result['cached_exists'],
        not result['bytecode_files'],
        result['bpy_tempdir_contained'],
        result['temporary_directory_matches'],
        result['save_version'] == 0,
        not result['use_auto_save_temporary_files'],
    ))
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise AssertionError('Blender runtime setup did not establish the required state')


if __name__ == '__main__':
    main()
