"""Private stock RAM handoff fixtures; no bank, mount, ENV or AP writes."""
import importlib.util
import os
from pathlib import Path
import subprocess

owner = Path(os.environ['WLAN_AP_SOURCE_DIR'])/'tools/oem-migration/recovery/scripts/tests/test_cambium_installer_settings.py'
spec = importlib.util.spec_from_file_location('shared_settings_fixture', owner)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
adapter = str(Path(os.environ['CHEETAH_GENERATED_BRIDGE'])/'cambium-installer-handoff.sh')
shared = str(owner.parents[1] / 'lib/cambium-installer-settings.sh')

cases = [('fresh-export-ram', {}, None, True),
         ('pending-target', {'TEST_PENDING_TARGET': '1'}, None, False),
         ('pending-job-only', {'TEST_PENDING_JOB': 'b'*64}, None, False),
         ('pending-image-only', {'TEST_PENDING_IMAGE': 'a'*64}, None, False),
         ('malformed-pending', {'TEST_PENDING_TARGET': 'garbage'}, None, False),
         ('unreadable-env', {'TEST_ENV_FAIL': '1'}, None, False),
         ('unqualified-model', {'TEST_QUALIFIED': '0'}, None, False),
         ('native-serial-conflict', {'TEST_NATIVE': '00:04:56:00:00:00'}, None, False),
         ('ram-wrong-boot', {}, 'boot', False),
         ('ram-archive-tamper', {}, 'archive', False),
         ('ram-image-tamper', {}, 'image', False),
         ('ram-source-bank-changed', {}, 'source-bank', False)]
for label, overrides, fault, expected in cases:
    fixture = module.SettingsTests()
    fixture.setUp()
    try:
        v = fixture.values
        v.update(family='cheetah', model='XV2-21X', source_operation='production-stock-openwrt-migration', source_release='2026.09.29.0')
        fixture.put('binding.tsv', ''.join(f'{k}\t{value}\n' for k,value in v.items()))
        fixture.manifest()
        boot = fixture.root / 'boot-id'
        boot.write_text('11111111-1111-1111-1111-111111111111\n')
        env = {**os.environ, 'PATH': str(fixture.tools) + ':' + os.environ['PATH'],
               'CAMBIUM_INSTALLER_SETTINGS_LIB': shared,
               'OW_SETTINGS_OWNER': str(os.getuid()), 'OW_STAGE_ADMISSION': 'qualified',
               'AB_INSTALLER_INPUT': str(fixture.input),
               'AB_INSTALLER_ARCHIVE': str(fixture.root / 'settings.tar'),
               'AB_INSTALLER_DESCRIPTOR': str(fixture.root / 'settings.descriptor'),
               'AB_BOOT_ID': str(boot), 'SAVE_CONFIG': '0', 'TEST_QUALIFIED': '1',
               'TEST_NATIVE': '00:04:56:ab:cd:ef'}
        names = {'serial': 'SERIAL', 'family': 'FAMILY', 'model': 'MODEL',
                 'source_operation': 'OPERATION', 'source_release': 'RELEASE',
                 'source_contract_sha256': 'CONTRACT', 'source_slot': 'SOURCE',
                 'target_slot': 'TARGET', 'job_id': 'JOB'}
        env.update({'OW_EXPECT_' + names[k]: value for k, value in v.items() if k in names})
        env.update(overrides)
        script = '''. "$1" || exit 1
ab_identity() { AB_ENV=cheetah; AB_FAMILY=cheetah; AB_MODEL=XV2-21X; AB_LAYOUT=banks; AB_CERTIFICATE_LEBS=20; AB_ACTIVE=${TEST_ACTIVE:-0}; AB_TARGET=1; AB_QUALIFIED=$TEST_QUALIFIED; }
ab_env_config() { AB_ENV_CONFIG=/fixture-only; }
fw_printenv() { [ "${TEST_ENV_FAIL:-0}" = 0 ] || return 1; printf 'cheetah_installer_target=%s\ncheetah_installer_job=%s\ncheetah_installer_image=%s\n' "${TEST_PENDING_TARGET:-}" "${TEST_PENDING_JOB:-}" "${TEST_PENDING_IMAGE:-}"; }
ab_getenv() { case "$1" in *_target) printf '%s' "${TEST_PENDING_TARGET:-}";; *_job) printf '%s' "${TEST_PENDING_JOB:-}";; *_image) printf '%s' "${TEST_PENDING_IMAGE:-}";; esac; }
get_mac_label_dt() { echo 00:04:56:ab:cd:ef; }
get_mac_label() { echo "$TEST_NATIVE"; }
ab_installer_export "$2" || exit 1
'''
        if fault == 'boot':
            script += 'printf wrong-boot > "$AB_BOOT_ID"\n'
        elif fault == 'archive':
            script += 'printf tamper >> "$AB_INSTALLER_ARCHIVE"\n'
        elif fault == 'image':
            script += 'printf tamper >> "$2"\n'
        elif fault == 'source-bank':
            script += 'TEST_ACTIVE=1\n'
        script += 'ab_installer_validate_ram "$2"\n'
        result = subprocess.run(['sh', '-c', script, 'fixture', adapter, str(fixture.image)],
                                capture_output=True, env=env)
        assert (result.returncode == 0) == expected, (label, result.returncode, result.stderr)
        assert b'X'*64 not in result.stdout + result.stderr
        if label.startswith('pending') or label in ('malformed-pending', 'unreadable-env'):
            assert not (fixture.root / 'settings.tar').exists()
            assert not (fixture.root / 'settings.descriptor').exists()
    finally:
        fixture.doCleanups()
print(f'{len(cases)} isolated pre-format/source/RAM handoff cases PASS; writer, mount, source ledgers and real runtime unqualified')
