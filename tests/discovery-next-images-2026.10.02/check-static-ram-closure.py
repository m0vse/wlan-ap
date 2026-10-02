#!/usr/bin/env python3
"""Inspect extracted stage2 payload/ELF closure; never execute target helpers."""
import glob
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

root = Path(sys.argv[1]).resolve()
release = (root / 'etc/openwrt_release').read_text()
expected_machine = 183 if "DISTRIB_ARCH='aarch64_cortex-a53'" in release else 40 if "DISTRIB_ARCH='arm_cortex-a7_neon-vfpv4'" in release else None
assert expected_machine, 'unknown target architecture'
stage = (root / 'lib/upgrade/stage2').read_text()
platform = (root / 'lib/upgrade/platform.sh').read_text()
helper = (root / 'lib/upgrade/cambium-ab-certificates.sh').read_text()

def resolve(path):
    path = Path(path)
    for _ in range(32):
        assert path.is_relative_to(root), f'escape: {path}'
        if not path.is_symlink():
            assert path.is_file(), f'missing payload: {path}'
            return path
        target = path.readlink()
        path = root / str(target).lstrip('/') if target.is_absolute() else path.parent / target
        path = Path(__import__('os').path.normpath(path))
    raise AssertionError(f'symlink cycle: {path}')

def command(name):
    candidates = [root / name.lstrip('/')] if name.startswith('/') else [root / directory / name for directory in ('usr/sbin', 'usr/bin', 'sbin', 'bin')]
    for path in candidates:
        if path.exists() or path.is_symlink():
            return resolve(path)
    return None

body = stage.split('for binary in', 1)[1].split('\n\tdo', 1)[0]
names = shlex.split(body.replace('\\\n', ' '))
extra = re.search(r"RAMFS_COPY_BIN='([^']*)'", platform).group(1).split()
assert 'cmp mktemp sha256sum' in helper, 'missing dynamic export binary closure'
names = [name for name in names if not name.startswith('$')] + extra + ['cmp', 'mktemp', 'sha256sum']
required = {'busybox', 'sh', 'mount', 'umount', 'tar', 'head', 'ls', 'find', 'cp', 'mv', 'rm', 'mkdir', 'rmdir', 'chmod', 'awk', 'sed', 'wc', 'tr', 'cmp', 'mktemp', 'sha256sum', 'fw_printenv', 'fw_setenv', 'ubiattach', 'ubidetach', 'ubiformat', 'ubimkvol', 'ubiupdatevol', 'ubirsvol', 'ubirmvol'}
retained_names = {Path(name).name for name in names}
for name in required:
    assert name in retained_names, f'required command not retained by stage2: {name}'
    assert command(name), f'missing required helper command: {name}'
    assert command(name).stat().st_mode & 0o111, f'nonexecutable required command: {name}'

pending = [command(name) for name in names if command(name)]
seen = {}
while pending:
    path = pending.pop()
    key = str(path.relative_to(root))
    if key in seen:
        continue
    data = path.read_bytes()
    if data[:4] != b'\x7fELF':
        assert data.startswith(b'#!'), f'unknown executable format: {key}'
        interpreter = data.splitlines()[0][2:].decode().split()[0]
        assert command(interpreter), f'missing script interpreter: {key}'
        pending.append(command(interpreter))
        seen[key] = {'script_interpreter': interpreter}
        continue
    output = subprocess.check_output(['readelf', '-d', '-l', str(path)], text=True)
    assert data[5] == 1 and int.from_bytes(data[18:20], 'little') == expected_machine, f'wrong ELF architecture/endian: {key}'
    needed = re.findall(r'\(NEEDED\).*?\[([^]]+)\]', output)
    interpreter = re.search(r'Requesting program interpreter: ([^]]+)', output)
    if interpreter:
        pending.append(resolve(root / interpreter.group(1).lstrip('/')))
    for library in needed:
        candidates = [root / directory / library for directory in ('lib', 'usr/lib', 'lib64', 'usr/lib64')]
        matches = [candidate for candidate in candidates if candidate.exists() or candidate.is_symlink()]
        assert matches, f'missing dependency {library} for {key}'
        pending.append(resolve(matches[0]))
    seen[key] = {'needed': needed, 'interpreter': interpreter.group(1) if interpreter else None}

for pattern in ('lib/*.sh', 'lib/functions/*.sh', 'lib/upgrade/*.sh'):
    assert pattern in stage, f'stage2 no longer copies {pattern}'
    for path in root.glob(pattern):
        resolve(path)
for path in ('lib/upgrade/do_stage2', 'usr/share/libubox/jshn.sh'):
    resolve(root / path)
runtime_inputs = []
if (root / 'etc/fw_env.config').is_file():
    resolve(root / 'etc/fw_env.config')
else:
    generator = resolve(root / 'etc/uci-defaults/30_uboot-envtools')
    library = resolve(root / 'lib/uboot-envtools.sh')
    assert any(name in generator.read_text() for name in ('ubootenv_add_mtd', 'ubootenv_add_uci_config'))
    assert 'config_foreach ubootenv_add_app_config' in generator.read_text()
    assert '/etc/fw_' in library.read_text() and 'ubootenv_add_app_config' in library.read_text()
    runtime_inputs.append('/etc/fw_env.config: generated at first boot; actual device contents/permissions remain runtime acceptance prerequisites')
print(json.dumps({'passed': True, 'root': str(root), 'required_commands': sorted(required),
                  'retained_command_names': sorted(retained_names),
                  'runtime_inputs': runtime_inputs, 'executables_and_libraries': seen, 'scope': 'Static actual extracted stage2 helper/script/ELF dependency closure only; no target commands executed, no physical RAM pivot or hardware flash proof'}, indent=2))
