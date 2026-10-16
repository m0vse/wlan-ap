"""Fresh do_stage2 import regression with real stock MAC helpers and ARM ash.

The hardware/bank identity boundary is isolated; MAC lookup is NOT mocked.
No mount, firmware writer, real ENV command or reboot is executed.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generator', BASE/'prepare-bridge.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
root = Path(sys.argv[1]).resolve()
family = 'sage'
command = ['/usr/bin/qemu-arm', '-L', str(root), str(root/'bin/busybox')]
with tempfile.TemporaryDirectory(prefix='stock-fresh-writer.') as tmp:
    work = Path(tmp)
    tools = work/'bin'
    tools.mkdir()
    for name in ('awk', 'cat', 'hexdump', 'tr', 'sed', 'ls'):
        tool = tools/name
        tool.write_text('#!/bin/sh\nexec '+ ' '.join(command)+' '+name+' "$@"\n')
        tool.chmod(0o700)
    for name in ('lib/functions.sh', 'lib/config/uci.sh',
                 'lib/functions/system.sh', 'usr/share/libubox/jshn.sh'):
        dest = work/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = (root/name).read_text()
        # Literal isolated path redirects only; execute the actual helper
        # definitions, not replacement get_mac_label* fixture functions.
        for prefix in ('/lib/', '/usr/share/libubox/', '/proc/device-tree'):
            text = text.replace(prefix, str(work)+prefix)
        dest.write_text(text)
    dt = work/'proc/device-tree'
    (dt/'aliases').mkdir(parents=True)
    (dt/'ethernet').mkdir()
    (dt/'aliases/label-mac-device').write_bytes(b'ethernet\0')
    (dt/'ethernet/mac-address').write_bytes(bytes.fromhex('000456abcdef'))
    empty = work/'empty.sh'
    empty.touch()
    shared = BASE.parent/'oem-migration/recovery/scripts/lib/cambium-installer-settings.sh'
    handoff = BASE/'cambium-installer-handoff.sh'
    old = (generator.REPO/'tests/installer/sage-stock6-r3/cambium-ab-upgrade.sh').read_text()
    fixed = generator.stock_writer(old, family)
    broken = fixed.replace('. "${CAMBIUM_SYSTEM_FUNCTIONS:-/lib/functions/system.sh}" || return 1\n', '', 1)
    assert fixed != broken
    for version, writer in [('missing-import', broken), ('explicit-import', fixed)]:
        directory = work/'lib/upgrade'
        directory.mkdir(exist_ok=True)
        file = directory/'cambium-ab.sh'
        file.write_text(writer)
        env = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'],
                   CAMBIUM_SYSTEM_FUNCTIONS=str(work/'lib/functions/system.sh'),
                   CAMBIUM_AB_LIB=str(empty), CAMBIUM_INSTALLER_HANDOFF_LIB=str(handoff),
                   CAMBIUM_INSTALLER_SETTINGS_LIB=str(shared),
                   CAMBIUM_AB_CERTIFICATE_LIB=str(work/'absent'))
        script = '''
set -e
. "$1/lib/functions.sh"
# This is the import boundary used by do_stage2, not its parent stage2.
! command -v get_mac_label_dt >/dev/null 2>&1 || exit 31
! command -v get_mac_label >/dev/null 2>&1 || exit 32
include "$1/lib/upgrade"
ab_identity() { AB_QUALIFIED=1 AB_FAMILY=sage AB_MODEL=E410B AB_ACTIVE=0 AB_TARGET=1; }
OW_EXPECT_SERIAL=000456abcdef OW_EXPECT_FAMILY=sage OW_EXPECT_MODEL=E410B
OW_EXPECT_SOURCE=0 OW_EXPECT_TARGET=1
ab_installer_live_context
'''
        run = subprocess.run(command+['ash', '-c', script, 'fresh-writer', str(work), str(file)], env=env, capture_output=True)
        assert (run.returncode == 0) == (version == 'explicit-import'), (version, run.returncode, run.stderr)
        if version == 'missing-import':
            assert b'get_mac_label_dt: not found' in run.stderr, run.stderr
print(f'{family} fresh target writer shell: missing import reproduces failure; explicit import executes real DT/native MAC lookup PASS; no bank/ENV operations')
