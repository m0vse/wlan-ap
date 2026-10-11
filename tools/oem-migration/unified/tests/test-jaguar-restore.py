#!/usr/bin/env python3
"""Composed return writer on nonflashable sparse payloads and inert devices.
No OEM signature/hardware/flash durability claim from these fixtures.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tarfile
import unittest

HERE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
BACKEND=r'''
import json,os,shutil,sys
from pathlib import Path
r=Path(os.environ['FIXTURE']);cmd,a=sys.argv[1],sys.argv[2:];fault=os.environ.get('FAULT','');p=r/'env.json';s=json.loads(p.read_text());dev=r/'dev';sysdir=r/'sys/class/ubi'
if cmd=='fw_printenv':print(''.join(k+'='+v+'\n' for k,v in s.items()),end='');sys.exit(0)
if cmd=='fw_setenv':
 args=a[2:];label='SOURCE' if args[0]=='-s' and Path(args[1]).name=='return-source.env' else ('ARM' if args[0]=='-s' else 'SELECTOR')
elif cmd=='ubirsvol':label='RESIZE'
elif cmd=='ubirmvol':label='REMOVE'+a[2]
elif cmd=='ubimkvol':label='CREATE'+a[2]
elif cmd=='ubiupdatevol':label='WRITE'+Path(a[0]).name.split('_')[1]
elif cmd=='ubiattach':label='ATTACH'
elif cmd=='ubiblock':label='ROOTMAP'
else:label=cmd
with (r/'events').open('a') as log:log.write(label+' '+json.dumps(a)+'\n')
if fault==label:sys.exit(1)
def node(i):return sysdir/f'ubi1_{i}'
def free(delta):
 p=sysdir/'ubi1/avail_eraseblocks';p.write_text(str(int(p.read_text())+delta))
if cmd=='ubiblock':
 assert a==['--remove',str(dev/'ubi1_1')]
 shutil.rmtree(r/'sys/class/block/ubiblock1_1')
elif cmd=='ubiattach':
 assert a==['-m',str(1-int(os.environ['SOURCE']))]
 if fault=='attach-missing':sys.exit(0)
 for old in (r/'detached/sys').iterdir():shutil.move(str(old),str(sysdir/old.name))
 for old in (r/'detached/dev').iterdir():shutil.move(str(old),str(dev/old.name))
 if fault=='attach-alias':
  (sysdir/'ubi2').mkdir();(sysdir/'ubi2/mtd_num').write_text(a[1])
 if fault=='attach-wrong-parent':(sysdir/'ubi1/mtd_num').write_text(os.environ['SOURCE'])
 if fault=='attach-cert-type':(sysdir/'ubi1_4/type').write_text('static')
elif cmd=='fw_setenv':
 if args[0]=='-s':
  for row in Path(args[1]).read_text().splitlines():
   fields=row.split(' ',1)
   if len(fields)==1:s.pop(fields[0],None)
   else:s[fields[0]]=fields[1]
  if fault=='source-readback' and label=='SOURCE':s['jaguar_oem_restore_state']='wrong'
  if fault=='arm-readback' and label=='ARM':s['jaguar_oem_restore_state']='wrong'
  if fault=='late-vault' and label=='ARM':
   with (dev/'ubi1_3').open('r+b') as f:f.write(b'BAD!')
  if fault=='late-cert-geometry' and label=='ARM':(sysdir/'ubi1_4/alignment').write_text('2')
 else:s[args[0]]=args[1]
 p.write_text(json.dumps(s))
elif cmd=='ubirsvol':
 assert a[:3]==[str(dev/'ubi1'),'-n','3'] and a[3]=='-s'
 blocks=int(a[4])//126976;old=int((node(3)/'reserved_ebs').read_text());assert 1<=blocks<old
 (node(3)/'reserved_ebs').write_text(str(blocks));free(old-blocks)
 data=(dev/'ubi1_3').read_bytes()[:blocks*126976]
 if fault=='vault-readback':data=b'BAD!'+data[4:]
 (dev/'ubi1_3').write_bytes(data)
elif cmd=='ubirmvol':
 assert a[:2]==[str(dev/'ubi1'),'-n'];i=int(a[2]);assert i in (0,1,2)
 free(int((node(i)/'reserved_ebs').read_text()));shutil.rmtree(node(i));(dev/f'ubi1_{i}').unlink()
elif cmd=='ubimkvol':
 assert a[0]==str(dev/'ubi1') and a[1]=='-n' and a[3]=='-N' and a[5]=='-s'
 i,name,blocks=int(a[2]),a[4],int(a[6])//126976;assert (i,name,blocks) in ((0,'kernel',32),(1,'ubi_rootfs',337))
 node(i).mkdir()
 for k,v in dict(name=name,reserved_ebs=blocks,usable_eb_size=126976,type='dynamic',corrupted=0,upd_marker=0).items():(node(i)/k).write_text(str(v))
 (dev/f'ubi1_{i}').write_bytes(b'');free(-blocks)
elif cmd=='ubiupdatevol':
 i=int(Path(a[0]).name.split('_')[1]);assert i in (0,1) and Path(a[0])==dev/f'ubi1_{i}'
 shutil.copyfile(a[1],a[0])
 if fault=='readback':
  with open(a[0],'r+b') as f:f.write(b'BAD!')
 if fault=='late-kernel' and i==1:
  with (dev/'ubi1_0').open('r+b') as f:f.write(b'BAD!')
elif cmd!='sync':raise AssertionError(cmd)
'''
class RestoreTests(unittest.TestCase):
 def fixture(self,model='XV2-2',slot=0):
  compile(BACKEND,'inert-return-backend','exec')
  spec=importlib.util.spec_from_file_location('jag_forward',HERE/'tests/test-jaguar-forward.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  holder=module.ForwardTests();case=holder.fixture(model,slot);self.addCleanup(holder.doCleanups)
  root,bundle,work,bin,model,sku=case;release='jaguar-2026.10.05.8'
  def put(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data);return p
  def member(name,data):return put(bundle/name,data)
  put(root/'etc/openwrt_release',"DISTRIB_TIP_VERSION='"+release+"'\n")
  put(root/'tmp/sysinfo/board_name','cambiumnetworks,'+model.lower()+'\n')
  put(root/'lib/functions/system.sh','get_mac_label_dt() { echo bc:a9:93:00:00:02; }\n')
  put(root/'proc/cmdline',f'ubi.mtd={"rootfs" if slot==0 else "rootfs_1"} root=/dev/ubiblock0_1 rootfstype=squashfs\n')
  boot=f'KNOWN_NONFLASHABLE_SOURCE_BOOT_SLOT_{slot}'
  state=dict(image=str(slot),bootcmd=f'run jaguar_stable{slot}',jaguar_ab_confirmed=str(slot),jaguar_ab_state='confirmed',factory_mac='bca993000002')
  state[f'jaguar_boot{slot}']=boot;state[f'jaguar_stable{slot}']=f'run jaguar_boot{slot}; run jaguar_boot{1-slot}'
  put(root/'env.json',json.dumps(state))
  status=bin/'cambium-ab-status';put(status,f'#!/bin/sh\nprintf "mode=ab\\nfamily=jaguar\\nmodel={model}\\nrunning={slot}\\nconfirmed={slot}\\nstate=confirmed\\n"\n');status.chmod(0o755)
  lebs=392 if model=='XV2-2' else 724
  art=sha(root/'dev/mtd3ro');assets=[('lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock',65536)] if model!='XE3-4' else [('lib/firmware/IPQ6018/WIFI_FW/bdwlan.b10-puma',65536),('lib/firmware/qcn9000/WIFI_FW/bdwlan.bab-puma',131072)]
  vaultdir=root/'native-vault';vaultdir.mkdir();manifest=f'format 1\nboard cambiumnetworks,{model.lower()}\nsku {sku}\nart_sha256 {art}\nnvram_sha256_at_capture unknown\nsource fixture\n'
  for path,size in assets:
   p=put(vaultdir/'files'/path,b'B'*size);manifest+=f'file {path} {size} {sha(p)}\n'
  put(vaultdir/'MANIFEST',manifest);archive=root/'vault.tar'
  with tarfile.open(archive,'w',format=tarfile.USTAR_FORMAT) as tar:tar.add(vaultdir/'MANIFEST',arcname='MANIFEST');tar.add(vaultdir/'files',arcname='files')
  data=archive.read_bytes();data+=b'\xff'*(8*126976-len(data))
  for u in (0,1):
   for i,name,blocks in ((0,'kernel',45),(1,'rootfs',129),(2,'rootfs_data',lebs-202),(3,'cambium_device_data',8),(4,'certificates',20)):
    node=root/f'sys/class/ubi/ubi{u}_{i}';node.mkdir(exist_ok=True)
    for k,v in dict(name=name,reserved_ebs=blocks,usable_eb_size=126976,type='dynamic',alignment=1,data_bytes=blocks*126976,corrupted=0,upd_marker=0).items():put(node/k,str(v))
    put(root/f'dev/ubi{u}_{i}',data if i==3 else ('original protected '+str(u)+name).encode())
   put(root/f'sys/class/ubi/ubi{u}/avail_eraseblocks','0')
  profile=f'profiles/{model}/restore/'
  member('adapters/jaguar.sh',(HERE/'adapters/jaguar.sh').read_bytes())
  member(profile+'source-contract',release+'\n'+'a'*64+'\n')
  member(profile+'source-sets/runtime-implementation.set','F '+sha(root/'etc/openwrt_release')+' /etc/openwrt_release\nF '+sha(root/'lib/functions/system.sh')+' /lib/functions/system.sh\n')
  member(profile+f'source-boot{slot}.sha256',hashlib.sha256(boot.encode()).hexdigest()+'\n')
  for source in (0,1):member(profile+f'mtd-slot{source}.tsv',(bundle/f'profiles/{model}/mtd-slot{source}.tsv').read_bytes())
  member(profile+'oem-release','7.2-r1\n')
  k=member(f'payloads/{model}/oem/kernel.itb',b'');r=member(f'payloads/{model}/oem/rootfs.squashfs',b'')
  for p,magic,size in ((k,bytes.fromhex('d00dfeed'),4048776),(r,b'hsqs',42709508)):
   with p.open('wb') as f:f.write(magic);f.seek(size-1);f.write(b'\0')
  shared=member(f'payloads/{model}/oem/shared.json','{"version":"7.2-r1","fixture":"nonflashable"}\n')
  member(profile+'operator-artifact-pins',sha(k)+'\n'+sha(r)+'\n'+sha(shared)+'\n')
  member(profile+'critical-backup.tsv',(work/'critical/manifest.tsv').read_bytes())
  (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
  put(root/'return-backend.py',BACKEND)
  for cmd in ('fw_printenv','fw_setenv','ubirmvol','ubimkvol','ubirsvol','ubiupdatevol','ubiattach','ubiblock','sync'):
   p=put(bin/cmd,'#!/bin/sh\nexec python3 "$FIXTURE/return-backend.py" '+cmd+' "$@"\n');p.chmod(0o755)
  return case,release
 def invoke(self,fixture,fault=''):
  case,release=fixture;root,bundle,work,bin,model,sku=case
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),HERE=str(HERE),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_RECOVERY_DIR=str(work/'critical'),OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SUPPORTED_RELEASE=release,FAULT=fault,SOURCE=json.loads((root/'env.json').read_text())['image'])
  script='. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/lib/critical-backup.sh"; . "$HERE/adapters/restore-jaguar.sh"; oem_restore_inspect && oem_restore_preflight && oem_restore_boot_preflight && oem_restore_migrate'
  return subprocess.run(['sh']+(['-x'] if os.environ.get('JAGUAR_RETURN_TRACE') else [])+['-c',script],env=env,capture_output=True,text=True)
 def test_all_known_models_slots_source_first_cert_vault_preserved(self):
  for model in ('XV2-2','XV2-2T1','XE3-4'):
   for slot in (0,1):
    fixture=self.fixture(model,slot);root=fixture[0][0];protected={p:p.read_bytes() for p in (root/'dev').iterdir() if not p.name.startswith('ubi1_')};cert=(root/'dev/ubi1_4').read_bytes()
    result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
    events=(root/'events').read_text();self.assertLess(events.index('SOURCE '),events.index('REMOVE'))
    self.assertEqual(protected,{p:p.read_bytes() for p in protected});self.assertEqual(cert,(root/'dev/ubi1_4').read_bytes())
    self.assertEqual((root/'sys/class/ubi/ubi1_4/reserved_ebs').read_text(),'20')
    self.assertEqual((root/'sys/class/ubi/ubi1_1/name').read_text(),'ubi_rootfs')
    values=json.loads((root/'env.json').read_text());self.assertIn('saveenv && run jaguar_oem_boot',values['bootcmd']);self.assertEqual(values[f'jaguar_boot{slot}'],f'KNOWN_NONFLASHABLE_SOURCE_BOOT_SLOT_{slot}')
    self.assertEqual(values[f'jaguar_stable{slot}'],f'run jaguar_boot{slot}')
    if model=='XV2-2':self.assertIn('RESIZE ',events);self.assertEqual((root/'sys/class/ubi/ubi1_3/reserved_ebs').read_text(),'1')
    else:self.assertNotIn('RESIZE ',events)
    # Existing actual incoming consumer must still accept the exact retained
    # archive after raw-vault reduction; no regenerated manifest/assets.
    spec=importlib.util.spec_from_file_location('consumer',HERE/'tests/test-jaguar-consumers.py');consumer=importlib.util.module_from_spec(spec);spec.loader.exec_module(consumer)
    unpacked=root/'return-vault-consumer';unpacked.mkdir()
    subprocess.run(['tar','-xf',str(root/'dev/ubi1_3'),'-C',str(unpacked)],check=True)
    checker=consumer.ConsumerTests();checked=checker.consume(fixture[0],unpacked)
    self.assertEqual(checked.returncode,0,checked.stderr)
    self.assertIn('identity_retired=no',result.stdout)
 def test_failures_never_select_oem_or_touch_working_source(self):
  for fault in ('SOURCE','source-readback','RESIZE','vault-readback','REMOVE2','REMOVE1','REMOVE0','CREATE0','CREATE1','WRITE0','WRITE1','readback','ARM','arm-readback','SELECTOR'):
   fixture=self.fixture();root=fixture[0][0];source=(root/'dev/ubi0_1').read_bytes();cert=(root/'dev/ubi1_4').read_bytes()
   result=self.invoke(fixture,fault);self.assertNotEqual(result.returncode,0,fault)
   self.assertEqual(source,(root/'dev/ubi0_1').read_bytes());self.assertEqual(cert,(root/'dev/ubi1_4').read_bytes())
   self.assertIn(json.loads((root/'env.json').read_text())['bootcmd'],('run jaguar_stable0','run jaguar_boot0'))
 def detach_fixture(self,fixture):
  root=fixture[0][0];(root/'detached/sys').mkdir(parents=True);(root/'detached/dev').mkdir()
  for p in (root/'sys/class/ubi').glob('ubi1*'):shutil.move(str(p),str(root/'detached/sys'/p.name))
  for p in (root/'dev').glob('ubi1_*'):shutil.move(str(p),str(root/'detached/dev'/p.name))
 def test_unattached_bank_attached_only_after_source_saved(self):
  for slot in (0,1):
   fixture=self.fixture(slot=slot);root=fixture[0][0];self.detach_fixture(fixture)
   result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
   events=(root/'events').read_text();self.assertLess(events.index('SOURCE '),events.index('ATTACH '));self.assertLess(events.index('ATTACH '),events.index('RESIZE '))
 def test_attach_failure_or_uncertain_metadata_never_erases(self):
  for fault in ('ATTACH','attach-missing','attach-alias','attach-wrong-parent','attach-cert-type'):
   fixture=self.fixture();root=fixture[0][0];self.detach_fixture(fixture)
   result=self.invoke(fixture,fault);self.assertNotEqual(result.returncode,0,fault)
   events=(root/'events').read_text();self.assertIn('SOURCE ',events)
   for operation in ('RESIZE ','REMOVE','CREATE','WRITE','ARM '):self.assertNotIn(operation,events)
   self.assertEqual(json.loads((root/'env.json').read_text())['bootcmd'],'run jaguar_boot0')
 def test_unattached_direct_mount_fd_or_duplicate_parent_refuses_before_source_save(self):
  for fault in ('mount','fd','alias'):
   fixture=self.fixture();root=fixture[0][0];self.detach_fixture(fixture)
   if fault=='mount':(root/'proc/mounts').write_text(str(root/'dev/mtdblock1')+' /hidden squashfs ro 0 0\n')
   if fault=='fd':
    p=root/'proc/999/fd';p.mkdir(parents=True);(p/'7').symlink_to(root/'dev/mtd1ro')
   if fault=='alias':
    for u in ('ubi1','ubi2'):
     p=root/'sys/class/ubi'/u;p.mkdir();(p/'mtd_num').write_text('1')
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0,fault)
   self.assertFalse((root/'events').exists())
 def test_invalid_target_vault_identity_format_or_geometry_is_not_resize_permission(self):
  for fault in ('formatted','wrong-art','certificate-id','certificate-lebs'):
   fixture=self.fixture();root=fixture[0][0]
   if fault=='formatted':(root/'dev/ubi1_3').write_bytes(bytes.fromhex('31181006')+b'formatted UBIFS is not rawtar')
   if fault=='wrong-art':
    p=root/'dev/ubi1_3';data=p.read_bytes();old=sha(root/'dev/mtd3ro').encode();self.assertIn(old,data);p.write_bytes(data.replace(old,b'f'*64))
   if fault=='certificate-id':(root/'sys/class/ubi/ubi1_4/name').write_text('other_identity')
   if fault=='certificate-lebs':(root/'sys/class/ubi/ubi1_4/reserved_ebs').write_text('19')
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0,fault)
   self.assertFalse((root/'events').exists())
 def test_late_target_payload_vault_or_certificate_geometry_drift_never_selects(self):
  for fault in ('late-kernel','late-vault','late-cert-geometry'):
   fixture=self.fixture();root=fixture[0][0];result=self.invoke(fixture,fault)
   self.assertNotEqual(result.returncode,0,fault)
   self.assertEqual(json.loads((root/'env.json').read_text())['bootcmd'],'run jaguar_boot0')
   self.assertNotIn('SELECTOR ',(root/'events').read_text())
 def test_idle_target_rootmap_removed_after_source_save_but_mounted_map_refuses(self):
  for busy in (False,True):
   fixture=self.fixture();root=fixture[0][0];block=root/'sys/class/block/ubiblock1_1';block.mkdir(parents=True);(block/'dev').write_text('254:1')
   if busy:(root/'proc/self/mountinfo').write_text('1 0 254:1 / /hidden ro - squashfs /dev/ubiblock1_1 ro\n')
   result=self.invoke(fixture)
   if busy:
    self.assertNotEqual(result.returncode,0);self.assertFalse((root/'events').exists())
   else:
    self.assertEqual(result.returncode,0,result.stderr);events=(root/'events').read_text()
    self.assertLess(events.index('SOURCE '),events.index('ROOTMAP '));self.assertLess(events.index('ROOTMAP '),events.index('RESIZE '))
 def test_wrong_source_slot_role_map_never_saves_or_writes(self):
  for slot in (0,1):
   fixture=self.fixture(slot=slot);root,bundle,_,_,model,_=fixture[0]
   profile=bundle/f'profiles/{model}/restore'
   (profile/f'mtd-slot{slot}.tsv').write_bytes((profile/f'mtd-slot{1-slot}.tsv').read_bytes())
   (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0)
   self.assertFalse((root/'events').exists())

if __name__=='__main__':unittest.main()
