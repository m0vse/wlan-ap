#!/usr/bin/env python3
"""Actual shared-core/family/country policies with isolated synthetic storage."""
from pathlib import Path
import argparse,subprocess,tempfile,os,struct,json,re,shutil
p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--ucode');p.add_argument('--capabilities',type=Path);a=p.parse_args()
repo=Path(__file__).resolve().parents[3]
with tempfile.TemporaryDirectory(prefix='miami-storage-source-') as td:
 root=Path(td);modules=root/'modules';modules.mkdir();module=repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh';shutil.copy2(module,modules/module.name)
 (root/'dt/cambium-platform').mkdir(parents=True);(root/'dt/cambium-platform/board-sku').write_bytes(struct.pack('>I',44));slot=root/'dt/cambium-platform/storage-slot';slot.write_bytes(struct.pack('>I',0))
 (root/'mtd').mkdir();(root/'ubi/ubi0').mkdir(parents=True);(root/'ubi/ubi0/mtd_num').write_text('2\n')
 mtdrows=[]
 for idx,name,size in [(2,'rootfs',0x6000000),(3,'rootfs_1',0x6000000),(18,'0:APPSBLENV',65536),(4,'0:NVRAM',0x2f40000),(5,'crashLog',0x1000000),(6,'0:ART',0x100000),(7,'mfginfo',65536),(8,'0:SBL1',0x80000),(9,'0:SBL1_1',0x80000),(10,'0:APPSBL',0xa0000),(11,'0:APPSBL_1',0xa0000)]:
  d=root/f'mtd/mtd{idx}';d.mkdir();(d/'type').write_text('nand' if idx in (2,3,4,5) else 'nor');(d/'flags').write_text('0xc00' if idx in (2,18) else '0x800');mtdrows.append(f'mtd{idx}: {size:08x} '+('00020000' if idx in (2,3) else '00010000')+f' "{name}"')
 (root/'proc-mtd').write_text('\n'.join(mtdrows)+'\n');(root/'cmdline').write_text('console=ttyMSM0,115200n8 ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs rootwait\n')
 for idx,name in enumerate(['kernel','rootfs','rootfs_data','cambium_device_data','certificates']):
  d=root/f'ubi/ubi0_{idx}';d.mkdir();(d/'name').write_text(name+'\n');(d/'reserved_ebs').write_text('64\n' if idx==4 else '72\n')
 mounts=root/'mounts';mounts.write_text('/dev/ubi0_4 /certificates ubifs rw,relatime 0 0\n')
 (root/'bin').mkdir();hexdump=root/'bin/hexdump';hexdump.write_text('#!/usr/bin/env python3\nimport pathlib,sys\nprint(pathlib.Path(sys.argv[-1]).read_bytes().hex(),end="")\n');hexdump.chmod(0o755)
 env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'],CAMBIUM_AB_MODULES=str(modules),AB_DT=str(root/'dt'),AB_PROC_MTD=str(root/'proc-mtd'),AB_CMDLINE=str(root/'cmdline'),AB_UBI_SYS=str(root/'ubi'),AB_MTD_SYS=str(root/'mtd'),AB_PROC_MOUNTS=str(mounts))
 prelude=f'board_name() {{ echo cambiumnetworks,x7-35x; }}; get_mac_label_dt() {{ echo "${{TEST_DT_MAC:-02:11:22:33:44:66}}"; }}; get_mac_label() {{ echo "${{TEST_NATIVE_MAC:-02:11:22:33:44:66}}"; }}; . "{a.core}/cambium-ab.sh"; '
 def check(code,ok=True,extra=None):
  r=subprocess.run(['sh','-c',prelude+code],env=dict(env,**(extra or {})),capture_output=True,text=True);assert (r.returncode==0)==ok,(r.stdout,r.stderr,code);return r.stdout
 check('ab_identity && ab_miami_storage_context && ab_miami_certificate_mount')
 for value in ['00:00:00:00:00:00','ff:ff:ff:ff:ff:ff','01:11:22:33:44:66','00:11:22:33:44:55','bad']:
  check('ab_identity && ab_miami_storage_context',False,{'TEST_DT_MAC':value,'TEST_NATIVE_MAC':value})
 check('ab_identity && ab_miami_storage_context',False,{'TEST_NATIVE_MAC':'02:11:22:33:44:77'})
 slot.write_bytes(struct.pack('>I',1));check('ab_identity && ab_miami_storage_context',False);slot.write_bytes(struct.pack('>I',0))
 (root/'mtd/mtd3/flags').write_text('0xc00');check('ab_identity && ab_miami_storage_context',False);(root/'mtd/mtd3/flags').write_text('0x800')
 for table in ['/dev/ubi9_4 /certificates ubifs rw 0 0\n','/dev/ubi0_4 /certificates ubifs ro 0 0\n','/dev/ubi0_4 /certificates ubifs rw 0 0\n/dev/ubi0_2 /certificates/child ubifs rw 0 0\n']:
  mounts.write_text(table);check('ab_identity && ab_miami_certificate_mount',False)
 mounts.write_text('/dev/ubi0_4 /certificates ubifs rw 0 0\n')
 (root/'ubi/ubi0_4/reserved_ebs').write_text('20');check('ab_identity && ab_miami_certificate_mount',False);(root/'ubi/ubi0_4/reserved_ebs').write_text('64')
 # Reverse slot mapping uses its own DTS policy and the same guarded contract.
 slot.write_bytes(struct.pack('>I',1));(root/'cmdline').write_text('ubi.mtd=rootfs_1 root=/dev/ubiblock0_1 rootfstype=squashfs rootwait\n');(root/'ubi/ubi0/mtd_num').write_text('3\n')
 (root/'mtd/mtd2/flags').write_text('0x800');(root/'mtd/mtd3/flags').write_text('0xc00')
 check('ab_identity && ab_miami_storage_context && ab_miami_certificate_mount')
 check('ab_identity && ab_miami_boot_command 1 | grep -F "0x60c0000(fs)"')
 check('ab_identity && ab_miami_boot_command 1 | grep -F "ubi.mtd=rootfs_1 root=/dev/ubiblock0_1"')
 slot.write_bytes(struct.pack('>I',0));(root/'cmdline').write_text('ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs rootwait\n');(root/'ubi/ubi0/mtd_num').write_text('2\n')
 (root/'mtd/mtd2/flags').write_text('0xc00');(root/'mtd/mtd3/flags').write_text('0x800')
 # Current generated core already contains the certificate policy; older
 # supplied base source may be replayed in an isolated copy.
 policy=(a.core/'cambium-ab-upgrade.sh').read_text()
 if '64-LEB policy requires exact Miami model' not in policy:
  copied=root/'patch-tree/package/cambium/cambium-ab';(copied/'files').mkdir(parents=True)
  for name in ['cambium-ab-upgrade.sh','cambium-ab-certificates.sh','cambium-return-oem']:shutil.copy2(a.core/name,copied/'files'/name)
  shutil.copy2(a.core.parent/'Makefile',copied/'Makefile')
  r=subprocess.run(['patch','--fuzz=0','-p1','-i',str(repo/'patches-25.12/0164-cambium-ab-miami-certificate-capacity.patch')],cwd=root/'patch-tree',capture_output=True,text=True);assert r.returncode==0,(r.stdout,r.stderr)
  policy=(copied/'files/cambium-ab-upgrade.sh').read_text()
 start=policy.index('ab_certificate_lebs() {');end=policy.index('\n}\n',start)+3;func=policy[start:end]
 for family,model,lebs,ok in [('miami','X7-35X',64,True),('jaguar','XV2-2',20,True),('sage','E410',0,True),('thor','XV3-8',64,False),('miami','X7-other',64,False),('miami','X7-35X',63,False)]:
  r=subprocess.run(['sh','-c','ab_fail(){ :; }; '+func+'\nAB_FAMILY=$1; AB_MODEL=$2; AB_CERTIFICATE_LEBS=$3; ab_certificate_lebs','fixture',family,model,str(lebs)],capture_output=True,text=True);assert (r.returncode==0)==ok
  if ok:assert r.stdout.strip()==str(lebs)
 # Read-only country resolver: actual function body, protected context mocked
 # only after the core/context tests above establish its refusals.
 for path in ['etc/ucentral','certificates']:(root/path).mkdir(parents=True,exist_ok=True)
 (root/'etc/ucentral/country').write_text('GB\n');(root/'etc/ucentral/ucentral.defaults').write_text('{"country":"GB"}')
 helper=(repo/'feeds/tip/cambium-miami-persistent/files/miami-country-defaults').read_text()
 helper=helper.replace('. /lib/functions/system.sh\n. /lib/functions/cambium-ab.sh', 'ab_identity(){ :; }; ab_miami_storage_context(){ :; }; ab_miami_certificate_mount(){ :; }; AB_FAMILY=miami; AB_MODEL=X7-35X; AB_CERTIFICATE_LEBS=64')
 helper=helper.replace('/etc/ucentral/',str(root/'etc/ucentral')+'/').replace('/certificates/',str(root/'certificates')+'/')
 # Stub only JSON parsing with Python, real helper still owns file/path checks.
 jf=root/'bin/jsonfilter';jf.write_text('#!/usr/bin/env python3\nimport json,sys\nprint(json.load(open(sys.argv[sys.argv.index("-i")+1]))["country"])\n');jf.chmod(0o755)
 def country(ok=True):
  before={str(p):p.read_bytes() for p in (root/'certificates').rglob('*') if p.is_file()};r=subprocess.run(['sh','-c',helper],env=env,capture_output=True,text=True);assert (r.returncode==0)==ok,(r.stdout,r.stderr);assert before=={str(p):p.read_bytes() for p in (root/'certificates').rglob('*') if p.is_file()}
  if ok:assert r.stdout.strip()=='GB'
 country();assert list((root/'certificates').iterdir())==[]
 (root/'certificates/unknown').write_text('must remain');country()
 (root/'certificates/ucentral.defaults').write_text('{"country":"GB"}');country()
 (root/'certificates/ucentral.defaults').write_text('{"country":"US"}');country(False)
 (root/'certificates/ucentral.defaults').write_text('not json');country(False)
 (root/'certificates/ucentral.defaults').unlink();(root/'certificates/ucentral.defaults').symlink_to(root/'etc/ucentral/ucentral.defaults');country(False)
print('PASS: actual family/core active bank and protected storage context; legal native label identity; exact active64 certificate mount; wrong bank/RO/child/size refusal; policy0/20 unchanged and64 Miami-only; actual country helper no store writes/unknown preservation/conflict refusal')
