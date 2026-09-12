"""Establish isolated Blender runtime state before loading review helpers."""

import sys
sys.dont_write_bytecode = True

import os
from pathlib import Path

import bpy


def contained(path, parent):
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


root_value = os.environ.get('SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT')
if not root_value:
    raise RuntimeError('SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT is required')
runtime_root = Path(root_value)
if not runtime_root.is_absolute():
    raise RuntimeError('SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT must be absolute')
runtime_root = runtime_root.resolve(strict=True)
if not runtime_root.is_dir():
    raise RuntimeError('SCAN_TO_MODEL_BLENDER_RUNTIME_ROOT must be a directory')

temporary = (runtime_root / 'tmp').resolve(strict=True)
if not temporary.is_dir() or not contained(temporary, runtime_root):
    raise RuntimeError('Runtime tmp must be an existing directory inside the runtime root')
environment_temporary = os.environ.get('TMPDIR')
if not environment_temporary or Path(environment_temporary).resolve() != temporary:
    raise RuntimeError('TMPDIR must identify the runtime root tmp directory')
actual_temporary = Path(bpy.app.tempdir).resolve(strict=True)
if not contained(actual_temporary, temporary):
    raise RuntimeError('Blender temporary directory is outside the runtime root tmp directory')

filepaths = bpy.context.preferences.filepaths
filepaths.temporary_directory = str(temporary)
filepaths.save_version = 0
filepaths.use_auto_save_temporary_files = False
if Path(filepaths.temporary_directory).resolve() != temporary:
    raise RuntimeError('Blender temporary-directory preference was not applied')
if filepaths.save_version != 0 or filepaths.use_auto_save_temporary_files:
    raise RuntimeError('Blender save and recovery preferences were not applied')

print(f'Scan-to-model Blender runtime initialized under {runtime_root}')
