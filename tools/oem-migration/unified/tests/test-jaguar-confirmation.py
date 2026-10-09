#!/usr/bin/env python3
"""Actual confirm handler on inert post-trial OEM media and atomic ENV backend.
Fixture version/kernel/root/boot strings never qualify actual hardware/CMS.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import unittest

HERE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
BACKEND=r'''
import json,os,sys
from pathlib import Path
r=Path(os.environ['FIXTURE']);p=r/'env.json';s=json.loads(p.read_text());cmd,a=sys.argv[1],sys.argv[2:];fault=os.environ.get('FAULT','')
if cmd=='fw_printenv':print(''.join(k+'='+v+'\n' for k,v in s.items()),end='');sys.exit(0)
if cmd=='sync':sys.exit(0)
assert cmd=='fw_setenv' and a[2]=='-s'
file=Path(a[3]);label='CONFIRM' if file.name=='confirm.env' else 'ROLLBACK'
with (r/'confirm-events').open('a') as out:out.write(label+'\n')
if fault==label or (fault=='rollback-failure' and label=='ROLLBACK'):sys.exit(1)
for row in file.read_text().splitlines():
 fields=row.split(' ',1)
 if len(fields)==1:s.pop(fields[0],None)
 else:s[fields[0]]=fields[1]
if fault in ('readback','rollback-failure') and label=='CONFIRM':s['bootcmd']='wrong'
p.write_text(json.dumps(s))
'''
class ConfirmationTests(unittest.TestCase):
 def fixture(self,model='XV2-2T1',source=0):
  compile(BACKEND,'inert-confirm-backend','exec')
  spec=importlib.util.spec_from_file_location('return_fixture',HERE/'tests/test-jaguar-restore.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  holder=module.RestoreTests();fixture=holder.fixture(model,source);self.addCleanup(holder.doCleanups)
  case,_=fixture;root,bundle,work,bin,model,sku=case;target=1-source
  (root/'etc/openwrt_release').unlink();(root/'etc/version').write_text('PRODUCT=jaguar\nVERSION=7.2-r1\nCHANGESET=nonflashable-fixture\n')
  (root/'proc/cmdline').write_text(f'ubi.mtd={"rootfs" if target==0 else "rootfs_1"} root=ubi1:ubi_rootfs rootfstype=squashfs\n')
  (root/'proc/mounts').write_text('/dev/ubiblock1_1 / squashfs ro 0 0\n')
  state=json.loads((root/'env.json').read_text());state.update(bootcmd=f'run jaguar_boot{source}',jaguar_oem_restore_state='trial-started',jaguar_oem_restore_target=str(target),jaguar_ab_target=str(target),jaguar_ab_state='armed')
  state[f'jaguar_stable{source}']=f'run jaguar_boot{source}';state[f'jaguar_oem_boot{target}']=f'setenv image {target}; bootipq'
  (root/'env.json').write_text(json.dumps(state))
  for i,name,blocks,file in ((0,'kernel',32,'kernel.itb'),(1,'ubi_rootfs',337,'rootfs.squashfs')):
   node=root/f'sys/class/ubi/ubi1_{i}';(node/'name').write_text(name);(node/'reserved_ebs').write_text(str(blocks));shutil.copyfile(bundle/f'payloads/{model}/oem/{file}',root/f'dev/ubi1_{i}')
  shutil.rmtree(root/'sys/class/ubi/ubi1_2');(root/'dev/ubi1_2').unlink()
  profile=bundle/f'profiles/{model}/restore';confirm=profile/'confirm';(confirm/'source-sets').mkdir(parents=True)
  (confirm/'source-contract').write_text('7.2-r1\n'+'a'*64+'\n')
  (confirm/'source-sets/runtime-implementation.set').write_text('F '+sha(root/'etc/version')+' /etc/version\n')
  for slot in (0,1):shutil.copyfile(profile/f'mtd-slot{slot}.tsv',confirm/f'mtd-slot{slot}.tsv')
  (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
  shutil.rmtree(work/'critical')
  (root/'confirm-backend.py').write_text(BACKEND)
  for cmd in ('fw_printenv','fw_setenv','sync'):
   p=bin/cmd;p.write_text('#!/bin/sh\nexec python3 "$FIXTURE/confirm-backend.py" '+cmd+' "$@"\n');p.chmod(0o755)
  return case,state
 def invoke(self,fixture,fault=''):
  case,_=fixture;root,bundle,work,bin,model,sku=case
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),HERE=str(HERE),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SUPPORTED_RELEASE='7.2-r1',FAULT=fault)
  script=r'''
. "$HERE/lib/common.sh";. "$HERE/lib/protection.sh";. "$HERE/lib/critical-backup.sh";. "$HERE/adapters/restore-jaguar.sh"
oem_backup_capture() {
 [ "$FAULT" != backup ] || return 1
 mkdir -m 700 "$4" || return 1
 cp "$OEM_SYS_ROOT/dev/mtd2ro" "$4/ENV.bin";cp "$OEM_SYS_ROOT/dev/mtd3ro" "$4/ART.bin";cp "$OEM_SYS_ROOT/dev/mtd4ro" "$4/MFG.bin";cp "$1" "$4/manifest.tsv"
 (cd "$4" && sha256sum ENV.bin ART.bin MFG.bin manifest.tsv > SHA256SUMS);chmod 600 "$4/"*
}
oem_backup_upload() {
 [ "$FAULT" != upload ] || return 1
 oem_sha "$1/SHA256SUMS" > "$1/OFFDEVICE_VERIFIED";chmod 600 "$1/OFFDEVICE_VERIFIED"
 [ "$FAULT" != upload-drift ] || printf 'BAD!' > "$OEM_SYS_ROOT/dev/ubi1_0"
}
oem_restore_confirm_inspect && oem_restore_confirm_preflight && oem_restore_confirm
'''
  return subprocess.run(['sh']+(['-x'] if os.environ.get('JAGUAR_CONFIRM_TRACE') else [])+['-c',script],env=env,capture_output=True,text=True)
 def test_all_three_models_both_slots_confirm_only_native_selectors(self):
  for model in ('XV2-2','XV2-2T1','XE3-4'):
   for source in (0,1):
    fixture=self.fixture(model,source);root=fixture[0][0];before={p:p.read_bytes() for p in (root/'dev').iterdir()}
    result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
    self.assertEqual(before,{p:p.read_bytes() for p in before})
    state=json.loads((root/'env.json').read_text());self.assertEqual(state['bootcmd'],'bootipq');self.assertEqual(state['image'],str(1-source))
    self.assertEqual(state['jaguar_oem_restore_state'],'confirmed');self.assertEqual(state[f'jaguar_boot{source}'],fixture[1][f'jaguar_boot{source}'])
    self.assertEqual((root/'confirm-events').read_text(),'CONFIRM\n');self.assertIn('No reboot, vendor factory reset or identity retirement',result.stdout)
 def test_backup_upload_batch_and_readback_failures_keep_source_default(self):
  for fault in ('backup','upload','CONFIRM','readback'):
   fixture=self.fixture();root=fixture[0][0];result=self.invoke(fixture,fault)
   self.assertNotEqual(result.returncode,0,fault);state=json.loads((root/'env.json').read_text())
   self.assertEqual(state['bootcmd'],'run jaguar_boot0');self.assertEqual(state['image'],'0');self.assertNotIn('OEM boot confirmed;',result.stdout)
 def test_wrong_release_root_pending_source_boot_and_payload_refuse_before_write(self):
  for fault in ('version','running','temporary-root','pending','source-boot','kernel','root'):
   fixture=self.fixture();root=fixture[0][0]
   if fault=='version':(root/'etc/version').write_text('PRODUCT=jaguar\nVERSION=7.1-r1\n')
   if fault=='running':(root/'proc/cmdline').write_text('ubi.mtd=rootfs root=ubi1:ubi_rootfs\n')
   if fault=='temporary-root':(root/'proc/mounts').write_text('rootfs / rootfs rw 0 0\n')
   if fault in ('pending','source-boot'):
    state=json.loads((root/'env.json').read_text());state['jaguar_oem_restore_state' if fault=='pending' else 'jaguar_boot0']='wrong';(root/'env.json').write_text(json.dumps(state))
   if fault in ('kernel','root'):(root/f'dev/ubi1_{0 if fault=="kernel" else 1}').write_bytes(b'wrong deployed payload')
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0,fault);self.assertFalse((root/'confirm-events').exists())
 def test_mutable_oem_configuration_activity_is_not_root_image_equality_gate(self):
  fixture=self.fixture();root=fixture[0][0];config=root/'mnt/flash/config/config.txt';config.parent.mkdir(parents=True);config.write_text('legitimate mutable OEM configuration outside immutable kernel/root\n')
  result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
 def test_uncertain_native_env_rollback_is_reported_not_hidden(self):
  fixture=self.fixture();root=fixture[0][0];before=(root/'dev/ubi0_1').read_bytes()
  result=self.invoke(fixture,'rollback-failure');self.assertNotEqual(result.returncode,0)
  self.assertIn('confirmation selector rollback is uncertain',result.stdout+result.stderr)
  self.assertNotIn('OEM boot confirmed;',result.stdout);self.assertEqual(before,(root/'dev/ubi0_1').read_bytes())
 def test_wrong_running_slot_physical_roles_refuse_before_confirm(self):
  for source in (0,1):
   fixture=self.fixture(source=source);root,bundle,_,_,model,_=fixture[0];profile=bundle/f'profiles/{model}/restore/confirm'
   (profile/f'mtd-slot{1-source}.tsv').write_bytes((profile/f'mtd-slot{source}.tsv').read_bytes())
   (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0);self.assertFalse((root/'confirm-events').exists())
 def test_post_upload_candidate_drift_refuses_before_selector(self):
  fixture=self.fixture();root=fixture[0][0];result=self.invoke(fixture,'upload-drift')
  self.assertNotEqual(result.returncode,0);self.assertFalse((root/'confirm-events').exists())
  self.assertEqual(json.loads((root/'env.json').read_text())['bootcmd'],'run jaguar_boot0')

if __name__=='__main__':unittest.main()
