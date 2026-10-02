#!/usr/bin/env python3
"""Execute frozen startup and export with synthetic credentials/mount stubs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
canonical_test = Path(sys.argv[2]).resolve()
family = sys.argv[3]
assert family in ('sage', 'jaguar')
work = Path(tempfile.mkdtemp(prefix='sage-jaguar-incoming-cert.', dir='/tmp'))
reports = []
startup = (root / 'etc/init.d/early_boot').read_text()
for provisioned in (True, False):
    case = work / ('provisioned' if provisioned else 'bootstrap-only')
    runtime = case / 'runtime'
    runtime.mkdir(parents=True)
    (runtime / 'key.pem').write_text('synthetic fixture, not a key\n')
    if provisioned:
        (runtime / 'operational.pem').write_text('synthetic fixture, not a certificate\n')
    text = startup.replace('/etc/ucentral', str(runtime)).replace('/usr/bin/mount_certs', 'fixture_mount')
    script = 'board_name() { echo cambiumnetworks,test; }; fixture_mount() { echo mount-called; };\n' + text
    script += '\ncopy_certificates() { echo copy-called; }; boot\n'
    result = subprocess.run(['/bin/sh', '-c', script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    expected = '' if provisioned else 'mount-called\ncopy-called\n'
    assert result.stdout == expected, result.stdout
    reports.append({'case': case.name, 'startup_skips_mount': provisioned, 'passed': True})
if family == 'jaguar':
    # Reuse the canonical file-level retention suite against ACTUAL extracted
    # helper/common sources. Only source paths and target hexdump are redirected.
    text = canonical_test.read_text()
    text = text.replace('"$top/package/cambium/cambium-ab/files/cambium-ab-certificates.sh"',
                        '"$FROZEN_ROOT/lib/upgrade/cambium-ab-certificates.sh"')
    text = text.replace('"$top/package/base-files/files/lib/upgrade/common.sh"',
                        '"$FROZEN_ROOT/lib/upgrade/common.sh"')
    # Anchor top calculation to the existing test; the result is not sourced.
    text = text.replace('top=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)', 'top=/unused')
    binpath = work / 'bin'
    binpath.mkdir()
    shim = binpath / 'hexdump'
    shim.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/bin/busybox" hexdump "$@"\n')
    shim.chmod(0o755)
    script = work / 'retention.sh'
    script.write_text(text)
    env = dict(os.environ, FROZEN_ROOT=str(root), PATH=str(binpath) + ':' + os.environ['PATH'])
    result = subprocess.run(['/bin/sh', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reports.append({'case': 'unmounted-UBIFS-export-runtime-policy-precedence-restore-and-refusals',
                    'passed': True, 'result': result.stdout.strip()})
else:
    # Shared store export must return without mounting/snapshotting/writing.
    helper = root / 'lib/upgrade/cambium-ab-certificates.sh'
    script = f'. "{helper}"\nab_certificate_lebs() {{ echo 0; }}\n'
    script += 'ab_identity() { echo forbidden-identity; return 99; }; mount() { echo forbidden-mount; return 99; };\nab_certificate_export\nab_certificate_restore\n'
    result = subprocess.run(['/bin/sh', '-c', script], capture_output=True, text=True)
    assert result.returncode == 0 and not result.stdout, result.stderr
    reports.append({'case': 'Sage-zero-LEB-shared-store-export-restore-no-op', 'passed': True})
print(json.dumps({'passed': True, 'family': family, 'cases': reports,
                  'source_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                                     for p in ('etc/init.d/early_boot', 'lib/upgrade/cambium-ab-certificates.sh')},
                  'fixture': str(work),
                  'scope': 'Actual frozen scripts, file-only startup and canonical retention tests with synthetic locally generated credentials and mount/UBI identity stubs. No production key/cert access, actual mounts, AP access, flash or reboot.'}, indent=2))
