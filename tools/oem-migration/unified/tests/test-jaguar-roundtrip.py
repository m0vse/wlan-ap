#!/usr/bin/env python3
"""Carried media through real return, confirm and forward handlers.
Only boot/reset/explicit identity retirement are inert actors. No AP or
signature/hardware qualification is inferred from nonflashable fixtures.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tarfile
import unittest

HERE=Path(__file__).resolve().parent
def load(name):
 spec=importlib.util.spec_from_file_location(name,HERE/('test-jaguar-'+name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def authenticate(bundle):
 (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))

class RoundtripTests(unittest.TestCase):
 def carried(self,model,source):
  ret=load('restore').RestoreTests();fixture=ret.fixture(model,source);self.addCleanup(ret.doCleanups)
  case,_=fixture;root,bundle,work,bin,_,_=case
  certs={root/f'dev/ubi{u}_4':(root/f'dev/ubi{u}_4').read_bytes() for u in (0,1)}
  copies=root/'retained-key-copies';copies.mkdir()
  for u in (0,1):(copies/f'bank{u}.key').write_bytes(b'inert-old-private-key-copy')
  state=json.loads((root/'env.json').read_text());state['jaguar_ab_version']='1';(root/'env.json').write_text(json.dumps(state))
  result=ret.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
  # Confirm the very same media and ENV written by return, not a new fixture.
  conf=load('confirmation').ConfirmationTests();confirmed=conf.fixture(model,source,carried=fixture)
  result=conf.invoke(confirmed);self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(certs,{p:p.read_bytes() for p in certs})
  state=json.loads((root/'env.json').read_text());self.assertEqual(state['jaguar_ab_version'],'1');self.assertEqual(state['jaguar_oem_restore_state'],'confirmed')
  # Native factory reset actor changes config only, never certs or A/B ENV.
  config=root/'mnt/flash/config/config.txt';config.parent.mkdir(parents=True,exist_ok=True);config.write_text('factory-default-config\n')
  self.assertTrue((root/'dev/ubi0_4').exists());self.assertTrue((root/'dev/ubi1_4').exists())
  for u in (0,1):self.assertEqual((copies/f'bank{u}.key').read_bytes(),b'inert-old-private-key-copy')
  # Separate explicitly-consented retirement actor: both named cert stores.
  for u in (0,1):
   node=root/f'sys/class/ubi/ubi{u}_4';self.assertEqual((node/'name').read_text(),'certificates')
   free=root/f'sys/class/ubi/ubi{u}/avail_eraseblocks';free.write_text(str(int(free.read_text())+int((node/'reserved_ebs').read_text())))
   shutil.rmtree(node);(root/f'dev/ubi{u}_4').unlink()
  for u in (0,1):(copies/f'bank{u}.key').unlink()
  self.assertEqual(list(copies.iterdir()),[])
  # Cold native boot renumbers the running OEM bank to ubi0.
  for base in (root/'sys/class/ubi',root/'dev'):
   nodes=[p for p in base.iterdir() if p.name.startswith(('ubi0','ubi1'))]
   for p in nodes:p.rename(p.with_name('swap-'+p.name))
   for p in nodes:
    new='ubi1'+p.name[4:] if p.name.startswith('ubi0') else 'ubi0'+p.name[4:]
    p.with_name('swap-'+p.name).rename(p.with_name(new))
  target=1-source
  # Native coldboot exposes the new inactive bank as writable. Carrying the
  # former OpenWiFi running-bank read-only flag across boots is not a real
  # native kernel transition; the production writer must still enforce it.
  (root/f'sys/class/mtd/mtd{source}/flags').write_text('0xc00')
  (root/'proc/cmdline').write_text(f'ubi.mtd={"rootfs" if target==0 else "rootfs_1"} root=/dev/ubiblock0_1 rootfstype=squashfs\n')
  (root/'proc/mounts').write_text('/dev/ubiblock0_1 / squashfs ro 0 0\n')
  # Existing forward provider already contains both physical slot maps.
  profile=bundle/f'profiles/{model}'
  (profile/'source-sets/runtime-implementation.set').write_text('F '+sha(root/'etc/version')+' /etc/version\n')
  authenticate(bundle)
  backend=load('forward').BACKEND;compile(backend,'forward-backend','exec');(root/'backend.py').write_text(backend)
  for cmd in ('fw_printenv','fw_setenv','ubirmvol','ubimkvol','ubiupdatevol','ubiattach','mount','umount','ls','sync'):
   p=bin/cmd;p.write_text('#!/bin/sh\nexec python3 "$FIXTURE/backend.py" '+cmd+' "$@"\n');p.chmod(0o755)
  # Retain the confirmation phase's off-device-verified critical snapshot,
  # refreshing only the inert ENV representation, never private identity.
  critical=work/'critical';critical.mkdir(mode=0o700,exist_ok=True)
  for kind,i in (('ENV',2),('ART',3),('MFG',4)):shutil.copyfile(root/f'dev/mtd{i}ro',critical/(kind+'.bin'))
  shutil.copyfile(profile/'restore/critical-backup.tsv',critical/'manifest.tsv')
  (critical/'SHA256SUMS').write_text(''.join(sha(critical/name)+'  '+name+'\n' for name in ('ENV.bin','ART.bin','MFG.bin','manifest.tsv')))
  (critical/'OFFDEVICE_VERIFIED').write_text(sha(critical/'SHA256SUMS')+'\n')
  for p in critical.iterdir():p.chmod(0o600)
  (root/'events').unlink(missing_ok=True)
  return case
 def test_real_carried_return_confirm_retirement_forward_all_models_slots(self):
  for model in ('XV2-2','XV2-2T1','XE3-4'):
   for slot in (0,1):
    with self.subTest(model=model,slot=slot):
     case=self.carried(model,slot);root=case[0]
     before={p:p.read_bytes() for p in (root/'dev').iterdir() if not p.name.startswith('ubi1_') or p.name=='ubi1_3'}
     result=load('forward').ForwardTests().invoke(case);self.assertEqual(result.returncode,0,result.stderr+result.stdout+(root/'events').read_text() if (root/'events').exists() else result.stderr)
     self.assertEqual(before,{p:p.read_bytes() for p in before})
     events=(root/'events').read_text();self.assertLess(events.index('SOURCE '),events.index('ubirmvol '))
     self.assertNotIn('ubi1_3', '\n'.join(row for row in events.splitlines() if row.startswith('ubiupdatevol ')))
     state=json.loads((root/'env.json').read_text());self.assertNotIn('jaguar_oem_restore_state',state);self.assertNotIn('jaguar_oem_restore_target',state)
     self.assertEqual(state['jaguar_ab_state'],'armed');self.assertTrue((root/'sys/class/ubi/ubi1_4/name').exists())
 def test_remaining_identity_unknown_namespace_and_pending_return_refuse(self):
  for fault in ('source-cert','target-cert','unknown','wrong-art','pending'):
   case=self.carried('XV2-2',0);root=case[0]
   if fault in ('source-cert','target-cert','unknown'):
    u=0 if fault=='source-cert' else 1;i=5 if fault=='unknown' else 4
    node=root/f'sys/class/ubi/ubi{u}_{i}';node.mkdir();(node/'name').write_text('unknown' if fault=='unknown' else 'certificates');(root/f'dev/ubi{u}_{i}').write_bytes(b'retained identity')
   elif fault=='wrong-art':(root/'dev/mtd3ro').write_bytes(b'wrong own ART')
   else:
    state=json.loads((root/'env.json').read_text());state['jaguar_oem_restore_state']='trial-started';(root/'env.json').write_text(json.dumps(state))
   before={p:p.read_bytes() for p in (root/'dev').iterdir()}
   result=load('forward').ForwardTests().invoke(case);self.assertNotEqual(result.returncode,0,fault)
   self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertFalse((root/'events').exists())
 def test_self_consistent_changed_bdf_refuses_before_any_write(self):
  case=self.carried('XV2-2',0);root=case[0];vault=root/'dev/ubi1_3'
  unpacked=root/'changed-vault';unpacked.mkdir()
  with tarfile.open(vault,'r:') as archive:archive.extractall(unpacked)
  asset=unpacked/'files/lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock'
  old=sha(asset);asset.write_bytes(b'C'*len(asset.read_bytes()))
  manifest=unpacked/'MANIFEST';manifest.write_text(manifest.read_text().replace(old,sha(asset)))
  changed=root/'changed-vault.tar'
  with tarfile.open(changed,'w',format=tarfile.USTAR_FORMAT) as archive:
   archive.add(manifest,arcname='MANIFEST');archive.add(unpacked/'files',arcname='files')
  data=changed.read_bytes();vault.write_bytes(data+b'\xff'*(vault.stat().st_size-len(data)))
  # The old own-ART/model/SKU/manifest parser really accepts this archive.
  import os,subprocess
  _,bundle,work,bin,model,sku=case
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),HERE=str(HERE.parent),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_MODEL=model,OEM_SKU=sku)
  result=subprocess.run(['sh','-c','. "$HERE/lib/common.sh"; . "$HERE/adapters/restore-jaguar.sh"; RJ_ART_PIN=$(oem_sha "$OEM_SYS_ROOT/dev/mtd3ro"); oem_restore_jaguar_vault_capture "$OEM_SYS_ROOT/dev/ubi1_3" "$OEM_WORK/old-parser.tar" 8'],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  before={p:p.read_bytes() for p in (root/'dev').iterdir()};state=(root/'env.json').read_bytes()
  result=load('forward').ForwardTests().invoke(case);self.assertNotEqual(result.returncode,0)
  self.assertIn('radio assets differ',result.stderr+result.stdout)
  self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertEqual(state,(root/'env.json').read_bytes());self.assertFalse((root/'events').exists())
 def test_unattached_native_reuse_refuses_before_source_save(self):
  case=self.carried('XV2-2',0);root=case[0];detached=root/'detached';detached.mkdir()
  for p in list((root/'sys/class/ubi').glob('ubi1*')):p.rename(detached/('sys-'+p.name))
  for p in list((root/'dev').glob('ubi1*')):p.rename(detached/('dev-'+p.name))
  state=(root/'env.json').read_bytes();before={p:p.read_bytes() for p in [*(root/'dev').iterdir(),*detached.glob('dev-*')]}
  result=load('forward').ForwardTests().invoke(case);self.assertNotEqual(result.returncode,0)
  self.assertIn('pre-write asset validation',result.stderr+result.stdout)
  self.assertEqual(state,(root/'env.json').read_bytes());self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertFalse((root/'events').exists())

if __name__=='__main__':unittest.main()
