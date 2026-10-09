#!/usr/bin/env python3
"""Actual factory/context readers and physical/profile preflight on fake trees.
No real devices, credentials, mounts, firmware or bootloaders are accessed.
"""
from pathlib import Path
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
READERS=REPO/'tools/oem-migration/recovery/scripts'
sys.path.insert(0,str(READERS/'tests'))
from test_cambium_oem_sage_prepare import CaptureTests

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

class SageAdapterTests(unittest.TestCase):
 def setup_case(self,model='E410',slot=0):
  capture=CaptureTests();capture.setUp();self.addCleanup(capture.tearDown)
  root=capture.root.resolve(); outer=tempfile.TemporaryDirectory(prefix='sage-adapter-case-');self.addCleanup(outer.cleanup)
  stage=Path(outer.name).resolve();bundle=stage/'bundle';bundle.mkdir();work=stage/'work';work.mkdir(mode=0o700)
  sku=10 if model=='E410' else 21;product='PL-E410XXX'+('A' if model=='E410' else 'B')+'-EU'
  capture.put('dev/mtd6ro',bytes.fromhex('05ca01000c00')+b'000456abcdef'+b'\0'+product.encode()+b'\0')
  capture.put('sys/firmware/devicetree/base/cambium-platform/board-sku',struct.pack('>I',sku))
  capture.put('etc/version','PRODUCT=sage\nVERSION=4.2.3.3-r10\n')
  capture.put('environment/image',str(slot)+'\n');capture.put('proc/cmdline',f'ubi.mtd=fs root=ubi0:rootfs{slot}\n')
  capture.put('proc/mounts',f'ubi0:rootfs{slot} / ubifs rw 0 0\n');(root/'root').mkdir()
  capture.put('sys/class/ubi/ubi0/avail_eraseblocks','22\n');capture.put('sys/class/ubi/ubi0/ro_mode','0\n')
  for i in range(4):
   for name,value in [('type','dynamic'),('upd_marker','0'),('corrupted','0')]:capture.put(f'sys/class/ubi/ubi0_{i}/{name}',value+'\n')
   capture.put(f'dev/ubi0_{i}',f'protected OEM volume {i}'.encode())
  for domain in ('nor0','nand0'):(root/'chips'/domain).mkdir(parents=True)
  rows=[]
  for index,name,domain,offset,size,erase,write,role in [(2,'0:APPSBLENV','nor0',0,65536,65536,1,'environment'),(4,'0:ART','nor0',65536,65536,65536,1,'identity'),(6,'mfginfo','nor0',131072,65536,65536,1,'identity'),(9,'fs','nand0',0,134217728,131072,2048,'shared-parent')]:
   for key,value in [('name',name),('type',domain[:-1]),('offset',offset),('size',size),('erasesize',erase),('writesize',write),('flags','0xc00')]:capture.put(f'sys/class/mtd/mtd{index}/{key}',str(value)+'\n')
   (root/f'sys/class/mtd/mtd{index}/device').symlink_to(root/'chips'/domain)
   if index!=6:capture.put(f'dev/mtd{index}ro',bytes([index])*65536)
   rows.append(f'{name}\t{domain}\t{offset}\t{size}\t{domain[:-1]}\t{erase}\t{write}\t{role}\n')
  def member(name,data):
   p=bundle/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data.encode() if isinstance(data,str) else data);return p
  for name in ('cambium-oem-sage-prepare.sh','cambium-oem-sage-storage-check.sh','cambium-oem-sage-context.sh','cambium-oem-models.tsv'):
   member('readers/sage/'+name,(READERS/name).read_bytes())
  for name in ('cambium-sage-pair-write.sh','cambium-installer-settings.sh','cambium-oem-sage-transaction.sh','cambium-oem-sage-boot.sh'):
   member('lib/'+name,(READERS/'lib'/name).read_bytes())
  member('lib/runtime-implementation-contract.sh',(REPO/'tests/installer/common-minimum-v1/runtime-implementation-contract.sh').read_bytes())
  image=member(f'payloads/{model}/image.bin',b'nonflashable image fixture')
  kernel=member(f'payloads/{model}/kernel.itb',bytes.fromhex('d00dfeed')+b'nonflashable kernel fixture')
  fs=member(f'payloads/{model}/rootfs.squashfs',b'hsqsnonflashable root fixture')
  member(f'profiles/{model}/operator-model',model+'\n'+product+'\n')
  member(f'profiles/{model}/source-contract','4.2.3.3-r10\n'+'a'*64+'\n')
  member(f'profiles/{model}/operator-artifact-pins',sha(image)+'\n'+sha(kernel)+'\n'+sha(fs)+'\n')
  member(f'profiles/{model}/fit.tsv',f'{sha(kernel)}\t{model}\t{sku:08x}\t'+('config@5' if model=='E410' else 'config@17')+'\n')
  member(f'profiles/{model}/mtd.tsv',''.join(rows))
  member(f'profiles/{model}/source-sets/runtime-implementation.set',f'F {sha(root/"etc/version")} /etc/version\n')
  (bundle/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(bundle)}\n' for p in sorted(bundle.rglob('*')) if p.is_file()))
  # Exact environment API; no real fwtools. All destructive tools remain the
  # inherited refusal sentinels; successful preflight cannot execute them.
  fw=capture.bin/'fw_printenv'
  fw.write_text('#!/bin/sh\n[ "${CRC_WARN:-}" != 1 ] || echo "Warning: Bad CRC, using default environment" >&2\nif [ "$3" = -n ]; then cat "$FIXTURE/environment/$4"; else printf "image=%s\\nbootcmd=bootipq\\nfactory_mac=000456abcdef\\n" "$(cat "$FIXTURE/environment/image")"; fi\n')
  fw.chmod(0o755)
  for name in ('ubirmvol','ubimkvol'):
   p=capture.bin/name;p.write_text('#!/bin/sh\necho forbidden >> "$FIXTURE/MUTATOR_INVOKED"\nexit 77\n');p.chmod(0o755)
  return root,bundle,work,capture.bin,model,sku
 def invoke(self,case,phase='inspect',extra=None):
  root,bundle,work,bin,model,sku=case
  before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
  script='. "$COMMON"; . "$PROTECTION"; . "$ADAPTER"; if [ "$PHASE" = detect ]; then oem_sage_detect; exit $?; fi; oem_adapter_inspect || exit 1; [ "$PHASE" != preflight ] || oem_adapter_preflight\n'
  env=dict(os.environ,LC_ALL='C',PATH=str(bin)+':'+os.environ['PATH'],FIXTURE=str(root),OEM_SYS_ROOT=str(root),OEM_BUNDLE=str(bundle),OEM_WORK=str(work),OEM_FAMILY='sage',OEM_MODEL=model,OEM_SKU=f'{sku:08x}',OEM_SUPPORTED_RELEASE='4.2.3.3-r10',COMMON=str(HERE/'lib/common.sh'),PROTECTION=str(HERE/'lib/protection.sh'),ADAPTER=str(HERE/'adapters/sage.sh'),PHASE=phase)
  env.update(extra or {})
  command=['sh']+(['-x'] if os.environ.get('SAGE_FIXTURE_TRACE') else [])+['-c',script]
  result=subprocess.run(command,env=env,capture_output=True,text=True)
  self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
  self.assertFalse((root/'MUTATOR_INVOKED').exists())
  return result
 def test_both_exact_models_both_slots_actual_readers_and_range_preflight(self):
  for model in ('E410','E410B'):
   for slot in (0,1):
    with self.subTest(model=model,slot=slot):
     r=self.invoke(self.setup_case(model,slot),'preflight');self.assertEqual(r.returncode,0,r.stderr)
 def test_unknown_old_new_duplicate_source_versions_refuse_before_mutation(self):
  case=self.setup_case();root=case[0]
  for text in ('PRODUCT=sage\nVERSION=4.2.3.1-r17\n','PRODUCT=sage\nVERSION=4.2.3.4-r1\n','PRODUCT=sage\nVERSION=4.2.3.3-r10\nVERSION=4.2.3.3-r10\n','PRODUCT=sage\n'):
   (root/'etc/version').write_text(text);self.assertNotEqual(self.invoke(case).returncode,0)
 def test_bad_crc_alias_wrong_parent_readonly_and_hidden_partition_refuse(self):
  for failure in ('crc','alias','parent','readonly','hidden','overlap'):
   case=self.setup_case();root=case[0];extra={}
   if failure=='crc':extra['CRC_WARN']='1'
   if failure=='alias':
    p=root/'sys/class/ubi/ubi1';p.mkdir();(p/'mtd_num').write_text('9\n')
   if failure=='parent':(root/'sys/class/ubi/ubi0/mtd_num').write_text('4\n')
   if failure=='readonly':(root/'sys/class/mtd/mtd9/flags').write_text('0x800\n')
   if failure=='hidden':
    p=root/'sys/class/mtd/mtd10';p.mkdir();(p/'name').write_text('unknown-unique');(p/'type').write_text('nor')
   if failure=='overlap':(root/'sys/class/mtd/mtd9/device').unlink();(root/'sys/class/mtd/mtd9/device').symlink_to(root/'chips/nor0')
   r=self.invoke(case,'preflight',extra);self.assertNotEqual(r.returncode,0,failure)
 def test_sibling_model_and_factory_sku_disagreement_refuse(self):
  for model,sku in [('E600',11),('E430W',13),('E700',14),('E430H',15),('E510',16),('E410',21)]:
   r=self.invoke(self.setup_case(),extra={'OEM_MODEL':model,'OEM_SKU':f'{sku:08x}'});self.assertNotEqual(r.returncode,0)
 def test_factory_detection_no_case_or_capacity_inference(self):
  for model,reported in [('E410',''),('E410','0000000a'),('E410B',''),('E410B','00000015'),('E410B','0000000a')]:
   case=self.setup_case(model);r=self.invoke(case,'detect',{'OEM_SKU':reported})
   self.assertEqual(r.returncode,0,r.stderr)
   self.assertEqual(r.stdout.strip(),('0000000a' if model=='E410' else '00000015')+'\t'+model)
  self.assertNotEqual(self.invoke(self.setup_case(),'detect',{'OEM_REPORTED_SKU':'00000015'}).returncode,0)
 def test_factory_duplicate_product_invalid_header_and_multicast_label_refuse(self):
  for failure in ('duplicate','header','multicast'):
   case=self.setup_case();mfg=case[0]/'dev/mtd6ro';data=mfg.read_bytes()
   if failure=='duplicate':data+=b'\0PL-E410XXXB-EU\0'
   if failure=='header':data=b'BADHDR'+data[6:]
   if failure=='multicast':data=data[:6]+b'010456abcdef'+data[18:]
   mfg.write_bytes(data);self.assertNotEqual(self.invoke(case,'detect').returncode,0)

if __name__=='__main__':unittest.main()
