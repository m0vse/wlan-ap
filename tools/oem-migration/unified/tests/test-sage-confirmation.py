#!/usr/bin/env python3
"""Actual defaults + adapter confirm: synthetic devices, transport/vendor hashes.
No AP/flash/network/vendor script execution; full OEM runtime closure not proved.
"""
from pathlib import Path
import hashlib
import os
import subprocess
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
REPO=HERE.parents[2]
READERS=REPO/'tools/oem-migration/recovery/scripts'
sys.path.insert(0,str(READERS/'tests'))
import test_cambium_sage_oem_deferred as deferred

class ConfirmationTests(unittest.TestCase):
 def fixture(self,slot):
  holder=deferred.DeferredTests();case,extra=holder.fixture(slot);self.addCleanup(holder.doCleanups)
  root,f=case.r,case.f;target=1-slot
  f.put('dev/mtd8ro',(bytes.fromhex('05ca01000c00')+b'000456abcdef\0PL-E410XXXA-EU\0').ljust(65536,b'\0'))
  for identifier,original in ((2*target,'kernel'),(2*target+1,'rootfs')):f.put(f'dev/ubi0_{identifier}',(root/original).read_bytes())
  f.put('etc/version','PRODUCT=sage\nVERSION=4.2.3.3-r10\n')
  f.put('etc/fw_env.config','/dev/mtd5 0x0 0x00010000 0x00010000 1\n')
  f.put('dev/urandom',bytes(range(32)))
  f.put('proc/cmdline',f'ubi.mtd=fs root=ubi0:rootfs{target} rootfstype=ubifs rw\n')
  f.put('env-snapshot',f'image={slot}\nbootcmd=run sage_boot{slot}\nsage_ab_state=trial-started\nsage_ab_confirmed={slot}\nsage_ab_target={target}\nsage_boot{slot}={case.source_boot}\nsage_boot{target}=setenv image {target}; bootipq\nsage_oem_restore_target={target}\nsage_oem_restore_state=armed\nethaddr=00:04:56:ab:cd:ef\nserial#=keep-factory\n')
  f.put('proc/mtd',(root/'proc-mtd').read_bytes())
  (root/'sys/class').mkdir(parents=True);(root/'sys/class/mtd').symlink_to(f.mtd);(root/'sys/class/ubi').symlink_to(f.sys)
  for domain in ('nor0','nand0'):(root/'chips'/domain).mkdir(parents=True)
  rows=[]
  for index,name,offset,size,domain,role in ((5,'0:APPSBLENV',0,65536,'nor0','environment'),(7,'0:ART',65536,65536,'nor0','identity'),(8,'mfginfo',131072,65536,'nor0','identity'),(10,'config',196608,65536,'nor0','nonunique-config'),(6,'0:APPSBL',262144,524288,'nor0','bootcode'),(11,'fs',0,134217728,'nand0','shared-parent')):
   erase,write=(131072,2048) if domain=='nand0' else (65536,1)
   for key,value in dict(name=name,offset=offset,size=size,type=domain[:-1],erasesize=erase,writesize=write,flags='0x800' if index==10 else '0xc00').items():f.put(f'mtd/mtd{index}/{key}',str(value))
   (f.mtd/f'mtd{index}/device').symlink_to(root/'chips'/domain)
   rows.append(f'{name}\t{domain}\t{offset}\t{size}\t{domain[:-1]}\t{erase}\t{write}\t{role}\n')
  for identifier in (0,1,2,3,4,6,7):f.put(f'ubi/ubi0_{identifier}/corrupted','0')
  bundle=root/'bundle';bundle.mkdir()
  def member(name,data):
   path=bundle/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data.encode() if isinstance(data,str) else data);path.chmod(0o600)
  for name in ('cambium-sage-pair-write.sh','cambium-installer-settings.sh','cambium-sage-oem-reset.sh','cambium-sage-oem-recovery.sh','cambium-sage-oem-defaults.sh'):member('lib/'+name,(READERS/'lib'/name).read_bytes())
  member('lib/runtime-implementation-contract.sh',(REPO/'tests/installer/common-minimum-v1/runtime-implementation-contract.sh').read_bytes())
  member('adapters/required-source.sh',(HERE/'adapters/required-source.sh').read_bytes())
  member('adapters/sage.sh',(HERE/'adapters/sage.sh').read_bytes())
  profile='profiles/E410/restore/'
  member(profile+'confirm/source-contract','4.2.3.3-r10\n'+'a'*64+'\n')
  member(profile+'confirm/source-sets/runtime-implementation.set','F '+hashlib.sha256((root/'etc/version').read_bytes()).hexdigest()+' /etc/version\n')
  member(profile+'mtd.tsv',''.join(rows));member(profile+f'source-boot{slot}.sha256',hashlib.sha256(case.source_boot.encode()).hexdigest()+'\n')
  for original,final in (('kernel','kernel.itb'),('rootfs','rootfs.ubifs'),('shared-manifest','shared.json')):member('payloads/E410/oem/'+final,(root/original).read_bytes())
  member(profile+'operator-artifact-pins',''.join(hashlib.sha256((root/name).read_bytes()).hexdigest()+'\n' for name in ('kernel','rootfs','shared-manifest')))
  member(profile+'critical-backup.tsv','ENV\t0:APPSBLENV\t65536\tunique-env\nART\t0:ART\t65536\tcalibration\nMFG\tmfginfo\t65536\tfactory\n')
  (bundle/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n' for p in sorted(bundle.rglob('*')) if p.is_file()))
  work=root/'work';work.mkdir(mode=0o700)
  setter=f.bin/'fw_setenv';setter.write_text(setter.read_text().replace('k,v=row.split(" ",1);s[k]=v','a=row.split(" ",1)\n  if len(a)==1:s.pop(a[0],None)\n  else:s[a[0]]=a[1]'))
  return case,bundle,work
 def invoke(self,fixture,fault=''):
  case,bundle,work=fixture
  env=dict(os.environ,PATH=str(case.f.bin)+':'+os.environ['PATH'],LC_ALL='C',FIXTURE=str(case.r),LIB=str(READERS/'lib'),HERE=str(HERE),OEM_BUNDLE=str(bundle),OEM_SYS_ROOT=str(case.r),OEM_WORK=str(work),OEM_FAMILY='sage',OEM_MODEL='E410',OEM_SKU='0000000a',OEM_SUPPORTED_RELEASE='4.2.3.3-r10',FAULT=fault)
  script=r'''
. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/lib/critical-backup.sh"
. "$HERE/adapters/restore-sage.sh"
oem_restore_confirm_inspect || exit 1
csr_is_device() { [ -f "$1" ]; }
csr_hash() { if [ "$1" = "$CSR_DEV/mtd6ro" ]; then echo 066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1; else sha256sum < "$1" | awk '{print $1}'; fi; }
id() { echo 0; }
oem_sha() {
 case "$1" in
  */usr/bin/scripts/delconfig.sh) [ "$FAULT" != vendor ] && echo 4fb70585e9abfae317899a78ce7e988895731a58899b477e16156a28437fcd09;;
  */usr/bin/scripts/savecfg2nor.sh) echo f71c829e276e500c88d86cc812e6e90f2e39bd464fe9a2b45704018f951520d0;;
  */usr/bin/scripts/savecfgfromnnand.sh) echo a1f72635074c3fe4dd498ae3d75953512481d8843ecbc5c3c006f94fb1fe0644;;
  *) sha256sum < "$1" | awk '{print $1}';;
 esac
}
oem_backup_capture() {
 [ "$FAULT" != backup ] || return 1
 mkdir -m 700 "$4" || return 1
 cp "$CSR_DEV/mtd5ro" "$4/ENV.bin"; cp "$CSR_DEV/mtd7ro" "$4/ART.bin"; cp "$CSR_DEV/mtd8ro" "$4/MFG.bin"
 cp "$1" "$4/manifest.tsv"; chmod 600 "$4/"*
 (cd "$4" && sha256sum ./*.bin manifest.tsv > SHA256SUMS); chmod 600 "$4/SHA256SUMS"
}
oem_backup_upload() {
 [ "$FAULT" != upload ] || return 1
 oem_sha "$1/SHA256SUMS" > "$1/OFFDEVICE_VERIFIED"; chmod 600 "$1/OFFDEVICE_VERIFIED"
}
oem_restore_confirm_preflight && oem_restore_confirm
'''
  return subprocess.run(['sh']+(['-x'] if os.environ.get('SAGE_CONFIRM_TRACE') else [])+['-c',script],env=env,capture_output=True,text=True)
 def test_confirm_both_oem_slots_changes_only_reviewed_environment(self):
  for source in (0,1):
   fixture=self.fixture(source);case=fixture[0];protected={p:p.read_bytes() for p in case.f.dev.iterdir()}
   result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
   self.assertEqual(protected,{p:p.read_bytes() for p in protected})
   values=dict(row.split('=',1) for row in (case.r/'env-snapshot').read_text().splitlines())
   self.assertEqual(values['bootcmd'],'bootipq');self.assertEqual(values['image'],str(1-source));self.assertEqual(values['serial#'],'keep-factory')
   self.assertNotIn('sage_oem_restore_state',values);self.assertEqual((case.r/'operations').read_text().splitlines(),['ENV_BATCH'])
   self.assertIn('Separate explicit factory-reset action',result.stdout)
 def test_failed_vendor_backup_upload_or_selector_never_reports_confirmed(self):
  for fault in ('vendor','backup','upload','batch'):
   fixture=self.fixture(0);original=(fixture[0].r/'env-snapshot').read_bytes();result=self.invoke(fixture,fault)
   self.assertNotEqual(result.returncode,0);self.assertEqual(original,(fixture[0].r/'env-snapshot').read_bytes());self.assertNotIn('OEM confirmed',result.stdout)
 def test_actual_write_boundary_accepts_only_target_child_requests(self):
  for source in (0,1):
   case,bundle,work=self.fixture(source)
   target=1-source
   plan=work/'plan.tsv';plan.write_text(f'ubi-update\t11\t{2*target}\tlinux{target}\nubi-update\t11\t{2*target+1}\trootfs{target}\n')
   env=dict(os.environ,PATH=str(case.f.bin)+':'+os.environ['PATH'],HERE=str(HERE),OEM_BUNDLE=str(bundle),OEM_SYS_ROOT=str(case.r),OEM_WORK=str(work),OEM_MODEL='E410',OEM_SOURCE_SLOT=str(source),OEM_TARGET_SLOT=str(target),PLAN=str(plan))
   script=r'''
. "$HERE/lib/common.sh"; . "$HERE/lib/protection.sh"; . "$HERE/adapters/restore-sage.sh"
CSR_MTD_SYS=$OEM_SYS_ROOT/sys/class/mtd
CSP_SYS=$OEM_SYS_ROOT/sys/class/ubi; CSP_FS_MTD=11
OEM_PROTECTED_RANGES=$OEM_WORK/ranges.tsv; OEM_WRITE_PLAN=$PLAN
oem_restore_sage_write_check ubi-update "$((2*OEM_TARGET_SLOT))" || exit 1
! oem_restore_sage_write_check ubi-update "$((2*OEM_SOURCE_SLOT))" || exit 1
! oem_restore_sage_write_check ubi-update 4 || exit 1
'''
   result=subprocess.run(['sh','-c',script],env=env,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertFalse((case.r/'operations').exists())
 def test_normal_oem_root_activity_not_golden_image_equality_after_boot(self):
  fixture=self.fixture(0)
  fixture[0].f.put('dev/ubi0_3',b'legitimate OEM UBIFS firstboot journal/config changes')
  result=self.invoke(fixture);self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn('OEM confirmed',result.stdout)
 def test_wrong_running_root_changed_runtime_or_kernel_refuses_confirmation(self):
  for path,data in (('proc/cmdline','ubi.mtd=fs root=ubi0:rootfs0 rootfstype=squashfs\n'),('etc/version','PRODUCT=sage\nVERSION=4.2.3.4-r1\n'),('dev/ubi0_2',b'wrong deployed kernel')):
   fixture=self.fixture(0);fixture[0].f.put(path,data)
   result=self.invoke(fixture);self.assertNotEqual(result.returncode,0)
   self.assertFalse((fixture[0].r/'operations').exists())

if __name__=='__main__':unittest.main()
