"""Ordered caller fault boundaries; payload/settings semantics tested separately."""
import pathlib
import subprocess
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1] / 'lib/cambium-oem-sage-transaction.sh'

class SageTransactionTests(unittest.TestCase):
    def run_transaction(self, failure='', model='E410', pending=False, free=87, existing_store=False):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            (p / 'sys/ubi0_5').mkdir(parents=True)
            (p / 'sys/ubi0_5/name').write_text('rootfs_data1\n')
            (p / 'sys/ubi0').mkdir()
            (p / 'sys/ubi0/avail_eraseblocks').write_text(str(free) + '\n')
            (p / 'sys/ubi0_3').mkdir()
            (p / 'sys/ubi0_3/reserved_ebs').write_text('285\n')
            if existing_store:
                (p / 'sys/ubi0_7').mkdir()
                (p / 'sys/ubi0_7/name').write_text('certificates\n')
            script = r'''
. "$LIB"
step() { printf '%s\n' "$1" >> "$LOG"; [ "$FAILURE" != "$1" ]; }
cos_admit() { step admit || return 1; OW_EXPECT_FAMILY=sage; OW_EXPECT_MODEL=$MODEL;
 OW_EXPECT_OPERATION=production-oem-migration; OW_EXPECT_SOURCE=0; OW_EXPECT_TARGET=1; CSP_FS_MTD=11; }
cos_authenticate() { step authenticate; }
cos_source_check() { step source; }
cos_refuse_pending() { step pending && [ "$PENDING" = no ]; }
cos_boot_preflight() { step boot_preflight; }
cos_recovery() { step recovery; }
cos_arm() { step arm; }
ow_settings_tree() { step settings_validate; }
ow_settings_context() { step settings_context; }
csp_payload_check() { step payload_check || return 1; CSP_TARGET=1; CSP_ROOT_ID=3; CSP_OVERLAY_LEBS=0; }
csp_number() { case "$1" in ""|*[!0-9]*) return 1 ;; esac; }
csp_read() { cat "$CSP_SYS/$1/$2"; }
csp_stage_pair() { step writer; }
csp_readback() { step readback; }
ow_settings_stage_overlay() { step settings_stage; }
mount() { step mount; }
umount() { step unmount; }
rmdir() { step rmdir; }
sync() { step sync; }
mktemp() { step mkdir || return 1; printf '%s\n' "$MOUNT"; }
ubirmvol() { :; }; ubimkvol() { :; }; ubiupdatevol() { :; }
cos_install image kernel root settings
'''
            env = {'PATH': '/usr/bin:/bin', 'LIB': str(LIB), 'LOG': str(p/'log'),
                   'FAILURE': failure, 'MODEL': model, 'PENDING': 'yes' if pending else 'no',
                   'CSP_SYS': str(p/'sys'), 'MOUNT': str(p/'mount')}
            result = subprocess.run(['sh', '-c', script], env=env, capture_output=True, text=True)
            calls = (p/'log').read_text().splitlines() if (p/'log').exists() else []
            return result, calls

    def test_success_orders_readback_settings_unmount_then_arm(self):
        result, calls = self.run_transaction()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls.count('readback'), 2)
        self.assertLess(calls.index('writer'), calls.index('readback'))
        self.assertLess(calls.index('readback'), calls.index('settings_stage'))
        self.assertLess(calls.index('settings_stage'), calls.index('unmount'))
        self.assertLess(calls.index('unmount'), calls.index('arm'))
        self.assertEqual(calls[-1], 'arm')

    def test_every_failure_before_activation_refuses_arm(self):
        for failure in ('admit', 'authenticate', 'source', 'pending', 'boot_preflight',
                        'settings_validate', 'settings_context', 'payload_check',
                        'recovery', 'writer', 'readback', 'mkdir', 'mount',
                        'settings_stage', 'sync', 'unmount', 'rmdir'):
            with self.subTest(failure=failure):
                result, calls = self.run_transaction(failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('arm', calls)

    def test_unsupported_model_refuses_before_backup_or_writer(self):
        result, calls = self.run_transaction(model='E600')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, ['admit'])

    def test_existing_pending_refuses_before_backup_or_writer(self):
        result, calls = self.run_transaction(pending=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('recovery', calls)
        self.assertNotIn('writer', calls)

    def test_certificate_capacity_or_existing_store_refuses_before_changes(self):
        for kwargs in ({'free': 86}, {'existing_store': True}):
            with self.subTest(kwargs=kwargs):
                result, calls = self.run_transaction(**kwargs)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('recovery', calls)
                self.assertNotIn('writer', calls)
                self.assertNotIn('arm', calls)

    def test_failed_arm_reports_failure_and_never_reboots(self):
        result, calls = self.run_transaction(failure='arm')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('reboot', calls)
        self.assertNotIn('candidate_staged=', result.stdout)

if __name__ == '__main__':
    unittest.main()
