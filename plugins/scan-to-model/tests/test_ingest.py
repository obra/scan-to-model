"""Exercise ZIP and directory intake on actual calibrated source files."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ingest import ingest
from polycam import digest
from test_polycam import frame_fixture, write_png


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source'
        depth, _ = frame_fixture(self.source)
        write_png(depth, np.full((2, 3), 1000), 16, 0)
        self.original = self.hashes()
        self.project = self.root / 'project'

    def hashes(self):
        return {p.relative_to(self.source).as_posix(): digest(p)
                for p in self.source.rglob('*') if p.is_file()}

    def test_directory_cli_audits_in_place_and_creates_readable_sheets(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/ingest.py'
        result = subprocess.run([sys.executable, '-B', str(script), str(self.source),
                                 '--project', str(self.project), '--capture-id', 'visit'],
                                capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report['capture_root'], str(self.source))
        self.assertEqual(report['frames'], 1)
        records = self.project / 'docs/scan-to-model/captures/visit'
        row = json.loads((records / 'index.json').read_text())[0]
        self.assertEqual(row['component_hashes']['depth'], self.original['keyframes/depth/001.png'])
        for kind in ['all', 'overview']:
            with Image.open(self.project / 'derived/scan-to-model/captures/visit' / kind / '01.jpg') as image:
                image.load()
                self.assertGreater(image.width, 0)
        self.assertEqual(ingest(self.source, self.project, 'visit'), report)
        self.assertEqual(self.hashes(), self.original)
        self.assertFalse((self.project / 'sources').exists())

    def test_changed_components_need_a_new_capture_id(self):
        ingest(self.source, self.project, 'visit')
        write_png(self.source / 'keyframes/depth/001.png', np.full((2, 3), 1100), 16, 0)
        with self.assertRaises(ValueError):
            ingest(self.source, self.project, 'visit')
        self.assertEqual(ingest(self.source, self.project, 'second-visit')['frames'], 1)

    def test_intake_cannot_write_inside_the_original_source(self):
        with self.assertRaises(ValueError):
            ingest(self.source, self.source / 'generated', 'visit')
        self.assertEqual(self.hashes(), self.original)
        self.assertFalse((self.source / 'generated').exists())

    def test_incomplete_capture_does_not_produce_a_successful_inventory(self):
        (self.source / 'keyframes/depth/001.png').unlink()
        with self.assertRaises(ValueError):
            ingest(self.source, self.project, 'visit')
        self.assertFalse(self.project.exists())

    def test_zip_still_preserves_and_audits_an_enclosed_capture(self):
        archive = self.root / 'capture.zip'
        with zipfile.ZipFile(archive, 'w') as output:
            for name in self.original:
                output.write(self.source / name, 'enclosed/' + name)
        report = ingest(archive, self.project, 'visit')
        self.assertEqual(report['source_sha256'], digest(archive))
        self.assertEqual(report['frames'], 1)
        self.assertEqual(digest(self.project / 'sources/capture.zip'), digest(archive))
        capture = Path(report['capture_root'])
        self.assertEqual(capture.name, 'enclosed')
        self.assertEqual({name: digest(capture / name) for name in self.original}, self.original)


if __name__ == '__main__':
    unittest.main()
