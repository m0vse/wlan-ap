"""Critical boot-selection records remain bounded and individually named."""
from pathlib import Path
import subprocess
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]


class CriticalPlanTests(unittest.TestCase):
    def check(self, plan, rows):
        plan.write_text(rows)
        return subprocess.run(['sh', '-c', '. "$1";oem_backup_plan_check "$2"',
                               'check', str(BASE/'lib/critical-backup.sh'), str(plan)],
                              capture_output=True).returncode

    def test_exact_bootconfig_pair_accepts_real_thor_size(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td)/'plan'
            for prefix in ('0:', ''):
                for size in (65536, 131072):
                    rows = (f'BOOTCONFIG0\t{prefix}BOOTCONFIG\t{size}\tboot-selection\n'
                            f'BOOTCONFIG1\t{prefix}BOOTCONFIG1\t{size}\tboot-selection\n')
                    self.assertEqual(self.check(plan, rows), 0)

    def test_oversize_swapped_and_firmware_records_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            plan = Path(td)/'plan'
            for name, size in (('0:BOOTCONFIG',131073), ('0:BOOTCONFIG1',131072),
                               ('rootfs',131072), ('0:APPSBL',131072),
                               ('0:ART',131072), ('BOOTCONFIG2',131072)):
                rows = (f'BOOTCONFIG0\t{name}\t{size}\tboot-selection\n'
                        'ENV\t0:APPSBLENV\t65536\tboot-environment\n')
                self.assertNotEqual(self.check(plan, rows), 0, (name,size))


if __name__ == '__main__':
    unittest.main()
