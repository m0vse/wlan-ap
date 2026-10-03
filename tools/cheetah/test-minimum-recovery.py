#!/usr/bin/env python3
import hashlib,json,os,pathlib,shutil,subprocess,tempfile
base=pathlib.Path('/home/phil/openwifi-cheetah-build');work=pathlib.Path(tempfile.mkdtemp(prefix='cheetah-minimum-recovery.'));cases=[]
for route in ['stock','preserve']:
 suite=base/f'operator-{route}-minimum-r6';report=json.loads((suite/'transaction-tests-final.log').read_text());run=pathlib.Path(report['fixture'])/'normal-0';template=run/'root';bundle=run/'bundle';receipt=next((template/'root').glob('cheetah-upgrader-backup-*/transaction'));required=(bundle/'source-sets/required-paths').read_text().splitlines()
 for case,good in [('below-minimum',True),('malformed',True),('compatible-metadata-change',True),('unknown-live-target',False),('unknown-live-target-mode',False),('unknown-staged-target',False),('unknown-extra-script',False),('unrelated-code-drift',False),('runtime-gate-refused',False)]:
  root=work/(route+'-'+case);root.mkdir()
  for path in required+['/etc/openwrt_release','/etc/cambium-openwrt-release']:
   src=template/path.lstrip('/');dest=root/path.lstrip('/')
   if src.is_file():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);os.chown(dest,src.stat().st_uid,src.stat().st_gid)
  journal=root/'root/cheetah-upgrader-transaction';shutil.copytree(receipt,journal);journal.chmod(0o700)
  for path in required:
   for directory in ['original','staged']:
    p=journal/directory/path.lstrip('/');src=receipt/directory/path.lstrip('/')
    if p.exists():os.chown(p,src.stat().st_uid,src.stat().st_gid)
  meta=root/('etc/cambium-openwrt-release' if route=='stock' else 'etc/openwrt_release');old='2026.09.29.0' if route=='stock' else '2026.10.02.11'
  if case in ['below-minimum','compatible-metadata-change']:meta.write_text(meta.read_text().replace(old,'2026.09.28.0' if case=='below-minimum' else '2026.10.03.100'))
  if case=='malformed':meta.write_text(meta.read_text()+'FORCE=1\n')
  if case=='unknown-live-target':
   p=root/'lib/upgrade/platform.sh';p.write_bytes(p.read_bytes()+b'unknown')
  if case=='unknown-live-target-mode':(root/'lib/upgrade/platform.sh').chmod(0o777)
  if case=='unknown-staged-target':
   p=journal/'staged/lib/upgrade/platform.sh';p.write_bytes(p.read_bytes()+b'unknown')
  if case=='unknown-extra-script':(root/'lib/upgrade/unknown.sh').write_text('exit 99\n')
  if case=='unrelated-code-drift':
   p=root/'sbin/sysupgrade';p.write_bytes(p.read_bytes()+b'unknown')
  before={str(p.relative_to(root)): (p.read_bytes(),p.stat().st_mode,p.stat().st_uid,p.stat().st_gid) for path in required for p in [root/path.lstrip('/')] if p.is_file()};meta_before=meta.read_bytes()
  driver='''set -eu
bundle=$TEST_BUNDLE
BRIDGE_ROOT=$TEST_ROOT
BRIDGE_JOURNAL=$BRIDGE_ROOT/root/cheetah-upgrader-transaction
. "$bundle/checker.sh"
ow_source_set_matches() { ow_actual_source_set_matches "$@"; }
runtime_gate() { [ "$TEST_RUNTIME_REFUSE" = 0 ]; }
implementation_gate() { return 1; }
. "$TEST_SUITE/bridge-transaction.sh"
bridge_recover_pending
'''
  env=dict(os.environ,TEST_BUNDLE=str(bundle),TEST_ROOT=str(root),TEST_SUITE=str(suite),TEST_RUNTIME_REFUSE='1' if case=='runtime-gate-refused' else '0')
  result=subprocess.run(['sh','-c',driver],env=env,capture_output=True,text=True)
  assert (result.returncode==0)==good,(route,case,result.stderr,result.stdout)
  assert meta.read_bytes()==meta_before,(route,case,'metadata restored or changed')
  if good:
   assert not journal.exists()
   for path in required:
    p=root/path.lstrip('/');src=receipt/'original'/path.lstrip('/')
    assert p.exists()==src.exists()
    if p.exists():assert p.read_bytes()==src.read_bytes() and (p.stat().st_mode,p.stat().st_uid,p.stat().st_gid)==(src.stat().st_mode,src.stat().st_uid,src.stat().st_gid),(case,path)
   release=subprocess.run(['sh','-c','. "$1"; ow_release_contract_check "$2" "$3"','fixture',str(suite/'minimum-release-contract.sh'),str(suite/'release-policy'),str(root)],capture_output=True)
   assert (release.returncode==0)==(case=='compatible-metadata-change')
  else:
   after={str(p.relative_to(root)): (p.read_bytes(),p.stat().st_mode,p.stat().st_uid,p.stat().st_gid) for path in required for p in [root/path.lstrip('/')] if p.is_file()};assert before==after,(route,case,'refused recovery changed live code')
  cases.append(dict(route=route,case=case,rollback_completed=good,metadata_untouched=True,passed=True))
print(json.dumps(dict(passed=True,count=len(cases),cases=cases,fixture=str(work),scope='Real fixed-target authenticated rollback with journal states; below/malformed metadata permits repair then blocks upgrade. Runtime preflight refusal injected; runtime matcher tested separately on full tool closure. File-only fixtures, no AP actions/flash.'),indent=2))
