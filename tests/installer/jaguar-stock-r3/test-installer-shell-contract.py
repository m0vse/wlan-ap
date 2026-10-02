#!/usr/bin/env python3
"""Exact authenticated outgoing shell logic; no AP/helper bank actions."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

bundle, source = (Path(p).resolve() for p in sys.argv[1:3])
family = sys.argv[3]
assert family in ('sage', 'jaguar')
work = Path(tempfile.mkdtemp(prefix='sage-jaguar-installer-shell.', dir='/tmp'))
paths = ['lib/functions.sh', 'lib/functions/system.sh', 'usr/share/libubox/jshn.sh', 'lib/config/uci.sh']
prepare = (bundle / 'prepare-upgrader.sh').read_text()
assert prepare.index('source_gate ||') < prepare.index('set +u') < prepare.index('. /lib/functions/system.sh')
assert prepare.index("if [ \"$mode\" = --verify-installed ]; then") < prepare.index('set +u')
assert '/lib/config/uci.sh' in (bundle / 'source-sets/required-paths').read_text().splitlines()
assert 'set -eu' in prepare and 'set +e' not in prepare
qemu = '/usr/bin/qemu-arm' if family == 'sage' else '/usr/bin/qemu-aarch64'
shells = {'native-fixture-ash': ['/home/phil/openwifi-cheetah-build/operator-r2/busybox-ash/busybox', 'ash'],
          'actual-outgoing-target-ash': [qemu, '-L', str(source), str(source / 'bin/busybox'), 'ash']}
cases = []
for name, command in shells.items():
    for case in ('unset-IPKG_INSTROOT-reproduces', 'empty-IPKG-only-unsafe',
                 'fixed-authenticated-normal-contract', 'tampered-UCI-before-source'):
        root = work / (name + '-' + case)
        root.mkdir()
        for path in paths:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            text = (source / path).read_text()
            for prefix in ('/lib/', '/usr/share/libubox/'):
                text = text.replace(prefix, str(root) + prefix)
            target.write_text(text)
        checker = root / 'checker'
        checker.write_bytes((bundle / 'source-set-check.sh').read_bytes())
        required = root / 'required'
        required.write_text(''.join('/' + p + '\n' for p in paths))
        manifest = root / 'set'
        manifest.write_text(''.join(hashlib.sha256((root / p).read_bytes()).hexdigest() + ' /' + p + '\n' for p in paths))
        if case == 'tampered-UCI-before-source':
            target = root / 'lib/config/uci.sh'
            target.write_text(target.read_text() + '\necho EXECUTED > ' + str(root / 'unsafe-marker') + '\n')
        options = 'IPKG_INSTROOT=\n' if case == 'empty-IPKG-only-unsafe' else 'unset IPKG_INSTROOT\n'
        if case == 'fixed-authenticated-normal-contract':
            options += 'set +u\n'
        driver = f'set -eu\n. "{checker}"\now_source_set_matches "{manifest}" "{required}" "{root}" || exit 71\n'
        driver += options + f'. "{root}/lib/functions/system.sh"\nconfig_get optional missing missing\n[ -z "$optional" ]\n'
        env = dict(os.environ)
        env.pop('IPKG_INSTROOT', None)
        result = subprocess.run(command + ['-c', driver], env=env, capture_output=True, text=True)
        if case == 'fixed-authenticated-normal-contract':
            assert result.returncode == 0, (name, result.stderr)
        elif case == 'tampered-UCI-before-source':
            assert result.returncode == 71 and not (root / 'unsafe-marker').exists(), (name, result.stderr)
        else:
            assert result.returncode != 0 and ('parameter not set' in result.stderr or 'parameter notset' in result.stderr), (name, case, result.stderr)
        cases.append({'shell': name, 'case': case, 'passed': True, 'exit': result.returncode})
# Execute the exact preparer's dependency loop, restricted to tr, to verify
# both missing and nonexecutable tools refuse. No sourced AP scripts here.
loop = 'for binary in' + prepare.split('for binary in', 1)[1].split('\ndone', 1)[0] + '\ndone\n'
header = loop.split('; do', 1)[0]
assert ' tr ' in header + ' '
loop = loop.replace(header, 'for binary in tr', 1)
for case in ('missing-tr', 'nonexecutable-tr', 'executable-tr'):
    tools = work / case
    tools.mkdir()
    if case != 'missing-tr':
        (tools / 'tr').write_text('#!/bin/sh\nexit 0\n')
        (tools / 'tr').chmod(0o755 if case == 'executable-tr' else 0o644)
    driver = 'set -e\ndie() { echo REFUSED; exit 73; };\n' + loop
    result = subprocess.run(['/bin/sh', '-c', driver], env=dict(os.environ, PATH=str(tools)), capture_output=True, text=True)
    assert result.returncode == (0 if case == 'executable-tr' else 73), (case, result.stderr)
    cases.append({'case': case, 'passed': True, 'exit': result.returncode})
print(json.dumps({'passed': True, 'count': len(cases), 'cases': cases,
                  'preparer_sha256': hashlib.sha256(prepare.encode()).hexdigest(),
                  'actual_outgoing_source_sha256': {p: hashlib.sha256((source / p).read_bytes()).hexdigest() for p in paths},
                  'fixture': str(work),
                  'scope': 'Actual outgoing native/target ash library logic with literal private path redirects; authenticated UCI refusal before source; exact executable dependency loop with isolated PATH. No AP, bank, mount, environment writes or reboot.'}, indent=2))
