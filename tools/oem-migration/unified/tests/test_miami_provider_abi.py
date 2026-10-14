"""Unified pinned-provider contract only; never execute an installer or AP tool."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
ADAPTER = ROOT / 'tools/oem-migration/unified/adapters/miami.sh'

class MiamiProviderTests(unittest.TestCase):
    def invoke(self, core, slot=0, fault=''):
        code = r'''
. "$ADAPTER"
oem_bundle_member() { [ "$1" = miami-installer.sh ] && printf '%s\n' "$CORE"; }
fw_printenv() { case "$1" in bootcmd) echo bootcmd=bootipq;; image) echo image=$SLOT;; *) return 99;; esac; [ "$FAULT" != "$1" ]; }
fw_setenv() { echo FORBIDDEN; return 99; }
oem_adapter_boot_preflight
'''
        return subprocess.run(['sh', '-c', code], env=dict(os.environ, ADAPTER=str(ADAPTER), CORE=str(core), SLOT=str(slot), OEM_SOURCE_SLOT=str(slot), OEM_TARGET_SLOT=str(1-slot), FAULT=fault), capture_output=True, text=True)

    def test_safe_contract_and_error_returning_correct_selectors(self):
        with tempfile.TemporaryDirectory() as directory:
            core = Path(directory) / 'miami-installer.sh'
            core.write_text("restore='setenv bootcount 0 && setenv bootcmd bootipq && setenv changing_bootcmd && saveenv'\nput bootcmd 'if run miami_persistent_restore; then run miami_persistent_load; bootipq; fi'\n")
            for slot in (0, 1):
                self.assertEqual(self.invoke(core, slot).returncode, 0)
                for fault in ('bootcmd', 'image'):
                    result = self.invoke(core, slot, fault)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn('FORBIDDEN', result.stdout)
            core.write_text(core.read_text().replace('if run miami_persistent_restore; then run miami_persistent_load; bootipq; fi', 'run miami_persistent_restore && run miami_persistent_load || bootipq'))
            self.assertNotEqual(self.invoke(core).returncode, 0)

    def test_reviewed_merged_provider_contract(self):
        source = Path(os.environ.get('MIAMI_PROVIDER_SOURCE', str(ROOT / 'contrib/cambium/miami/miami-oem-persistent.sh.in')))
        if not source.is_file():
            self.skipTest('Merged public Miami provider source is a separate integration prerequisite')
        for slot in (0, 1):
            result = self.invoke(source, slot)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
