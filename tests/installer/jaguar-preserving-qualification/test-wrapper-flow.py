#!/usr/bin/env python3
"""Real wrapper control flow with isolated preflight/sysupgrade boundaries."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

bundle = Path(sys.argv[1]).resolve()
family = sys.argv[2]
route = sys.argv[3] if len(sys.argv) > 3 else 'preserving'
assert route in ('preserving', 'stock-clean')
original = (bundle / f'{family}-sysinstall.sh').read_bytes()
work = Path(tempfile.mkdtemp(prefix=f'{family}-wrapper-flow.', dir='/tmp'))
cases = []
for case in ('default', 'explicit-check', 'check-refusal', 'recover-refusal', 'bridge-refusal', 'verify-refusal', 'validator-refusal', 'install-flow', 'unsafe-active-document'):
    fixture = work / case
    root = fixture / 'root'
    payload = fixture / 'bundle'
    tools = fixture / 'bin'
    for path in (payload, tools, root / 'etc/config', root / 'etc/config-shadow', root / 'etc/ucentral'):
        path.mkdir(parents=True, exist_ok=True)
    for directory, name in (('config', 'system'), ('config-shadow', 'network'), ('ucentral', 'key.pem')):
        (root / 'etc' / directory / name).write_text('fixture-only\n')
    if case == 'unsafe-active-document':
        (root / 'etc/ucentral/ucentral.active').symlink_to('/etc/passwd')
    wrapper = payload / f'{family}-sysinstall.sh'
    text = re.sub(r'(?<![A-Za-z0-9_])/(?:etc|rom)(?=/|[\s"\'])', lambda m: str(root) + m.group(), original.decode())
    # Redirect only the production fixed PATH to isolated test tools. The
    # actual wrapper sequencing and archive construction remain unchanged.
    text = text.replace('PATH=/usr/sbin:/usr/bin:/sbin:/bin',
                        'PATH="'+str(tools)+':/usr/sbin:/usr/bin:/sbin:/bin"')
    wrapper.write_text(text)
    (payload / 'IMAGE').write_text('fixture.bin\n')
    (payload / 'fixture.bin').write_bytes(b'fixture-image-not-flashable')
    preflight = payload / 'prepare-upgrader.sh'
    preflight.write_text('''#!/bin/sh
set -eu
echo "preflight:$1" >> "$TEST_CALLS"
case "$TEST_CASE:$1" in check-refusal:--check|recover-refusal:--recover|bridge-refusal:--install|verify-refusal:--verify-installed) exit 1 ;; esac
''')
    checksum = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in sorted(payload.iterdir()))
    (payload / 'SHA256SUMS').write_text(checksum)
    upgrade = tools / 'sysupgrade'
    upgrade.write_text('''#!/bin/sh
set -eu
echo "sysupgrade:$1" >> "$TEST_CALLS"
case "$1" in
 -b) tar -czf "$2" -C "$TEST_ROOT" etc/config ;;
 -T) [ "$TEST_CASE" != validator-refusal ] ;;
 -n) [ "$TEST_ROUTE" = stock-clean ]; [ "$2" = -T ]; [ "$TEST_CASE" != validator-refusal ] ;;
 -v) if [ "$TEST_ROUTE" = stock-clean ]; then [ "$2" = -n ]; [ "$#" = 3 ]; else [ "$2" = -f ]; test -f "$3"; tar -tzf "$3" > "$TEST_ARCHIVE_LIST"; fi ;;
 *) exit 99 ;;
esac
''')
    upgrade.chmod(0o755)
    for name in ('ubiformat', 'ubiupdatevol', 'fw_setenv', 'mtd', 'reboot'):
        tool = tools / name
        tool.write_text('#!/bin/sh\necho forbidden >> "$TEST_CALLS"\nexit 99\n')
        tool.chmod(0o755)
    calls = fixture / 'calls'
    calls.touch()
    env = dict(os.environ, PATH=str(tools) + ':' + os.environ['PATH'], TEST_ROUTE=route, TEST_CALLS=str(calls), TEST_CASE=case, TEST_ROOT=str(root), TEST_ARCHIVE_LIST=str(fixture / 'archive-list'))
    args = [] if case == 'default' else ['--check'] if case in ('explicit-check', 'check-refusal', 'unsafe-active-document') else ['--install']
    before = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
    result = subprocess.run(['sh', str(wrapper), *args], env=env, text=True, capture_output=True)
    successful = case in ('default', 'explicit-check', 'install-flow') or (route == 'stock-clean' and case == 'unsafe-active-document')
    assert (result.returncode == 0) == successful, (case, result.stdout, result.stderr)
    trace = calls.read_text().splitlines()
    assert 'forbidden' not in trace, case
    after = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
    assert before == after, f'fixture device data changed: {case}'
    if case in ('default', 'explicit-check', 'check-refusal', 'unsafe-active-document'):
        assert trace == ['preflight:--check'], (case, trace)
    if route == 'stock-clean':
        assert 'sysupgrade:-b' not in trace
        assert not (fixture / 'archive-list').exists()
    if case != 'install-flow':
        assert 'sysupgrade:-v' not in trace, (case, trace)
    else:
        if route == 'stock-clean':
            assert trace == ['preflight:--recover', 'preflight:--check', 'preflight:--install', 'preflight:--verify-installed', 'sysupgrade:-n', 'sysupgrade:-v'], trace
        else:
            assert trace == ['preflight:--recover', 'preflight:--check', 'sysupgrade:-b', 'preflight:--install', 'preflight:--verify-installed', 'sysupgrade:-T', 'sysupgrade:-v'], trace
            archive = (fixture / 'archive-list').read_text()
            assert all(path in archive for path in ('etc/config/system', 'etc/config-shadow/network', 'etc/ucentral/key.pem'))
    cases.append({'case': case, 'passed': True, 'trace': trace, 'device_fixture_unchanged': True})
assert (bundle / f'{family}-sysinstall.sh').read_bytes() == original
print(json.dumps({'passed': True, 'count': len(cases), 'cases': cases, 'fixture': str(work), 'wrapper_sha256': hashlib.sha256(original).hexdigest(), 'scope': 'Actual wrapper with filesystem-only path redirects; preflight and sysupgrade boundaries stubbed; no AP scripts, flash, environment changes or reboot'}, indent=2))
