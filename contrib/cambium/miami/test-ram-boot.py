#!/usr/bin/env python3
"""Exercise actual one-shot helper with filesystem/env hardware boundaries mocked."""
from pathlib import Path
import os, json, subprocess, tempfile
repo=Path(__file__).resolve().parents[3]
source=(repo/'contrib/cambium/miami/miami-ram-boot.sh').read_text()
with tempfile.TemporaryDirectory(prefix='miami-oneshot-') as td:
 w=Path(td);(w/'bin').mkdir();(w/'dev').mkdir()
 (w/'sku').write_bytes(bytes.fromhex('0000002c'))
 (w/'mtd').write_text('mtd0: 00010000 00010000 "0:APPSBLENV"\nmtd1: 000a0000 00010000 "0:APPSBL"\n')
 (w/'dev/mtd0ro').write_bytes(b'e'*65536)
 (w/'dev/mtd1ro').write_bytes(b'tftpboot\0bootm\0saveenv\0')
 helper=w/'helper';helper.write_text(source.replace('/proc/mtd',str(w/'mtd')).replace('/dev/mtd',str(w/'dev/mtd')))
 for cmd in ['fw_printenv','fw_setenv']:
  p=w/'bin'/cmd
  p.write_text('''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
p=Path(os.environ['ENV_FILE']); e=json.loads(p.read_text()); a=sys.argv[1:]
if Path(sys.argv[0]).name=='fw_printenv':
 key=a[-1]
 if os.environ.get('READ_FAIL_KEY')==key:print(e.get(key,'0'));sys.exit(1)
 if key not in e:sys.exit(1)
 print(e[key]);sys.exit(0)
key=a[0]
if os.environ.get('FAIL_KEY')==key:sys.exit(1)
if len(a)==1:e.pop(key,None)
else:e[key]=a[1]
p.write_text(json.dumps(e))
''');p.chmod(0o755)
 env=dict(os.environ,PATH=str(w/'bin')+':'+os.environ['PATH'],ENV_FILE=str(w/'env'),MIAMI_RAM_SKU_NODE=str(w/'sku'),MIAMI_RAM_BOOT_WORK=str(w/'work'))
 def call(args,expected=0,extra={}):
  command=['sh','-c','helper=$1;shift;if . "$helper";then exit 0;else exit 1;fi','fixture',str(helper),*args] if extra.get('CONDITIONAL_IMPORT') else ['sh',str(helper),*args]
  r=subprocess.run(command,env=dict(env,**extra),capture_output=True,text=True)
  assert (r.returncode==0)==(expected==0),(r.returncode,r.stdout,r.stderr)
 def initial(old,changing=None):
  e={'bootcmd':old,'bootcount':'9','image':'1','ipaddr':'198.18.0.7','serverip':'198.18.0.8'}
  if changing is not None:e['changing_bootcmd']=changing
  (w/'env').write_text(json.dumps(e))
  if (w/'work').exists():import shutil;shutil.rmtree(w/'work')
  return e
 def simulate(fail_download,fail_set="",fail_save=0):
  e=json.loads((w/'env').read_text())
  # Real shell evaluation of generated U-Boot bodies; only commands mocked.
  pre='''#!/bin/sh
setenv(){ key=$1;shift;[ "$key" != "$FAIL_SET" ] || return 1;if [ "$#" = 0 ];then unset "$key";else export "$key=$*";fi; }
saveenv(){ echo save >> "$CALLS";[ "$FAIL_SAVE" = 0 ] || return 1;printf '%s\\n' "$bootcmd" > "$PERSIST";env > "$SAVED_ENV"; }
run(){ for key in "$@";do eval 'script=${'"$key"'}'; eval "$script" || return;done; }
tftpboot(){ echo tftp >> "$CALLS";return "$TFTP_FAIL"; }
bootm(){ echo bootm >> "$CALLS";exit 0; }
reset(){ echo reset >> "$CALLS";exit 0; }
if run miami_ram_restore; then run miami_ram_load; reset; fi
'''
  boot=w/'boot';boot.write_text(pre.replace('if run miami_ram_restore; then run miami_ram_load; reset; fi',e['bootcmd']))
  (w/'calls').write_text('');(w/'saved').write_text('bootcount=9\n')
  subprocess.run(['sh',str(boot)],env=dict({**env,**e},bootcount='9',FAIL_SET=fail_set,FAIL_SAVE=str(fail_save),PERSIST=str(w/'persist'),SAVED_ENV=str(w/'saved'),CALLS=str(w/'calls'),TFTP_FAIL=str(int(fail_download))),check=True)
  calls=(w/'calls').read_text().splitlines();(w/'calls').unlink()
  if fail_set or fail_save:
   assert not any(v in ('tftp','bootm','reset','OEM') for v in calls),calls
   assert (w/'saved').read_text()=='bootcount=9\n'
   return {'bootcount':'9'}
  assert calls[:2]==['save','tftp'],calls
  assert calls[-1]==('reset' if fail_download else 'bootm'),calls
  saved=dict(line.split('=',1) for line in (w/'saved').read_text().splitlines() if '=' in line)
  assert saved['ipaddr']=='198.18.0.7' and saved['serverip']=='198.18.0.8'
  return saved
 count=0
 for old,changing in [('bootipq',None),('run miami_start && run miami_load; run miami_fallback','1')]:
  for fail in [False,True]:
   original=initial(old,changing)
   call(['prepare','198.18.0.1','198.18.0.2','miami-auto.itb','a'*64])
   assert json.loads((w/'env').read_text())==original
   assert (w/'work/APPSBLENV.bin').stat().st_size==65536
   call(['arm','--yes','--backed-up'])
   saved=simulate(fail)
   assert saved['bootcount']=='0' and saved['bootcmd']==old
   assert saved.get('changing_bootcmd')==changing
   # Returning to the saved system permits removal of test helper keys.
   e=json.loads((w/'env').read_text());e['bootcmd']=old
   if changing is None:e.pop('changing_bootcmd',None)
   else:e['changing_bootcmd']=changing
   (w/'env').write_text(json.dumps(e));call(['cleanup','--yes'])
   assert json.loads((w/'env').read_text())==dict(original,bootcount='0')
   count+=1
 original=initial('bootipq')
 call(['prepare','198.18.0.1','198.18.0.2','miami-auto.itb','a'*64]);call(['arm','--yes','--backed-up'])
 for fail_set,fail_save in [('bootcount',0),('bootcmd',0),('changing_bootcmd',0),('',1)]:simulate(False,fail_set,fail_save)
 original=initial('bootipq')
 call(['prepare','198.18.0.1','198.18.0.2','miami-auto.itb','a'*64]);call(['arm','--yes'],1)
 assert json.loads((w/'env').read_text())==original
 state=json.loads((w/'env').read_text());state['bootcount']='0';(w/'env').write_text(json.dumps(state))
 call(['arm','--yes','--backed-up'],1,{'FAIL_KEY':'bootcount','CONDITIONAL_IMPORT':'1'})
 assert json.loads((w/'env').read_text())['bootcmd']=='bootipq'
 call(['arm','--yes','--backed-up'],1,{'READ_FAIL_KEY':'bootcount','CONDITIONAL_IMPORT':'1'})
 assert json.loads((w/'env').read_text())['bootcmd']=='bootipq'
 original=initial('bootipq');call(['prepare','198.18.0.1','198.18.0.2','miami-auto.itb','a'*64])
 call(['arm','--yes','--backed-up'],1,{'FAIL_KEY':'bootcount'})
 assert json.loads((w/'env').read_text())==original
 call(['arm','--yes','--backed-up'],1,{'FAIL_KEY':'bootcmd'})
 e=json.loads((w/'env').read_text());assert e['bootcmd']=='bootipq' and 'changing_bootcmd' not in e
 initial('bootipq');(w/'dev/mtd1ro').write_bytes(b'bootm\0')
 call(['prepare','198.18.0.1','198.18.0.2','miami-auto.itb','a'*64],1)
 assert json.loads((w/'env').read_text())['bootcmd']=='bootipq'
print('PASS: OEM/OpenWrt previous commands, restore-before-TFTP, success/failure fallback, cleanup, arming refusal/rollback and unavailable TFTP')
