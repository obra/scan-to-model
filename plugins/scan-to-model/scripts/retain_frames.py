"""Run selected Polycam frame retention with frozen local helpers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
HELPER_NAMES = ('retain_frames_worker.py', 'polycam.py', 'pixel_inspection.py')


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', required=True)
    parser.add_argument('--frame-id', action='append', required=True)
    parser.add_argument('--orientation', choices=('raw', 'upright90cw'), required=True)
    parser.add_argument('--record', action='append', default=[])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    capture = Path(args.capture).expanduser().resolve(strict=True)
    output = Path(args.output).expanduser().resolve()
    if output.exists():
        raise ValueError(f'output must be a new directory: {output}')
    runtime = output.parent / f'.{output.name}.frame-retention-runtime'
    if runtime.exists():
        raise ValueError(f'runtime must be a new directory: {runtime}')
    runtime.mkdir(parents=True)
    helpers = {}
    for name in HELPER_NAMES:
        source = SCRIPT_DIR / name
        target = runtime / name
        shutil.copyfile(source, target)
        helpers[name] = {'path': str(target), 'sha256': digest(target)}
    source_launcher = SCRIPT_DIR / 'retain_frames.py'
    launcher = runtime / 'retain_frames.py'
    shutil.copyfile(source_launcher, launcher)
    launcher_binding = {'path': str(launcher), 'sha256': digest(launcher)}
    command = [sys.executable, '-B', str(runtime / 'retain_frames_worker.py'),
               '--capture', str(capture)]
    for frame_id in args.frame_id:
        command.extend(('--frame-id', frame_id))
    command.extend(('--orientation', args.orientation))
    for record in args.record:
        command.extend(('--record', str(Path(record).expanduser().resolve(strict=True))))
    command.extend(('--output', str(output)))
    environment = os.environ.copy()
    environment.update({'PYTHONPATH': str(runtime), 'PYTHONDONTWRITEBYTECODE': '1'})
    controlled_environment = {key: environment[key] for key in ('PYTHONPATH', 'PYTHONDONTWRITEBYTECODE')}
    preflight = {
        'status': 'frozen_before_process', 'argv': command, 'cwd': str(output.parent),
        'python': sys.executable, 'capture': str(capture), 'helpers': helpers,
        'launcher': launcher_binding,
        'source_launcher': {'path': str(source_launcher), 'sha256': digest(source_launcher)},
        'environment_overrides': controlled_environment,
        'frame_ids': args.frame_id, 'orientation': args.orientation,
        'records': [str(Path(record).expanduser().resolve(strict=True)) for record in args.record],
    }
    (runtime / 'preflight.json').write_text(json.dumps(preflight, indent=2, sort_keys=True) + '\n')
    process = subprocess.run(command, cwd=output.parent, env=environment, capture_output=True, text=True)
    if not output.exists():
        output.mkdir(parents=True)
    (output / 'run-stdout.log').write_text(process.stdout)
    (output / 'run-stderr.log').write_text(process.stderr)
    receipt = {
        'status': 'pass' if process.returncode == 0 else 'fail', 'returncode': process.returncode,
        'argv': command, 'cwd': str(output.parent), 'python': sys.executable,
        'capture': str(capture), 'helpers': helpers, 'launcher': launcher_binding,
        'source_launcher': {'path': str(source_launcher), 'sha256': preflight['source_launcher']['sha256'],
                            'unchanged': digest(source_launcher) == preflight['source_launcher']['sha256']},
        'environment_overrides': controlled_environment, 'frame_ids': args.frame_id,
        'orientation': args.orientation, 'records': preflight['records'],
        'stdout': 'run-stdout.log', 'stderr': 'run-stderr.log', 'runtime': str(runtime),
    }
    (output / 'run-receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': receipt['status'], 'returncode': process.returncode, 'output': str(output)}))
    return 0 if process.returncode == 0 else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f'frame retention refused: {error}', file=sys.stderr)
        raise SystemExit(2)
