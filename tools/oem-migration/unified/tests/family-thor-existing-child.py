#!/usr/bin/env python3
"""Actual local payload/update/readback helper with shared protection code.

Only the character-device boundary and ubiupdatevol process are simulated.
No mounts, devices, downloads, credentials, firmware builds or boot changes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('common_lib', nargs='?', type=Path, default=Path(__file__).resolve().parents[1] / 'lib', help='Reviewed unified lib directory (defaults to this checkout)')
    a = ap.parse_args()
    common_source = a.common_lib.resolve()
    helper_bytes = {}
    for helper in ('common.sh', 'protection.sh'):
        path = common_source / helper
        if not path.is_file():
            ap.error(f'missing shared helper {path}; supply the reviewed unified lib directory')
        helper_bytes[helper] = path.read_bytes()
    adapter = Path(__file__).resolve().parents[1] / 'adapters/thor.sh'
    cases = []
    with tempfile.TemporaryDirectory(prefix='thor-local-child-') as temporary:
        work = Path(temporary).resolve()
        isolated_common = work / 'shared-lib'
        isolated_common.mkdir(mode=0o700)
        for helper, content in helper_bytes.items():
            (isolated_common / helper).write_bytes(content)

        def fixture(prior=1):
            import shutil
            root = work / 'case'
            shutil.rmtree(root, ignore_errors=True)
            root.mkdir(mode=0o700)
            bundle = root / 'bundle'
            (bundle / 'payloads/XV3-8').mkdir(parents=True)
            (bundle / 'profiles/XV3-8').mkdir(parents=True)
            for role in ('kernel', 'rootfs'):
                (bundle / f'payloads/XV3-8/{role}.bin').write_bytes(('synthetic-local-' + role).encode())
            rows = []
            for role in ('kernel', 'rootfs'):
                p = bundle / f'payloads/XV3-8/{role}.bin'
                rows.append(f'{role}\tpayloads/XV3-8/{role}.bin\t{p.stat().st_size}\t{hashlib.sha256(p.read_bytes()).hexdigest()}\n')
            (bundle / 'profiles/XV3-8/payloads.tsv').write_text(''.join(rows))
            seal(bundle)
            target = 9 if prior == 0 else 7
            source = 7 if prior == 0 else 9
            sys = root / 'sys/class/ubi'
            (sys / 'ubi6').mkdir(parents=True)
            (sys / 'ubi6/mtd_num').write_text(str(target))
            dev = root / 'dev'
            dev.mkdir()
            for child, role in enumerate(('kernel', 'rootfs')):
                node = sys / f'ubi6_{child}'
                node.mkdir()
                for key, value in {'name': role, 'upd_marker': '0', 'corrupted': '0'}.items():
                    (node / key).write_text(value)
                (dev / f'ubi6_{child}').write_bytes(('old-target-' + role).encode())
            private = root / 'work'
            private.mkdir(mode=0o700)
            protected = root / 'protected'
            protected.mkdir()
            for label in ('active-bank', 'ART', 'MFG', 'ENV', 'BOOTCONFIG', 'certificates', 'vault'):
                (protected / label).write_bytes(('synthetic-own-' + label).encode())
            inventory = root / 'physical.tsv'
            inventory.write_text(f'7\t0\t100663296\t{"target" if target == 7 else "active-oem"}\tnand0\n'
                                 f'9\t100663296\t100663296\t{"target" if target == 9 else "active-oem"}\tnand0\n'
                                 '15\t6094848\t262144\tidentity\tnor0\n')
            env = dict(os.environ, OEM_SKU='00000013', OEM_MODEL='XV3-8',
                       OEM_SOURCE_SLOT=str(prior), OEM_TARGET_SLOT=str(1-prior),
                       OEM_SOURCE_MTD=str(source), OEM_TARGET_MTD=str(target), OEM_TARGET_UBI='ubi6',
                       OEM_SYS_ROOT=str(root), OEM_BUNDLE=str(bundle), OEM_WORK=str(private),
                       OEM_PROTECTED_RANGES=str(inventory), COMMON=str(isolated_common),
                       ADAPTER=str(adapter), TRACE=str(root / 'trace'), FAULT='')
            return root, bundle, env

        def seal(bundle):
            files = sorted(p for p in bundle.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
            (bundle / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle)}\n' for p in files))

        shell = r'''
umask 077
. "$COMMON/common.sh"
. "$COMMON/protection.sh"
. "$ADAPTER"
forbidden(){ printf '%s\n' forbidden >> "$TRACE"; return 99; }
flash_erase(){ forbidden; }; ubiformat(){ forbidden; }; fw_setenv(){ forbidden; }
ubirmvol(){ forbidden; }; ubirsvol(){ forbidden; }; ubimkvol(){ forbidden; }
curl(){ forbidden; }; wget(){ forbidden; }; reboot(){ forbidden; }
# The only substituted device boundary returns a file inside this fixture.
oem_thor_target_node(){ [ "$FAULT" != node ] || return 1; printf '%s\n' "$OEM_SYS_ROOT/dev/${OEM_TARGET_UBI}_$1"; }
ubiupdatevol(){
 printf '%s\n' update >> "$TRACE"
 case "$FAULT" in
 write) printf partial > "$1"; return 1;;
 readback) printf corrupt > "$1"; return 0;;
 post-metadata) cp "$2" "$1"; printf 1 > "$OEM_SYS_ROOT/sys/class/ubi/ubi6_0/upd_marker"; return 0;;
 *) cp "$2" "$1";;
 esac
}
oem_thor_update_existing_child "$ROLE"
'''

        def run(name, root, env, ok, writes=False, role='kernel'):
            protected = {p.name: p.read_bytes() for p in (root / 'protected').iterdir()}
            result = subprocess.run(['sh', '-c', shell], env={**env, 'ROLE': role},
                                    input='SYNTHETIC-PRIVATE-INPUT-NEVER-PRINT', text=True,
                                    capture_output=True, timeout=5)
            assert (result.returncode == 0) == ok, (name, result.stdout, result.stderr)
            trace = (root / 'trace').read_text().splitlines() if (root / 'trace').exists() else []
            assert bool(trace) == writes and 'forbidden' not in trace, (name, trace)
            assert protected == {p.name: p.read_bytes() for p in (root / 'protected').iterdir()}
            assert 'SYNTHETIC-PRIVATE-INPUT-NEVER-PRINT' not in result.stdout + result.stderr
            cases.append(name)

        for prior in (0, 1):
            for role in ('kernel', 'rootfs'):
                root, bundle, env = fixture(prior)
                run(f'bank-{prior}-local-{role}-write-and-readback', root, env, True, True, role)
                assert (root / f'dev/ubi6_{0 if role == "kernel" else 1}').read_bytes() == (bundle / f'payloads/XV3-8/{role}.bin').read_bytes()
        for name in ('missing-root', 'tampered-kernel', 'wrong-pinned-size', 'wrong-descriptor-sha',
                     'duplicate-role', 'wrong-model', 'active-alias', 'wrong-parent', 'duplicate-attachment',
                     'duplicate-volume', 'corrupted', 'upd-marker', 'protected-target', 'overlap', 'node'):
            root, bundle, env = fixture()
            descriptor = bundle / 'profiles/XV3-8/payloads.tsv'
            if name == 'missing-root': (bundle / 'payloads/XV3-8/rootfs.bin').unlink()
            elif name == 'tampered-kernel': (bundle / 'payloads/XV3-8/kernel.bin').write_bytes(b'tamper')
            elif name in ('wrong-pinned-size', 'wrong-descriptor-sha'):
                rows = descriptor.read_text().splitlines(); fields = rows[0].split('\t')
                fields[2 if name == 'wrong-pinned-size' else 3] = '999' if name == 'wrong-pinned-size' else '0'*64
                rows[0] = '\t'.join(fields); descriptor.write_text('\n'.join(rows)+'\n'); seal(bundle)
            elif name == 'duplicate-role': descriptor.write_text(descriptor.read_text().splitlines()[0]+'\n'+descriptor.read_text().splitlines()[0]+'\n'); seal(bundle)
            elif name == 'wrong-model': env['OEM_MODEL'] = 'XE5-8'
            elif name == 'active-alias': env['OEM_TARGET_MTD'] = env['OEM_SOURCE_MTD']
            elif name == 'wrong-parent': (root / 'sys/class/ubi/ubi6/mtd_num').write_text(env['OEM_SOURCE_MTD'])
            elif name == 'duplicate-attachment': (root / 'sys/class/ubi/ubi8').mkdir(); (root / 'sys/class/ubi/ubi8/mtd_num').write_text(env['OEM_TARGET_MTD'])
            elif name == 'duplicate-volume': (root / 'sys/class/ubi/ubi6_8').mkdir(); (root / 'sys/class/ubi/ubi6_8/name').write_text('kernel')
            elif name in ('corrupted', 'upd-marker'): (root / ('sys/class/ubi/ubi6_0/' + ('corrupted' if name == 'corrupted' else 'upd_marker'))).write_text('1')
            elif name == 'protected-target': p = root / 'physical.tsv'; p.write_text(p.read_text().replace('\ttarget\t', '\tidentity\t'))
            elif name == 'overlap': p = root / 'physical.tsv'; p.write_text(p.read_text().replace('9\t100663296', '9\t0'))
            elif name == 'node': env['FAULT'] = 'node'
            run(name+'-no-update', root, env, False)
        for fault in ('write', 'readback', 'post-metadata'):
            root, bundle, env = fixture(); env['FAULT'] = fault
            run(fault+'-stops-without-arm', root, env, False, True)
            assert (root / 'work/thor-child-journal.tsv').exists()
            if fault == 'write':
                env['FAULT'] = ''
                run('same-pinned-write-retry', root, env, True, True)
        print(json.dumps({'passed': True, 'count': len(cases), 'cases': cases,
                          'scope': 'Actual Thor local-pin/update/readback logic and owner shared bundle/range/UBI checks. Char-device lookup and updater process are substituted with temporary-file actors. No erase, ENV, network, boot, mount, device or firmware build; not a complete OEM migration or restoration qualification.'}, indent=2))


if __name__ == '__main__':
    main()
