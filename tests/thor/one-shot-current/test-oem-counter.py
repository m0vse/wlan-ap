#!/usr/bin/env python3
"""Exact Thor family scripts under isolated shell boundaries; no U-Boot/AP claim."""
from pathlib import Path
import argparse,json,subprocess,tempfile,os,hashlib
p=argparse.ArgumentParser();p.add_argument('--module',type=Path);p.add_argument('--runtime-root',type=Path);p.add_argument('--old-module',type=Path);p.add_argument('--guard',type=Path);a=p.parse_args();rows=[]
# Standalone default: replay exact package hunks in the current series into
# temporary files, never modify an SDK/source tree or forge package releases.
fixture=None
if not a.module:
 repo=Path(__file__).resolve().parents[3]
 fixture=tempfile.TemporaryDirectory(prefix='thor-current-counter-')
 tree=Path(fixture.name)
 relatives=['package/cambium/cambium-ab/files/cambium-ab-guard','package/cambium/cambium-ab/Makefile',
  'package/cambium/cambium-thor-support/files/cambium-ab-thor.sh','package/cambium/cambium-thor-support/Makefile']
 initial=(repo/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
 for relative in relatives[:2]:
  section=initial.split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
  dest=tree/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_text(''.join(line[1:]+'\n' for line in section.splitlines() if line.startswith('+')))
 for patch in sorted((repo/'patches-25.12').glob('*.patch')):
  if 124 < int(patch.name[:4]) < 189:
   subprocess.run(['git','apply',*['--include='+relative for relative in relatives],str(patch)],cwd=tree,check=True,capture_output=True)
 a.old_module=tree/'old-thor.sh';a.old_module.write_text((tree/relatives[2]).read_text())
 assert 'PKG_RELEASE:=13\n' in (tree/relatives[3]).read_text()
 assert 'PKG_RELEASE:=20\n' in (tree/relatives[1]).read_text()
 patch=repo/'patches-25.12/0189-cambium-thor-clear-oem-bank-flip-before-guarded-return.patch'
 subprocess.run(['git','apply','--check',str(patch)],cwd=tree,check=True)
 subprocess.run(['git','apply',str(patch)],cwd=tree,check=True)
 assert 'PKG_RELEASE:=14\n' in (tree/relatives[3]).read_text()
 a.module=tree/relatives[2];a.guard=tree/relatives[0]
command=['sh','-c'] if not a.runtime_root else ['/usr/bin/qemu-aarch64','-L',str(a.runtime_root),str(a.runtime_root/'bin/busybox'),'ash','-c']
def execute(script,env):
 r=subprocess.run(command+[script],env={**os.environ,**{k:str(v) for k,v in env.items()}},text=True,capture_output=True)
 return r
stub=r'''
AB_STOCK_BOOTCMD='aq_load_fw&&bootipq'; AB_FIT=config@hk02; AB_SLOT1_OFFSET=0x6000000
ab_bank_hex(){ echo 0x6000000; }
ab_converted(){ return 1; }
mock_bootcmd=$AB_STOCK_BOOTCMD; mock_image=$IMAGE; mock_count=$COUNT
ab_getenv(){ case "$1" in bootcmd) echo "$mock_bootcmd";; image) echo "$mock_image"; [ "$READ_FAIL" != image ];; bootcount) echo "$mock_count";; esac; }
'''
for slot in (0,1):
 r=execute('. "$MODULE"\n'+stub+'ab_thor_guarded_command "$SLOT"',{'MODULE':a.module,'SLOT':slot,'IMAGE':1-slot,'COUNT':9,'READ_FAIL':'image'})
 assert r.returncode!=0 and not r.stdout,('failed getter printed expected selector',slot,r.stdout,r.stderr)
 rows.append({'case':'failed-image-getter-with-expected-stdout-refused','slot':slot,'passed':True})
 for image in ('0','1','','2'):
  r=execute('. "$MODULE"\n'+stub+'ab_thor_guarded_command "$SLOT"',{'MODULE':a.module,'SLOT':slot,'IMAGE':image,'COUNT':9})
  allowed=image==str(1-slot)
  assert (r.returncode==0)==allowed,(slot,image,r.stderr)
  rows.append({'case':'selector-admission','slot':slot,'image':image,'passed':True})
 for count in (0,1,7,8,9):
  generated=execute('. "$MODULE"\n'+stub+'ab_thor_guarded_command "$SLOT"',{'MODULE':a.module,'SLOT':slot,'IMAGE':1-slot,'COUNT':count});assert generated.returncode==0
  for fail in ('','bootcount','image','bootcmd','changing_bootcmd','save'):
   with tempfile.TemporaryDirectory() as td:
    t=Path(td); trace=t/'trace';durable=t/'durable'
    harness=r'''
bootcmd='aq_load_fw&&bootipq'; image=$IMAGE; bootcount=$COUNT
setenv(){ key=$1; shift; echo set:$key >> "$TRACE"; [ "$FAIL" != "$key" ] || return 1; case "$key" in bootcmd) bootcmd=$*;; image) image=$*;; bootcount) bootcount=$*;; esac; }
saveenv(){ echo save >> "$TRACE"; [ "$FAIL" != save ] || return 1; printf '%s\n%s\n%s\n' "$bootcount" "$image" "$bootcmd" > "$DURABLE"; }
aq_load_fw(){ echo phy >> "$TRACE"; return 0; }
nand(){ echo candidate-read >> "$TRACE"; return 1; }
bootipq(){ [ "$bootcount" -le 7 ] || image=$((1-image)); echo oem:$image >> "$TRACE"; }
reset(){ echo unsafe-reset:$IMAGE:$COUNT >> "$TRACE"; }
'''
    r=execute(harness+'\n'+generated.stdout,{'TRACE':trace,'DURABLE':durable,'IMAGE':1-slot,'COUNT':count,'FAIL':fail})
    lines=trace.read_text().splitlines();loads=[x for x in lines if x.startswith(('phy','candidate-read','oem:','unsafe-reset:'))]
    if fail:assert not loads and not durable.exists(),(slot,count,fail,lines)
    else:assert durable.read_text().splitlines()==['0',str(1-slot),'aq_load_fw&&bootipq'] and lines[-1]=='oem:'+str(1-slot),(slot,count,lines)
    rows.append({'case':'rendered-trial-save-gate','slot':slot,'initial_counter':count,'failure':fail,'passed':True})
for slot in (0,1):
 for image,count,fail,corrupt,expected in [(str(1-slot),9,'','',True),(str(1-slot),8,'','',True),(str(1-slot),0,'','',True),(str(slot),9,'','',False),('',9,'','',False),(str(1-slot),9,'write','',False),(str(1-slot),9,'','counter',False),(str(1-slot),9,'','image',False),(str(1-slot),9,'','bootcmd',False)]:
  script='. "$MODULE"\n'+stub+r'''
ab_setenv(){ [ "$FAIL" != write ] || return 1; mock_count=$2; case "$CORRUPT" in counter) mock_count=9;; image) mock_image=$SLOT;; bootcmd) mock_bootcmd=unexpected;; esac; }
sync(){ :; }
ab_thor_prepare_oem_return "$SLOT"
'''
  r=execute(script,{'MODULE':a.module,'SLOT':slot,'IMAGE':image,'COUNT':count,'FAIL':fail,'CORRUPT':corrupt});assert (r.returncode==0)==expected,(slot,image,count,fail,corrupt,r.stderr)
  rows.append({'case':'linux-legacy-return-readback','slot':slot,'image':image,'counter':count,'failure':fail,'corrupt':corrupt,'passed':True})
if a.old_module:
 for slot in (0,1):
  generated=execute('. "$MODULE"\n'+stub+'ab_thor_guarded_command "$SLOT"',{'MODULE':a.old_module,'SLOT':slot,'IMAGE':1-slot,'COUNT':9}); assert generated.returncode==0
  with tempfile.TemporaryDirectory() as td:
   t=Path(td); trace=t/'trace'; durable=t/'durable'
   r=execute(harness+'\n'+generated.stdout,{'TRACE':trace,'DURABLE':durable,'IMAGE':1-slot,'COUNT':9,'FAIL':''})
   assert durable.read_text().splitlines()[0]=='9' and trace.read_text().splitlines()[-1]=='oem:'+str(slot)
   rows.append({'case':'old-prefix-counter9-selects-destroyed-bank-negative-control','slot':slot,'passed':True})

merged=[]
if a.guard:
 # Execute the actual shared 0187 legacy callback sites, not a hand-picked
 # equivalent. Converted renderer/ABI functions must remain byte-identical.
 import re
 legacy=re.search(r'(?ms)^legacy_guard\(\) \{.*?^\}',a.guard.read_text()).group()
 for slot in (0,1):
  for healthy in ('yes','no'):
   for fault in ('','write','sync','counter'):
    script='. "$MODULE"\n'+stub+r'''
ab_running_slot(){ echo "$SLOT"; }
ab_guarded_command(){ ab_thor_guarded_command "$@"; }
ab_hook(){ command -v "ab_${AB_FAMILY}_$1" >/dev/null; }
AB_FAMILY=thor AB_MARKER=1
wait_healthy(){ [ "$HEALTH" = yes ]; }
ab_setenv(){
 echo "WRITE:$1:$2"
 [ "$FAIL" != write ] || return 1
 case "$1" in bootcount) mock_count=$2; [ "$FAIL" != counter ] || mock_count=9;; bootcmd) mock_bootcmd=$2;; esac
}
sync(){ [ "$FAIL" != sync ]; }
log(){ :; }
do_reboot(){ echo REBOOT; }
'''+legacy+'\nlegacy_guard\n'
    with tempfile.TemporaryDirectory() as td:
     empty=Path(td)/'empty';empty.touch()
     r=execute(script,{'MODULE':a.module,'SLOT':slot,'IMAGE':1-slot,'COUNT':9,'HEALTH':healthy,'FAIL':fault,
      'CAMBIUM_SYSTEM_FUNCTIONS':empty,'CAMBIUM_AB_LIB':empty,'CAMBIUM_INSTALLER_HEALTH_LIB':Path(td)/'absent','AB_GUARD_SOURCE_ONLY':'1'})
    if fault: assert r.returncode!=0 and 'REBOOT' not in r.stdout and 'WRITE:changing_bootcmd' not in r.stdout,(r.stdout,r.stderr)
    else:
     assert r.returncode==0 and 'WRITE:bootcount:0' in r.stdout,(r.stdout,r.stderr)
     assert ('REBOOT' in r.stdout)==(healthy=='no'),r.stdout
     assert ('WRITE:changing_bootcmd:1' in r.stdout)==(healthy=='yes'),r.stdout
    merged.append({'slot':slot,'healthy':healthy,'failure':fault,'passed':True})
 if a.old_module:
  old=a.old_module.read_text();current=a.module.read_text()
  for function in ('ab_thor_boot_command','ab_thor_boot_preflight','ab_thor_boot_command_matches','ab_thor_prior_boot_valid'):
   pattern=r'(?ms)^'+function+r'\(\) \{.*?^\}'
   assert re.search(pattern,old).group()==re.search(pattern,current).group(),function

print(json.dumps({'passed':True,'count':len(rows),'cases':rows,'merged_guard_cases':len(merged),'merged_guard_results':merged,'candidate_module_sha256':hashlib.sha256(a.module.read_bytes()).hexdigest(),'scope':'Exact family module generator + isolated environment/save/load boundaries; threshold model backed by independently disassembled Thor bootloader; no firmware build, AP writes or hardware acceptance'},indent=2))
