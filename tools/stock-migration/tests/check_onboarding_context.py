"""Actual stock ARM shell/applets for shared context and key preparation.

Full source/device/storage preflight is deliberately isolated, not asserted
by this test. No AP, ENV, mount, bridge install or firmware write is used.
Run as root for the production root-only metadata checks.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root, source, bundle = (Path(p).resolve() for p in sys.argv[1:])
assert os.getuid() == 0, 'run as root in disposable qualification environment'
command = ['/usr/bin/qemu-arm', '-L', str(root), str(root/'bin/busybox')]
with tempfile.TemporaryDirectory(prefix='shared-onboarding-test.') as tmp:
    work = Path(tmp)
    tools = work/'bin'
    tools.mkdir()
    for name in ('sh', 'awk', 'cat', 'chmod', 'cmp', 'cp', 'dirname', 'hexdump',
                 'ls', 'mkdir', 'mktemp', 'mv', 'readlink', 'rm', 'rmdir', 'sed',
                 'sha256sum', 'tr', 'wc'):
        (tools/name).write_text('#!/bin/sh\nexec '+' '.join(command)+' '+name+' "$@"\n')
        (tools/name).chmod(0o700)
    test_bundle = work/'bundle'
    seed = test_bundle/'onboarding'
    seed.mkdir(parents=True, mode=0o700)
    shutil.copyfile(bundle/'cambium-installer-settings.sh', test_bundle/'cambium-installer-settings.sh')
    for name, data in [('est.json', '{}\n'), ('gateway.json', '{}\n')]:
        (seed/name).write_text(data)
        (seed/name).chmod(0o600)
    (test_bundle/'IMAGE').write_text('image.bin\n')
    (test_bundle/'image.bin').write_bytes(b'isolated candidate fixture\n')
    (test_bundle/'source-contract').write_text('2026.10.13.0\n'+'a'*64+'\n')
    text = (bundle/'prepare-upgrader.sh').read_text()
    context = text[text.index('if [ "$mode" = --context ]; then'):text.index('case "$mode" in\n --check)')]
    assert context.index('ow_settings_binding') > context.index('get_mac_label_dt')
    assert text.index('sysupgrade -n -T "$image"') < text.index(context)
    # Only the post-qualified context emitter runs here. These callbacks stand
    # for independently checked live identity and the complete wrapper gate.
    preamble = '''set -eu
[ -z "${OPENWIFI_ONBOARD_KEY+x}" ] || exit 71
mode=$1 image=$2
bundle=$(dirname "$0")
. "$bundle/cambium-installer-settings.sh"
die() { echo "context refused" >&2; exit 1; }
get_mac_label_dt() { echo "$TEST_SERIAL"; }
get_mac_label() { echo "${TEST_NATIVE:-$TEST_SERIAL}"; }
AB_FAMILY=sage AB_MODEL=$TEST_MODEL AB_ACTIVE=$TEST_SLOT
AB_TARGET=$((1-TEST_SLOT))
'''
    (test_bundle/'prepare-upgrader.sh').write_text(preamble+context)
    frontend = (source/'prepare-onboarding.sh').read_text()
    key = 'X'*64
    count = 0
    for model, serial in [('E410', '000456abc001'), ('E410B', '000456abc002')]:
        for slot in ('0', '1'):
            private = work/(model+slot)
            (seed/'prepare.sh').write_text(frontend.replace('dest=/root/.cambium-installer-input', 'dest='+str(private)))
            base = dict(os.environ, PATH=str(tools)+':'+os.environ['PATH'],
                        TEST_SERIAL=serial, TEST_MODEL=model, TEST_SLOT=slot)
            def run(supplied=key, **changes):
                env = {**base, 'OPENWIFI_ONBOARD_KEY': supplied, **changes}
                result = subprocess.run(command+['ash', str(seed/'prepare.sh')], env=env, capture_output=True)
                assert key.encode() not in result.stdout+result.stderr
                assert b'Y'*64 not in result.stdout+result.stderr
                return result
            fresh = run()
            assert fresh.returncode == 0, fresh.stderr
            binding = (private/'binding.tsv').read_text()
            assert 'serial\t'+serial+'\n' in binding
            assert 'model\t'+model+'\n' in binding
            assert 'source_slot\t'+slot+'\n' in binding
            assert 'target_slot\t'+str(1-int(slot))+'\n' in binding
            before = {p.name: p.read_bytes() for p in private.iterdir()}
            for supplied, changes, ok in [(key, {}, True), ('', {}, True),
                    ('Y'*64, {}, False), (key, {'TEST_SERIAL': '000456abcdef'}, False),
                    (key, {'TEST_MODEL': 'E410' if model=='E410B' else 'E410B'}, False),
                    (key, {'TEST_SLOT': str(1-int(slot))}, False),
                    (key, {'TEST_NATIVE': '000456abcdef'}, False)]:
                result = run(supplied, **changes)
                assert (result.returncode == 0) == ok, (model, slot, changes, result.stderr)
                assert before == {p.name: p.read_bytes() for p in private.iterdir()}
                count += 1
            (test_bundle/'image.bin').write_bytes(b'changed image fixture\n')
            assert run().returncode != 0
            (test_bundle/'image.bin').write_bytes(b'isolated candidate fixture\n')
            count += 1
    print(f'Shared context: E410/E410B both slot directions; {count} reuse/key/identity/slot/image checks PASS with actual stock ARM ash/applets; preflight boundary isolated, no AP writes')
