#!/usr/bin/env python3
"""Actual allocator source with isolated identity/sysfs/UBI boundaries."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).resolve()
work = Path(tempfile.mkdtemp(prefix='sage-certificate-allocator.', dir='/tmp'))
cases = []
names = ('absent-capacity20', 'absent-capacity19', 'existing-empty', 'existing-nonempty',
         'wrong-mtd', 'wrong-geometry', 'wrong-layout', 'unqualified', 'identity-refusal',
         'existing-short', 'existing-wrong-geometry', 'allocation-refusal', 'invalid-capacity')
for name in names:
    root = work / name
    for directory in ('sys/ubi0', 'sys/ubi0_7', 'dev', 'store', 'bin'):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / 'sys/ubi0/mtd_num').write_text('8' if name == 'wrong-mtd' else '11')
    (root / 'sys/ubi0/eraseblock_size').write_text('131072' if name == 'wrong-geometry' else '126976')
    (root / 'sys/ubi0/avail_eraseblocks').write_text('invalid' if name == 'invalid-capacity' else '19' if name == 'absent-capacity19' else '20')
    existing = name in ('existing-empty', 'existing-nonempty', 'existing-short', 'existing-wrong-geometry')
    (root / 'sys/ubi0_7/reserved_ebs').write_text('19' if name == 'existing-short' else '20')
    (root / 'sys/ubi0_7/usable_eb_size').write_text('131072' if name == 'existing-wrong-geometry' else '126976')
    if name == 'existing-nonempty':
        (root / 'store/key.pem').write_text('fixture existing identity never changed')
    before = {p.name: p.read_bytes() for p in (root / 'store').iterdir()}
    core = root / 'core.sh'
    core.write_text('''board_name() { echo cambiumnetworks,e410; }
ab_identity() {
 [ "$FIXTURE_CASE" != identity-refusal ] || return 1
 AB_FAMILY=sage; AB_LAYOUT=pair; AB_QUALIFIED=1; AB_CERTIFICATE_LEBS=0
 AB_ACTIVE_MTD=11; AB_TARGET_MTD=11; AB_ACTIVE_UBI=ubi0; AB_LEB=126976
 [ "$FIXTURE_CASE" != wrong-layout ] || AB_LAYOUT=banks
 [ "$FIXTURE_CASE" != unqualified ] || AB_QUALIFIED=0
}
ab_ubi_volume() { [ "$FIXTURE_EXISTING" = yes ] && echo ubi0_7; }
''')
    for binary in ('ubimkvol', 'ubirsvol', 'ubirmvol', 'mount', 'umount'):
        tool = root / 'bin' / binary
        tool.write_text('''#!/bin/sh
name=${0##*/}
echo "$name $*" >> "$FIXTURE_CALLS"
[ "$name" = ubimkvol ] || exit 99
[ "$FIXTURE_CASE" != allocation-refusal ]
''')
        tool.chmod(0o755)
    calls = root / 'calls'
    calls.touch()
    env = dict(os.environ, PATH=str(root / 'bin') + ':' + os.environ['PATH'],
               CAMBIUM_AB_CORE=str(core), AB_UBI_SYS=str(root / 'sys'), AB_DEV=str(root / 'dev'),
               FIXTURE_CALLS=str(calls), FIXTURE_CASE=name, FIXTURE_EXISTING='yes' if existing else 'no')
    driver = 'boot_hook_add() { :; }; . "$1"; generate_certificate_volume'
    result = subprocess.run(['sh', '-c', driver, 'fixture', str(source)], env=env, capture_output=True, text=True)
    success = name in ('absent-capacity20', 'existing-empty', 'existing-nonempty')
    assert (result.returncode == 0) == success, (name, result.stdout, result.stderr)
    trace = calls.read_text().splitlines()
    if name in ('absent-capacity20', 'allocation-refusal'):
        assert trace == [f'ubimkvol {root}/dev/ubi0 -N certificates -S 20'], trace
    else:
        assert not trace, (name, trace)
    assert {p.name: p.read_bytes() for p in (root / 'store').iterdir()} == before
    cases.append({'case': name, 'passed': True, 'trace': trace, 'existing_store_unchanged': True})
print(json.dumps({'passed': True, 'count': len(cases), 'cases': cases,
                  'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                  'fixture': str(work),
                  'scope': 'Actual preinit dispatch/allocator with identity and UBI/sysfs fixture boundaries; no real allocation, resize, erase, mount or AP execution'}, indent=2))
