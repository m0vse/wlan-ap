#!/usr/bin/env python3
"""Frozen incoming image's next-upgrade copy loop/extractor; no bank writes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root, image = (Path(p).resolve() for p in sys.argv[1:3])
family = sys.argv[3]
assert family in ('sage', 'jaguar')
work = Path(tempfile.mkdtemp(prefix='sage-jaguar-incoming-ram.', dir='/tmp'))
ash = '/home/phil/openwifi-cheetah-build/operator-r2/busybox-ash/busybox'
qemu = '/usr/bin/qemu-arm' if family == 'sage' else '/usr/bin/qemu-aarch64'
stage = (root / 'lib/upgrade/stage2').read_text()
function = stage[stage.index('switch_to_ramfs()'):stage.index('\nkill_remaining()')]
platform = root / 'lib/upgrade/platform.sh'
helper = root / 'lib/upgrade/cambium-ab-certificates.sh'
assignments = '\n'.join(line for line in platform.read_text().splitlines()
                        if line.startswith('RAMFS_COPY_'))
# Successful bank-local export appends these; Sage already declares them.
assignments += '\n' + next(line.strip() for line in helper.read_text().splitlines()
                            if line.strip().startswith('RAMFS_COPY_BIN='))
digest = hashlib.sha256(image.read_bytes()).hexdigest()
driver = r'''
command() {
 [ "$1" = -v ] || return 1
 case "$2" in /*) path=$2 ;; *)
  for d in /bin /sbin /usr/bin /usr/sbin; do
   if [ -x "$IMAGE_ROOT$d/$2" ]; then printf '%s\n' "$d/$2"; return 0; fi
  done
  return 1 ;;
 esac
 [ -x "$IMAGE_ROOT$path" ] && printf '%s\n' "$path"
}
install_bin() { printf '%s\n' "$1" >> "$COPY_LIST"; }
install_file() { printf '%s\n' "$@" >> "$DATA_LIST"; }
supivot() { echo stopped-before-pivot >> "$BOUNDARY"; return 1; }
v() { :; }
''' + assignments + '\n' + function + '\nswitch_to_ramfs\n'
(work / 'ram').mkdir()
env = dict(os.environ, IMAGE_ROOT=str(root), COPY_LIST=str(work / 'copy-list'),
           DATA_LIST=str(work / 'data-list'), BOUNDARY=str(work / 'boundary'),
           RAM_ROOT=str(work / 'ram'))
result = subprocess.run([ash, 'ash', '-c', driver], env=env, capture_output=True, text=True)
assert result.returncode == 1 and (work / 'boundary').exists(), result.stderr
names = {Path(p).name for p in (work / 'copy-list').read_text().splitlines()}
assert {'tr', 'sha256sum', 'cmp', 'mktemp'} <= names, names
binpath = work / 'bin'
binpath.mkdir()
for name in names:
    host = shutil.which(name)
    if host:
        (binpath / name).symlink_to(host)
for name in ('hexdump', 'tr'):
    path = binpath / name
    if path.is_symlink():
        path.unlink()
    path.write_text(f'#!/bin/sh\nexec {qemu} -L "{root}" "{root}/bin/busybox" {name} "$@"\n')
    path.chmod(0o755)
env.update(PATH=str(binpath), CAMBIUM_AB_LIB=str(root / 'lib/functions/cambium-ab.sh'),
           CAMBIUM_AB_MODULES=str(root / 'lib/functions'),
           CAMBIUM_SAGE_LIB=str(root / 'lib/functions/cambium-sage.sh'),
           CAMBIUM_AB_CERTIFICATE_LIB=str(helper),
           UPGRADE_HELPER=str(root / 'lib/upgrade/cambium-ab.sh'),
           TEST_IMAGE=str(image), AB_WORK=str(work / 'extract'),
           AB_UBI_SYS=str(work / 'ubi'))
if family == 'sage':
    for volume, name, lebs in ((0, 'linux1', 34), (1, 'rootfs1', 305), (2, 'rootfs_data1', 67)):
        path = work / 'ubi' / f'ubi0_{volume}'
        path.mkdir(parents=True)
        for key, value in (('name', name), ('reserved_ebs', lebs), ('usable_eb_size', 126976)):
            (path / key).write_text(str(value) + '\n')
    board = 'ab_sage_legacy_b() { return 1; }; ab_sage_board cambiumnetworks,e410\nAB_ACTIVE_UBI=ubi0; AB_TARGET=1'
else:
    board = 'ab_jaguar_board cambiumnetworks,xv2-2t1'
extract = '. "$UPGRADE_HELPER"\nAB_FAMILY=' + family + '; AB_ROOT_MAGIC=hsqs; AB_LAYOUT=banks\n' + board + '\nab_image_extract "$TEST_IMAGE"\n'
cases = []
for phase in ('retained', 'negative-no-tr'):
    if phase == 'negative-no-tr':
        (binpath / 'tr').unlink()
    # The minimal native fixture BusyBox lacks the command builtin needed by
    # Sage's ab_hook dispatch; use host POSIX sh for the unmodified extractor.
    # Target BusyBox ash's external tr contract is checked separately below.
    result = subprocess.run(['/bin/sh', '-c', extract], env=env, capture_output=True, text=True)
    if phase == 'retained':
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0 and 'tr: not found' in result.stderr and 'FIT lacks' in result.stderr, result.stderr
    cases.append({'case': phase, 'extract_exit': result.returncode, 'passed': True})
    target = subprocess.run([qemu, '-L', str(root), str(root / 'bin/busybox'), 'ash', '-c',
                             'printf abc | tr a b'], env=env, capture_output=True, text=True)
    assert (target.returncode == 0 and target.stdout == 'bbc') if phase == 'retained' else target.returncode == 127, target.stderr
    cases.append({'case': phase, 'target_ash_tr_exit': target.returncode, 'passed': True})
assert hashlib.sha256(image.read_bytes()).hexdigest() == digest
print(json.dumps({'passed': True, 'family': family, 'image_sha256': digest,
                  'platform_sha256': hashlib.sha256(platform.read_bytes()).hexdigest(),
                  'stage2_sha256': hashlib.sha256(stage.encode()).hexdigest(),
                  'retained_commands': sorted(names), 'cases': cases, 'fixture': str(work),
                  'scope': 'Exact incoming switch_to_ramfs copy loop in native fixture ash, executable inventory and blocked pivot; actual incoming extractor in host POSIX sh and immutable image using retained-only host tools plus target BusyBox hexdump/tr via QEMU; target ash external-tr contract; real family FIT/capacity checks with file-only Sage UBI geometry. No physical install_bin/library copy, mounts, flash, reboot or AP access.'}, indent=2))
