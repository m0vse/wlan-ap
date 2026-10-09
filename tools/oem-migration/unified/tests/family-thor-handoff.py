#!/usr/bin/env python3
"""Replay shipped .8 guard/health with staged hook; native acceptance/device actors."""
from pathlib import Path
import os, subprocess, tempfile, json, hashlib

base=Path(__file__).resolve().parents[1]
fixture=base/'tests/fixtures/thor-2026.10.05.8'
with tempfile.TemporaryDirectory(prefix='thor-handoff-') as td:
 root=Path(td);(root/'system').write_text('')
 actor=root/'fw';actor.write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
p=Path(os.environ['ENVFILE']);d=json.loads(p.read_text());a=sys.argv[1:]
if '-n' in a:
 k=a[a.index('-n')+1]
 if k not in d:sys.exit(1)
 print(d[k]);sys.exit(0)
if '-s' in a:
 for line in Path(a[a.index('-s')+1]).read_text().splitlines():
  k,_,v=line.partition(' ')
  if v:d[k]=v
  else:d.pop(k,None)
else:
 k=a[2]
 if len(a)>3:d[k]=a[3]
 else:d.pop(k,None)
p.write_text(json.dumps(d))
''');actor.chmod(0o700)
 for n in ('fw_printenv','fw_setenv'):(root/n).symlink_to('fw')
 accept=root/'accept';accept.write_text('#!/bin/sh\n[ "$ACCEPT" = 1 ]\n');accept.chmod(0o700)
 seed=root/'seed';seed.mkdir();(seed/'binding.tsv').write_text('job_id\t'+'1'*64+'\nimage_sha256\t'+'2'*64+'\ntarget_slot\t0\n')
 env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH'],ENVFILE=str(root/'env.json'),CAMBIUM_SYSTEM_FUNCTIONS=str(root/'system'),CAMBIUM_AB_LIB=str(fixture/'lib/functions/cambium-ab.sh'),CAMBIUM_AB_MODULES=str(fixture/'lib/functions'),CAMBIUM_INSTALLER_HEALTH_LIB=str(fixture/'lib/functions/cambium-installer-health.sh'),AB_GUARD_SOURCE_ONLY='1',AB_INSTALLER_INCOMING_SEED=str(seed),AB_INSTALLER_ACCEPT=str(accept),HOOK=str(base/'adapters/thor-handoff.sh'),GUARD=str(fixture/'usr/sbin/cambium-ab-guard'),AB_ENV_CONFIG=str(root/'dummy'),REBOOT=str(root/'reboot'))
 script=r'''
. "$GUARD"; . "$HOOK"
ab_identity(){ AB_ACTIVE=0; AB_FAMILY=thor; AB_MODEL=XV3-8; AB_ENV=thor; }
wait_healthy(){ installer_healthy && [ "$HEALTH" = 1 ]; }
do_reboot(){ printf reboot > "$REBOOT"; }
ab_thor_takeover
'''
 cases=[]
 for name,acceptance,healthy,change,ok in [('healthy',1,1,{},True),('native-not-accepted',0,1,{},True),('network-unhealthy',1,0,{},True),('wrong-job',1,1,{'thor_installer_job':'3'*64},True),('already-converted',1,1,{'thor_ab_version':'1'},False),('wrong-target',1,1,{'thor_ab_target':'1'},False)]:
  d={'image':'1','bootcmd':'run thor_boot1','thor_migration_oem_slot':'1','thor_ab_state':'trial-started','thor_ab_confirmed':'1','thor_ab_target':'0','thor_installer_target':'0','thor_installer_job':'1'*64,'thor_installer_image':'2'*64,**change}
  (root/'env.json').write_text(json.dumps(d));(root/'reboot').unlink(missing_ok=True)
  r=subprocess.run(['sh','-c',script],env={**env,'ACCEPT':str(acceptance),'HEALTH':str(healthy)},capture_output=True,text=True)
  assert (r.returncode==0)==ok,(name,r.stderr)
  if name=='already-converted':assert r.returncode==2
  after=json.loads((root/'env.json').read_text())
  if name=='healthy':
   assert after['bootcmd']=='run thor_stable0' and after['thor_ab_confirmed']=='0'
   assert not any(k.startswith('thor_installer_') for k in after)
   assert 'thor_ab_version' not in after and not (root/'reboot').exists()
  else:
   assert after['bootcmd']=='run thor_boot1' and after['thor_ab_confirmed']=='1'
  cases.append(name)
 print(f'PASS: {len(cases)} actual .8 guard/health handoff cases; only native-accepted healthy candidate commits; no false converted flag')
 print('Scope: unchanged shipped guard/health, staged takeover hook. Device/network health and identity accepted/cleanup subprocess are actors; no EST, physical boot or AP operation.')
