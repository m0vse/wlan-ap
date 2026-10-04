#!/usr/bin/env python3
"""Small offline helper-control tests. All loaders/hashes are mocks; no AP."""
import hashlib
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

helper = Path(sys.argv[1]).read_text()
hashes = {
    'ath11k.ko':'bc51dc38ba8bd5884bcc24cbf6f0a750d7be22d67b11dba33c1b0fe20410fa0e',
    'ath11k_ahb.ko':'e3d7661fb85d5813cf931b1ff78f3261c2102fabf1864fb4f7ec3e6fb2adc2c6',
    'ath11k_pci.ko':'0cad8a114ba0b5b2b9383de412cb08fc0aa7ac2e00b7eb8897c2397d150e2f31',
    'ath11k-ap-tpc.ko':'4d706f5518ce5ffa960a50577ee9d0d4876ab39c131b6ca2d027aded1a782b45',
    'board-2.bin':'ec7f6118fb340f5f752e6f160c633148a400b779500e5e139b57c822b1f060b4',
}
for mode in ['success','bad-board','autoload-race','load-failure','invalid-parameter']:
    with tempfile.TemporaryDirectory(prefix='tpc-once-offline.') as tmp:
        root = Path(tmp)
        work = root/'root/xe34-ath11k-tpc-once'
        work.mkdir(parents=True)
        mock = root/'mock'
        mock.mkdir()
        for path in ['etc/rc.d','etc/init.d','sys/module','tmp/sysinfo','lib/modules/6.12.85']:
            (root/path).mkdir(parents=True)
        link = root/'etc/rc.d/S09zz_ath11k_tpc_once'
        link.symlink_to('../init.d/zz_ath11k_tpc_once')
        (root/'etc/init.d/zz_ath11k_tpc_once').touch()
        for name in ['S09cambium-board-data','S09early_boot','S10boot']:
            (root/'etc/rc.d'/name).symlink_to('../init.d/zz_ath11k_tpc_once')
        (root/'tmp/sysinfo/board_name').write_text('wrong-board' if mode=='bad-board' else 'cambiumnetworks,xe3-4')
        (work/'armed').touch()
        params='cold_boot_cal=N\ncrypto_mode=0\ndebug_mask=0\nframe_mode=0\nftm_mode=N\nxv3_8_hw_mode=(null)\n'
        if mode=='invalid-parameter':
            params+='unrecognised=1\n'
        (work/'parameters').write_text(params)
        (work/'parameters.sha256').write_text(hashlib.sha256(params.encode()).hexdigest())
        def command(name, body):
            file = mock/name
            file.write_text('#!/bin/sh\nset -eu\n'+body+'\n')
            file.chmod(0o700)
        command('uci', '''case "$4" in *) :;; esac
case "$*" in
*ucentral.config.serial) echo b4a25c05c018;;
*radio2.band) echo 6g;; *radio2.country) echo GB;; *radio2.txpower) echo 14;;
*) echo 0;; esac'''.replace('case "$4" in *) :;; esac\n',''))
        command('uname','echo 6.12.85')
        command('dmesg','echo offline-kernel-fixture')
        command('sync','echo sync >> "$TPCI_MOCK_ROOT/events"')
        command('cat','''case "$1" in /proc/sys/kernel/random/boot_id) echo offline-boot;; *) exec /bin/cat "$@";; esac''')
        cases='\n'.join(f'*{name}) echo "{value}  $1";;' for name,value in hashes.items())
        command('sha256sum','case "$1" in\n'+cases+f'\n*parameters) echo "{hashlib.sha256(params.encode()).hexdigest()}  $1";;\n*) exit 1;; esac')
        guard='''test -f "$TPCI_MOCK_ROOT/root/xe34-ath11k-tpc-once/consumed"
test ! -e "$TPCI_MOCK_ROOT/root/xe34-ath11k-tpc-once/armed"
test ! -e "$TPCI_MOCK_ROOT/etc/rc.d/S09zz_ath11k_tpc_once"
grep -q sync "$TPCI_MOCK_ROOT/events"
'''
        command('modprobe',guard+'''echo "modprobe $*" >> "$TPCI_MOCK_ROOT/events"
if [ "$TPCI_MOCK_MODE" = autoload-race ] && [ "$1" = qmi_helpers ]; then
    mkdir "$TPCI_MOCK_ROOT/sys/module/ath11k"
fi''')
        command('insmod',guard+'''echo "insmod $*" >> "$TPCI_MOCK_ROOT/events"
[ "$TPCI_MOCK_MODE" != load-failure ] || exit 1
mkdir "$TPCI_MOCK_ROOT/sys/module/ath11k"''')
        script = re.sub(r'(?<![a-zA-Z0-9_/.])(?:/tmp/sysinfo|/root|/etc|/lib|/sys)(?=/)',
                        lambda match: str(root)+match.group(), helper)
        script = script.replace('/sbin/modprobe',str(mock/'modprobe')).replace('/sbin/insmod',str(mock/'insmod'))
        env = dict(os.environ, PATH=str(mock)+':'+os.environ['PATH'], TPCI_MOCK_ROOT=tmp, TPCI_MOCK_MODE=mode)
        result = subprocess.run(['/bin/sh'], input=script+'\nboot\n', text=True, capture_output=True, env=env)
        assert result.returncode==0, (mode,result.stderr)
        events=(root/'events').read_text()
        assert not (work/'armed').exists() and (work/'consumed').exists() and not link.exists(), mode
        assert ('insmod ' in events)==(mode in ['success','load-failure']), (mode,events)
        if mode=='success':
            assert 'xv3_8_hw_mode=' not in events
            assert 'candidate-core-loaded-no-hardware-acceptance' in (work/'stages.log').read_text()
        before=events
        result=subprocess.run(['/bin/sh'],input=script+'\nboot\n',text=True,capture_output=True,env=env)
        assert result.returncode==0 and (root/'events').read_text()==before, mode
        print(mode+': disarmed-before-load/second-boot-no-load PASS')
