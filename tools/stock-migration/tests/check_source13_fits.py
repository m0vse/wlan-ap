"""Actual generated boot commands against stock13 and incoming FIT nodes.

No U-Boot command is executed; only shell functions emitting strings run.
"""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tarfile

bundle, stock_image, incoming_image = (Path(p).resolve() for p in sys.argv[1:])
assert hashlib.sha256(stock_image.read_bytes()).hexdigest() == 'f44fccdb8205e29c3cabd140a5bc9cfcac334d7e3a3c45eabb5d3f48f2968182'
assert hashlib.sha256(incoming_image.read_bytes()).hexdigest() == '669f036bc2cffeaa8edbe9f3dfb9641ad839a4fef4d10b5f3696f834d5c7068c'
def kernel(image):
    with tarfile.open(image) as archive:
        return archive.extractfile('sysupgrade-cambium_e410/kernel').read()
old, new = kernel(stock_image), kernel(incoming_image)
script = '''
CAMBIUM_SAGE_LIB=$1/cambium-sage.sh
. "$1/modules/cambium-ab-sage.sh" || exit 1
ab_sage_legacy_b() { [ "$LEGACY_B" = 1 ]; }
ab_sage_root_format() { echo "$ROOT_FORMAT"; }
ab_sage_board "$BOARD" || exit 1
AB_ACTIVE=$ACTIVE
ab_sage_boot_command "$SLOT"
'''
count = 0
for board, legacy in [('cambium,e410', '0'), ('cambiumnetworks,e410', '0'),
                      ('cambiumnetworks,e410b', '0'), ('cambiumnetworks,e410', '1')]:
    for active in ('0', '1'):
        for slot in ('0', '1'):
            for fmt in ('ubifs', 'squashfs'):
                active_fit = 'config@17' if board.endswith(',e410b') else 'config@ap.dk01.1-c2'
                target_fit = 'config@17' if board.endswith(',e410b') or legacy == '1' else 'config@5'
                fit = active_fit if slot == active else target_fit
                blob = old if slot == active else new
                assert b'\x00\x00\x00\x01'+fit.encode()+b'\x00' in blob, fit
                env = dict(os.environ, BOARD=board, LEGACY_B=legacy, ACTIVE=active, SLOT=slot, ROOT_FORMAT=fmt)
                run = subprocess.run(['sh', '-c', script, 'fit-test', str(bundle)], env=env, capture_output=True, text=True)
                assert run.returncode == 0, run.stderr
                assert run.stdout.strip().endswith('bootm 0x84000000#'+fit), run.stdout
                assert 'ubi read 0x84000000 linux'+slot+' &&' in run.stdout, run.stdout
                assert 'setenv image '+slot+';' in run.stdout, run.stdout
                count += 1
print(f'stock13: {count} generated E410/E410B/legacy-B slot/format boot entries match real stock and incoming kernel FITs PASS; no boot commands executed')
