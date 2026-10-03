#!/usr/bin/env python3
"""Check the regular script's real config expansion and vendor separation.

Usage: test_mbssid.py WLAN_AP_ROOT PATCHED_OPENWRT_ROOT REGULAR_CONFIG_FILE_C
Run after applying patch 0157 to an isolated copy of the selected wifi-scripts.
No AP access, daemon start, radio changes or credentials.
"""
import pathlib
import re
import subprocess
import sys
import unittest

repo, openwrt, parser = map(pathlib.Path, sys.argv[1:])
sys.argv = sys.argv[:1]
script = openwrt / 'package/network/config/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'


class MbssidTests(unittest.TestCase):
    def test_patch_hunk_lengths(self):
        text = (repo / 'patches-25.12/0157-wifi-scripts-use-regular-hostapd-mbssid-key.patch').read_text()
        for hunk in re.finditer(r'(?ms)^@@ -\d+,(\d+) \+\d+,(\d+) @@[^\n]*\n(.*?)(?=^--- |^@@ |\Z)', text):
            body = hunk[3].splitlines()
            self.assertEqual(sum(line.startswith((' ', '-')) for line in body), int(hunk[1]))
            self.assertEqual(sum(line.startswith((' ', '+')) for line in body), int(hunk[2]))

    def test_regular_emission(self):
        lines = [s for s in script.read_text().splitlines()
                 if s.startswith('${multiple_bssid:+')]
        self.assertEqual(lines, ['${multiple_bssid:+mbssid=$multiple_bssid}'])
        for value in (None, '', '0', '1', '2'):
            with self.subTest(value=value):
                setup = 'unset multiple_bssid' if value is None else f"multiple_bssid='{value}'"
                result = subprocess.run(['sh', '-c', setup + '\ncat <<EOF\n' + lines[0] + '\nEOF\n'],
                                        check=True, capture_output=True, text=True)
                expected = '' if not value else f'mbssid={value}'
                self.assertEqual(result.stdout.strip(), expected)

    def test_regular_parser(self):
        text = parser.read_text()
        self.assertRegex(text, r'os_strcmp\(buf, "mbssid"\) == 0')
        self.assertNotRegex(text, r'os_strcmp\(buf, "multiple_bssid"\) == 0')

    def test_vendor_qca6_contract(self):
        vendor = repo / 'feeds/qca-wifi-6/hostapd'
        self.assertIn('append base_cfg "multiple_bssid=$multiple_bssid"',
                      (vendor / 'files/hostapd.sh').read_text())
        self.assertIn('os_strcmp(buf, "multiple_bssid")',
                      (vendor / 'patches/d00-011-01-multiple_bssid-add-the-config-file.patch').read_text())

    def test_vendor_qca7_contract(self):
        text = (repo / 'feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh').read_text()
        self.assertIn('append base_cfg "mbssid=$multiple_bssid"', text)

    def test_scope_release_and_syntax(self):
        patch = (repo / 'patches-25.12/0157-wifi-scripts-use-regular-hostapd-mbssid-key.patch').read_text()
        paths = re.findall(r'^\+\+\+ b/(.*)$', patch, re.M)
        self.assertEqual(paths, ['package/network/config/wifi-scripts/Makefile',
                                'package/network/config/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'])
        self.assertIn('PKG_RELEASE:=2', (openwrt / paths[0]).read_text())
        subprocess.run(['sh', '-n', str(script)], check=True)


if __name__ == '__main__':
    unittest.main()
