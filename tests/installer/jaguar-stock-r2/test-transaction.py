#!/usr/bin/env python3
"""Disposable file-only fault injection; never runs device upgrade helpers."""
import hashlib,json,os,pathlib,shutil,stat,subprocess,tempfile
base=pathlib.Path(os.environ['OW_JAGUAR_TEST_BASE']);suite=base/'operator-r1';source=base/'outgoing-source/rootfs';payload=suite
helper_sha=hashlib.sha256((suite/'bridge-transaction.sh').read_bytes()).hexdigest()
work=pathlib.Path(tempfile.mkdtemp(prefix='jaguar-transaction-tests.',dir='/tmp'));cases=[]
items=[('cambium-ab.sh','/lib/functions/cambium-ab.sh'),('cambium-ab-upgrade.sh','/lib/upgrade/cambium-ab.sh'),('cambium-ab-certificates.sh','/lib/upgrade/cambium-ab-certificates.sh'),('modules/cambium-ab-jaguar.sh','/lib/functions/cambium-ab-jaguar.sh'),('platform.sh','/lib/upgrade/platform.sh')]
wrapper='''#!/usr/bin/python3
import os,pathlib,signal,sys
args=sys.argv[1:];tool=pathlib.Path(sys.argv[0]).name;kind=os.environ.get('FAULT_KIND','');root=pathlib.Path(os.environ['TEST_ROOT']);hit=False
if args:
 dest=args[-1]
 hit=(kind=='stage-copy' and tool=='cp' and '/staged/' in dest and not ('-p' in args)) or (kind=='install-copy' and tool=='cp' and dest.endswith('.jaguar-new')) or (kind=='install-chmod' and tool=='chmod' and dest.endswith('.jaguar-new')) or (kind in ('install-move','term','kill') and tool=='mv' and args[-2].endswith('.jaguar-new'))
if hit and not (root/'fault-consumed').exists():
 p=root/'fault-count';count=int(p.read_text())+1 if p.exists() else 1;p.write_text(str(count))
 if count==int(os.environ.get('FAULT_N','1')):
  (root/'fault-consumed').touch()
  if kind in ('term','kill'):
   import subprocess
   subprocess.run(['/bin/'+tool,*args],check=True)
   os.kill(os.getppid(),signal.SIGTERM if kind=='term' else signal.SIGKILL)
   sys.exit(0)
  sys.exit(71)
os.execv('/bin/'+tool,[tool,*args])
'''
checker=(payload/'source-set-check.sh').read_text().replace('ow_source_set_matches()', 'ow_actual_source_set_matches()')
for kind,n in [('normal',0)]+[(k,i) for k in ('stage-copy','install-copy','install-chmod','install-move','term','kill') for i in range(1,6)]+[('postcheck',1)]:
 run=work/(kind+'-'+str(n));root=run/'root';bundle=run/'bundle';bin=run/'bin';root.mkdir(parents=True);bundle.mkdir();bin.mkdir()
 required=(payload/'source-sets/required-paths').read_text().splitlines()+['/usr/libexec/validate_firmware_image']
 for path in required:
  src=source/path.lstrip('/');dest=root/path.lstrip('/')
  if src.is_file():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
 (root/'root').mkdir(exist_ok=True)
 for index,(_,path) in enumerate(items):
  p=root/path.lstrip('/')
  if p.exists():p.chmod((0o600,0o444,0o640,0o755,0o644)[index]);os.chown(p,1234+index,2345+index)
 original={path:(hashlib.sha256((root/path.lstrip('/')).read_bytes()).hexdigest(),stat.S_IMODE((root/path.lstrip('/')).stat().st_mode),(root/path.lstrip('/')).stat().st_uid,(root/path.lstrip('/')).stat().st_gid) if (root/path.lstrip('/')).exists() else None for _,path in items}
 for name,_ in items:
  p=bundle/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(payload/name,p)
 subprocess.run(['python3',str(suite/'make-source-sets.py'),str(root),str(bundle)],check=True,stdout=subprocess.DEVNULL)
 (bundle/'checker.sh').write_text(checker)
 for tool in ('cp','mv','chmod'):(bin/tool).write_text(wrapper);(bin/tool).chmod(0o755)
 (bin/'sync').write_text('#!/bin/sh\nexit 0\n');(bin/'sync').chmod(0o755)
 driver=run/'driver.sh';driver.write_text('''#!/bin/sh
set -eu
bundle=$TEST_BUNDLE
BRIDGE_ROOT=$TEST_ROOT
BRIDGE_JOURNAL=$BRIDGE_ROOT/root/jaguar-upgrader-transaction
. "$bundle/checker.sh"
ow_source_set_matches() {
 if [ "${FAULT_KIND:-}" = postcheck ] && [ "$3" = "$BRIDGE_ROOT" ] && [ -f "$BRIDGE_JOURNAL/READY" ] && [ ! -f "$BRIDGE_ROOT/fault-consumed" ]; then
  : > "$BRIDGE_ROOT/fault-consumed"
  return 1
 fi
 ow_actual_source_set_matches "$@"
}
source_gate() {
 for candidate in "$bundle"/source-sets/outgoing-*.set "$bundle/source-sets/installed-bridge.set"; do
  if ow_source_set_matches "$candidate" "$bundle/source-sets/required-paths" "$BRIDGE_ROOT"; then MATCHED_SOURCE_SET=$candidate; return 0; fi
 done
 return 1
}
. "$TEST_SUITE/bridge-transaction.sh"
bridge_recover_pending
source_gate
bridge_install
''')
 env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],TEST_ROOT=str(root),TEST_BUNDLE=str(bundle),TEST_SUITE=str(suite),FAULT_KIND=kind,FAULT_N=str(n))
 with (run/'first.log').open('w') as log:result=subprocess.run(['sh',str(driver)],env=env,stdout=log,stderr=log)
 if kind=='normal':assert result.returncode==0,(kind,(run/'first.log').read_text())
 else:
  assert result.returncode!=0,(kind,n,'failure did not trigger')
  if kind!='kill':
   for _,path in items:
    p=root/path.lstrip('/');saved=original[path]
    if saved is None:assert not p.exists(),(kind,n,path,'original absence not restored')
    else:assert (hashlib.sha256(p.read_bytes()).hexdigest(),stat.S_IMODE(p.stat().st_mode),p.stat().st_uid,p.stat().st_gid)==saved,(kind,n,path,'metadata/content not restored')
  env['FAULT_KIND']=''
  with (run/'retry.log').open('w') as log:retry=subprocess.run(['sh',str(driver)],env=env,stdout=log,stderr=log)
  assert retry.returncode==0,(kind,n,(run/'retry.log').read_text())
 check=' . "$1/checker.sh"; ow_actual_source_set_matches "$1/source-sets/installed-bridge.set" "$1/source-sets/required-paths" "$2"'
 assert subprocess.run(['sh','-c',check,'sh',str(bundle),str(root)]).returncode==0,(kind,n,'retry tuple invalid')
 assert not (root/'root/jaguar-upgrader-transaction').exists(),(kind,n,'journal not archived')
 cases.append({'case':kind,'target_index':n,'passed':True,'retry':kind!='normal','original_content_modes_uid_gid_restored':kind not in ('normal','kill'),'killed_process_recovered_before_retry':kind=='kill'})
assert hashlib.sha256((suite/'bridge-transaction.sh').read_bytes()).hexdigest()==helper_sha
print(json.dumps({'helper_sha256':helper_sha,'passed':True,'cases':cases,'count':len(cases),'fixture':str(work),'scope':'Real transaction functions and canonical complete tuple checker; file-only root fixtures; no AP scripts, flash, reboot or environment tools executed'},indent=2))
