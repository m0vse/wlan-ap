#!/usr/bin/env python3
"""Actual FORMAT2 producer/stager and Thor context; fixture-only mount/image pin."""
from pathlib import Path
import argparse
import hashlib
import os
import stat
import subprocess
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('settings_lib', nargs='?', type=Path,
                    default=Path(__file__).resolve().parents[2] / 'recovery/scripts/lib/cambium-installer-settings.sh')
    a = ap.parse_args()
    if not a.settings_lib.is_file(): ap.error(f'missing settings library {a.settings_lib}')
    adapter = Path(__file__).resolve().parents[1] / 'adapters/thor.sh'
    count = 0
    with tempfile.TemporaryDirectory(prefix='thor-native-seed-') as td:
        top = Path(td).resolve(); lib = top / 'settings.sh'; lib.write_bytes(a.settings_lib.read_bytes())
        driver = top / 'driver.sh'
        driver.write_text(r'''
umask 077
. "$SETTINGS"
. "$ADAPTER"
# Only the already separately verified published-image boundary is substituted.
oem_thor_published_image_valid(){ [ "$FAIL_PIN" != 1 ]; }
IFS= read -r credential || exit 1
ow_settings_prepare "$PUBLIC/binding.tsv" "$PUBLIC/est.json" "$PUBLIC/gateway.json" "$credential" "$SEED" || exit 1
credential=
oem_thor_stage_native_overlay "$SEED" "$IMAGE" "$MOUNT"
''')

        def fixture():
            import shutil
            root = top / 'case'; shutil.rmtree(root, ignore_errors=True); root.mkdir(mode=0o700)
            public = root / 'public'; public.mkdir(mode=0o700)
            image = root / 'image'; image.write_bytes(b'synthetic-qualified-image')
            sha = hashlib.sha256(image.read_bytes()).hexdigest()
            fields = dict(format='2', serial='001122334455', family='thor', model='XV3-8',
                          source_operation='production-oem-migration', source_release='7.2-r1',
                          source_contract_sha256='a'*64, source_slot='1', target_slot='0',
                          image_sha256=sha, job_id='b'*64)
            (public / 'binding.tsv').write_text(''.join(f'{k}\t{v}\n' for k,v in fields.items()))
            (public / 'est.json').write_text('{"server":"issuer.invalid","tls_ca":"/etc/ssl/certs/ca-certificates.crt"}\n')
            (public / 'gateway.json').write_text('{"DEFAULT":{"gateway":"controller.invalid"}}\n')
            for p in public.iterdir(): p.chmod(0o600)
            mnt = root / 'mounted'; mnt.mkdir(mode=0o700)
            sys = root / 'sys'; (sys / 'ubi6').mkdir(parents=True); (sys / 'ubi6/mtd_num').write_text('7')
            (sys / 'ubi6_2').mkdir(); (sys / 'ubi6_2/name').write_text('rootfs_data')
            mounts = root / 'mounts'; mounts.write_text(f'/dev/ubi6_2 {mnt} ubifs rw 0 0\n')
            # Numeric ls fixture strips macOS xattr annotations; actual modes/UID/link count remain.
            tools = root / 'bin'; tools.mkdir()
            ls = tools / 'ls'
            ls.write_text('#!/usr/bin/env python3\nimport os,stat,sys\np=sys.argv[-1];s=os.lstat(p);print(stat.filemode(s.st_mode),s.st_nlink,s.st_uid,s.st_gid,s.st_size,"Jan 1 00:00",p)\n'); ls.chmod(0o700)
            sync = tools / 'sync'; sync.write_text('#!/bin/sh\n[ "${FAIL_SYNC:-0}" != 1 ]\n'); sync.chmod(0o700)
            env = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'], SETTINGS=str(lib), ADAPTER=str(adapter),
                       PUBLIC=str(public), SEED=str(root/'seed'), IMAGE=str(image), MOUNT=str(mnt),
                       OEM_SKU='00000013', OEM_MODEL='XV3-8', OEM_SERIAL='001122334455', OEM_SOURCE_RELEASE='7.2-r1',
                       OEM_SOURCE_SLOT='1', OEM_TARGET_SLOT='0', OEM_TARGET_MTD='7', OEM_TARGET_UBI='ubi6',
                       OW_SETTINGS_OWNER=str(os.getuid()), OW_SETTINGS_SYS=str(sys), OW_SETTINGS_MOUNTS=str(mounts),
                       OW_STAGE_ADMISSION='qualified', OW_EXPECT_SERIAL='001122334455', OW_EXPECT_FAMILY='thor',
                       OW_EXPECT_MODEL='XV3-8', OW_EXPECT_OPERATION='production-oem-migration', OW_EXPECT_RELEASE='7.2-r1',
                       OW_EXPECT_CONTRACT='a'*64, OW_EXPECT_SOURCE='1', OW_EXPECT_TARGET='0', OW_EXPECT_JOB='b'*64,
                       OW_EXPECT_TARGET_VOLUME='ubi6_2', OW_EXPECT_TARGET_MTD='7', FAIL_PIN='0')
            return root, env

        for fault in ('success', 'serial', 'source-slot', 'target-mtd', 'cert-volume', 'read-only', 'upper-private', 'sync', 'image-pin'):
            root, env = fixture()
            if fault == 'serial': env['OEM_SERIAL'] = '000000000001'
            elif fault == 'source-slot': env['OEM_SOURCE_SLOT'] = '0'
            elif fault == 'target-mtd': env['OEM_TARGET_MTD'] = '9'
            elif fault == 'cert-volume': env['OW_EXPECT_TARGET_VOLUME'] = 'ubi6_4'
            elif fault == 'read-only': (root/'mounts').write_text((root/'mounts').read_text().replace(' rw ', ' ro '))
            elif fault == 'upper-private': (root/'mounted/upper').mkdir(mode=0o700)
            elif fault == 'sync': env['FAIL_SYNC'] = '1'
            elif fault == 'image-pin': env['FAIL_PIN'] = '1'
            result = subprocess.run(['sh', str(driver)], env=env, input='X'*64+'\n', text=True,
                                    capture_output=True, timeout=5)
            assert 'X'*64 not in result.stdout+result.stderr
            assert (result.returncode == 0) == (fault == 'success'), (fault, result.stdout, result.stderr)
            dest = root/'mounted/upper/root/.cambium-installer-settings'
            if fault == 'success':
                assert stat.S_IMODE((root/'mounted/upper').stat().st_mode) == 0o755
                assert stat.S_IMODE((root/'mounted/upper/root').stat().st_mode) == 0o700
                assert stat.S_IMODE(dest.stat().st_mode) == 0o700
                assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in dest.iterdir())
            else: assert not dest.exists()
            count += 1
        print(f'PASS: {count} actual producer/Thor/stager cases with fresh umask077; public upper0755/private700600; no private-input output')
        print('Scope: real files/permissions, actual FORMAT2 producer/context/mount-record checks. Published image pin and mount are fixture boundaries; no real OverlayFS/UID81 exec, issuer, device, boot or firmware build.')


if __name__ == '__main__': main()
