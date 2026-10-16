#!/usr/bin/env python3
"""Actual b6 shared guard after first-transition failure; disposable ENV only."""
from pathlib import Path
import subprocess,tempfile,os,json
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-b6-guard-') as td:
 r=Path(td);relative='package/cambium/cambium-ab/files/cambium-ab-guard';guard=r/relative
 for patch in sorted((repo/'patches-25.12').glob('*.patch')):
  if patch.name[:4].isdigit() and int(patch.name[:4])>168:continue
  lines=patch.read_text().splitlines(keepends=True);starts=[i for i,l in enumerate(lines) if l.startswith('--- ') and i+1<len(lines) and lines[i+1].startswith('+++ ')]
  for j,i in enumerate(starts):
   if lines[i+1].split()[1]!='b/'+relative:continue
   part=lines[i:starts[j+1] if j+1<len(starts) else len(lines)]
   for k,l in enumerate(part):
    if l.startswith(('diff --git ','-- \n')):part=part[:k];break
   p=r/'selected.patch';p.write_text(''.join(part));subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(p)],cwd=r,check=True,capture_output=True)
 (r/'empty').write_text('')
 script='''
. "$GUARD"
ab_family(){ AB_ENV=miami AB_LAYOUT=banks AB_STOCK_BOOTCMD=bootipq AB_ACTIVE=0; }
ab_identity(){ AB_ACTIVE=0; }
ab_running_slot(){ echo 0; }
ab_converted(){ [ "$VERSION" = 1 ]; }
ab_hook(){ return 1; }
ab_getenv(){ python3 -c 'import json,sys,os;print(json.load(open(os.environ["STATE"])).get(sys.argv[1],""))' "$1"; }
ab_setenv(){ echo FORBIDDEN_BOOT_WRITE;exit 90; }
ab_setenv_batch(){ python3 -c 'import json,sys,os;from pathlib import Path;p=Path(os.environ["STATE"]);e=json.loads(p.read_text());[(e.update({l.split(" ",1)[0]:l.split(" ",1)[1]}) if " " in l else e.pop(l,None)) for l in Path(sys.argv[1]).read_text().splitlines()];p.write_text(json.dumps(e))' "$1"; }
ab_guarded_command(){ echo old-oem-guard-route; }
wait_healthy(){ [ "$HEALTHY" = 1 ]; }
do_reboot(){ echo FORBIDDEN_REBOOT;exit 91; }
main
'''
 env={**os.environ,'GUARD':str(guard),'CAMBIUM_SYSTEM_FUNCTIONS':str(r/'empty'),'CAMBIUM_AB_LIB':str(r/'empty'),'CAMBIUM_INSTALLER_HEALTH_LIB':str(r/'absent'),'AB_GUARD_SOURCE_ONLY':'1','STATE':str(r/'state')}
 n=0
 for version,state,target in [('', 'bootstrap','1'),('', 'writing','1'),('', 'write-failed','1'),('1','writing','1'),('1','write-failed','1'),('1','trial-started','1'),('1','rolled-back','')]:
  for healthy in ('0','1'):
   before={'bootcmd':'run miami_boot0','image':'0','miami_boot0':'untouched exact b6 boot function','miami_ab_state':state,'miami_ab_target':target,'miami_ab_confirmed':'0'}
   (r/'state').write_text(json.dumps(before))
   p=subprocess.run(['sh','-c',script],env={**env,'VERSION':version,'HEALTHY':healthy},capture_output=True,text=True)
   assert p.returncode in (0,1) and 'FORBIDDEN' not in p.stdout+p.stderr,(version,state,healthy,p.stdout,p.stderr)
   after=json.loads((r/'state').read_text())
   assert all(after.get(k)==before[k] for k in ['bootcmd','image','miami_boot0'])
   if version=='1' and state=='trial-started':assert after['miami_ab_state']=='rolled-back' and 'miami_ab_target' not in after
   n+=1
 print(f'PASS: {n} actual b6 guard rollback/startup cases retain prior-only OpenWiFi; no OEM rearm, boot-function rewrite or reboot')
