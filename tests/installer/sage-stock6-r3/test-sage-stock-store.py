#!/usr/bin/env python3
"""Actual clean stock Sage preflight and installed pre-RAM hook; no real UBI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

helper = Path(sys.argv[1]).resolve()
platform = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
work = Path(tempfile.mkdtemp(prefix='sage-stock-store.', dir='/tmp'))
names = ('empty-mounted', 'nonempty-mounted', 'absent20', 'absent19', 'wrong-mtd',
         'wrong-mount', 'duplicate-mount', 'short-volume', 'wrong-geometry',
         'symlink-store', 'missing-mounts', 'preserving-refused', 'late-identity-file', 'unmounted-store')
reports = []
for case in names:
    root = work / case
    for directory in ('sys/ubi0', 'sys/ubi0_7', 'store', 'runtime', 'bin'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'sys/ubi0/mtd_num').write_text('8' if case == 'wrong-mtd' else '11')
    (root / 'sys/ubi0/eraseblock_size').write_text('131072' if case == 'wrong-geometry' else '126976')
    (root / 'sys/ubi0/avail_eraseblocks').write_text('19' if case == 'absent19' else '20')
    (root / 'sys/ubi0_7/reserved_ebs').write_text('19' if case == 'short-volume' else '20')
    (root / 'sys/ubi0_7/usable_eb_size').write_text('126976')
    store = root / 'store'
    if case == 'nonempty-mounted':
        (store / 'gateway.json').write_text('legacy trust must not enter')
    if case == 'symlink-store':
        store = root / 'linked-store'
        store.symlink_to(root / 'store')
    mounts = root / 'mounts'
    absent = case in ('absent20', 'absent19')
    mounts.write_text('' if absent else f'{root}/dev/ubi0_7 {store} ubifs rw 0 0\n')
    if case == 'unmounted-store':
        mounts.write_text('')
    if case == 'wrong-mount':
        mounts.write_text(f'{root}/dev/ubi1_7 {store} ubifs rw 0 0\n')
    if case == 'duplicate-mount':
        mounts.write_text(mounts.read_text() * 2)
    if case == 'missing-mounts':
        mounts.unlink()
    calls = root / 'calls'
    calls.touch()
    for binary in ('openssl', 'mount', 'umount', 'ubimkvol', 'ubirsvol', 'ubirmvol', 'fw_setenv'):
        tool = root / 'bin' / binary
        tool.write_text('#!/bin/sh\necho forbidden >> "$FIXTURE_CALLS"\nexit 99\n')
        tool.chmod(0o755)
    env = dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH'],
               AB_UBI_SYS=str(root / 'sys'), AB_PROC_MOUNTS=str(mounts), AB_DEV=str(root / 'dev'),
               AB_CERTIFICATE_STORE=str(store), FIXTURE_CALLS=str(calls), FIXTURE_ABSENT='yes' if absent else 'no',
               FIXTURE_CASE=case, SAVE_CONFIG='1' if case == 'preserving-refused' else '0')
    driver = '''set -eu
. "$1"
AB_FAMILY=sage; AB_LAYOUT=pair; AB_ACTIVE_MTD=11; AB_TARGET_MTD=11; AB_ACTIVE_UBI=ubi0; AB_LEB=126976
ab_identity() { :; }
ab_family() { return 0; }
ab_upgrade_preflight() { return 0; }
ab_ubi_volume() { [ "$FIXTURE_ABSENT" = no ] && echo ubi0_7; }
sage_stock_store_check
if [ "$FIXTURE_CASE" = late-identity-file ]; then
 printf fixture > "$AB_CERTIFICATE_STORE/key.pem"
fi
[ -z "$2" ] || . "$2"
if [ -z "$2" ]; then ab_certificate_export; else platform_pre_upgrade fixture; fi
'''
    result = subprocess.run(['sh', '-c', driver, 'fixture', str(helper), str(platform) if platform else ''], env=env, capture_output=True, text=True)
    expected = case in ('empty-mounted', 'absent20')
    assert (result.returncode == 0) == expected, (case, result.stdout, result.stderr)
    assert not calls.read_text(), case
    if case == 'nonempty-mounted':
        assert (store / 'gateway.json').read_text() == 'legacy trust must not enter'
    reports.append({'case': case, 'passed': True, 'no_crypto_mount_allocation_env_commands': True})
print(json.dumps({'passed': True, 'count': len(reports), 'cases': reports,
                  'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                  'fixture': str(work),
                  'actual_platform_hook': platform is not None,
                  'scope': 'Actual stock store checker/pre-RAM export and optional real platform hook; identity/sysfs/mount-table fixtures; no AP, real mount, bank/env or allocation writes'}, indent=2))
