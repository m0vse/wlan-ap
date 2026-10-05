"""Actual complete-ENV pending reader: missing key never masks read failure."""
import os
import pathlib
import subprocess
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1] / 'lib/cambium-oem-sage-source.sh'

class SourcePendingTests(unittest.TestCase):
    def invoke(self, snapshot, status=0):
        return subprocess.run(['sh', '-c', '''
. "$LIB"
COS_ENV_CONFIG=/verified/existing/config
fw_printenv() { printf '%s' "$SNAPSHOT"; return "$READ_STATUS"; }
cos_refuse_pending
'''], env={**os.environ, 'LIB':str(LIB), 'SNAPSHOT':snapshot,
            'READ_STATUS':str(status)}, capture_output=True, text=True)

    def test_absent_and_empty_pending_keys_are_fresh(self):
        for snapshot in ('image=0\nbootcmd=bootipq\n',
                         'sage_installer_target=\nsage_installer_job=\nsage_installer_image=\n'):
            self.assertEqual(self.invoke(snapshot).returncode, 0)

    def test_existing_partial_duplicate_or_malformed_pending_refuses(self):
        for snapshot in ('sage_installer_target=1\n', 'sage_installer_job=secret\n',
                         'sage_installer_image=digest\n',
                         'sage_installer_job=\nsage_installer_job=\n',
                         'sage_installer_job\n', 'sage_installer_job=a=b\n'):
            with self.subTest(snapshot=snapshot):
                result = self.invoke(snapshot)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, '')

    def test_failed_complete_env_read_refuses_even_with_no_pending_output(self):
        self.assertNotEqual(self.invoke('', 1).returncode, 0)
        self.assertNotEqual(self.invoke('image=0\n', 1).returncode, 0)

if __name__ == '__main__': unittest.main()
