#!/usr/bin/env python3
"""Ensure every setup.py patch has metadata accepted by git am."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class PatchMailTests(unittest.TestCase):
    def test_complete_patch_series(self):
        patches = sorted((ROOT / 'patches-25.12').glob('*.patch'))
        self.assertTrue(patches)
        with tempfile.TemporaryDirectory(prefix='patch-mail-test.') as work:
            for patch in patches:
                with self.subTest(patch=patch.name):
                    result = subprocess.run(
                        ['git', 'mailinfo', str(Path(work) / 'message'),
                         str(Path(work) / 'diff')],
                        input=patch.read_bytes(), capture_output=True, check=True)
                    metadata = dict(line.split(': ', 1) for line in
                                    result.stdout.decode().splitlines()
                                    if ': ' in line)
                    for field in ('Author', 'Email', 'Subject'):
                        self.assertTrue(metadata.get(field),
                                        f'{patch.name}: missing {field}')
                    self.assertTrue((Path(work) / 'diff').read_bytes())


if __name__ == '__main__':
    unittest.main()
