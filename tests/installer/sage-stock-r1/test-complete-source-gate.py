#!/usr/bin/env python3
"""Actual preparer's source_gate, with private filesystem namespace redirects."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

bundle, source = (Path(arg).resolve() for arg in sys.argv[1:])
work = Path(tempfile.mkdtemp(prefix='family-complete-source-gate.', dir='/tmp'))
prepare = (bundle / 'prepare-upgrader.sh').read_text()
function = 'source_gate() {' + prepare.split('source_gate() {', 1)[1].split('\n}\nBRIDGE_ROOT', 1)[0] + '\n}\n'
checker = (bundle / 'source-set-check.sh').read_text().replace('ow_source_set_matches()', 'ow_actual_source_set_matches()')
items = []
for line in (bundle / 'bridge-transaction.sh').read_text().split("cat <<'ITEMS'\n", 1)[1].split('\nITEMS', 1)[0].splitlines():
    items.append(line.split())
reports = []
for name in ('outgoing', 'installed', 'changed-source', 'missing-source', 'mixed-tuple', 'extra-upgrade-script', 'extra-function-script', 'symlink-source'):
    root = work / name
    root.mkdir()
    paths = (bundle / 'source-sets/required-paths').read_text().splitlines()
    for path in paths:
        original = source / path.lstrip('/')
        if original.is_file():
            target = root / path.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
    if name in ('installed', 'mixed-tuple'):
        for item, path in items if name == 'installed' else items[:1]:
            shutil.copy2(bundle / item, root / path.lstrip('/'))
    if name == 'changed-source':
        path = root / 'sbin/sysupgrade'
        path.write_bytes(path.read_bytes() + b'\nunknown-source\n')
    elif name == 'missing-source':
        (root / 'lib/functions.sh').unlink()
    elif name in ('extra-upgrade-script', 'extra-function-script'):
        directory = 'lib/upgrade' if name == 'extra-upgrade-script' else 'lib/functions'
        (root / directory / 'unknown.sh').write_text('echo NEVER_EXECUTED\n')
    elif name == 'symlink-source':
        target = root / 'sbin/sysupgrade'
        target.unlink()
        target.symlink_to(source / 'sbin/sysupgrade')
    # Only filesystem namespace prefixes change. Lookup keys strip the
    # fixture root to retain exact original absolute manifest membership.
    redirected = function.replace('for path in /lib/', f'for path in {root}/lib/').replace(' /lib/', f' {root}/lib/')
    redirected = redirected.replace('grep -Fxq "$path"', f'grep -Fxq "${{path#"{root}"}}"')
    driver = root / 'gate-driver.sh'
    driver.write_text(checker + '\n' +
        'ow_source_set_matches() { ow_actual_source_set_matches "$1" "$2" "$FIXTURE_ROOT"; }\n' +
        redirected + '\nsource_gate\n')
    env = dict(os.environ, bundle=str(bundle), FIXTURE_ROOT=str(root))
    result = subprocess.run(['sh', str(driver)], env=env, capture_output=True, text=True)
    assert (result.returncode == 0) == (name in ('outgoing', 'installed')), (name, result.stdout, result.stderr)
    assert 'NEVER_EXECUTED' not in result.stdout, name
    reports.append({'case': name, 'passed': True, 'accepted': result.returncode == 0})
print(json.dumps({'passed': True, 'count': len(reports), 'cases': reports, 'fixture': str(work),
                  'preparer_sha256': hashlib.sha256(prepare.encode()).hexdigest(),
                  'scope': 'Actual complete source gate and tuple checker; private filesystem prefix/root mapping only; no AP script sourced or executed'}, indent=2))
