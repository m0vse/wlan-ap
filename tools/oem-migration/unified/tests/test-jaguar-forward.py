#!/usr/bin/env python3
"""Actual Jaguar caller/F2/vault/writer/boot flow on isolated file backends.
Nonflashable provider inputs, UID/device/ENV/mount/receipt mocks; no hardware.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
BACKEND=r'''
import json,os,shutil,stat,sys
from pathlib import Path
p=Path(os.environ['FIXTURE']);cmd,a=sys.argv[1],sys.argv[2:];fault=os.environ.get('FAULT','');key=(p/'key').read_text().strip()
assert not any(key in value for value in [*a,*os.environ.values()]),'credential escaped'
if cmd=='ls':
 s=Path(a[-1]).lstat();print(stat.filemode(s.st_mode),s.st_nlink,0,0,s.st_size,'Jan 1 00:00',a[-1]);sys.exit(0)
ef=p/'env.json';e=json.loads(ef.read_text())
if cmd=='fw_printenv':
 print(''.join(k+'='+v+'\n' for k,v in e.items()),end='');sys.exit(0)
if cmd=='fw_setenv':
 args=a[2:];label='SOURCE' if args[0]=='-s' and 'jaguar-source.' in args[1] else ('ARM' if args[0]=='-s' else 'SELECTOR')
else:label=cmd
with (p/'events').open('a') as out:out.write(label+' '+json.dumps(a)+'\n')
if label==fault:sys.exit(1)
sysdir=p/'sys/class/ubi';dev=p/'dev'
def node(i):return sysdir/f'ubi1_{i}'
def free(delta):
 f=sysdir/'ubi1/avail_eraseblocks';f.write_text(str(int(f.read_text())+delta))
if cmd=='fw_setenv':
 if args[0]=='-s':
  for line in Path(args[1]).read_text().splitlines():
   v=line.split(' ',1)
   if len(v)==1:e.pop(v[0],None)
   else:e[v[0]]=v[1]
  if fault=='source-readback' and label=='SOURCE':e['jaguar_storage_pending']='wrong'
  if fault=='arm-readback' and label=='ARM':e['jaguar_ab_target']='wrong'
  if fault.startswith('metadata-') and label=='ARM':e['jaguar_installer_'+fault.removeprefix('metadata-')]='wrong'
 else:
  if len(args)==1:e.pop(args[0],None)
  else:e[args[0]]=args[1]
 ef.write_text(json.dumps(e))
elif cmd=='ubirmvol':
 assert a[0]==str(dev/'ubi1') and a[1]=='-n' and int(a[2]) in (0,1)
 i=int(a[2]);free(int((node(i)/'reserved_ebs').read_text()));shutil.rmtree(node(i));(dev/f'ubi1_{i}').unlink()
elif cmd=='ubimkvol':
 assert a[0]==str(dev/'ubi1') and a[1]=='-n' and a[3]=='-N' and a[5]=='-s'
 i,name,size=int(a[2]),a[4],int(a[6]);assert (i,name) in ((0,'kernel'),(1,'rootfs'),(2,'rootfs_data'),(3,'cambium_device_data'),(4,'certificates'))
 n=node(i);n.mkdir()
 for k,v in dict(name=name,reserved_ebs=size//126976,usable_eb_size=126976,type='dynamic',upd_marker=0,corrupted=0).items():(n/k).write_text(str(v))
 (dev/f'ubi1_{i}').write_bytes(b'');free(-size//126976)
elif cmd=='ubiupdatevol':
 assert Path(a[0]) in (dev/'ubi1_0',dev/'ubi1_1',dev/'ubi1_3')
 data=Path(a[1]).read_bytes();Path(a[0]).write_bytes(b'BAD!'+data[4:] if fault=='readback' else data)
elif cmd=='mount':
 assert a[:3]==['-t','ubifs',str(dev/'ubi1_2')]
 (p/'mounted').write_text(a[3]);withfile=p/'proc/mounts'
 with withfile.open('a') as out:out.write(a[2]+' '+a[3]+' ubifs rw 0 0\n')
elif cmd=='umount':
 m=Path(a[0]);f=p/'proc/mounts';f.write_text('\n'.join(row for row in f.read_text().splitlines() if row.split()[1]!=str(m))+'\n')
 for c in m.iterdir():shutil.move(str(c),str(p/('staged-'+c.name)))
elif cmd=='ubiattach':raise AssertionError('fixture target is already attached')
elif cmd!='sync':raise AssertionError(cmd)
'''
class ForwardTests(unittest.TestCase):
 def fixture(self,model='XV2-2T1',slot=0):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name).resolve()
  bank,lebs,sku,fit=(54525952,392,'00000014','config@cp01-c1') if model=='XV2-2' else ((100663296,724,'00000020','config@cp01-c3-xv3-4') if model=='XE3-4' else (100663296,724,'0000001f','config@cp01-c1-2'))
  def put(name,data,mode=None):
   p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data)
   if mode is not None:p.chmod(mode)
   return p
  def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
  put('key','z'*64+'\n',0o600);put('dev/urandom',bytes(range(32)));put('etc/version','PRODUCT=jaguar\nVERSION=7.2-r1\n')
  put('etc/fw_env.config','/dev/mtd2 0x0 0x10000 0x10000 1\n')
  put('env.json',json.dumps(dict(image=str(slot),bootcmd='bootipq',factory_mac='bca993000002')))
  put('proc/cmdline',f'ubi.mtd='+('rootfs' if slot==0 else 'rootfs_1')+' root=/dev/ubiblock0_1 rootfstype=squashfs\n')
  put('proc/mounts','/dev/ubiblock0_1 / squashfs ro 0 0\n');put('proc/self/mountinfo','')
  rows=[];mtd=[]
  for domain in ('nor0','nand0'):(root/'chips'/domain).mkdir(parents=True)
  for i,name,domain,offset,size,role in ((0,'rootfs','nand0',0,bank,'active-oem' if slot==0 else 'target'),(1,'rootfs_1','nand0',bank,bank,'target' if slot==0 else 'active-oem'),(2,'0:APPSBLENV','nor0',0,65536,'environment'),(3,'0:ART','nor0',65536,65536,'identity'),(4,'mfginfo','nor0',131072,65536,'identity'),(5,'0:APPSBL','nor0',196608,524288,'bootcode')):
   erase,write=(131072,2048) if domain=='nand0' else (65536,1)
   for k,v in dict(name=name,type=domain[:-1],offset=offset,size=size,erasesize=erase,writesize=write,flags='0xc00' if role in ('target','environment') else '0x800').items():put(f'sys/class/mtd/mtd{i}/{k}',str(v))
   (root/f'sys/class/mtd/mtd{i}/device').symlink_to(root/'chips'/domain)
   data=bytes([i])*min(size,65536)
   if i==4:data=(bytes.fromhex('05ca01000c00')+b'bca993000002\0').ljust(65536,b'\0')
   put(f'dev/mtd{i}ro',data)
   rows.append(f'{name}\t{domain}\t{offset}\t{size}\t{domain[:-1]}\t{erase}\t{write}\t{role}\n');mtd.append(f'mtd{i}: {size:08x} {erase:08x} "{name}"\n')
  put('proc/mtd',''.join(mtd))
  for u,parent in ((0,slot),(1,1-slot)):
   for k,v in dict(mtd_num=parent,eraseblock_size=126976,min_io_size=2048,ro_mode=0,avail_eraseblocks=lebs-369).items():put(f'sys/class/ubi/ubi{u}/{k}',str(v))
   for i,name,blocks in ((0,'kernel',32),(1,'ubi_rootfs',337)):
    for k,v in dict(name=name,reserved_ebs=blocks,usable_eb_size=126976,type='dynamic',upd_marker=0,corrupted=0).items():put(f'sys/class/ubi/ubi{u}_{i}/{k}',str(v))
    put(f'dev/ubi{u}_{i}',b'original immutable software'+bytes([u,i]))
  bundle=root/'bundle';bundle.mkdir();work=root/'work';work.mkdir(mode=0o700);bin=root/'bin';bin.mkdir()
  def member(name,data):return put('bundle/'+name,data,0o600)
  profile=f'profiles/{model}/'
  image=member(f'payloads/{model}/image.bin',b'nonflashableimage');kernel=member(f'payloads/{model}/kernel.itb',bytes.fromhex('d00dfeed')+b'nonflashablekernel');fs=member(f'payloads/{model}/rootfs.squashfs',b'hsqsnonflashableroot')
  member(profile+'source-contract','7.2-r1\n'+'a'*64+'\n');member(profile+'source-sets/runtime-implementation.set','F '+sha(root/'etc/version')+' /etc/version\n')
  member('adapters/required-source.sh',(HERE/'adapters/required-source.sh').read_bytes())
  # One provider contains BOTH source-slot maps, not a regenerated single map.
  for source in (0,1):
   mapped=[]
   for row in rows:
    fields=row.rstrip('\n').split('\t')
    if fields[0] in ('rootfs','rootfs_1'):fields[-1]='active-oem' if fields[0]==('rootfs' if source==0 else 'rootfs_1') else 'target'
    mapped.append('\t'.join(fields)+'\n')
   member(profile+f'mtd-slot{source}.tsv',''.join(mapped))
  member(profile+'operator-artifact-pins',sha(image)+'\n'+sha(kernel)+'\n'+sha(fs)+'\n');member(profile+'fit.tsv',f'{sha(kernel)}\t{model}\t{sku}\t{fit}\n')
  member(profile+'vault-board','cambiumnetworks,'+model.lower()+'\n')
  assets=[('lib/firmware/IPQ6018/WIFI_FW/bdwlan.b13.stock',65536)] if model!='XE3-4' else [('lib/firmware/IPQ6018/WIFI_FW/bdwlan.b10-puma',65536),('lib/firmware/qcn9000/WIFI_FW/bdwlan.bab-puma',131072)]
  lines=[]
  for name,size in assets:
   asset=member(f'payloads/{model}/assets/{name}',b'B'*size);lines.append(f'{name}\t{size}\t{sha(asset)}\n')
  member(profile+'radio-assets.tsv',''.join(lines))
  for name,src in (('runtime-implementation-contract.sh',REPO/'tests/installer/common-minimum-v1/runtime-implementation-contract.sh'),('cambium-installer-settings.sh',REPO/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh')):member('lib/'+name,src.read_bytes())
  (bundle/'SHA256SUMS').write_text(''.join(sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file()))
  critical=work/'critical';critical.mkdir(mode=0o700);manifest='ENV\t0:APPSBLENV\t65536\tenvironment\nART\t0:ART\t65536\tcalibration\nMFG\tmfginfo\t65536\tfactory\n'
  put('work/critical/manifest.tsv',manifest,0o600)
  for kind,i in (('ENV',2),('ART',3),('MFG',4)):put('work/critical/'+kind+'.bin',(root/f'dev/mtd{i}ro').read_bytes(),0o600)
  put('work/critical/SHA256SUMS',''.join(sha(critical/name)+'  '+name+'\n' for name in ('ENV.bin','ART.bin','MFG.bin','manifest.tsv')),0o600);put('work/critical/OFFDEVICE_VERIFIED',sha(critical/'SHA256SUMS')+'\n',0o600)
  put('backend.py',BACKEND)
  for cmd in ('fw_printenv','fw_setenv','ubirmvol','ubimkvol','ubiupdatevol','ubiattach','mount','umount','ls','sync'):put('bin/'+cmd,'#!/bin/sh\nexec python3 "$FIXTURE/backend.py" '+cmd+' "$@"\n',0o755)
  put('bin/mktemp','#!/bin/sh\np=$(/usr/bin/mktemp "$@") || exit 1\nreadlink -f "$p"\n',0o755)
  def cleanup():
   marker=root/'mounted'
   if marker.exists():
    p=Path(marker.read_text())
    if p.is_dir() and p.parent.resolve()==Path('/tmp').resolve() and p.name.startswith('cambium-jaguar-settings.'):shutil.rmtree(p)
  self.addCleanup(cleanup)
  return root,bundle,work,bin,model,sku
 def invoke(self,case,fault=''):
  root,bundle,work,bin,model,sku=case
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],LC_ALL='C',FIXTURE=str(root),HERE=str(HERE),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_RECOVERY_DIR=str(work/'critical'),OEM_FAMILY='jaguar',OEM_MODEL=model,OEM_SKU=sku,OEM_SUPPORTED_RELEASE='7.2-r1',OEM_CONTROLLER='controller.invalid',FAULT=fault)
  script='. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/lib/critical-backup.sh"; . "$HERE/adapters/jaguar.sh"; IFS= read -r input < "$FIXTURE/key";oem_adapter_migrate "$input"'
  return subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
 def test_all_models_slots_real_stager_f2_vault_and_boot(self):
  for model in ('XV2-2','XV2-2T1','XE3-4'):
   for slot in (0,1):
    with self.subTest(model=model,slot=slot):
     case=self.fixture(model,slot);root=case[0];protected={p:p.read_bytes() for p in (root/'dev').iterdir() if not p.name.startswith('ubi1_')}
     result=self.invoke(case);events=(root/'events').read_text() if (root/'events').exists() else ''
     self.assertEqual(result.returncode,0,result.stderr+'\nevents='+events)
     self.assertEqual(protected,{p:p.read_bytes() for p in protected});self.assertLess(events.index('SOURCE '),events.index('ubirmvol '));self.assertLess(events.index('umount '),events.index('ARM '))
     values=json.loads((root/'env.json').read_text());self.assertIn(f'saveenv && run jaguar_boot{1-slot}; run jaguar_boot{slot}',values['bootcmd'])
     binding=dict(row.split('\t',1) for row in (root/'staged-upper/root/.cambium-installer-settings/binding.tsv').read_text().splitlines())
     self.assertEqual(values['jaguar_installer_target'],str(1-slot));self.assertEqual(values['jaguar_installer_job'],binding['job_id']);self.assertEqual(values['jaguar_installer_image'],binding['image_sha256'])
     spec=importlib.util.spec_from_file_location('incoming_consumers',HERE/'tests/test-jaguar-consumers.py');consumer=importlib.util.module_from_spec(spec);spec.loader.exec_module(consumer)
     consumer.check_incoming_context(root,model,case[-1],slot)
     self.assertEqual((root/'staged-upper').stat().st_mode&0o777,0o755)
     self.assertTrue((root/'staged-upper/root/.cambium-installer-settings/est-bootstrap.conf').exists())
     self.assertNotIn('z'*64,events+result.stdout+result.stderr)
 def test_faults_never_activate_or_touch_source(self):
  for fault in ('SOURCE','source-readback','ubirmvol','ubimkvol','ubiupdatevol','readback','mount','umount','ARM','arm-readback','metadata-target','metadata-job','metadata-image'):
   case=self.fixture();root=case[0];source=(root/'dev/ubi0_0').read_bytes()
   result=self.invoke(case,fault);self.assertNotEqual(result.returncode,0)
   self.assertEqual(source,(root/'dev/ubi0_0').read_bytes());self.assertIn(json.loads((root/'env.json').read_text())['bootcmd'],('bootipq','run jaguar_boot0'))
 def test_existing_inactive_identity_is_never_erased(self):
  case=self.fixture();root=case[0];p=root/'sys/class/ubi/ubi1_4';p.mkdir();(p/'name').write_text('certificates');(root/'dev/ubi1_4').write_bytes(b'own retained private identity')
  result=self.invoke(case);self.assertNotEqual(result.returncode,0);self.assertEqual((root/'dev/ubi1_4').read_bytes(),b'own retained private identity')
  self.assertNotIn('ubirmvol',(root/'events').read_text())
 def test_partial_foreign_installer_fields_refuse_before_any_mutation(self):
  for key,value in (('jaguar_installer_target','1'),('jaguar_installer_job','f'*64),('jaguar_installer_image','a'*64)):
   case=self.fixture();root=case[0];state=json.loads((root/'env.json').read_text());state[key]=value;(root/'env.json').write_text(json.dumps(state))
   result=self.invoke(case);self.assertNotEqual(result.returncode,0)
   self.assertFalse((root/'events').exists());self.assertEqual(json.loads((root/'env.json').read_text()),state)
 def test_wrong_slot_roles_refuse_before_env_or_target_writes(self):
  for slot in (0,1):
   case=self.fixture(slot=slot);root,bundle,work,bin,model,sku=case
   path=bundle/f'profiles/{model}/mtd-slot{slot}.tsv';path.write_bytes((bundle/f'profiles/{model}/mtd-slot{1-slot}.tsv').read_bytes())
   (bundle/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
   result=self.invoke(case);self.assertNotEqual(result.returncode,0)
   self.assertFalse((root/'events').exists())

if __name__=='__main__':unittest.main()
