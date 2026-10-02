#!/usr/bin/env python3
import hashlib,json,os,pathlib,shutil,subprocess
base=pathlib.Path(os.environ['OW_SAGE_TEST_BASE'])/'operator-openwifi-r1';report=json.loads((base/'transaction-tests-final.log').read_text());run=pathlib.Path(report['fixture'])/'normal-0';root=run/'root';bundle=run/'bundle';journal=root/'root/sage-upgrader-transaction'
receipt=next((root/'root').glob('sage-upgrader-backup-*/transaction'))
paths=[p.lstrip('/') for p in (bundle/'source-sets/required-paths').read_text().splitlines()];before={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths if (root/p).is_file()};tests=[]
env=dict(os.environ,PATH=str(run/'bin')+':'+os.environ['PATH'],TEST_ROOT=str(root),TEST_BUNDLE=str(bundle),TEST_SUITE=str(base),FAULT_KIND='',FAULT_N='0')
for name in ('initializing-without-pid','live-owner','symlink-pid','unsafe-journal-mode','corrupt-original','unrelated-source-drift','unapproved-source-set','symlink-original','changed-original-mode','symlink-source-set','symlink-state','invalid-state','extra-upgrade-script','extra-function-script'):
 if journal.exists():shutil.rmtree(journal)
 shutil.copytree(receipt,journal,copy_function=shutil.copy2);journal.chmod(0o700)
 restore=None; extra=None
 if name in ('extra-upgrade-script','extra-function-script'):
  extra=root/('lib/upgrade/unknown.sh' if name=='extra-upgrade-script' else 'lib/functions/unknown.sh');extra.write_text('echo NEVER_EXECUTED\n')
 if name=='initializing-without-pid':(journal/'PID').unlink();(journal/'READY').unlink()
 elif name=='live-owner':(journal/'PID').write_text(str(os.getpid())+'\n')
 elif name=='symlink-pid':(journal/'PID').unlink();(journal/'PID').symlink_to(root/'sbin/sysupgrade')
 elif name=='unsafe-journal-mode':journal.chmod(0o755)
 elif name=='corrupt-original':
  p=journal/'original/lib/functions/cambium-ab.sh';p.write_bytes(p.read_bytes()+b'\nchanged\n')
 elif name=='unrelated-source-drift':
  p=root/'sbin/sysupgrade';restore=(p,p.read_bytes());p.write_bytes(p.read_bytes()+b'\nunknown-source\n')
 elif name=='unapproved-source-set':(journal/'source.set').write_text('0'*64+' /sbin/sysupgrade\n')
 elif name=='changed-original-mode':(journal/'original/lib/functions/cambium-ab.sh').chmod(0o777)
 elif name=='symlink-source-set':(journal/'source.set').unlink();(journal/'source.set').symlink_to(bundle/'source-sets/outgoing-openwifi-2026.10.02.1.set')
 elif name=='symlink-state':(journal/'STATE').unlink();(journal/'STATE').symlink_to(root/'sbin/sysupgrade')
 elif name=='invalid-state':(journal/'STATE').write_text('unknown\n')
 elif name=='symlink-original':
  p=journal/'original/lib/functions/cambium-ab.sh';p.unlink();p.symlink_to(root/'lib/functions/cambium-ab.sh')
 live_before={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths if (root/p).is_file()}
 result=subprocess.run(['sh',str(run/'driver.sh')],env=env,capture_output=True,text=True)
 assert result.returncode!=0,(name,result.stdout,result.stderr)
 live_after={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths if (root/p).is_file()}
 assert live_before==live_after,(name,'recovery wrote live source despite refusal')
 tests.append({'case':name,'passed':True,'live_source_unchanged':True})
 if restore:restore[0].write_bytes(restore[1])
 if extra:extra.unlink()
shutil.rmtree(journal)
print(json.dumps({'passed':True,'cases':tests,'count':len(tests),'fixture':str(run),'scope':'Malformed, unsafe or live-owner journals and unrelated source drift refused before writes; file-only fixture'},indent=2))
