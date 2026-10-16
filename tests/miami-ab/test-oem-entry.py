#!/usr/bin/env python3
"""Run the actual entry helper; device/crypto facts and ENV I/O are actors."""
from pathlib import Path
import json, os, subprocess, tempfile

repo = Path(__file__).resolve().parents[2]
script = (repo / 'contrib/cambium/miami/ab/enter-oem-once.sh').read_text()
module = repo / 'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'
count = 0
with tempfile.TemporaryDirectory(prefix='miami-oem-entry-test-') as td:
    r = Path(td)
    tools = r / 'bin'
    tools.mkdir()
    actor = tools / 'actor'
    actor.write_text('''#!/usr/bin/env python3
from pathlib import Path
import json,os,sys
p=Path(os.environ['STATE']);e=json.loads(p.read_text());a=sys.argv[1:]
if a[0]=='get':print(e.get(a[1],''));sys.exit()
counter=Path(os.environ['COUNTER']);n=int(counter.read_text())+1;counter.write_text(str(n))
if str(n)==os.environ.get('FAIL_WRITE'):sys.exit(1)
if a[0]=='set':e[a[1]]=a[2]
elif a[0]=='batch':
 for row in Path(a[1]).read_text().splitlines():k,v=row.split(' ',1);e[k]=v
else:raise AssertionError(a)
p.write_text(json.dumps(e))
''')
    actor.chmod(0o755)
    for name, body in {
        'head': 'case "$*" in *kernel*) echo "$KERNEL_SHA";;*) echo 1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9;;esac',
        'sha256sum': 'read digest;printf "%s  -\\n" "$digest"',
        'sync': ':',
    }.items():
        path = tools / name
        path.write_text('#!/bin/sh\n' + body + '\n')
        path.chmod(0o755)
    callbacks = r / 'callbacks.sh'
    callbacks.write_text('''
. "$MODULE"
ab_getenv(){ actor get "$1"; }
ab_setenv(){ actor set "$1" "$2"; }
ab_setenv_batch(){ actor batch "$1"; }
ab_identity(){ AB_FAMILY=miami;AB_MODEL=X7-35X;AB_SKU=0000002c;[ "$FAULT" != identity ]; }
ab_miami_storage_context(){ AB_ACTIVE=$SLOT;AB_TARGET=$((1-SLOT));AB_ACTIVE_UBI=ubi0;AB_SLOT0_OFFSET=0xc0000;AB_SLOT1_OFFSET=0x60c0000;[ "$FAULT" != storage ]; }
ab_miami_upgrade_geometry(){ [ "$FAULT" != geometry ]; }
ab_miami_certificate_mount(){ [ "$FAULT" != certificates ]; }
ab_miami_readiness_identity(){ [ "$FAULT" != crypto ]; }
ab_miami_native_connected(){ [ "$FAULT" != network ]; }
ab_ubi_volume(){ echo "ubi0_$2"; }
''')
    actual = r / 'enter-oem-once.sh'
    body = script.replace('. /lib/functions/system.sh', ':')
    body = body.replace('. "$CAMBIUM_AB_LIB"', '. "$CALLBACKS"')
    body = body.replace('. "$kit/shared/cambium-ab-upgrade.sh"', ':')
    body = body.replace('/proc/device-tree/cambium-platform/storage-policy', str(r / 'storage-policy'))
    body = body.replace('/etc/openwrt_release', str(r / 'release'))
    actual.write_text(body)
    (r / 'release').write_text("DISTRIB_TIP='OpenWrt / TIP-devel-b6d1a26f'\n")
    state = r / 'state'
    counter = r / 'counter'
    for slot in (0, 1):
        route = subprocess.check_output(['sh', '-c', '. "$1";AB_SLOT0_OFFSET=0xc0000;AB_SLOT1_OFFSET=0x60c0000;ab_miami_slot_command "$2" legacy',
                                         'fixture', str(module), str(slot)], text=True).strip()
        original = {'bootcmd': 'run miami_persistent_restore && run miami_persistent_load || bootipq',
                    'image': str(1-slot), 'changing_bootcmd': '1',
                    'miami_persistent_restore': 'setenv bootcmd bootipq && setenv changing_bootcmd && saveenv',
                    'miami_persistent_slot': str(slot), 'miami_persistent_load': route + '; reset',
                    'factory.region': 'untouched'}
        env = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'], STATE=str(state),
                   COUNTER=str(counter), MODULE=str(module), CALLBACKS=str(callbacks), SLOT=str(slot),
                   KERNEL_SHA=('9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b' if slot==0 else
                               'dcf685056218b88a8685ea2c60c8cc0fceef5a39dcc168691541f9fb90e4a255'))
        for fault in ('', 'identity', 'storage', 'geometry', 'certificates', 'crypto', 'network', 'prior', 'already-armed'):
            before = dict(original)
            if fault == 'prior':before['miami_persistent_slot'] = str(1-slot)
            if fault == 'already-armed':before['miami_oem_once_state'] = 'started'
            state.write_text(json.dumps(before));counter.write_text('0')
            result = subprocess.run(['sh', str(actual), 'arm', '--yes'], env={**env, 'FAULT': fault}, capture_output=True, text=True)
            after = json.loads(state.read_text())
            if fault:
                assert result.returncode != 0 and before == after, (fault, result.stderr, after)
            else:
                assert result.returncode == 0, result.stderr
                assert after['image'] == str(slot) and after[f'miami_boot{slot}'] == route
                expected = f'setenv bootcmd run miami_boot{slot} && setenv image {slot} && setenv miami_oem_once_state started && saveenv && setenv image {1-slot} && bootipq; run miami_boot{slot}'
                assert after['bootcmd'] == expected and after['miami_oem_once_state'] == 'prepared'
                assert after['factory.region'] == 'untouched'
            count += 1
        for failure in range(1, 6):
            state.write_text(json.dumps(original));counter.write_text('0')
            result = subprocess.run(['sh', str(actual), 'arm', '--yes'], env={**env, 'FAULT': '', 'FAIL_WRITE': str(failure)}, capture_output=True, text=True)
            assert result.returncode != 0, (failure, result.stdout)
            after = json.loads(state.read_text())
            assert after['bootcmd'] in (original['bootcmd'], f'run miami_boot{slot}')
            assert after['factory.region'] == 'untouched'
            count += 1
print(f'PASS: {count} actual entry-helper control-flow cases; hardware/crypto facts mocked, no AP I/O')
