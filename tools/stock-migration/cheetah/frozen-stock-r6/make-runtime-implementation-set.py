#!/usr/bin/env python3
"""Generate runtime ledger ONLY from SHA-qualified offline extracted root.

Usage: ROOT OUTPUT_LEDGER SEED_COMMANDS_FILE [expected ELF e_machine]
Seeds: one resolved command name or absolute executable path per line.
Prefix optional commands with ? (record absence if unavailable); prefix
explicit plugin/library seed paths with @ (readable objects, not executables).
Records all standard PATH candidates, resolved aliases, ELF interpreters and
DT_NEEDED libraries. Include known interpreter plugin paths explicitly as
seeds: DT_NEEDED cannot discover dlopen/ucode modules.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

root, output, seeds = (Path(p).resolve() for p in sys.argv[1:4])
machine = int(sys.argv[4]) if len(sys.argv) > 4 else None
records = {}
pending = []
search = ('usr/sbin', 'usr/bin', 'sbin', 'bin')
def inspect(logical):
    logical = '/' + str(logical).lstrip('/')
    for _ in range(32):
        # Resolve directory symlinks in the target namespace, not the host.
        parts = Path(logical).parts[1:]
        changed = False
        for count in range(1, len(parts)):
            parent_logical = '/' + '/'.join(parts[:count])
            parent = root / parent_logical.lstrip('/')
            if parent.is_symlink():
                target = str(parent.readlink())
                records[parent_logical] = ('L', target)
                prefix = target if target.startswith('/') else str(Path(parent_logical).parent / target)
                logical = os.path.normpath(prefix + '/' + '/'.join(parts[count:]))
                changed = True
                break
        if changed:
            continue
        path = root / logical.lstrip('/')
        assert path.is_relative_to(root), logical
        if path.is_symlink():
            target = str(path.readlink())
            records[logical] = ('L', target)
            new = target if target.startswith('/') else str(Path(logical).parent / target)
            logical = os.path.normpath(new)
            assert logical.startswith('/') and not logical.startswith('/../'), new
            continue
        if not path.exists():
            records[logical] = ('A', '-')
            return None
        assert path.is_file(), logical
        kind = 'X' if records.get(logical, ('', ''))[0] == 'X' else 'F'
        records[logical] = (kind, hashlib.sha256(path.read_bytes()).hexdigest())
        return logical
    raise AssertionError('link cycle: ' + logical)
for name in seeds.read_text().splitlines():
    if not name or name.startswith('#'):
        continue
    optional = name.startswith('?')
    library_seed = name.startswith('@')
    if optional or library_seed:
        name = name[1:]
    if name.startswith('/'):
        chosen = inspect(name)
    else:
        chosen = None
        for directory in search:
            candidate = inspect('/' + directory + '/' + name)
            if chosen is None and candidate is not None:
                chosen = candidate
    if chosen is None and optional:
        continue
    assert chosen is not None, 'required executable missing: ' + name
    if not library_seed:
        assert (root / chosen.lstrip('/')).stat().st_mode & stat.S_IXUSR, 'nonexecutable: ' + name
        records[chosen] = ('X', records[chosen][1])
    pending.append(chosen)
seen = set()
while pending:
    logical = pending.pop()
    if logical in seen:
        continue
    seen.add(logical)
    path = root / logical.lstrip('/')
    data = path.read_bytes()
    if data[:4] != b'\x7fELF':
        assert data.startswith(b'#!'), 'unknown executable format: ' + logical
        interpreter = data.splitlines()[0][2:].decode().split()[0]
        target = inspect(interpreter)
        assert target, 'missing script interpreter: ' + logical
        assert (root / target.lstrip('/')).stat().st_mode & stat.S_IXUSR, 'nonexecutable interpreter'
        records[target] = ('X', records[target][1])
        pending.append(target)
        continue
    if machine is not None:
        assert int.from_bytes(data[18:20], 'little' if data[5] == 1 else 'big') == machine, 'wrong ELF machine: ' + logical
    details = subprocess.check_output(['readelf', '-d', '-l', str(path)], text=True)
    interpreter = re.search(r'Requesting program interpreter: ([^]]+)', details)
    if interpreter:
        target = inspect(interpreter.group(1))
        assert target, 'missing ELF interpreter: ' + logical
        assert (root / target.lstrip('/')).stat().st_mode & stat.S_IXUSR, 'nonexecutable ELF interpreter'
        records[target] = ('X', records[target][1])
        pending.append(target)
    for library in re.findall(r'\(NEEDED\).*?\[([^]]+)\]', details):
        chosen = None
        for directory in ('lib', 'usr/lib', 'lib64', 'usr/lib64'):
            target = inspect('/' + directory + '/' + library)
            if chosen is None and target is not None:
                chosen = target
        assert chosen, 'missing ELF dependency: ' + library
        pending.append(chosen)
output.write_text(''.join(f'{kind} {value} {path}\n' for path, (kind, value) in sorted(records.items())))
print(json.dumps({'ledger_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                  'records': len(records), 'resolved_executables_libraries': sorted(seen),
                  'scope': 'Offline exact identity closure; no live enrollment, no executable target code. Caller must verify source-image provenance and explicitly seed interpreter plugins/dlopen modules.'}, indent=2))
