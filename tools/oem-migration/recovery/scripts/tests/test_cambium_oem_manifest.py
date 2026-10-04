#!/usr/bin/env python3
"""Manifest/source coverage fence: a new source model must receive a row."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'scripts/cambium-oem-models.tsv'


class ManifestTests(unittest.TestCase):
    def test_source_coverage_and_schema(self):
        rows = [line.split('\t') for line in MANIFEST.read_text().splitlines()
                if line and not line.startswith('#')]
        identifiers = set()
        skus = set()
        for row in rows:
            self.assertEqual(len(row), 9, row)
            sku, family, model, layout, size, compatible, assets, status, production = row
            self.assertRegex(sku, r'^[0-9a-f]{8}$')
            self.assertNotIn(sku, skus)
            skus.add(sku)
            self.assertNotIn(compatible, identifiers)
            identifiers.add(compatible)
            self.assertIn(family, ('sage', 'jaguar', 'cheetah', 'thor', 'gambit'))
            self.assertIn(status, ('layout-only', 'uncaptured', 'identity-unqualified'))
            self.assertIn(production, ('unsupported', 'unqualified', 'qualified'))
            if status == 'uncaptured':
                self.assertEqual((layout, size, assets), ('-', '-', '-'))
                self.assertEqual(production, 'unsupported')
        # OpenWiFi adds family support as patches; upstream Sage definitions
        # do not require a patch here. Every added supported-device/DTS model
        # must still have an explicit OEM admission row.
        repo = pathlib.Path(__file__).resolve().parents[5]
        source_identifiers = set()
        for source in (repo / 'patches-25.12').glob('*.patch'):
            text = source.read_text().replace('\\\n', ' ')
            for line in text.splitlines():
                if line.startswith('+') and ('SUPPORTED_DEVICES' in line or 'compatible =' in line or line.startswith('+\t\tcambiumnetworks,')):
                    source_identifiers.update(re.findall(r'cambium(?:networks)?,[a-z0-9-]+', line))
        source_identifiers.discard('cambium,e410')
        self.assertTrue(source_identifiers, 'family source coverage must not be empty')
        self.assertFalse(source_identifiers - identifiers, source_identifiers - identifiers)



if __name__ == '__main__':
    unittest.main()
