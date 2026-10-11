"""Generated writer ordering: ENV/flash boundaries isolated, not AP proof."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

GENERATED = Path(os.environ['CHEETAH_GENERATED_BRIDGE'])

class WriterTests(unittest.TestCase):
    def test_frozen_writer_integration(self):
        for family in ('cheetah',):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)/'root'
                root.mkdir()
                # Sources are taken from existing fixture captures only to
                # exercise generator logic; root is not approved firmware.
                # Reconstructing a root from the approved source files would
                # require the actual source capture; test just transformation.
                text = (GENERATED/'cambium-ab-upgrade.sh').read_text()
                writer = root/'writer.sh'
                writer.write_text(text)
                subprocess.run(['sh', '-n', str(writer)], check=True)
                for fault in ('none','pending-existing','unreadable-env','ram','pending','env','write','readback','stage','sync-stage','unmount-stage','arm'):
                    with self.subTest(family=family, fault=fault):
                        trace = root/'trace'
                        if trace.exists(): trace.unlink()
                        core = root/'core'; core.touch()
                        env = dict(os.environ, CAMBIUM_AB_LIB=str(core), CAMBIUM_INSTALLER_HANDOFF_LIB=str(core), CAMBIUM_AB_CERTIFICATE_LIB=str(root/'absent'), FAMILY=family, FAULT=fault, TRACE=str(trace))
                        script = '''. "$1" || exit 1
AB_FAMILY=$FAMILY AB_ENV=$FAMILY AB_ACTIVE=0 AB_TARGET=1 AB_VAULT=0 AB_TARGET_PART=fixture
AB_KERNEL=fixture AB_ROOT=fixture AB_KERNEL_SIZE=1 AB_ROOT_SIZE=1 AB_CERTIFICATE_LEBS=0
if [ "$FAMILY" = sage ]; then AB_LAYOUT=pair; else AB_LAYOUT=banks; fi
event() { printf '%s\n' "$1" >> "$TRACE"; [ "$FAULT" != "$1" ]; }
ab_installer_refuse_pending() { event fresh && [ "$FAULT" != pending-existing ] && [ "$FAULT" != unreadable-env ]; }
ab_hook() { [ "$AB_LAYOUT:$1" = pair:write_target ]; }
ab_upgrade_preflight() { event preflight; }
ab_image_extract() { event extract; }
ab_installer_validate_ram() { event ram; }
ab_installer_pending() { event pending || return 1; printf 'installer_job protected-job\n' >> "$1"; }
ab_setenv_batch() { event env; }
ab_sage_write_target() { event write && event readback; }
ab_prepare_bank() { event write || return 1; AB_TARGET_UBI=ubi1; }
ubiupdatevol() { event payload; }
ab_step() { shift; "$@"; }
ab_verify_volume() { event readback; }
ab_installer_install_settings() { event stage && event sync-stage && event unmount-stage; }
ab_arm_trial() { event arm; }
ab_fail() { event failure; return 1; }
ab_record_failure() { event failure; return 1; }
sync() { event sync; }
cambium_ab_do_upgrade fixture-image
'''
                        run = subprocess.run(['sh','-c',script,'test',str(writer)], env=env, capture_output=True)
                        events = trace.read_text().splitlines()
                        self.assertEqual(run.returncode == 0, fault == 'none', (events,run.stderr))
                        if fault in ('pending-existing','unreadable-env','ram','pending','env'):
                            self.assertNotIn('write',events)
                        if fault != 'none' and fault != 'arm':
                            self.assertNotIn('arm',events)
                        if 'arm' in events:
                            self.assertLess(events.index('pending'),events.index('env'))
                            self.assertLess(events.index('env'),events.index('write'))
                            self.assertLess(events.index('readback'),events.index('stage'))
                            self.assertLess(events.index('stage'),events.index('arm'))
                        # No boot operation is exposed by this generated writer
                        # outside the preserved ab_arm_trial callback.
                        body = text.split('cambium_ab_do_upgrade() {',1)[1]
                        self.assertNotIn('ab_setenv bootcmd',body)

if __name__ == '__main__':
    unittest.main()
