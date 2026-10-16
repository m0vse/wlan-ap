#!/usr/bin/env python3
"""Reconstruct actual Miami shared package; test mixed first-pair boot routing.
No AP, flash or build server access. Geometry and crypto stay separate checks.
"""
from pathlib import Path
import subprocess, tempfile, os
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-ab-source-') as td:
 from prepare_source import prepare_package
 root=Path(td);package=prepare_package(repo,root);files=package/'files'
 # Public integration preserves newer shared bodies and advances above
 # retained Miami23, without importing the private qualified history.
 assert 'PKG_RELEASE:=24\n' in (package/'Makefile').read_text()

 for p in files.iterdir():
  if p.suffix not in ('.orig','.rej'):subprocess.run(['sh','-n',str(p)],check=True)
 core=(files/'cambium-ab.sh').read_text();upgrade=(files/'cambium-ab-upgrade.sh').read_text()
 assert 'saveenv && run ${AB_ENV}_boot$2; run ${AB_ENV}_boot$1' in core
 assert upgrade.index('ab_persist_prior_boot || return 1')<upgrade.index('ab_prepare_bank "$AB_KERNEL_SIZE"')
 assert '64) [ "$AB_FAMILY:$AB_MODEL" = miami:X7-35X ]' in upgrade
 # Actual boot renderer with binary DT policy, exact legacy/new source spellings.
 dt=root/'dt/cambium-platform';dt.mkdir(parents=True)
 env={**os.environ,'MODULE':str(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),'AB_DT':str(dt.parent)}
 script='''ab_running_slot(){ echo "$ACTIVE"; }
ab_getenv(){ printf '%s\\n' "$STORED"; }
. "$MODULE"
ab_miami_board cambiumnetworks,x7-35x || exit 1
ab_miami_boot_command "$SLOT"
'''
 def run(active,slot,stored='',image='',good=True):
  p=subprocess.run(['sh','-c',script],env={**env,'ACTIVE':str(active),'SLOT':str(slot),'STORED':stored,'AB_MIAMI_IMAGE_TARGET':image},capture_output=True,text=True)
  assert (p.returncode==0)==good,(active,slot,p.stdout,p.stderr)
  return p.stdout.strip()
 n=0
 for active in (0,1):
  (dt/'storage-slot').write_bytes(active.to_bytes(4,'big'))
  legacy={slot:run(active,slot) for slot in (0,1)};n+=2
  (dt/'storage-policy').write_bytes(b'ab\0');(dt/'upgrade-policy').write_bytes((1).to_bytes(4,'big'))
  current=run(active,active);assert '#config@mi01.6-acadia-ab-slot'+str(active) in current;n+=1
  assert run(active,1-active,legacy[1-active])==legacy[1-active];n+=1
  target=run(active,1-active,legacy[1-active],str(1-active));assert '-ab-slot'+str(1-active) in target;n+=1
  assert run(active,1-active,target)==target;n+=1
  run(active,1-active,'unqualified arbitrary command',good=False);n+=1
  (dt/'boot-mode').write_bytes(b'bridge\0');run(active,active,legacy[active],good=False);n+=1;(dt/'boot-mode').unlink()
  (dt/'upgrade-policy').write_bytes((2).to_bytes(4,'big'));run(active,active,good=False);n+=1
  (dt/'storage-policy').unlink();(dt/'upgrade-policy').unlink()
 print(f'PASS: actual public package all-hunk forward-only reconstruction/fuzz0; shared source-before-write and64LEB policy; {n} mixed/target/invalid/bridge boot-route cases')
