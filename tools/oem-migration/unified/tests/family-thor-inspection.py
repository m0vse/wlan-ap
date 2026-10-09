#!/usr/bin/env python3
"""Exact Thor inspection with real synthetic files and actual shared readers."""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess
import tempfile


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('common_lib', type=Path); a = ap.parse_args()
    adapter = Path(__file__).resolve().parents[1] / 'adapters/thor.sh'
    count = 0
    with tempfile.TemporaryDirectory(prefix='thor-inspect-') as temporary:
        top = Path(temporary).resolve()

        def fixture(slot=1, indices=(7, 9, 12, 15)):
            import shutil
            root = top / 'case'; shutil.rmtree(root, ignore_errors=True); root.mkdir()
            def put(name, value):
                p = root / name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(value if isinstance(value, bytes) else str(value).encode())
            for index, name, offset, size, erase, write, kind in (
                    (indices[0], 'rootfs', 0, 100663296, 131072, 2048, 'nand'),
                    (indices[1], 'rootfs_1', 100663296, 100663296, 131072, 2048, 'nand'),
                    (indices[2], '0:APPSBLENV', 6946816, 65536, 4096, 1, 'nor'),
                    (indices[3], '0:ART', 6094848, 262144, 4096, 1, 'nor')):
                for key, value in dict(name=name, offset=offset, size=size, erasesize=erase, writesize=write, type=kind).items():
                    put(f'sys/class/mtd/mtd{index}/{key}', value)
            put('etc/version', 'VERSION=fixture-supported\n')
            put('tmp/fw_env.config', f'/dev/mtd{indices[2]} 0x0 0x10000 0x10000 1\n')
            put('environment/image', slot); put('environment/bootcmd', 'aq_load_fw&&bootipq')
            put('proc/cmdline', 'ubi.mtd=' + ('rootfs_1' if slot else 'rootfs') + ' root=ubi6:ubi_rootfs')
            for key, value in dict(mtd_num=indices[slot], eraseblock_size=126976, min_io_size=2048).items():
                put('sys/class/ubi/ubi6/' + key, value)
            for child, name in ((0, 'kernel'), (1, 'ubi_rootfs')):
                for key, value in dict(name=name, upd_marker=0, corrupted=0).items():
                    put(f'sys/class/ubi/ubi6_{child}/{key}', value)
            put('fixture-ART', bytes(64) + bytes.fromhex('001122334455') + bytes(16))
            return root, put, indices

        script = r'''
. "$COMMON/common.sh"
. "$COMMON/protection.sh"
. "$ADAPTER"
oem_thor_art_node(){ printf '%s\n' "$OEM_SYS_ROOT/fixture-ART"; }
fw_printenv(){ [ "$1" = -c ] && [ "$3" = -n ] || return 1; cat "$OEM_SYS_ROOT/environment/$4"; }
fw_setenv(){ exit 99; }; ubiupdatevol(){ exit 99; }; ubiformat(){ exit 99; }
inspect=0
oem_adapter_inspect || inspect=$?
if [ "$inspect" != 0 ]; then
 [ -z "$OEM_SERIAL$OEM_SOURCE_RELEASE$OEM_SOURCE_SLOT$OEM_TARGET_SLOT$OEM_SOURCE_MTD$OEM_TARGET_MTD" ] || exit 98
 exit 1
fi
oem_context_check || exit 1
printf '%s\n' "$OEM_SERIAL" "$OEM_SOURCE_RELEASE" "$OEM_SOURCE_SLOT" "$OEM_TARGET_SLOT" "$OEM_SOURCE_MTD" "$OEM_TARGET_MTD"
'''

        def run(root, ok, model='XV3-8'):
            nonlocal count
            before = {str(p.relative_to(root)): (p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in root.rglob('*') if p.is_file()}
            env = dict(os.environ, COMMON=str(a.common_lib.resolve()), ADAPTER=str(adapter),
                       OEM_SYS_ROOT=str(root), OEM_SKU='00000013', OEM_MODEL=model,
                       OEM_SUPPORTED_RELEASE='fixture-supported', OEM_SERIAL='stale',
                       OEM_SOURCE_RELEASE='stale', OEM_SOURCE_SLOT='stale', OEM_TARGET_SLOT='stale')
            result = subprocess.run(['sh', '-c', script], env=env, text=True, capture_output=True, timeout=5)
            assert (result.returncode == 0) == ok, (result.returncode, result.stdout, result.stderr)
            assert before == {str(p.relative_to(root)): (p.stat().st_mode, hashlib.sha256(p.read_bytes()).hexdigest())
                              for p in root.rglob('*') if p.is_file()}
            count += 1; return result

        for slot in (0, 1):
            for indices in ((7, 9, 12, 15), (3, 6, 24, 30)):
                root, put, _ = fixture(slot, indices)
                result = run(root, True)
                assert result.stdout.splitlines() == ['001122334455', 'fixture-supported', str(slot),
                                                       str(1-slot), str(indices[slot]), str(indices[1-slot])]
        faults = ('converted', 'version-missing', 'version-duplicate', 'version-old', 'version-new',
                  'offset-missing', 'offset-wrong', 'size-wrong', 'write-wrong', 'attachment-duplicate',
                  'attachment-wrong', 'cmdline-duplicate', 'root-wrong', 'volume-wrong', 'ubi-leb-wrong',
                  'conflicting-env', 'env-slot-wrong', 'boot-wrong', 'art-size-wrong', 'serial-zero')
        for fault in faults:
            root, put, indices = fixture()
            if fault == 'converted': put('etc/openwrt_release', 'synthetic')
            elif fault == 'version-missing': (root/'etc/version').unlink()
            elif fault == 'version-duplicate': put('etc/version', 'VERSION=fixture-supported\nVERSION=other\n')
            elif fault in ('version-old', 'version-new'): put('etc/version', 'VERSION='+fault+'\n')
            elif fault == 'offset-missing': (root/f'sys/class/mtd/mtd{indices[1]}/offset').unlink()
            elif fault == 'offset-wrong': put(f'sys/class/mtd/mtd{indices[1]}/offset', 0)
            elif fault == 'size-wrong': put(f'sys/class/mtd/mtd{indices[0]}/size', 54525952)
            elif fault == 'write-wrong': put(f'sys/class/mtd/mtd{indices[0]}/writesize', 4096)
            elif fault == 'attachment-duplicate': put('sys/class/ubi/ubi8/mtd_num', indices[1])
            elif fault == 'attachment-wrong': put('sys/class/ubi/ubi6/mtd_num', indices[0])
            elif fault == 'cmdline-duplicate': put('proc/cmdline', 'ubi.mtd=rootfs ubi.mtd=rootfs_1 root=ubi6:ubi_rootfs')
            elif fault == 'root-wrong': put('proc/cmdline', 'ubi.mtd=rootfs_1 root=ubi6:rootfs')
            elif fault == 'volume-wrong': put('sys/class/ubi/ubi6_1/name', 'rootfs')
            elif fault == 'ubi-leb-wrong': put('sys/class/ubi/ubi6/eraseblock_size', 131072)
            elif fault == 'conflicting-env': put('etc/fw_env.config', '/dev/mtd99 0x0 0x10000 0x10000 1\n')
            elif fault == 'env-slot-wrong': put('environment/image', 0)
            elif fault == 'boot-wrong': put('environment/bootcmd', 'run another')
            elif fault == 'art-size-wrong': put(f'sys/class/mtd/mtd{indices[3]}/size', 65536)
            elif fault == 'serial-zero': put('fixture-ART', bytes(80))
            run(root, False)
        root, put, _ = fixture(); run(root, False, 'XE5-8')
        print(f'PASS: {count} actual Thor inspections/context checks; fixture file bytes/modes unchanged')
        print('Scope: exact synthetic geometry/version/slot/serial readers; fw_printenv and char-device lookup simulated; no actual OEM version admitted or write/boot action')


if __name__ == '__main__': main()
