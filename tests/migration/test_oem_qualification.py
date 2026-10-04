#!/usr/bin/env python3
"""Synthetic admission policy tests; no real record, identity or AP acceptance."""
import copy
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('qualification', ROOT / 'tools/oem-migration/qualification.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.record = {
            'schema': MODULE.SCHEMA, 'operation': 'production-oem-migration', 'status': 'qualified',
            'exact_model': 'SYNTHETIC-MODEL', 'sku_hex': '00000063', 'hardware_revision': 'A',
            'region_compatibility': ['EU'],
            **{field: 'a' * 64 for field in MODULE.DIGEST_FIELDS},
        }
        self.inventory = {'serial': '001122334455', 'exact_model': 'SYNTHETIC-MODEL',
                          'sku_hex': '00000063', 'hardware_revision': 'A', 'region': 'EU'}
        self.runtime = {'operation': 'production-oem-migration', **self.inventory,
                        **{field: 'a' * 64 for field in MODULE.DIGEST_FIELDS}}

    def evaluate(self):
        snapshot = copy.deepcopy((self.record, self.inventory, self.runtime))
        result = MODULE.evaluate(self.record, self.inventory, self.runtime)
        self.assertEqual(snapshot, (self.record, self.inventory, self.runtime))
        return result

    def test_exact_bindings_allow_without_mutation(self):
        self.assertTrue(self.evaluate()['allowed'])

    def test_stock_route_has_separate_admission(self):
        self.runtime['operation'] = 'production-stock-openwrt-migration'
        self.assertFalse(self.evaluate()['allowed'])
        self.record['operation'] = self.runtime['operation']
        self.assertTrue(self.evaluate()['allowed'])

    def test_unsupported_unqualified_and_trial_never_allow(self):
        for field, value in (('status', 'unsupported'), ('status', 'unqualified'),
                             ('status', 'trial'), ('status', True), ('operation', 'experimental-trial')):
            original = self.record[field]
            self.record[field] = value
            self.assertFalse(self.evaluate()['allowed'])
            self.record[field] = original

    def test_missing_unknown_fields_refuse(self):
        for collection in (self.record, self.inventory, self.runtime):
            for field in list(collection):
                saved = collection.pop(field)
                self.assertFalse(self.evaluate()['allowed'])
                collection[field] = saved
            collection['force'] = True
            self.assertFalse(self.evaluate()['allowed'])
            del collection['force']

    def test_every_digest_binds_actual_runtime(self):
        for field in MODULE.DIGEST_FIELDS:
            self.runtime[field] = 'b' * 64
            self.assertFalse(self.evaluate()['allowed'])
            self.runtime[field] = 'a' * 64
            for invalid in (None, '', True, 'a' * 63, 'A' * 64, 'g' * 64):
                self.record[field] = invalid
                self.assertFalse(self.evaluate()['allowed'])
            self.record[field] = 'a' * 64

    def test_identity_substitution_and_revision_region_refuse(self):
        for field in self.inventory:
            saved = self.runtime[field]
            self.runtime[field] = 'SUBSTITUTED'
            self.assertFalse(self.evaluate()['allowed'])
            self.runtime[field] = saved
        self.inventory['hardware_revision'] = self.runtime['hardware_revision'] = 'B'
        self.assertFalse(self.evaluate()['allowed'])
        self.inventory['hardware_revision'] = self.runtime['hardware_revision'] = 'A'
        self.inventory['region'] = self.runtime['region'] = 'US'
        self.assertFalse(self.evaluate()['allowed'])

    def test_schema_and_region_ambiguity_refuse(self):
        self.record['schema'] = 'future-schema'
        self.assertFalse(self.evaluate()['allowed'])
        self.record['schema'] = MODULE.SCHEMA
        for regions in ([], ['EU', 'EU'], [''], None, 'EU'):
            self.record['region_compatibility'] = regions
            self.assertFalse(self.evaluate()['allowed'])

    def test_malformed_types_return_refusal(self):
        for collection, field in ((self.record, 'operation'), (self.inventory, 'serial')):
            saved = collection[field]
            for invalid in (None, 10, True, [], {}):
                collection[field] = invalid
                self.assertFalse(self.evaluate()['allowed'])
            collection[field] = saved


if __name__ == '__main__':
    unittest.main()
