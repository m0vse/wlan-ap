#!/usr/bin/env python3
"""Actual Jaguar renderer; mocked save/load/reset, no device/bootloader calls."""
from pathlib import Path
import os
import subprocess
import tempfile

REPO=Path(__file__).resolve().parents[2]
PATCH=REPO/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch'
def created(relative):
    section=PATCH.read_text().split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
    return ''.join(x[1:]+'\n' for x in section.splitlines() if x.startswith('+'))

with tempfile.TemporaryDirectory(prefix='jaguar-oem-boot-') as td:
    root=Path(td)
    core=root/'core'; core.write_text(created('package/cambium/cambium-ab/files/cambium-ab.sh'))
    module=root/'package/cambium/cambium-jaguar-support/files/cambium-ab-jaguar.sh'
    module.parent.mkdir(parents=True);module.write_text(created('package/cambium/cambium-jaguar-support/files/cambium-ab-jaguar.sh'))
    recipe=module.parent.parent/'Makefile'
    recipe.write_text(created('package/cambium/cambium-jaguar-support/Makefile'))
    subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(REPO/'patches-25.12/0180-cambium-jaguar-gate-oem-first-boot-on-save.patch')],cwd=root,check=True,capture_output=True)
    assert 'PKG_RELEASE:=9\n' in recipe.read_text()
    total=0
    for model,fit,bank in [('xv2-2','config@cp01-c1','0x3400000'),('xv2-2t1','config@cp01-c1-2','0x6000000'),('xe3-4','config@cp01-c3-xv3-4','0x6000000')]:
        for target in (0,1):
            env=dict(os.environ,CORE=str(core),MODULE=str(module),MODEL=model,TARGET=str(target),CAMBIUM_AB_MODULES=str(root/'no-modules'))
            script=subprocess.check_output(['sh','-c','. "$CORE"; . "$MODULE"; ab_jaguar_board "cambiumnetworks,$MODEL" || exit 1; [ "$AB_QUALIFIED" = 1 ] || exit 1; ab_jaguar_guarded_command "$TARGET"'],env=env,text=True).strip()
            assert 'bootm 0x60000000#'+fit in script
            assert bank+'@'+('0x0' if target==0 else bank) in script
            for failure in ('bootcmd','changing_bootcmd','save','nand','read','bootm',''):
                trace=root/'trace';saved=root/'saved';trace.unlink(missing_ok=True);saved.unlink(missing_ok=True)
                harness=r'''
bootcmd=unattempted_trial; image=$PRIOR
setenv(){ key=$1;shift;echo "set:$key" >> "$TRACE";[ "$FAIL" != "$key" ] || return 1;
 [ "$key" != bootcmd ] || bootcmd="$*"; }
saveenv(){ echo save >> "$TRACE";[ "$FAIL" != save ] || return 1;printf '%s\n' "$bootcmd" "$image" > "$SAVED"; }
nand(){ echo nand >> "$TRACE";[ "$FAIL" != nand ]; }
ubi(){ echo "ubi:$1" >> "$TRACE";[ "$FAIL:$1" != read:read ]; }
bootm(){ echo candidate >> "$TRACE";[ "$FAIL" != bootm ] || return 1;exit 0; }
reset(){ echo reset >> "$TRACE";exit 0; }
'''
                runenv=dict(env,TRACE=str(trace),SAVED=str(saved),FAIL=failure,PRIOR=str(1-target))
                subprocess.run(['sh','-c',harness+'\n'+script],env=runenv,check=True)
                calls=trace.read_text().splitlines()
                if failure in ('bootcmd','changing_bootcmd','save'):
                    assert 'nand' not in calls and 'candidate' not in calls and not saved.exists(),calls
                else:
                    assert saved.read_text().splitlines()==['bootipq',str(1-target)]
                    assert calls.index('save')<calls.index('nand'),calls
                    if failure in ('nand','read'):assert 'candidate' not in calls,calls
                if failure:assert calls[-1]=='reset',calls
                total+=1
print(f'PASS: {total} exact-model/slot first-OEM-boot script cases')
print('Scope: actual renderer, mocked shell/load/durable ENV; not real U-Boot or watchdog proof')
