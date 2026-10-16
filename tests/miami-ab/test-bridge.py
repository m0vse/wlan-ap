#!/usr/bin/env python3
"""Actual cross-boot validator; synthetic bank reads, real sealed archive/key.
No flash/ENV tools or live identity. Never grants ordinary boot the old-ID hook.
"""
from pathlib import Path
import tempfile,subprocess,os,json,hashlib,tarfile
repo=Path(__file__).resolve().parents[2]
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with tempfile.TemporaryDirectory(prefix='miami-bridge-test-') as td:
 r=Path(td).resolve();store=r/'store';store.mkdir(mode=0o700);bin=r/'bin';bin.mkdir();dt=r/'dt/cambium-platform';dt.mkdir(parents=True);ubi=r/'ubi/ubi0';ubi.mkdir(parents=True);dev=r/'dev';dev.mkdir()
 (dt/'boot-mode').write_bytes(b'bridge\0');(dt/'storage-slot').write_bytes(bytes(4));(ubi/'mtd_num').write_text('2')
 (dev/'ubi0_0').write_bytes(b'qualified source kernel');(dev/'ubi0_1').write_bytes(b'qualified source root')
 (dev/'ubi0_5').write_bytes(b'qualified bridge FIT')
 (r/'mounts').write_text('tmpfs / tmpfs rw 0 0\n');(r/'cmdline').write_text('ubi.mtd=rootfs miami.bridge='+('a'*64))
 from prepare_source import prepare_package
 cert=prepare_package(repo,r/'prepared')/'files/cambium-ab-certificates.sh'
 key=r/'key.pem';subprocess.run(['openssl','genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:P-256','-out',str(key)],check=True,capture_output=True)
 before_spki=subprocess.check_output(['openssl','pkey','-in',str(key),'-pubout','-outform','DER'])
 archive=store/'certificates.tar'
 with tarfile.open(archive,'w') as t:t.add(key,arcname='./key.pem')
 archive.chmod(0o600)
 descriptor=store/'certificates.descriptor';boot='12345678-1234-1234-1234-123456789abc';binding=boot+':miami:X7-35X:0000002c:0:1:2:3'
 descriptor.write_text(binding+'\n'+h(archive)+'\n');descriptor.chmod(0o600)
 kernelsha='9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b';rootsha='1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9'
 ticket={'format':1,'nonce':'a'*64,'family':'miami','model':'X7-35X','sku':'0000002c','source_slot':0,'target_slot':1,'source_mtd':2,'target_mtd':3,'serial':'020000000001','source_boot_id':boot,'source_release':'b6d1a26f','source_kernel_sha':kernelsha,'source_root_sha':rootsha}
 tp=store/'ticket.json';ep=r/'env.json';rp=r/'binding';rp.write_text(binding)
 tool='''#!/usr/bin/env python3
import sys,json,hashlib
from pathlib import Path
if Path(sys.argv[0]).name=='jsonfilter':
 a=sys.argv;print(json.loads(Path(a[a.index('-i')+1]).read_text())[a[a.index('-e')+1][2:]])
else:
 if len(sys.argv)==1:
  data=sys.stdin.buffer.read();pins={b'qualified source kernel':'KERNEL',b'qualified source root':'ROOT'}
  print(pins.get(data,hashlib.sha256(data).hexdigest())+'  -')
 else:
  p=Path(sys.argv[1]);print(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p))
'''.replace("'KERNEL'",repr(kernelsha)).replace("'ROOT'",repr(rootsha))
 for name in ['sha256sum','jsonfilter']:
  f=bin/name;f.write_text(tool);f.chmod(0o755)
 ls=bin/'ls';ls.write_text('#!/usr/bin/env python3\nimport os,sys,stat\np=sys.argv[-1];s=os.lstat(p);print(stat.filemode(s.st_mode),s.st_nlink,s.st_uid,s.st_gid,s.st_size,p)\n');ls.chmod(0o755)
 # Keep all snapshot-content validation real except the physical bank boundary.
 script='''
AB_FAMILY=miami AB_MODEL=X7-35X AB_SKU=0000002c AB_ACTIVE=0 AB_TARGET=1 AB_ACTIVE_MTD=2 AB_TARGET_MTD=3 AB_ACTIVE_UBI=ubi0 AB_LAYOUT=banks AB_LEB=126976
ab_identity(){ :; };ab_miami_ab_profile(){ :; };ab_miami_upgrade_geometry(){ [ "$FAIL" != geometry ]; }
ab_miami_label_identity(){ [ "$FAIL" != mac ]; };get_mac_label_dt(){ echo 02:00:00:00:00:01; }
ab_getenv(){ python3 -c 'import json,sys,os;print(json.load(open(os.environ["ENV_FILE"])).get(sys.argv[1],""))' "$1"; }
ab_ubi_volume(){ case "$2" in kernel) echo ubi0_0;;rootfs) echo ubi0_1;;miami_ab_bridge) echo ubi0_5;;*) return 1;;esac; }
ab_miami_slot_command(){ echo qualified-prior-command; }
ab_certificate_lebs(){ echo 64; };ab_fail(){ return 1; }
. "$CERT_LIB"
. "$BRIDGE_LIB"
AB_BOOT_ID=stale-authority AB_MIAMI_BRIDGE_VALIDATED=1
ab_miami_bridge_validate
rc=$?
if [ "$rc" != 0 ];then [ -z "${AB_BOOT_ID:-}${AB_MIAMI_BRIDGE_VALIDATED:-}" ] || exit 99;exit 1;fi
[ "$AB_MIAMI_BRIDGE_VALIDATED" = 1 ] && [ "$(cat "$AB_BOOT_ID")" = "$EXPECTED_BOOT" ]
'''
 env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH'],'ENV_FILE':str(ep),'AB_DT':str(dt.parent),'AB_UBI_SYS':str(ubi.parent),'AB_DEV':str(dev),'AB_CMDLINE':str(r/'cmdline'),'AB_PROC_MOUNTS':str(r/'mounts'),'AB_MIAMI_BRIDGE_DIR':str(store),'AB_BRIDGE_OWNER':str(os.getuid()),'AB_CERTIFICATE_OWNER':str(os.getuid()),'BRIDGE_LIB':str(repo/'feeds/tip/cambium-miami-ab-bridge/files/miami-ab-bridge.sh'),'CERT_LIB':str(cert),'EXPECTED_BOOT':boot,'FAIL':''}
 base={'miami_bridge_fit_sha':h(dev/'ubi0_5'),'miami_bridge_fit_size':str((dev/'ubi0_5').stat().st_size),'miami_bridge_state':'started','miami_ab_version':'','miami_ab_confirmed':'0','miami_ab_state':'bootstrap','miami_bridge_nonce':'a'*64,'miami_bridge_archive_sha':h(archive),'miami_bridge_descriptor_sha':h(descriptor),'miami_boot0':'qualified-prior-command','bootcmd':'run miami_boot0','image':'0'}
 original_archive=archive.read_bytes();original_descriptor=descriptor.read_bytes();n=0
 def run(good,change=None,fields=None,fail=''):
  tp.write_text(json.dumps({**ticket,**(fields or {})})+'\n');tp.chmod(0o600)
  e={**base,'miami_bridge_ticket_sha':h(tp),**(change or {})};ep.write_text(json.dumps(e))
  p=subprocess.run(['sh','-c',script],env={**env,'FAIL':fail},capture_output=True,text=True)
  assert (p.returncode==0)==good,(change,fields,fail,p.returncode,p.stdout,p.stderr[-3500:])
 run(True);n+=1
 for field,value in [('family','thor'),('model','X7-35Y'),('sku','0000002d'),('source_slot',1),('target_slot',0),('source_mtd',3),('target_mtd',2),('serial','020000000002'),('source_boot_id','22345678-1234-1234-1234-123456789abc'),('source_release','incoming'),('source_kernel_sha','b'*64),('source_root_sha','c'*64),('nonce','d'*64)]:run(False,fields={field:value});n+=1
 for field,value in [('miami_bridge_state','consumed'),('miami_ab_version','1'),('miami_ab_confirmed','1'),('miami_ab_state','rolled-back'),('miami_bridge_nonce','e'*64),('miami_bridge_ticket_sha','f'*64),('miami_bridge_archive_sha','f'*64),('miami_bridge_descriptor_sha','f'*64),('miami_bridge_fit_sha','f'*64),('miami_bridge_fit_size','20316161'),('miami_bridge_fit_size','bad'),('miami_boot0','incoming-route'),('bootcmd','run miami_stable0'),('image','1')]:run(False,change={field:value});n+=1
 for fail in ['geometry','mac']:run(False,fail=fail);n+=1
 for vol in ['ubi0_0','ubi0_1','ubi0_5']:
  file=dev/vol;data=file.read_bytes();file.write_bytes(b'changed source');run(False);n+=1;file.write_bytes(data)
 (dt/'storage-slot').write_bytes((1).to_bytes(4,'big'));run(False);n+=1;(dt/'storage-slot').write_bytes(bytes(4))
 (ubi/'mtd_num').write_text('3');run(False);n+=1;(ubi/'mtd_num').write_text('2')
 (dt/'boot-mode').write_bytes(b'ordinary\0');run(False);n+=1;(dt/'boot-mode').write_bytes(b'bridge\0')
 descriptor.write_text(original_descriptor.decode()+'extra\n');run(False,change={'miami_bridge_descriptor_sha':h(descriptor)});n+=1;descriptor.write_bytes(original_descriptor)
 archive.chmod(0o644);run(False);n+=1;archive.chmod(0o600)
 hook=store/'source-boot-id';hook.unlink();hook.symlink_to(r/'outside');run(False);n+=1;hook.unlink()
 (r/'mounts').write_text('overlayfs:/overlay / overlay rw 0 0\n');run(False);n+=1;(r/'mounts').write_text('tmpfs / tmpfs rw 0 0\n')
 (r/'cmdline').write_text('ubi.mtd=rootfs miami.bridge='+('b'*64));run(False);n+=1;(r/'cmdline').write_text('ubi.mtd=rootfs miami.bridge='+('a'*64))
 run(True);n+=1
 assert archive.read_bytes()==original_archive and descriptor.read_bytes()==original_descriptor
 with tarfile.open(archive) as t:assert t.extractfile('./key.pem').read()==key.read_bytes()
 assert subprocess.check_output(['openssl','pkey','-in',str(key),'-pubout','-outform','DER'])==before_spki
 print(f'PASS: {n} actual bridge validator cases; immutable archive/key/SPKI; normal/replayed/wrong-bank/hash/boot-ID/source-payload refusals clear old-ID authority')
