#!/usr/bin/env python3
"""Exact family renderer/legacy guard, private ENV stubs, no AP operations."""
from pathlib import Path
import os, re, subprocess, tempfile, hashlib
REPO=Path(__file__).resolve().parents[2]
BASE=REPO/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch'
def created(relative):
    section=BASE.read_text().split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
    return ''.join(x[1:]+'\n' for x in section.splitlines() if x.startswith('+'))
def run(script, env):
    return subprocess.run(['sh','-c',script],env=dict(os.environ,**env),text=True,capture_output=True)
with tempfile.TemporaryDirectory(prefix='jaguar-bootcount-') as td:
    root=Path(td)
    family='package/cambium/cambium-jaguar-support'
    common='package/cambium/cambium-ab'
    relatives=(family+'/files/cambium-ab-jaguar.sh', family+'/Makefile',common+'/files/cambium-ab-guard',common+'/Makefile')
    for relative in relatives:
        p=root/relative;p.parent.mkdir(parents=True,exist_ok=True)
        text=created(relative)
        p.write_text(text)
    for patch in sorted((REPO/'patches-25.12').glob('*.patch')):
        if 124 < int(patch.name[:4]) < 187:
            subprocess.run(['git','apply',*['--include='+relative for relative in relatives],str(patch)],cwd=root,check=True,capture_output=True)
    assert 'PKG_RELEASE:=19\n' in (root/common/'Makefile').read_text()
    subprocess.run(['git','apply',str(REPO/'patches-25.12/0187-cambium-jaguar-neutralize-oem-bank-toggle-counter.patch')],cwd=root,check=True)
    module=root/family/'files/cambium-ab-jaguar.sh'
    guard=(root/common/'files/cambium-ab-guard').read_text()
    legacy=re.search(r'(?ms)^legacy_guard\(\) \{.*?^\}',guard).group()
    count=0
    for target in (0,1):
        source=1-target
        env={'MODULE':str(module),'TARGET':str(target),'SOURCE':str(source)}
        renderer=run('. "$MODULE"; ab_bank_hex(){ echo 0x6000000; }; ab_bank_name(){ [ "$1" = 0 ] && echo rootfs || echo rootfs_1; }; AB_SLOT1_OFFSET=0x6000000 AB_FIT=config@cp01-c1-2; ab_jaguar_guarded_command "$TARGET"',env)
        assert renderer.returncode==0,renderer.stderr
        for fail in ('image','bootcount','bootcmd','changing_bootcmd','saveenv',''):
            harness=r'''
image=$TARGET;bootcount=9
setenv(){ key=$1;shift; echo "set:$key";[ "$FAIL" != "$key" ] || return 1; case "$key" in image) image=$1;;bootcount) bootcount=$1;; esac; }
saveenv(){ [ "$FAIL" != saveenv ] || return 1;[ "$image:$bootcount" = "$SOURCE:0" ] || exit 90; echo "SAVE:$image:$bootcount"; }
nand(){ echo NAND; };ubi(){ :; };bootm(){ echo BOOT;exit 0; };reset(){ echo RESET;exit 0; }
'''
            r=run(harness+renderer.stdout,{**env,'FAIL':fail});assert r.returncode==0,r.stderr
            if fail: assert 'NAND' not in r.stdout and 'BOOT' not in r.stdout and 'RESET' not in r.stdout,r.stdout
            else: assert r.stdout.index('SAVE:')<r.stdout.index('NAND'),r.stdout
            count+=1
        for healthy in ('0','1'):
            for failure in ('','write','readback','image','command','sync',
                            'before-bootcmd-read-status','before-image-read-status','before-bootcount-read-status',
                            'after-bootcmd-read-status','after-image-read-status','after-bootcount-read-status'):
                stub=r'''
. "$MODULE"
AB_FAMILY=jaguar AB_STOCK_BOOTCMD=bootipq AB_MARKER=1; ENV_IMAGE=$SOURCE; ENV_BOOTCMD=bootipq; ENV_COUNT=9
[ "$FAIL" != image ] || ENV_IMAGE=$TARGET
[ "$FAIL" != command ] || ENV_BOOTCMD=custom
ab_running_slot(){ echo "$TARGET"; }
ab_guarded_command(){ echo MOCK_CANDIDATE; }
wait_healthy(){ [ "$HEALTHY" = 1 ]; }
ab_hook(){ [ "$1" = prepare_oem_return ]; }
READ_PHASE=before
ab_getenv(){ case "$1" in image) echo "$ENV_IMAGE";;bootcmd) echo "$ENV_BOOTCMD";;bootcount) [ "$FAIL" = readback ] && echo 9 || echo "$ENV_COUNT";;esac; [ "$FAIL" != "$READ_PHASE-$1-read-status" ]; }
ab_setenv(){ echo "WRITE:$1:$2";case "$1" in bootcount) [ "$FAIL" != write ] || return 1;ENV_COUNT=$2;READ_PHASE=after;;esac; }
sync(){ [ "$FAIL" != sync ]; }
log(){ :; }; do_reboot(){ echo REBOOT; }
'''
                r=run(stub+legacy+'\nlegacy_guard\n',{**env,'FAIL':failure,'HEALTHY':healthy})
                if failure:
                    assert r.returncode!=0,(failure,r.stdout,r.stderr)
                    assert 'REBOOT' not in r.stdout and 'WRITE:changing_bootcmd' not in r.stdout,r.stdout
                    if failure in ('image','command') or failure.startswith('before-'): assert 'WRITE:bootcount' not in r.stdout,r.stdout
                else:
                    assert r.returncode==0 and 'WRITE:bootcount:0' in r.stdout,(r.stdout,r.stderr)
                    assert ('WRITE:changing_bootcmd:1' in r.stdout) == (healthy=='1'),r.stdout
                    assert ('REBOOT' in r.stdout) == (healthy=='0'),r.stdout
                count+=1
        for healthy in ('0','1'):
            no_hook=r'''
AB_FAMILY=unmodified_family AB_STOCK_BOOTCMD=bootipq AB_MARKER=1
ab_running_slot(){ echo "$TARGET"; }
ab_guarded_command(){ echo MOCK_CANDIDATE; }
wait_healthy(){ [ "$HEALTHY" = 1 ]; }
ab_hook(){ return 1; }
ab_getenv(){ case "$1" in image) echo "$SOURCE";;bootcmd) echo bootipq;;bootcount) echo 9;;esac; }
ab_setenv(){ echo "WRITE:$1:$2"; }
log(){ :; };do_reboot(){ echo REBOOT; }
'''
            r=run(no_hook+legacy+'\nlegacy_guard\n',{**env,'HEALTHY':healthy})
            assert r.returncode==0 and 'WRITE:bootcount' not in r.stdout,(r.stdout,r.stderr)
            assert ('REBOOT' in r.stdout)==(healthy=='0'),r.stdout
            count+=1
    print(f'PASS {count} Jaguar count9 renderer and legacy rearm/OEM-return controls')
    print('candidate_module_sha256='+hashlib.sha256(module.read_bytes()).hexdigest())
    print('Scope: production shell/functions with private stubs; not installed bootloader or AP qualification.')
