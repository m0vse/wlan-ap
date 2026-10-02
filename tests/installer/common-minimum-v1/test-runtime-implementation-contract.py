#!/usr/bin/env python3
"""Synthetic matcher controls; no live runtime enrollment/target execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

helper = Path(sys.argv[1]).resolve()
work = Path(tempfile.mkdtemp(prefix='runtime-contract-tests.', dir='/tmp'))
reports = []
for case in ('reviewed', 'changed-binary', 'changed-library', 'nonexecutable', 'missing-library',
             'wrong-link', 'link-to-file', 'file-to-link', 'unexpected-optional', 'dangling-optional',
             'empty-ledger', 'duplicate-ledger', 'malformed-hash', 'unsafe-ledger-path', 'symlink-ledger'):
    root = work / case
    (root / 'bin').mkdir(parents=True)
    (root / 'lib').mkdir()
    executable = root / 'bin/tool'
    executable.write_text('#!/bin/sh\nexit 0\n')
    executable.chmod(0o755)
    library = root / 'lib/libtest.so'
    library.write_bytes(b'fixture library bytes, never executed')
    alias = root / 'bin/alias'
    alias.symlink_to('tool')
    ledger = root / 'ledger'
    rows = [f'X {hashlib.sha256(executable.read_bytes()).hexdigest()} /bin/tool\n',
            f'F {hashlib.sha256(library.read_bytes()).hexdigest()} /lib/libtest.so\n',
            'L tool /bin/alias\n', 'A - /bin/optional\n']
    ledger.write_text(''.join(rows))
    if case == 'changed-binary': executable.write_text('unknown')
    elif case == 'changed-library': library.write_bytes(b'unknown')
    elif case == 'nonexecutable': executable.chmod(0o644)
    elif case == 'missing-library': library.unlink()
    elif case == 'wrong-link': alias.unlink(); alias.symlink_to('../lib/libtest.so')
    elif case == 'link-to-file': alias.unlink(); alias.write_text('tool')
    elif case == 'file-to-link': executable.unlink(); executable.symlink_to('../lib/libtest.so')
    elif case == 'unexpected-optional': (root / 'bin/optional').touch()
    elif case == 'dangling-optional': (root / 'bin/optional').symlink_to('absent')
    elif case == 'empty-ledger': ledger.write_text('')
    elif case == 'duplicate-ledger': ledger.write_text(''.join(rows + rows[:1]))
    elif case == 'malformed-hash': ledger.write_text('X BAD /bin/tool\n')
    elif case == 'unsafe-ledger-path': ledger.write_text('A - /bin/../outside\n')
    elif case == 'symlink-ledger': ledger.rename(root / 'original'); ledger.symlink_to(root / 'original')
    result = subprocess.run(['sh', '-c', '. "$1"; ow_runtime_contract_check "$2" "$3"',
                             'fixture', str(helper), str(ledger), str(root)], capture_output=True, text=True)
    assert (result.returncode == 0) == (case == 'reviewed'), (case, result.stderr)
    reports.append({'case': case, 'accepted': result.returncode == 0, 'passed': True})
print(json.dumps({'passed': True, 'count': len(reports), 'cases': reports, 'fixture': str(work),
                  'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                  'scope': 'Synthetic files/links/absence and matcher only; no target code, live enrollment or AP actions'}, indent=2))
