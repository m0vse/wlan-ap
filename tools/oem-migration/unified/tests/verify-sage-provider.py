#!/usr/bin/env python3
"""Actual provider validation; requires separately retained private assets.

Uses real signed-vendor runtime bytes, actual current image/profile/pin inputs
and actual forward writer/FORMAT2/boot shell. Flash, ENV, mount, UBI and UID
boundaries are disposable actors. Never executes target ELF or accesses an AP.
"""
from pathlib import Path
import importlib.util,hashlib,json,shutil,tarfile,unittest
import argparse
parser=argparse.ArgumentParser(description='Verify actual Sage provider inputs using disposable device/ENV/mount actors; no AP or external network.')
parser.add_argument('provider',type=Path)
parser.add_argument('reviewed_oem_tar',type=Path)
args=parser.parse_args()
REPO=Path(__file__).resolve().parents[4]
BASE=REPO/'tools/oem-migration/unified'
spec=importlib.util.spec_from_file_location('forward',BASE/'tests/test-sage-forward.py');forward=importlib.util.module_from_spec(spec);spec.loader.exec_module(forward)
PROVIDER=args.provider.resolve(strict=True)
TAR=args.reviewed_oem_tar.resolve(strict=True)

class ActualProviderTests(forward.ForwardTests):
 def fixture(self,model='E410',slot=0):
  case=super().fixture(model,slot);root,bundle,work,bin,model,sku=case
  mfg=(root/'dev/mtd6ro').read_bytes()
  # Runtime files are actual verified vendor bytes; no target ELF is executed.
  assert hashlib.sha256(TAR.read_bytes()).hexdigest()=='58b26e51f393be45db5437db454a510c81379a277b1cff373e414f6678df89cf'
  with tarfile.open(TAR) as tar:
   members={m.name.removeprefix('./').rstrip('/'):m for m in tar.getmembers()}
   for row in (PROVIDER/f'profiles/{model}/source-sets/runtime-implementation.set').read_text().splitlines():
    kind,pin,name=row.split();path=root/name.lstrip('/')
    if kind=='A':continue
    member=members[name.lstrip('/')];path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() or path.is_symlink():path.unlink()
    if kind=='L':path.symlink_to(member.linkname)
    else:path.write_bytes(tar.extractfile(member).read());path.chmod(member.mode)
  shutil.rmtree(root/'sys/class/mtd');(root/'sys/class/mtd').mkdir()
  for path in (root/'dev').glob('mtd*'):path.unlink()
  proc=[]
  for index,row in enumerate((PROVIDER/f'profiles/{model}/mtd.tsv').read_text().splitlines()):
   name,domain,offset,size,kind,erase,write,role=row.split('\t');node=root/f'sys/class/mtd/mtd{index}';node.mkdir()
   for key,value in dict(name=name,offset=offset,size=size,type=kind,erasesize=erase,writesize=write,flags='0xc00').items():(node/key).write_text(value+'\n')
   (node/'device').symlink_to(root/'chips'/domain)
   data=mfg if name=='mfginfo' else bytes([index])*int(size) if int(size)<=524288 else b'inert physical chip actor'
   (root/f'dev/mtd{index}ro').write_bytes(data)
   proc.append(f'mtd{index}: {int(size):08x} {int(erase):08x} "{name}"\n')
   if name=='fs':(root/'sys/class/ubi/ubi0/mtd_num').write_text(str(index)+'\n')
   if name=='0:APPSBLENV':env_index=index
  (root/'proc/mtd').write_text(''.join(proc));(root/'etc/fw_env.config').write_text(f'/dev/mtd{env_index} 0x0 0x10000 0x10000 1\n')
  shutil.rmtree(bundle/f'profiles/{model}');shutil.copytree(PROVIDER/f'profiles/{model}',bundle/f'profiles/{model}')
  shutil.rmtree(bundle/f'payloads/{model}');shutil.copytree(PROVIDER/f'payloads/{model}',bundle/f'payloads/{model}')
  for path in (PROVIDER/'readers/sage').iterdir():shutil.copyfile(path,bundle/'readers/sage'/path.name)
  critical=work/'critical'
  for row in (PROVIDER/f'profiles/{model}/critical-backup.tsv').read_text().splitlines():
   kind,name,size,reason=row.split('\t');index=next(i for i,r in enumerate(proc) if r.endswith('"'+name+'"\n'))
   path=critical/(kind+'.bin');path.write_bytes((root/f'dev/mtd{index}ro').read_bytes());path.chmod(0o600)
  (critical/'manifest.tsv').write_bytes((PROVIDER/f'profiles/{model}/critical-backup.tsv').read_bytes())
  (critical/'SHA256SUMS').write_text(''.join(hashlib.sha256((critical/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in ('ENV.bin','ART.bin','MFG.bin','manifest.tsv')))
  (critical/'OFFDEVICE_VERIFIED').write_text(hashlib.sha256((critical/'SHA256SUMS').read_bytes()).hexdigest()+'\n')
  for path in critical.iterdir():path.chmod(0o600)
  (bundle/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file() and p.name!='SHA256SUMS'))
  return case

 def test_actual_provider_source_and_payload_refusals(self):
  for fault in ('source-version','kernel-bytes'):
   with self.subTest(fault=fault):
    case=self.fixture();root,bundle,work,*rest=case
    if fault=='source-version':(root/'etc/version').write_text('PRODUCT=sage\nVERSION=4.2.3.1-r17\n')
    else:
     path=bundle/'payloads/E410/kernel.itb';data=path.read_bytes();path.write_bytes(b'BAD!'+data[4:])
    result=self.invoke(case)
    self.assertNotEqual(result.returncode,0)
    self.assertFalse((root/'events').exists())


suite=unittest.TestSuite([ActualProviderTests('test_both_models_slots_actual_writer_format2_then_arm'),ActualProviderTests('test_actual_provider_source_and_payload_refusals')])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
