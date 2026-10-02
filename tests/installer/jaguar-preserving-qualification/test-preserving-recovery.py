#!/usr/bin/env python3
"""Actual bridge recovery; authenticated private file-only transaction fixtures."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile
bundle=pathlib.Path(sys.argv[1]);report=json.loads(pathlib.Path(sys.argv[2]).read_text())
source_version=(bundle/'release-contract-policy').read_text().split()[2].encode()
normal=pathlib.Path(report['fixture'])/'normal-0'
receipt=next((normal/'root/root').glob('jaguar-upgrader-backup-*/transaction'))
work=pathlib.Path(tempfile.mkdtemp(prefix='preserving-recovery-tests.'));cases=[]
names=('valid-recovery','initializing-without-pid','live-owner','symlink-pid','unsafe-journal-mode','corrupt-original','unrelated-source-drift','unapproved-source-set','symlink-original','changed-original-mode','symlink-source-set','symlink-state','invalid-state','extra-upgrade-script','extra-function-script','unknown-fixed-target','fixed-target-mode-drift','staged-target-corrupt','runtime-refusal','lower-metadata-repair','malformed-metadata-repair')
prefix=(normal/'driver.sh').read_text().split('bridge_recover_pending\n',1)[0]
for name in names:
 run=work/name;run.mkdir();root=run/'root';subprocess.run(['cp','-a',str(normal/'root'),str(root)],check=True)
 journal=root/'root/jaguar-upgrader-transaction';subprocess.run(['cp','-a',str(receipt),str(journal)],check=True)
 if name=='initializing-without-pid':(journal/'PID').unlink();(journal/'READY').unlink()
 elif name=='live-owner':(journal/'PID').write_text(str(os.getpid())+'\n')
 elif name=='symlink-pid':(journal/'PID').unlink();(journal/'PID').symlink_to(root/'sbin/sysupgrade')
 elif name=='unsafe-journal-mode':journal.chmod(0o755)
 elif name=='corrupt-original':
  p=journal/'original/lib/functions/cambium-ab.sh';p.write_bytes(p.read_bytes()+b'unknown')
 elif name=='unrelated-source-drift':
  p=root/'sbin/sysupgrade';p.write_bytes(p.read_bytes()+b'unknown')
 elif name=='unapproved-source-set':(journal/'source.set').write_text('0'*64+' /sbin/sysupgrade\n')
 elif name=='symlink-original':
  p=journal/'original/lib/functions/cambium-ab.sh';p.unlink();p.symlink_to(root/'lib/functions/cambium-ab.sh')
 elif name=='changed-original-mode':(journal/'original/lib/functions/cambium-ab.sh').chmod(0o777)
 elif name=='symlink-source-set':(journal/'source.set').unlink();(journal/'source.set').symlink_to(next((bundle/'source-sets').glob('outgoing-*.set')))
 elif name=='symlink-state':(journal/'STATE').unlink();(journal/'STATE').symlink_to(root/'sbin/sysupgrade')
 elif name=='invalid-state':(journal/'STATE').write_text('unknown\n')
 elif name in ('extra-upgrade-script','extra-function-script'):
  (root/('lib/upgrade/unknown.sh' if name=='extra-upgrade-script' else 'lib/functions/unknown.sh')).write_text('echo NEVER_EXECUTED\n')
 elif name=='unknown-fixed-target':
  p=root/'lib/functions/cambium-ab.sh';p.write_bytes(p.read_bytes()+b'unknown')
 elif name=='fixed-target-mode-drift':(root/'lib/functions/cambium-ab.sh').chmod(0o755)
 elif name=='staged-target-corrupt':
  p=journal/'staged/lib/functions/cambium-ab.sh';p.write_bytes(p.read_bytes()+b'unknown')
 elif name=='lower-metadata-repair':
  p=root/'etc/openwrt_release';p.write_bytes(p.read_bytes().replace(source_version,b'2026.10.02.0'))
 elif name=='malformed-metadata-repair':
  p=root/'etc/openwrt_release';p.write_bytes(p.read_bytes()+b"PATH='/tmp/unreviewed'\n")
 paths=(normal/'bundle/source-sets/required-paths').read_text().splitlines()
 def snapshot():
  return {p:(hashlib.sha256((root/p.lstrip('/')).read_bytes()).hexdigest(),(root/p.lstrip('/')).stat().st_mode,(root/p.lstrip('/')).stat().st_uid,(root/p.lstrip('/')).stat().st_gid) for p in paths if (root/p.lstrip('/')).is_file()}
 before=snapshot();metadata=(root/'etc/openwrt_release').read_bytes()
 driver=run/'driver.sh';driver.write_text(prefix+'\nruntime_gate() { [ "$TEST_CASE" != runtime-refusal ]; }\nbridge_recover_pending\n')
 env=dict(os.environ,PATH='/usr/sbin:/usr/bin:/sbin:/bin',TEST_ROOT=str(root),TEST_BUNDLE=str(normal/'bundle'),TEST_SUITE=str(bundle),FAULT_KIND='',FAULT_N='0',TEST_CASE=name)
 p=subprocess.run(['sh',str(driver)],env=env,capture_output=True,text=True)
 accepted=name in ('valid-recovery','lower-metadata-repair','malformed-metadata-repair')
 assert (p.returncode==0)==accepted,(name,p.stdout,p.stderr)
 assert (root/'etc/openwrt_release').read_bytes()==metadata,(name,'metadata rewritten')
 if accepted:
  assert not journal.exists(),name
  original=receipt/'original'
  for logical in paths:
   a=root/logical.lstrip('/');b=original/logical.lstrip('/')
   if b.is_file():assert a.read_bytes()==b.read_bytes(),(name,logical)
   else:assert not a.exists(),(name,logical)
 else:assert snapshot()==before,(name,'refused recovery changed live source')
 cases.append({'case':name,'passed':True,'accepted':accepted,'metadata_unchanged':True,'refusal_live_source_unchanged':not accepted})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'helper_sha256':hashlib.sha256((bundle/'bridge-transaction.sh').read_bytes()).hexdigest(),
 'scope':'Actual recovery functions and source tuple checker with private file/ownership fixtures. Runtime gate is an injected refusal boundary; actual runtime implementation gate is covered separately. No AP library sourced, mount, bank, environment, flash or reboot.'},indent=2))
