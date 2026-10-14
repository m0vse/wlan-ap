from pathlib import Path
import os,re,subprocess,tempfile,json,shutil
repo=Path(__file__).resolve().parents[3]
module=repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'
confirm=repo/'contrib/cambium/miami/ab/confirm-oem-entry.sh'
checks=0
shells=json.loads(os.environ['MIAMI_TEST_SHELLS']) if 'MIAMI_TEST_SHELLS' in os.environ else [['/bin/sh']]
if 'MIAMI_TEST_SHELLS' not in os.environ and shutil.which('busybox'):
 shells.append([shutil.which('busybox'),'sh'])
for shell in shells:
 for profile in (0,1):
  for slot in (0,1):
   for safe in (False,True):
    suffix=f'setenv image {1-slot} && ' if profile else ''
    restore=('setenv bootcount 0 && ' if safe else '')+'setenv bootcmd bootipq && '+suffix+'setenv changing_bootcmd && saveenv'
    driver='''. "$MODULE"
ab_miami_boot_command(){ printf '%s' boot-command; }
ab_miami_ab_profile(){ [ "$PROFILE" = 1 ]; }
ab_getenv(){ case "$1" in miami_persistent_restore) printf '%s' "$RESTORE";;miami_persistent_load) printf '%s' 'boot-command';;miami_persistent_slot) printf '%s' "$SLOT";;esac; }
ab_miami_guarded_command "$SLOT"
'''
    p=subprocess.run(shell+['-c',driver],env=dict(os.environ,MODULE=str(module),PROFILE=str(profile),RESTORE=restore,SLOT=str(slot)),capture_output=True,text=True)
    assert (p.returncode==0)==safe,(profile,slot,safe,p.stdout,p.stderr)
    checks+=1
 with tempfile.TemporaryDirectory() as td:
  for source in (0,1):
   target=1-source
   lines=[x for x in confirm.read_text().splitlines() if x.startswith("printf '") and (' > "$work/confirm"' in x or ' > "$work/rollback"' in x)]
   assert len(lines)==2
   for line in lines:
    subprocess.run(shell+['-c',line],env=dict(os.environ,work=td,source=str(source),target=str(target)),check=True)
    name='confirm' if 'work/confirm' in line else 'rollback'
    values=dict(x.split(' ',1) if ' ' in x else (x,'') for x in (Path(td)/name).read_text().splitlines())
    assert values['bootcount']=='0' and values['image']==str(target if name=='confirm' else source)
    checks+=1
once_line=next(x for x in (repo/'contrib/cambium/miami/ab/enter-oem-once.sh').read_text().splitlines() if x.startswith('once='))
for shell in shells:
 for active in (0,1):
  for failure in ('','bootcount','bootcmd','image','miami_oem_once_state','save','OEM'):
   with tempfile.TemporaryDirectory() as td:
    work=Path(td);saved=work/'saved';calls=work/'calls';saved.write_text('bootcount=9\n');calls.write_text('')
    pre="""setenv(){ key=$1;shift;[ "$key" != "$FAIL" ] || return 1;export "$key=$*"; }
saveenv(){ echo save >> "$CALLS";[ "$FAIL" != save ] || return 1;printf 'bootcount=%s\\nimage=%s\\nbootcmd=%s\\n' "$bootcount" "$image" "$bootcmd" > "$SAVED"; }
bootipq(){ echo OEM >> "$CALLS";[ "$FAIL" != OEM ] || return 1;exit 0; }
run(){ echo BOOT >> "$CALLS";exit 0; }
"""
    result=subprocess.run(shell+['-c',pre+once_line+'\neval "$once"'],env=dict(os.environ,AB_ACTIVE=str(active),AB_TARGET=str(1-active),bootcount='9',FAIL=failure,CALLS=str(calls),SAVED=str(saved)),capture_output=True,text=True)
    actions=calls.read_text().splitlines()
    if failure and failure!='OEM':
     assert not any(x in ('OEM','BOOT','reset') for x in actions),(failure,actions)
     assert saved.read_text()=='bootcount=9\n'
    else:
     values=dict(x.split('=',1) for x in saved.read_text().splitlines() if '=' in x)
     assert values['bootcount']=='0' and values['image']==str(active)
     assert actions==(['save','OEM','BOOT'] if failure=='OEM' else ['save','OEM'])
    checks+=1
print(f'PASS: {checks} actual guard/batch/legacy-prefix cases; shells={shells!r}; durable9 setter/save failure never reaches OEM/BOOT/reset')
