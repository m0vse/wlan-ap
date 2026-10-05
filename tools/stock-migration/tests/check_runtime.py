"""Actual outgoing BusyBox metadata/archive ABI, no flash/mount/ENV operation."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root, bundle = map(lambda p: Path(p).resolve(), sys.argv[1:3])
family = sys.argv[3]
qemu = '/usr/bin/qemu-arm' if family == 'sage' else '/usr/bin/qemu-aarch64'
command = [qemu, '-L', str(root), str(root/'bin/busybox')]

with tempfile.TemporaryDirectory(prefix='stock-format2-runtime.') as tmp:
    work = Path(tmp)
    tools = work/'bin'; tools.mkdir()
    # Every parser/archive applet introduced by settings staging executes the
    # exact qualified outgoing binary. Shell wrappers only select its argv0.
    for name in ('ls','awk','readlink','sha256sum','cat','mkdir','cp','chmod','mv','tar','tr','mktemp','wc','rmdir'):
        tool = tools/name
        tool.write_text('#!/bin/sh\nexec ' + ' '.join(command) + ' '+name+' "$@"\n')
        tool.chmod(0o700)
        run = subprocess.run(command+[name,'--help'], capture_output=True)
        assert b'applet not found' not in run.stderr, name
    private = work/'private'; private.mkdir(mode=0o700)
    payload = private/'payload'; payload.write_bytes(b'not an enrollment credential\n'); payload.chmod(0o600)
    env = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'], OW_SETTINGS_OWNER=str(os.getuid()))
    script = '''. "$1" || exit 1
[ "$(ow_settings_metadata "$2")" = "$OW_SETTINGS_OWNER:600:1" ] || exit 2
ow_settings_private "$2" || exit 3
archive=$3/archive.tar
tar cf "$archive" -C "$3/private" . || exit 4
tar tf "$archive" | awk '$0!="./" && $0!="./payload" {bad=1} END {exit bad}' || exit 5
tar tvf "$archive" | awk 'substr($1,1,1)!="-" && substr($1,1,1)!="d" {bad=1} END {exit bad}' || exit 6
mkdir "$3/extract" && tar xf "$archive" -C "$3/extract" || exit 7
[ "$(ow_settings_hash "$2")" = "$(ow_settings_hash "$3/extract/payload")" ] || exit 8
'''
    shared = bundle/'cambium-installer-settings.sh'
    run = subprocess.run(command+['ash','-c',script,'runtime',str(shared),str(payload),str(work)], env=env, capture_output=True)
    assert run.returncode == 0, (family,run.returncode,run.stderr)
    deny = '. "$1"; ! ow_settings_private "$2"'
    for fault in ('mode','hardlink','symlink'):
        if fault == 'mode': payload.chmod(0o644)
        elif fault == 'hardlink':
            payload.chmod(0o600); os.link(payload, private/'other')
        else:
            (private/'other').unlink(); payload.unlink(); payload.symlink_to(private/'absent')
        run = subprocess.run(command+['ash','-c',deny,'runtime',str(shared),str(payload)],env=env,capture_output=True)
        assert run.returncode == 0, (fault,run.stderr)
    checker = bundle/'runtime-implementation-contract.sh'
    run = subprocess.run(['sh','-c','. "$1"; ow_runtime_contract_check "$2" "$3"','ledger',str(checker),str(bundle/'source-sets/runtime-implementation.set'),str(root)],capture_output=True)
    assert run.returncode == 0, run.stderr
    stage2 = (root/'lib/upgrade/stage2').read_text()
    assert stage2.index('platform_pre_upgrade "$IMAGE"') < stage2.rindex('switch_to_ramfs')
    assert '$RAMFS_COPY_DATA' in stage2 and '$RAMFS_COPY_BIN' in stage2
    print(f'{family}: actual stock metadata/archive applets + privacy denial + executable/library ledger PASS; stage2 sha256={hashlib.sha256(stage2.encode()).hexdigest()}')
