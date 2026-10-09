#!/usr/bin/env python3
"""Actual forward adapter + pair writer + FORMAT2 producer on inert devices.
Physical flash, mounts, ENV durability and upload acknowledgment are mocked.
Synthetic payload/runtime/bootloader inputs never qualify real OEM hardware.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import shutil
import unittest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sage_inspection',HERE/'tests/test-sage-inspection.py')
inspection=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspection)

BACKEND=r'''
import json,os,shutil,stat,sys
from pathlib import Path
p=Path(os.environ['FIXTURE']); command,args=sys.argv[1],sys.argv[2:]
key=(p/'fixture-key').read_text().strip()
if any(key in value for value in [*args,*os.environ.values()]):
 (p/'PRIVACY_FAILURE').write_text('credential escaped to a child');sys.exit(73)
if command=='ls':
 s=Path(args[-1]).lstat();print(stat.filemode(s.st_mode),s.st_nlink,0,0,s.st_size,'Jan 1 00:00',args[-1]);sys.exit(0)
envfile=p/'env.json';env=json.loads(envfile.read_text());fault=os.environ.get('FAULT','')
if command=='fw_printenv':
 if '-n' in args:
  name=args[args.index('-n')+1]
  if name not in env:sys.exit(1)
  print('wrong' if (fault=='source-readback' and name=='sage_storage_pending') or (fault=='arm-readback' and name=='sage_installer_job') else env[name])
 else:print(''.join(k+'='+v+'\n' for k,v in env.items()),end='')
 sys.exit(0)
if command=='fw_setenv':
 a=args[2:]
 label='SOURCE' if a[0]=='-s' and Path(a[1]).name=='environment' else ('ARM' if a[0]=='-s' else 'SELECTOR')
else:label=command
with (p/'events').open('a') as out:out.write(label+' '+json.dumps(args)+'\n')
if fault==label:sys.exit(1)
ubi=p/'sys/class/ubi';dev=p/'dev';target=int(os.environ['TARGET'])
def volume(i):return ubi/f'ubi0_{i}'
def free(delta):
 path=ubi/'ubi0/avail_eraseblocks';path.write_text(str(int(path.read_text())+delta))
if command=='fw_setenv':
 if a[0]=='-s':
  for row in Path(a[1]).read_text().splitlines():
   fields=row.split(' ',1)
   if len(fields)==1:env.pop(fields[0],None)
   else:env[fields[0]]=fields[1]
 else:
  if len(a)==1:env.pop(a[0],None)
  else:env[a[0]]=a[1]
 envfile.write_text(json.dumps(env))
elif command=='ubirmvol':
 assert args[0]==str(dev/'ubi0') and args[1]=='-n'
 identifier=int(args[2]);assert identifier in (2*target+1,6-target)
 node=volume(identifier);free(int((node/'reserved_ebs').read_text()));shutil.rmtree(node);(dev/f'ubi0_{identifier}').unlink()
elif command=='ubimkvol':
 assert args[0]==str(dev/'ubi0') and args[1]=='-n' and args[3]=='-N' and args[5]=='-s'
 identifier,name,size=int(args[2]),args[4],int(args[6]);assert (identifier,name) in ((2*target+1,f'rootfs{target}'),(6-target,f'rootfs_data{target}'))
 node=volume(identifier);node.mkdir()
 for k,v in dict(name=name,reserved_ebs=size//126976,usable_eb_size=126976,type='dynamic',upd_marker=0,corrupted=0).items():(node/k).write_text(str(v))
 (dev/f'ubi0_{identifier}').write_bytes(b'');free(-(size//126976))
elif command=='ubiupdatevol':
 destination=Path(args[0]);assert destination in (dev/f'ubi0_{2*target}',dev/f'ubi0_{2*target+1}')
 data=Path(args[1]).read_bytes();destination.write_bytes(b'BAD!'+data[4:] if fault=='readback' else data)
 if os.environ.get('SOURCE_ACTIVITY')=='1':
  source=1-target
  (dev/f'ubi0_{2*source+1}').write_bytes(b'legitimate OEM writable-root daemon activity')
  (dev/'ubi0_4').write_bytes(b'legitimate shared nvram daemon activity')
elif command=='mount':
 assert args[:2]==['-t','ubifs'];assert args[2]==str(dev/f'ubi0_{6-target}')
 mount=Path(args[3]);(p/'mounted').write_text(str(mount))
 with (p/'proc/mounts').open('a') as out:out.write(args[2]+' '+str(mount)+' ubifs rw 0 0\n')
elif command=='umount':
 mount=Path(args[0]);rows=(p/'proc/mounts').read_text().splitlines();(p/'proc/mounts').write_text('\n'.join(row for row in rows if row.split()[1]!=str(mount))+'\n')
 for child in mount.iterdir():shutil.move(str(child),str(p/('staged-'+child.name)))
elif command!='sync':raise AssertionError(command)
'''

class ForwardTests(unittest.TestCase):
 def fixture(self,model='E410',slot=0):
  holder=inspection.SageAdapterTests();case=holder.setup_case(model,slot);self.addCleanup(holder.doCleanups)
  root,bundle,work,bin,model,sku=case
  def cleanup_mount():
   marker=root/'mounted'
   if marker.exists():
    mount=Path(marker.read_text())
    if mount.parent.resolve()==Path('/tmp').resolve() and mount.name.startswith('cambium-oem-settings.') and mount.is_dir():shutil.rmtree(mount)
  self.addCleanup(cleanup_mount)
  def put(path,data,mode=None):
   path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data.encode() if isinstance(data,str) else data)
   if mode is not None:path.chmod(mode)
  mfg=root/'dev/mtd6ro';mfg.write_bytes(mfg.read_bytes().ljust(65536,b'\0'))
  put(root/'dev/fixture-key',b'')
  put(root/'fixture-key','k'*64+'\n',0o600);put(root/'dev/urandom',bytes(range(32)))
  for key,value in dict(name='nvram',reserved_ebs=167,usable_eb_size=126976,type='dynamic',upd_marker=0,corrupted=0).items():put(root/f'sys/class/ubi/ubi0_4/{key}',str(value))
  put(root/'dev/ubi0_4',b'original shared nonunique configuration')
  put(root/'env.json',json.dumps(dict(image=str(slot),bootcmd='bootipq',factory_mac='000456abcdef')))
  put(root/'proc/cmdline',f'ubi.mtd=fs root=ubi0:rootfs{slot} rootfstype=ubifs\n')
  put(root/'sys/class/mtd/mtd7/name','0:APPSBL')
  for key,value in dict(offset=196608,size=524288,type='nor',erasesize=65536,writesize=1,flags='0xc00').items():put(root/f'sys/class/mtd/mtd7/{key}',str(value))
  (root/'sys/class/mtd/mtd7/device').symlink_to(root/'chips/nor0')
  put(root/'dev/mtd7ro',b'nonflashable bootloader reference')
  profile=bundle/f'profiles/{model}'
  with (profile/'mtd.tsv').open('a') as out:out.write('0:APPSBL\tnor0\t196608\t524288\tnor\t65536\t1\tbootcode\n')
  put(profile/'bootloader.sha256',inspection.sha(root/'dev/mtd7ro')+'\n')
  put(root/'proc/mtd',(root/'proc/mtd').read_text()+'mtd7: 00080000 00010000 "0:APPSBL"\n')
  critical=work/'critical';critical.mkdir(mode=0o700)
  manifest='ENV\t0:APPSBLENV\t65536\tenvironment\nART\t0:ART\t65536\tcalibration\nMFG\tmfginfo\t65536\tfactory\n'
  put(critical/'manifest.tsv',manifest,0o600)
  for kind,index in (('ENV',2),('ART',4),('MFG',6)):put(critical/f'{kind}.bin',(root/f'dev/mtd{index}ro').read_bytes(),0o600)
  put(critical/'SHA256SUMS',''.join(inspection.sha(critical/name)+'  '+name+'\n' for name in ('ENV.bin','ART.bin','MFG.bin','manifest.tsv')),0o600)
  put(critical/'OFFDEVICE_VERIFIED',inspection.sha(critical/'SHA256SUMS')+'\n',0o600)
  put(root/'backend.py',BACKEND)
  for command in ('fw_printenv','fw_setenv','ubiupdatevol','ubirmvol','ubimkvol','mount','umount','sync','ls'):
   put(bin/command,'#!/bin/sh\nexec python3 "$FIXTURE/backend.py" '+command+' "$@"\n',0o755)
  # macOS /tmp is a symlink; production Linux /tmp is canonical. Normalize
  # only this fixture boundary, retaining real mkdir/mktemp and private modes.
  put(bin/'mktemp','#!/bin/sh\nfixture_tmp=$(/usr/bin/mktemp "$@") || exit 1\nreadlink -f "$fixture_tmp"\n',0o755)
  (bundle/'SHA256SUMS').write_text(''.join(inspection.sha(p)+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
  return case
 def invoke(self,case,fault='',activity=False):
  root,bundle,work,bin,model,sku=case
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],LC_ALL='C',FIXTURE=str(root),TARGET=str(1-int((root/'environment/image').read_text())),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_FAMILY='sage',OEM_MODEL=model,OEM_SKU=f'{sku:08x}',OEM_SUPPORTED_RELEASE='4.2.3.3-r10',OEM_CONTROLLER='controller.invalid',HERE=str(HERE),FAULT=fault,SOURCE_ACTIVITY=str(int(activity)))
  script=r'''
. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/adapters/sage.sh"
IFS= read -r input < "$FIXTURE/fixture-key"
oem_adapter_migrate "$input"
'''
  return subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
 def test_both_models_slots_actual_writer_format2_then_arm(self):
  for model in ('E410','E410B'):
   for slot in (0,1):
    with self.subTest(model=model,slot=slot):
     case=self.fixture(model,slot);root,bundle,work,*rest=case
     protected={p:p.read_bytes() for p in (root/'dev').iterdir() if p.name not in (f'ubi0_{2*(1-slot)}',f'ubi0_{2*(1-slot)+1}')}
     result=self.invoke(case)
     diagnostic=result.stderr+'\nevents='+((root/'events').read_text() if (root/'events').exists() else 'none')+'\nwork='+','.join(str(p.relative_to(work)) for p in work.rglob('*'))
     self.assertEqual(result.returncode,0,diagnostic)
     self.assertEqual(protected,{p:p.read_bytes() for p in protected});self.assertFalse((root/'PRIVACY_FAILURE').exists())
     events=(root/'events').read_text();self.assertLess(events.index('SOURCE '),events.index('ubirmvol '));self.assertLess(events.index('umount '),events.index('ARM '))
     settings=root/'staged-upper/root/.cambium-installer-settings'
     self.assertEqual((settings/'est-bootstrap.conf').read_text(),'user = "000456abcdef:'+('k'*64)+'"\n')
     self.assertEqual((root/'staged-upper').stat().st_mode & 0o777,0o755)
     self.assertEqual(settings.stat().st_mode & 0o777,0o700)
     self.assertNotIn('k'*64,events+result.stdout+result.stderr)
     values=json.loads((root/'env.json').read_text());self.assertNotIn('sage_storage_pending',values)
     self.assertIn(f'saveenv && run sage_boot{1-slot}; run sage_boot{slot}',values['bootcmd'])
 def test_actual_fault_boundaries_never_arm(self):
  for fault in ('SOURCE','source-readback','ubirmvol','ubimkvol','ubiupdatevol','readback','mount','umount','ARM','arm-readback'):
   with self.subTest(fault=fault):
    case=self.fixture();root=case[0];result=self.invoke(case,fault)
    self.assertNotEqual(result.returncode,0);values=json.loads((root/'env.json').read_text())
    self.assertIn(values['bootcmd'],('bootipq','run sage_boot0'))
    self.assertFalse((root/'PRIVACY_FAILURE').exists());self.assertNotIn('handoff=one-shot-armed',result.stdout)
 def test_normal_source_activity_does_not_become_installer_source_write(self):
  case=self.fixture();root=case[0];kernel=(root/'dev/ubi0_0').read_bytes()
  result=self.invoke(case,activity=True);self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(kernel,(root/'dev/ubi0_0').read_bytes())
  self.assertEqual((root/'dev/ubi0_1').read_bytes(),b'legitimate OEM writable-root daemon activity')
  self.assertEqual((root/'dev/ubi0_4').read_bytes(),b'legitimate shared nvram daemon activity')
  events=(root/'events').read_text()
  self.assertNotIn(str(root/'dev/ubi0_0'),events);self.assertNotIn(str(root/'dev/ubi0_1'),events);self.assertNotIn(str(root/'dev/ubi0_4'),events)

if __name__=='__main__':unittest.main()
