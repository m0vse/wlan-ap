#!/usr/bin/env python3
"""Actual Cheetah command generators; simulated ENV/load, no bootloader calls."""
from pathlib import Path
import os, subprocess, tempfile, json, shlex
base=Path(__file__).resolve().parents[1]
shell=shlex.split(os.environ.get('OEM_TEST_SHELL','sh'));cases=[]
with tempfile.TemporaryDirectory(prefix='cheetah-rendered-boot.') as td:
 root=Path(td).resolve()
 for prior in (0,1):
  for marker in ('','0','1'):
   env={**os.environ,'ADAPTER':str(base/'adapters/cheetah.sh'),'OEM_FAMILY':'cheetah','OEM_MODEL':'XV2-21X','OEM_SKU':'00000023','OEM_SOURCE_SLOT':str(prior),'OEM_TARGET_SLOT':str(1-prior),'OEM_CHEETAH_PRIOR_MARKER':marker}
   render=root/'render';render.write_text('. "$ADAPTER"\noem_cheetah_candidate_command\noem_cheetah_trial_command\n')
   candidate,trial=subprocess.check_output(shell+[str(render)],env=env,text=True).splitlines()
   assert ('ubi.mtd=rootfs'+('_1' if 1-prior else '')+' ') in candidate
   for fault in ('','bootcmd','image','changing_bootcmd','save','power-after-save','nand','mtdids','mtdparts','ubi-part','ubi-read','bootargs','bootm','hang'):
    trace=root/'trace';saved=root/'saved';trace.unlink(missing_ok=True);saved.unlink(missing_ok=True)
    env.update(TRACE=str(trace),SAVED=str(saved),FAULT=fault,CANDIDATE=candidate,PRIOR=str(prior),MARKER=marker)
    harness=root/'driver';harness.write_text(r'''
bootcmd=unattempted-trial;image=$PRIOR;changing_bootcmd=$MARKER
setenv(){
 key=$1;shift;printf 'set:%s\n' "$key" >> "$TRACE"
 [ "$FAULT" != "$key" ] || return 1
 case "$key" in bootcmd) bootcmd="$*";;image) image="$*";;changing_bootcmd) changing_bootcmd="$*";;esac
}
saveenv(){
 printf 'save\n' >> "$TRACE";[ "$FAULT" != save ] || return 1
 printf '%s\n%s\n%s\n' "$bootcmd" "$image" "$changing_bootcmd" > "$SAVED"
 [ "$FAULT" != power-after-save ] || exit 78
}
run(){ printf 'run:%s\n' "$1" >> "$TRACE";[ "$1" = "cheetah_boot$OEM_TARGET_SLOT" ] || return 1;eval "$CANDIDATE"; }
nand(){ printf 'nand\n' >> "$TRACE";[ "$FAULT" != nand ]; }
ubi(){ printf 'ubi:%s\n' "$1" >> "$TRACE";[ "$FAULT" != "ubi-$1" ]; }
bootm(){
 printf 'candidate\n' >> "$TRACE"
 case "$FAULT" in bootm) return 1;;hang) exit 77;;*) exit 0;;esac
}
bootipq(){ printf 'prior\n' >> "$TRACE"; }
'''+'\n'+trial+'\n')
    result=subprocess.run(shell+[str(harness)],env=env,capture_output=True,text=True)
    calls=trace.read_text().splitlines()
    assert result.returncode==({'hang':77,'power-after-save':78}.get(fault,0)),(fault,result.stderr)
    if fault in ('bootcmd','image','changing_bootcmd','save'):
     assert not saved.exists() and 'nand' not in calls and not any(x.startswith('run:') for x in calls),calls
    else:
     assert saved.read_text().splitlines()==['bootipq',str(prior),marker],calls
     if fault!='power-after-save':assert calls.index('save')<calls.index('nand'),calls
    if fault in ('nand','mtdids','mtdparts','ubi-part','ubi-read','bootargs','power-after-save'):assert 'candidate' not in calls,calls
    assert ('prior' in calls)==(fault not in ('','hang','power-after-save')),calls
    cases.append({'prior':prior,'prior_marker':marker,'fault':fault or 'success','passed':True})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'scope':'Actual source-generated candidate/trial commands under selected shell; simulated ENV persistence, reset and load. Saved fallback is original OEM bootipq/image/marker. No real U-Boot, AP, watchdog or full migration acceptance.'},indent=2))
