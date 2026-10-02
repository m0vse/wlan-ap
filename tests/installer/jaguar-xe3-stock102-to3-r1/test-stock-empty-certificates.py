#!/usr/bin/env python3
"""Exercise actual stock-only helper, without UBI/mount/upgrade execution."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

helper = Path(sys.argv[1]).resolve()
work = Path(tempfile.mkdtemp(prefix='stock-empty-certificates.', dir='/tmp'))
legacy = work / 'legacy'
legacy.mkdir()
(legacy / 'key.pem').write_text('DO NOT IMPORT fixture legacy key')
(legacy / 'cert.pem').symlink_to('/nonexistent/fixture-cert')
(legacy / 'gateway.json').write_text('DO NOT IMPORT fixture endpoint')
(work / 'boot-id').write_text('fixture-boot\n')
tools = work / 'bin'
tools.mkdir()
(tools / 'openssl').write_text('#!/bin/sh\necho crypto-called >> "$FIXTURE_CRYPTO"\nexit 99\n')
(tools / 'openssl').chmod(0o755)
env = dict(os.environ, PATH=str(tools) + ':' + os.environ['PATH'],
           FIXTURE_CRYPTO=str(work / 'crypto-called'),
           AB_CERTIFICATE_OWNER=str(os.getuid()),
           AB_CERTIFICATE_STORE=str(legacy), AB_CERTIFICATE_RUNTIME=str(legacy),
           AB_BOOT_ID=str(work / 'boot-id'), AB_CERTIFICATE_ARCHIVE=str(work / 'archive'),
           AB_CERTIFICATE_DESCRIPTOR=str(work / 'descriptor'))
shell = '''set -eu
AB_LEB=126976
. "$1"
ab_certificate_lebs() { echo 20; }
ab_identity() { AB_LAYOUT=banks; AB_FAMILY=jaguar; AB_MODEL=XV2-2T1; AB_SKU=fixture; AB_ACTIVE=0; AB_TARGET=1; AB_ACTIVE_MTD=0; AB_TARGET_MTD=1; }
ab_fail() { echo "$*" >&2; }
ab_identity
'''
def run(command, good=True):
    result = subprocess.run(['sh', '-c', shell + command, 'fixture', str(helper)],
                            env=env, text=True, capture_output=True)
    assert (result.returncode == 0) == good, (command, result.stdout, result.stderr)

cases = []
run('SAVE_CONFIG=0; ab_certificate_export; ab_certificate_validate_snapshot')
original = (work / 'archive').read_bytes()
descriptor = (work / 'descriptor').read_bytes()
cases.append('empty-export-and-bound-validation')
run('SAVE_CONFIG=1; ab_certificate_export', False)
assert (work / 'archive').read_bytes() == original
cases.append('preserving-execution-refused-before-export')
assert not (work / 'crypto-called').exists()
assert (legacy / 'key.pem').read_text() == 'DO NOT IMPORT fixture legacy key'
assert (legacy / 'cert.pem').is_symlink()
assert (legacy / 'gateway.json').read_text() == 'DO NOT IMPORT fixture endpoint'
cases.append('legacy-unsafe-material-and-crypto-untouched')
def replace_archive(members):
    with tarfile.open(work / 'archive', 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.mode = 0o700 if name == './' else 0o600
            info.type = tarfile.DIRTYPE if name == './' else tarfile.REGTYPE
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    (work / 'archive').chmod(0o600)
    digest = hashlib.sha256((work / 'archive').read_bytes()).hexdigest()
    (work / 'descriptor').write_bytes(descriptor.splitlines()[0] + b'\n' + digest.encode() + b'\n')
    (work / 'descriptor').chmod(0o600)
base = [('./', b''), ('./.cambium-ab-manifest', b'')]
replace_archive(base)
run('ab_certificate_validate_snapshot')
cases.append('equivalent-empty-archive-accepted')
for label, members in (
    ('extra-key-refused', base + [('./key.pem', b'legacy')]),
    ('duplicate-manifest-refused', base + [('./.cambium-ab-manifest', b'')]),
    ('newline-manifest-refused', [('./', b''), ('./.cambium-ab-manifest', b'\n')]),
    ('nonempty-manifest-refused', [('./', b''), ('./.cambium-ab-manifest', b'legacy')]),
    ('missing-manifest-refused', [('./', b'')]),
):
    replace_archive(members)
    run('ab_certificate_validate_snapshot', False)
    cases.append(label)
(work / 'archive').write_bytes(original)
(work / 'descriptor').write_bytes(descriptor.replace(b'fixture-boot', b'wrong-boot'))
run('ab_certificate_validate_snapshot', False)
cases.append('wrong-boot-binding-refused')
(work / 'descriptor').write_bytes(descriptor)
(work / 'archive').write_bytes(original + b'changed')
run('ab_certificate_validate_snapshot', False)
cases.append('checksum-drift-refused')
print(json.dumps({'passed': True, 'count': len(cases), 'cases': cases,
                  'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                  'fixture': str(work),
                  'scope': 'Actual export/validator with identity fixtures; no mount, restore, bank/env writes or AP execution'}, indent=2))
