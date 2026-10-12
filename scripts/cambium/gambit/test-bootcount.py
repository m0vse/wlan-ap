#!/usr/bin/env python3
"""E400's own nboot counter hazard: only mocked environment and flash calls."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = Path(os.environ["GAMBIT_TEST_MODULE"])
SHELL = os.environ.get('CAMBIUM_TEST_SHELL', 'sh')
COMMAND = [SHELL, 'sh'] if Path(SHELL).name == 'busybox' else [SHELL]


class CounterTests(unittest.TestCase):
    def run_module(self, code):
        return subprocess.run(COMMAND + ['-c', '. ' + shlex.quote(str(MODULE)) + '\n' + code],
                              text=True, capture_output=True)

    def test_each_bank_clears_before_args_and_nboot(self):
        for slot, offset in ((0, '0x00000000'), (1, '0x03000000')):
            result = self.run_module(f'ab_gambit_boot_command {slot}')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("if setenv bootcount 0 && saveenv && setenv bootargs "))
            self.assertIn(f'ubi.mtd=rootfs{slot} root=/dev/ubiblock0_1', result.stdout)
            self.assertTrue(result.stdout.rstrip().endswith(f"nboot 0x83000000 0 {offset}; reset; fi"))

    def test_guard_saves_cleared_counter_before_runtime_args(self):
        for oem in (0, 1):
            result = self.run_module(f'''ab_getenv() {{ echo {oem}; }}
AB_STOCK_BOOTCMD="nboot 0x81000000 0 0x{'00000000' if oem == 0 else '03000000'}"
ab_gambit_guarded_command {1-oem}''')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(" && setenv bootcount 0 && saveenv; then if setenv bootcount 0 && saveenv && setenv bootargs ", result.stdout)

    def test_wrong_guard_bank_refused(self):
        result = self.run_module('ab_getenv() { echo 0; }; ab_gambit_guarded_command 0')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def writer(self, count, failure=0, valid=True):
        with tempfile.TemporaryDirectory(prefix='gambit-counter-test-') as directory:
            root = Path(directory) / 'root'
            root.write_bytes(b'hsqs')
            return self.run_module(f'''
AB_ACTIVE=0 AB_TARGET=1 AB_KERNEL_MTD1=2 AB_MTD1=3 AB_TARGET_MTD=3
AB_ROOT={shlex.quote(str(root))} AB_KERNEL=mock AB_KERNEL_SIZE=64 AB_ROOT_SIZE=4
ab_certificate_lebs() {{ echo 20; }}
ab_gambit_layout() {{ return 0; }}
ab_gambit_check_kernel() {{ return {0 if valid else 1}; }}
ab_gambit_image_fits() {{ return 0; }}
ab_mtd_writable() {{ return 0; }}
ab_ubi_for_mtd() {{ return 1; }}
ab_getenv() {{ printf '%s\\n' {shlex.quote(count)}; }}
ab_setenv() {{ echo "env:$1=$2"; return {failure}; }}
ab_step() {{ echo "step:$1"; return 1; }}
ab_gambit_write_target_inner''')

    def test_eight_and_nine_reset_precede_first_erase(self):
        for count in ('8', '9'):
            result = self.writer(count)
            self.assertEqual(result.stdout.splitlines(), ['env:bootcount=0', 'step:erase linux1'])

    def test_reset_failure_prevents_every_flash_step(self):
        result = self.writer('9', failure=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), ['env:bootcount=0'])

    def test_invalid_image_does_not_write_environment(self):
        result = self.writer('9', valid=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')

    def test_already_zero_does_not_rewrite_environment(self):
        result = self.writer('0')
        self.assertEqual(result.stdout.splitlines(), ['step:erase linux1'])

    def test_healthy_boot_still_clears_counter(self):
        result = self.run_module('ab_getenv() { echo 9; }; ab_setenv() { echo "$1=$2"; }; ab_gambit_healthy_boot')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), 'bootcount=0')


    def rendered_execution(self, guarded, failed_stage=0, nboot_failure=False):
        prepare = 'ab_getenv() { echo 0; }; AB_STOCK_BOOTCMD="nboot 0x81000000 0 0x00000000"; '
        rendered = self.run_module(prepare + ('ab_gambit_guarded_command 1' if guarded else 'ab_gambit_boot_command 1'))
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        harness = f'''
step=0
setenv() {{ step=$((step+1)); echo "ENV:$step:$1"; [ "$step" != {failed_stage} ]; }}
saveenv() {{ step=$((step+1)); echo "SAVE:$step"; [ "$step" != {failed_stage} ]; }}
nboot() {{ echo NBOOT; return {1 if nboot_failure else 0}; }}
reset() {{ echo RESET; }}
'''
        result = subprocess.run(COMMAND + ['-c', harness + rendered.stdout], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.splitlines()

    def test_rendered_direct_each_env_failure_never_reads_nand(self):
        for stage in (1, 2, 3):
            with self.subTest(stage=stage):
                trace = self.rendered_execution(False, stage)
                self.assertNotIn('NBOOT', trace)
                self.assertNotIn("RESET", trace)

    def test_rendered_guarded_each_env_or_save_failure_never_reads_nand(self):
        for stage in range(1, 7):
            with self.subTest(stage=stage):
                trace = self.rendered_execution(True, stage)
                self.assertNotIn('NBOOT', trace)
                self.assertNotIn("RESET", trace)

    def test_rendered_success_and_returned_nboot_always_reset(self):
        for guarded in (False, True):
            for nboot_failure in (False, True):
                trace = self.rendered_execution(guarded, nboot_failure=nboot_failure)
                self.assertEqual(trace[-2:], ['NBOOT', 'RESET'])


    def test_failed_save_with_durable_nine_never_resets_or_boots(self):
        for guarded, failed_stage in ((False, 2), (True, 3), (True, 5)):
            prepare = 'ab_getenv() { echo 0; }; AB_STOCK_BOOTCMD="nboot 0x81000000 0 0x00000000"; '
            rendered = self.run_module(prepare + ('ab_gambit_guarded_command 1' if guarded else 'ab_gambit_boot_command 1'))
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            harness = f'''
step=0
ram_count=9
durable_count=9
ram_route=OEM0
durable_route=OEM0
setenv() {{
 step=$((step+1)); [ "$step" != {failed_stage} ] || return 1
 case "$1" in bootcount) ram_count="$2" ;; bootcmd) ram_route=OEM0 ;; esac
}}
saveenv() {{
 step=$((step+1)); [ "$step" != {failed_stage} ] || return 1
 durable_count=$ram_count; durable_route=$ram_route
}}
nboot() {{ echo NBOOT; }}
reset() {{ echo RESET; }}
'''
            result = subprocess.run(COMMAND + ['-c', harness + rendered.stdout + '\nprintf "DURABLE:%s:%s\\n" "$durable_count" "$durable_route"'], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('NBOOT', result.stdout)
            self.assertNotIn('RESET', result.stdout)
            expected = 'DURABLE:0:OEM0' if guarded and failed_stage == 5 else 'DURABLE:9:OEM0'
            self.assertEqual(result.stdout.strip(), expected)


if __name__ == '__main__':
    unittest.main()
