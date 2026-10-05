"""Actual stock staging glue/shared stager; mount and ENV isolated."""
import importlib.util
import os
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parents[1]
owner = BASE.parent/'oem-migration/recovery/scripts/tests/test_cambium_installer_settings.py'
spec = importlib.util.spec_from_file_location('shared_fixture',owner)
fixture_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture_module)
count = 0
for family in ('sage','jaguar'):
    for fault in ('none','pending-mismatch','mtd-mismatch','mount','stage-sync','unmount','rmdir'):
        fixture = fixture_module.SettingsTests(); fixture.setUp()
        try:
            v = fixture.values
            v['family'] = family
            v['model'] = 'E410B' if family == 'sage' else 'XV2-2T1'
            fixture.put('binding.tsv',''.join(f'{k}\t{value}\n' for k,value in v.items()))
            fixture.manifest()
            (fixture.sys/'ubi0_5/name').write_text('rootfs_data1' if family == 'sage' else 'rootfs_data')
            env = dict(os.environ, PATH=str(fixture.tools)+':'+os.environ['PATH'],
                       CAMBIUM_INSTALLER_SETTINGS_LIB=str(owner.parents[1]/'lib/cambium-installer-settings.sh'),
                       OW_SETTINGS_OWNER=str(os.getuid()), OW_SETTINGS_SYS=str(fixture.sys),
                       AB_UBI_SYS=str(fixture.sys), OW_SETTINGS_MOUNTS=str(fixture.mounts),
                       OW_STAGE_ADMISSION='qualified', INPUT=str(fixture.input), IMAGE=str(fixture.image),
                       FAMILY=family, MODEL=v['model'], FAULT=fault,
                       FAIL_SYNC='1' if fault == 'stage-sync' else '0')
            names={'serial':'SERIAL','family':'FAMILY','model':'MODEL','source_operation':'OPERATION',
                   'source_release':'RELEASE','source_contract_sha256':'CONTRACT',
                   'source_slot':'SOURCE','target_slot':'TARGET','job_id':'JOB'}
            env.update({'OW_EXPECT_'+names[k]:value for k,value in v.items() if k in names})
            script = '''. "$1" || exit 1
AB_INSTALLER_VALIDATED=$INPUT
OW_IMAGE=$(ow_settings_hash "$IMAGE")
ab_identity() {
 AB_ENV=$FAMILY AB_FAMILY=$FAMILY AB_MODEL=$MODEL AB_ACTIVE=0 AB_TARGET=1 AB_QUALIFIED=1
 AB_TARGET_MTD=11 AB_TARGET_UBI=ubi0 AB_ACTIVE_UBI=ubi0 AB_ACTIVE_MTD=11 AB_LAYOUT=pair
 [ "$FAMILY" = sage ] || { AB_ACTIVE_MTD=0; AB_LAYOUT=banks; }
 [ "$FAULT" != mtd-mismatch ] || AB_TARGET_MTD=99
}
get_mac_label_dt() { echo 00:04:56:ab:cd:ef; }
get_mac_label() { echo 00:04:56:ab:cd:ef; }
ab_ubi_volume() { case "$2" in rootfs_data0) echo ubi0_6;; rootfs_data1|rootfs_data) echo ubi0_5;; *) return 1;; esac; }
ab_getenv() {
 [ "$FAULT" != pending-mismatch ] || return 1
 case "$1" in *_target) echo "$OW_EXPECT_TARGET";; *_job) echo "$OW_EXPECT_JOB";; *_image) echo "$OW_IMAGE";; esac
}
mount() {
 [ "$FAULT" != mount ] || return 1
 printf '/dev/ubi0_5 %s ubifs rw 0 0\n' "$4" > "$OW_SETTINGS_MOUNTS"
}
umount() { [ "$FAULT" != unmount ]; }
# The mock mount is an ordinary directory, so fake unmount/rmdir do not
# delete its published fixture files. No real filesystem is mounted.
rmdir() { [ "$FAULT" != rmdir ]; }
ab_installer_install_settings "$IMAGE"
'''
            before = fixture.source.read_bytes()
            run = subprocess.run(['sh','-c',script,'stage',str(BASE/'cambium-installer-handoff.sh')],env=env,capture_output=True)
            assert (run.returncode == 0) == (fault == 'none'), (family,fault,run.returncode,run.stderr)
            assert fixture.source.read_bytes() == before
            assert b'X'*64 not in run.stdout+run.stderr
            count += 1
        finally:
            fixture.doCleanups()
print(f'{count} actual stock glue/shared staging cases PASS; real mount/ENV operations isolated')
