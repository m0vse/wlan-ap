"""Actual native boot adapter under environment write/readback fault injection."""
import pathlib
import subprocess
import tempfile
import unittest

LIB = pathlib.Path(__file__).resolve().parents[1] / 'lib/cambium-oem-sage-boot.sh'

class SageBootTests(unittest.TestCase):
    def run_arm(self, source=0, model='E410', fault='', persist=False):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            state = p/'state'; state.mkdir()
            (state/'image').write_text(str(source))
            (state/'bootcmd').write_text('bootipq')
            config = p/'env.config'; config.write_text('/dev/mtd5 0x0 0x00010000 0x00010000 1\n')
            script = r'''
. "$LIB"
COS_BOOT_QUALIFIED=qualified; COS_ENV_CONFIG=$CONFIG
OW_EXPECT_SOURCE=$SOURCE; OW_EXPECT_TARGET=$((1 - SOURCE)); OW_EXPECT_MODEL=$MODEL
COS_TARGET_FIT=config@5; [ "$MODEL" != E410B ] || COS_TARGET_FIT=config@17
COS_OEM_BOOT_COMMAND="setenv image $SOURCE; bootipq"
OW_EXPECT_JOB=$(printf '%064d' 1); OW_IMAGE=$(printf '%064d' 2)
ow_settings_context() { return 0; }
fw_printenv() {
 shift 2; [ "$1" = -n ] || return 1; shift
 [ "$FAULT:$1" != readback:sage_installer_job ] || { echo wrong; return; }
 [ "$FAULT:$1" != source_readback:sage_storage_pending ] || { echo wrong; return; }
 cat "$STATE/$1"
}
fw_setenv() {
 shift 2
 if [ "$1" = -s ]; then
  echo batch >> "$LOG"; [ "$FAULT" != batch ] || return 1
  while read -r key value; do printf '%s' "$value" > "$STATE/$key"; done < "$2"
 else
  echo "$1" >> "$LOG"; [ "$FAULT" != bootcmd ] || return 1
  printf '%s' "$2" > "$STATE/$1"
 fi
}
sync() { [ "$FAULT" != source_sync ]; }
[ "$PERSIST" != 1 ] || { cos_persist_source "install:$SOURCE:$((1-SOURCE)):$OW_IMAGE:$OW_EXPECT_JOB" && echo writer >> "$LOG"; } || exit 1
cos_arm image
'''
            result = subprocess.run(['sh', '-c', script], env={
                'PATH':'/usr/bin:/bin', 'LIB':str(LIB), 'CONFIG':str(config),
                'STATE':str(state), 'LOG':str(p/'log'), 'SOURCE':str(source),
                'MODEL':model, 'FAULT':fault, 'PERSIST':str(int(persist))}, capture_output=True, text=True)
            return result, {f.name:f.read_text() for f in state.iterdir()}, (p/'log').read_text().splitlines() if (p/'log').exists() else []

    def test_both_banks_and_models_use_native_state_and_correct_fit(self):
        for source in (0, 1):
            for model, fit in (('E410', 'config@5'), ('E410B', 'config@17')):
                with self.subTest(source=source, model=model):
                    result, state, writes = self.run_arm(source, model)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    target = 1-source
                    self.assertEqual(state['sage_ab_version'], '1')
                    self.assertEqual(state['sage_ab_confirmed'], str(source))
                    self.assertEqual(state['sage_installer_target'], str(target))
                    self.assertEqual(state[f'sage_boot{source}'], f'setenv image {source}; bootipq')
                    self.assertIn(f'root=/dev/ubiblock0_{2*target+1}', state[f'sage_boot{target}'])
                    self.assertIn(f'bootm 0x84000000#{fit}', state[f'sage_boot{target}'])
                    self.assertIn('setenv bootargs "mtdparts=', state[f'sage_boot{target}'])
                    self.assertIn('setenv mtdparts "mtdparts=', state[f'sage_boot{target}'])
                    self.assertEqual(state[f'sage_stable{target}'], f'run sage_boot{target}; run sage_boot{source}')
                    self.assertEqual(state[f'sage_stable{source}'], f'run sage_boot{source}')
                    self.assertIn(f'setenv bootcmd run sage_boot{source}', state['bootcmd'])
                    self.assertIn(f'&& saveenv && run sage_boot{target}', state['bootcmd'])
                    self.assertLess(state['bootcmd'].index('saveenv'), state['bootcmd'].index(f'run sage_boot{target}'))
                    self.assertEqual(writes, ['batch', 'bootcmd'])

    def test_failed_metadata_batch_or_readback_never_activates(self):
        for fault in ('batch', 'readback'):
            with self.subTest(fault=fault):
                result, state, writes = self.run_arm(fault=fault)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(state['bootcmd'], 'bootipq')
                self.assertEqual(writes, ['batch'])

    def test_last_selector_failure_reports_failure_without_reboot(self):
        result, state, writes = self.run_arm(fault='bootcmd')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(state['bootcmd'], 'bootipq')
        self.assertEqual(writes, ['batch', 'bootcmd'])

    def test_unsupported_model_never_writes_environment(self):
        result, state, writes = self.run_arm(model='E600')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(writes, [])

    def test_source_only_default_and_journal_precede_writer_for_both_models_slots(self):
        for source in (0, 1):
            for model in ('E410', 'E410B'):
                result, state, writes = self.run_arm(source, model, persist=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(writes, ['batch', 'writer', 'batch', 'bootcmd'])
                self.assertEqual(state[f'sage_boot{source}'], f'setenv image {source}; bootipq')
                self.assertTrue(state['sage_storage_pending'].startswith(f'install:{source}:{1-source}:'))

    def test_source_batch_sync_and_readback_faults_never_reach_writer(self):
        for fault in ('batch', 'source_sync', 'source_readback'):
            result, state, writes = self.run_arm(fault=fault, persist=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('writer', writes)
            self.assertNotIn('sage_boot1', state)

if __name__ == '__main__': unittest.main()
