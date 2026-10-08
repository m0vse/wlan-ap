#!/usr/bin/env python3
"""Exercise actual OEM installer against mutable UBI/environment fixtures."""
from pathlib import Path
import os,json,subprocess,tempfile,hashlib,tarfile,io,struct
repo=Path(__file__).resolve().parents[3]
source=(repo/'contrib/cambium/miami/miami-oem-persistent.sh.in').read_text()
assert 'ubiformat ' not in source and 'flash_erase ' not in source
with tempfile.TemporaryDirectory(prefix='miami-oem-persistent-') as td:
 w=Path(td);r=w/'root';b=w/'bin';b.mkdir()
 for d in ['proc/device-tree/cambium-platform','sys/class/mtd','sys/class/ubi/ubi9','sys/class/block','dev','tmp','etc']:(r/d).mkdir(parents=True,exist_ok=True)
 for n,name,size,off in [(2,'rootfs',100663296,786432),(3,'rootfs_1',100663296,101449728),(18,'0:APPSBLENV',65536,0),(21,'0:ART',1048576,0)]:
  d=r/f'sys/class/mtd/mtd{n}';d.mkdir()
  for k,v in [('name',name),('size',size),('offset',off),('type','nor' if n==18 else 'nand'),('erasesize',65536 if n==18 else 131072),('writesize',1 if n==18 else 2048),('flags','0xc00')]:(d/k).write_text(str(v))
  (r/f'dev/mtd{n}ro').write_bytes(('own-'+name).encode())
 (r/'proc/device-tree/cambium-platform/board-sku').write_bytes(struct.pack('>I',44));(r/'proc/mounts').write_text('');(r/'etc/fw_env.config').write_text('/dev/mtd18 0 0x10000 0x10000\n')
 kernel=b'kernel payload fixture';rootfs=b'rootfs payload fixture';pins=''
 for slot in (0,1):
  for key,data in [('KERNEL',kernel),('ROOTFS',rootfs)]:
   name=f'miami-{slot}-{key.lower()}'
   pins+=f'{key}{slot}={name}\n{key}{slot}_SHA={hashlib.sha256(data).hexdigest()}\n{key}{slot}_SIZE={len(data)}\n'
   (r/'tmp'/name).write_bytes(data)
 prior_kernel=b'previous independently pinned kernel';prior_root=b'previous independently pinned rootfs'
 for slot in (0,1):
  for key,data in [('KERNEL',prior_kernel),('ROOTFS',prior_root)]:
   pins+=f'PRIOR_{key}{slot}_SHA={hashlib.sha256(data).hexdigest()}\nPRIOR_{key}{slot}_SIZE={len(data)}\n'
 helper=w/'installer';helper.write_text('#!/bin/sh\n'+pins+source)
 afiles=['lib/firmware/IPQ5332/WIFI_FW/'+n for n in ['q6_fw0.mdt','q6_fw1.mdt','iu_fw.mdt','bdwlan.b12-acadia','regdb.bin-acadia']]+['lib/firmware/qcn9224/WIFI_FW/bdwlan.b1019-acadia']
 artsha=hashlib.sha256((r/'dev/mtd21ro').read_bytes()).hexdigest();manifest=f'format 1\nboard cambiumnetworks,x7-35x\nsku 0000002c\nart_sha256 {artsha}\n'
 archive=w/'vault'
 with tarfile.open(archive,'w') as tf:
  for path in afiles:
   data=b'owned radio fixture';manifest+=f'file {path} {len(data)} {hashlib.sha256(data).hexdigest()}\n';ti=tarfile.TarInfo('files/'+path);ti.size=len(data);tf.addfile(ti,io.BytesIO(data))
  data=manifest.encode();ti=tarfile.TarInfo('MANIFEST');ti.size=len(data);tf.addfile(ti,io.BytesIO(data))
 mock='''#!/usr/bin/env python3
from pathlib import Path
import os,json,sys,shutil
r=Path(os.environ['CAMBIUM_OEM_INSTALL_ROOT']);ep=Path(os.environ['ENV_FILE']);e=json.loads(ep.read_text());a=sys.argv[1:];cmd=Path(sys.argv[0]).name
if cmd=='strace':
 Path(a[a.index('-o')+1]).write_text('open("/etc/fw_env.config",0)=3\\nopen("/dev/mtd18",0)=4\\n')
 if os.environ.get('BAD_CRC'):print('Warning: Bad CRC, using default environment',file=sys.stderr)
 sys.exit()
if cmd=='fw_printenv':
 if a[0] not in e:sys.exit(1)
 print(a[0]+'='+e[a[0]]);sys.exit()
with open(os.environ['CALLS'],'a') as f:f.write(cmd+' '+' '.join(a)+'\\n')
if cmd=='fw_setenv':
 if os.environ.get('FAIL_KEY')==a[0]:sys.exit(1)
 if len(a)==1:e.pop(a[0],None)
 else:e[a[0]]=a[1]
 ep.write_text(json.dumps(e));sys.exit()
if cmd=='wget':raise AssertionError('preverified files should not download')
u=r/'sys/class/ubi/ubi9';free=u/'avail_eraseblocks'
if cmd=='ubirmvol':
 assert a[0]==str(r/'dev/ubi9')
 assert a[-1] in ['kernel','ubi_rootfs','rootfs','rootfs_data','miami_openwifi_trial','certificates']
 for d in (r/'sys/class/ubi').glob('ubi9_*'):
  if (d/'name').read_text().strip()==a[-1]:
   free.write_text(str(int(free.read_text())+int((d/'reserved_ebs').read_text())));(r/'dev'/d.name).unlink();shutil.rmtree(d);break
 else:raise AssertionError(a)
elif cmd=='ubimkvol':
 assert a[0]==str(r/'dev/ubi9')
 idx=int(a[a.index('-n')+1]);name=a[a.index('-N')+1];size=int(a[a.index('-s')+1]);lebs=(size+126975)//126976
 d=r/f'sys/class/ubi/ubi9_{idx}';assert not d.exists();d.mkdir()
 for k,v in [('name',name),('reserved_ebs',lebs),('data_bytes',size),('upd_marker',0),('corrupted',0)]:(d/k).write_text(str(v))
 free.write_text(str(int(free.read_text())-lebs));assert int(free.read_text())>=0
 (r/'dev'/d.name).write_bytes(b'blank persistent volume')
elif cmd=='ubiupdatevol':
 assert a[0] in [str(r/'dev/ubi9_0'),str(r/'dev/ubi9_1'),str(r/'dev/ubi9_3')]
 if os.environ.get('FAIL_WRITE')==Path(a[0]).name:sys.exit(1)
 shutil.copyfile(a[1],a[0])
elif cmd in ['ubiattach','ubidetach']:raise AssertionError('borrowed UBI must not attach/detach')
else:raise AssertionError(cmd)
'''
 for cmd in ['strace','fw_printenv','fw_setenv','wget','ubirmvol','ubimkvol','ubiupdatevol','ubiattach','ubidetach']:
  p=b/cmd;p.write_text(mock);p.chmod(0o755)
 env=dict(os.environ,CAMBIUM_INSTALL_SERVER='https://operator.invalid/bundle',PATH=str(b)+':'+os.environ['PATH'],CAMBIUM_OEM_INSTALL_ROOT=str(r),ENV_FILE=str(w/'env'),CALLS=str(w/'calls'))
 def initial(slot=0):
  (w/'env').write_text(json.dumps({'bootcmd':'bootipq','image':str(1-slot),'mtdids':'OEMids','mtdparts':'OEMparts','bootargs':'OEMargs'}));(w/'calls').write_text('')
  (r/'proc/cmdline').write_text('ubi.mtd='+('rootfs_1' if slot==0 else 'rootfs'))
  u=r/'sys/class/ubi/ubi9'
  for k,v in [('mtd_num',2 if slot==0 else 3),('eraseblock_size',126976),('avail_eraseblocks',250),('ro_mode',0),('min_io_size',2048)]:(u/k).write_text(str(v))
  import shutil
  for d in (r/'sys/class/ubi').glob('ubi9_*'):shutil.rmtree(d)
  for idx,(name,lebs,data) in enumerate([('kernel',1,b'oldstockkernel'),('rootfs',1,b'oldstockrootfs'),('rootfs_data',400,b'old configuration'),('cambium_device_data',72,archive.read_bytes())]):
   d=r/f'sys/class/ubi/ubi9_{idx}';d.mkdir()
   for k,v in [('name',name),('reserved_ebs',lebs),('data_bytes',lebs*126976),('upd_marker',0),('corrupted',0)]:(d/k).write_text(str(v))
   (r/'dev'/d.name).write_bytes(data)
 def run(args,ok=True,extra=None):
  before=(w/'calls').read_text();p=subprocess.run(['sh',str(helper),*args],env=dict(env,**(extra or {})),capture_output=True,text=True)
  assert (p.returncode==0)==ok,(args,p.stdout,p.stderr)
  return (w/'calls').read_text()[len(before):]
 args=['install','--yes','--replace-openwrt','--backed-up']
 initial();assert run(['check'])==''
 # Actual OEM uses 4KiB physical sectors and a full 64KiB fwtools region.
 erase=r/'sys/class/mtd/mtd18/erasesize';erase.write_text('4096')
 (r/'etc/fw_env.config').write_text('/dev/mtd18 0x0 0x00010000 0x00010000 1\n')
 assert run(['check'])==''
 erase.write_text('8192');run(['check'],False);assert (w/'calls').read_text()==''
 erase.write_text('4096')
 flags=r/'sys/class/mtd/mtd18/flags';oldflags=flags.read_text();flags.write_text('0x800')
 run(['check'],False);assert (w/'calls').read_text()=='';flags.write_text(oldflags)

 # Real OEM class aliases and exported UBI MTD views are not physical banks.
 for idx in (2,3,18,21):(r/f'sys/class/mtd/mtd{idx}ro').symlink_to(r/f'sys/class/mtd/mtd{idx}',target_is_directory=True)
 view=r/'sys/class/mtd/mtd29';view.mkdir();(view/'name').write_text('rootfs');(view/'type').write_text('ubi')
 assert run(['check'])==''
 # A genuinely duplicated physical partition is still rejected before writes.
 duplicate=r/'sys/class/mtd/mtd30';duplicate.mkdir();(duplicate/'name').write_text('rootfs');(duplicate/'type').write_text('nand')
 run(['check'],False);assert (w/'calls').read_text()==''
 (duplicate/'name').unlink();(duplicate/'type').unlink();duplicate.rmdir()
 (r/'etc/fw_env.config').write_text('/dev/mtd18 0 0x10000\n');assert run(['check'])=='';(r/'etc/fw_env.config').write_text('/dev/mtd18 0 0x10000 0x10000\n')
 run(['install'],False);assert (w/'calls').read_text()==''
 # A concurrent writer and bad environment geometry stop before mutation.
 run(args,False,{'BAD_CRC':'1'});assert 'fw_setenv' not in (w/'calls').read_text()
 (r/'tmp/cambium-oem-install.lock').mkdir();run(args,False);(r/'tmp/cambium-oem-install.lock').rmdir()
 (r/'etc/fw_env.config').write_text('/dev/mtd18 0x1000 0x10000 0x10000\n');run(args,False);(r/'etc/fw_env.config').write_text('/dev/mtd18 0 0x10000 0x10000\n')
 (r/'sys/class/block/ubiblock9_1').touch();run(args,False);assert 'ubirmvol' not in (w/'calls').read_text();(r/'sys/class/block/ubiblock9_1').unlink()
 (r/'proc/mounts').write_text('ubi9:rootfs_data /target ubifs rw 0 0\n');run(args,False);(r/'proc/mounts').write_text('')
 (r/'sys/class/ubi/ubi9_0/upd_marker').write_text('1');run(args,False);(r/'sys/class/ubi/ubi9_0/upd_marker').write_text('0')
 (r/'sys/class/ubi/ubi9_3/reserved_ebs').write_text('8');run(args,False);(r/'sys/class/ubi/ubi9_3/reserved_ebs').write_text('72')
 (r/'sys/class/ubi/ubi9/avail_eraseblocks').write_text('0');run(args,False);assert 'ubirmvol' not in (w/'calls').read_text()
 initial();vbefore=(r/'dev/ubi9_3').read_bytes();obefore=(r/'dev/mtd3ro').read_bytes();run(args)
 assert (r/'dev/ubi9_3').read_bytes()==vbefore and (r/'dev/mtd3ro').read_bytes()==obefore
 assert (r/'dev/ubi9_0').read_bytes()==kernel and (r/'dev/ubi9_1').read_bytes()==rootfs
 assert (r/'sys/class/ubi/ubi9_4/name').read_text()=='certificates'
 data=(r/'dev/ubi9_2').read_bytes();cert=(r/'dev/ubi9_4').read_bytes()
 run(args,False) # never clean an existing certificate store
 calls=run(['update','--yes','--backed-up']);assert '-N rootfs_data' not in calls and '-N certificates' not in calls
 assert (r/'dev/ubi9_2').read_bytes()==data and (r/'dev/ubi9_4').read_bytes()==cert
 (r/'dev/ubi9_0').write_bytes(b'unknown');run(['update','--yes','--backed-up'],False);(r/'dev/ubi9_0').write_bytes(kernel)
 # Explicit existing-trial fresh reset, both target slots; no active OEM/vault writes.
 fresh=['install','--yes','--replace-inactive-bank','--backed-up','--fresh-enrolment']
 for slot in (0,1):
  initial(slot);run(args)
  preserved={n:(r/f'dev/{n}').read_bytes() for n in ('ubi9_3','mtd21ro',f'mtd{3 if slot==0 else 2}ro')}
  (r/'dev/ubi9_2').write_bytes(b'old settings and seed');(r/'dev/ubi9_4').write_bytes(b'old key CSR leaf')
  state=json.loads((w/'env').read_text());state.update(miami_installer_target=str(slot),miami_installer_job='a'*64,miami_installer_image='b'*64);(w/'env').write_text(json.dumps(state))
  # Complete same-target old enrollment state is inspectable without mutation.
  before_env=(w/'env').read_bytes();before_devices={p.name:p.read_bytes() for p in (r/'dev').iterdir() if p.is_file()}
  assert run(['check'],False)==''
  assert run(['check','--fresh-enrolment'])==''
  assert run(['check','--fresh-enrolment','--yes'],False)==''
  assert (w/'env').read_bytes()==before_env and all((r/'dev'/n).read_bytes()==v for n,v in before_devices.items())
  state['miami_installer_target']=str(1-slot);(w/'env').write_text(json.dumps(state));assert run(['check','--fresh-enrolment'],False)==''
  state['miami_installer_target']=str(slot);state['miami_installer_job']='bad';(w/'env').write_text(json.dumps(state));assert run(['check','--fresh-enrolment'],False)==''
  state['miami_installer_job']='';(w/'env').write_text(json.dumps(state));assert run(['check','--fresh-enrolment'],False)==''
  state['miami_installer_job']='a'*64;(w/'env').write_text(json.dumps(state))
  assert '-N certificates' not in run(fresh,False,{'CAMBIUM_INSTALL_SERVER':''})
  (r/'dev/ubi9_0').write_bytes(b'unknown pair');assert '-N certificates' not in run(fresh,False);(r/'dev/ubi9_0').write_bytes(kernel)
  state['miami_installer_target']=str(1-slot);(w/'env').write_text(json.dumps(state));run(fresh,False);state['miami_installer_target']=str(slot);(w/'env').write_text(json.dumps(state))
  calls=run(fresh)
  assert '-N certificates' in calls and '-N rootfs_data' in calls
  assert (r/'dev/ubi9_2').read_bytes()==b'blank persistent volume' and (r/'dev/ubi9_4').read_bytes()==b'blank persistent volume'
  assert all((r/f'dev/{n}').read_bytes()==v for n,v in preserved.items())
  state=json.loads((w/'env').read_text());assert state['bootcmd']=='bootipq' and not any(k.startswith('miami_installer_') for k in state) and 'miami_storage_pending' not in state
  run(fresh,False,{'FAIL_WRITE':'ubi9_1'});assert json.loads((w/'env').read_text())['miami_storage_pending'].startswith('install:');run(['arm','--yes'],False)
 # A prior image is admitted only as the exact independently pinned pair.
 for slot in (0,1):
  initial(slot);run(args)
  saved={idx:(r/f'dev/ubi9_{idx}').read_bytes() for idx in (2,3,4)}
  (r/'dev/ubi9_0').write_bytes(prior_kernel)
  run(['update','--yes','--backed-up'],False) # mixed old kernel/new rootfs
  (r/'dev/ubi9_0').write_bytes(kernel);(r/'dev/ubi9_1').write_bytes(prior_root)
  run(['update','--yes','--backed-up'],False) # mixed new kernel/old rootfs
  (r/'dev/ubi9_0').write_bytes(prior_kernel)
  run(['update','--yes','--backed-up'])
  for idx,payload in saved.items():assert (r/f'dev/ubi9_{idx}').read_bytes()==payload
  assert (r/'dev/ubi9_0').read_bytes()==kernel and (r/'dev/ubi9_1').read_bytes()==rootfs
 initial();run(args)

 run(['arm','--yes'],False,{'FAIL_KEY':'bootcmd'});e=json.loads((w/'env').read_text());assert e['bootcmd']=='bootipq' and 'changing_bootcmd' not in e
 run(['arm','--yes']);e=json.loads((w/'env').read_text());assert e['image']=='1' and e['miami_persistent_slot']=='0' and e['bootcmd']=='run miami_persistent_restore && run miami_persistent_load || bootipq'
 assert e['miami_persistent_restore']=='setenv bootcmd bootipq && setenv changing_bootcmd && saveenv'
 assert 'ubi read 0x60000000 kernel &&' in e['miami_persistent_load'] and 'saveenv' not in e['miami_persistent_load']
 assert 'ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs rootwait' in e['miami_persistent_load']
 # Execute the actual guarded hush-compatible script, including save failure.
 boot=w/'boot';boot.write_text("""setenv(){ key=$1;shift;if [ "$#" = 0 ];then unset "$key";else export "$key=$*";fi; }
saveenv(){ echo save >> "$BOOT_CALLS";[ "$FAIL_SAVE" = 0 ] || return 1;env > "$SAVED"; }
run(){ for key in "$@";do eval 'script=${'"$key"'}';eval "$script" || return;done; }
nand(){ echo nand >> "$BOOT_CALLS"; }
ubi(){ echo "ubi $*" >> "$BOOT_CALLS";[ "$1" != read ] || [ "$FAIL_READ" = 0 ]; }
bootm(){ echo bootm >> "$BOOT_CALLS";exit 0; }
bootipq(){ echo OEM >> "$BOOT_CALLS";exit 0; }
reset(){ echo reset >> "$BOOT_CALLS";exit 0; }
"""+e['bootcmd']+'\n')
 for fail_save,fail_read,last in [('0','0','bootm'),('0','1','reset'),('1','0','OEM')]:
  (w/'bootcalls').write_text('');subprocess.run(['sh',str(boot)],env=dict(env,**e,FAIL_SAVE=fail_save,FAIL_READ=fail_read,BOOT_CALLS=str(w/'bootcalls'),SAVED=str(w/'saved')),check=True)
  calls=(w/'bootcalls').read_text().splitlines();assert calls[0]=='save' and calls[-1]==last
  if fail_save=='1':assert calls==['save','OEM'] # no reset or temporary maps
  else:
   saved=dict(l.split('=',1) for l in (w/'saved').read_text().splitlines() if '=' in l);assert saved['bootcmd']=='bootipq' and saved['image']=='1' and saved['mtdparts']=='OEMparts' and 'changing_bootcmd' not in saved

 initial(1);run(args);run(['arm','--yes']);e=json.loads((w/'env').read_text());assert e['image']=='0' and e['miami_persistent_slot']=='1' and 'ubi.mtd=rootfs_1' in e['miami_persistent_load']
 # Power/write failure leaves OEM default and unit vault untouched.
 initial();run(args,False,{'FAIL_WRITE':'ubi9_1'});e=json.loads((w/'env').read_text());assert e['bootcmd']=='bootipq' and e['image']=='1' and (r/'dev/ubi9_3').read_bytes()==vbefore and e['miami_storage_pending'].startswith('install:0:');run(['arm','--yes'],False)
 # Clean dual-OEM migration stages own firmware before any target writes.
 def initial_oem(slot=0):
  initial(slot)
  for idx in (2,3):
   d=r/f'sys/class/ubi/ubi9_{idx}'
   import shutil
   shutil.rmtree(d);(r/f'dev/ubi9_{idx}').unlink(missing_ok=True)
  (r/'sys/class/ubi/ubi9_1/name').write_text('ubi_rootfs')
  (r/'sys/class/ubi/ubi9_1/reserved_ebs').write_text('500')
  (r/'sys/class/ubi/ubi9/avail_eraseblocks').write_text('223')
  for path in afiles+['lib/firmware/qcn9224/WIFI_FW/bdwlan.b1019-acadia.uk','lib/firmware/qcn9224/WIFI_FW/regdb.bin-acadia']:
   f=r/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(b'own OEM radio fixture')
 clean=['install','--yes','--replace-inactive-bank','--backed-up']
 for slot in (0,1):
  initial_oem(slot);assert run(['check'])==''
  run(args,False);assert not (w/'calls').read_text() # old flag cannot authorize OEM replacement
  run(['update','--yes','--backed-up'],False);assert not (w/'calls').read_text()
  missing=r/'lib/firmware/qcn9224/WIFI_FW/bdwlan.b1019-acadia.uk';payload=missing.read_bytes();missing.unlink();run(clean,False);assert not (w/'calls').read_text();missing.write_bytes(payload)
  # Unknown extra volume is never removed, even with clean-install consent.
  d=r/'sys/class/ubi/ubi9_7';d.mkdir()
  for k,v in [('name','foreign'),('upd_marker','0'),('corrupted','0')]:(d/k).write_text(v)
  run(clean,False);assert not (w/'calls').read_text()
  import shutil
  shutil.rmtree(d)
  source_bank=r/f'dev/mtd{3 if slot==0 else 2}ro';before=source_bank.read_bytes()
  calls=run(clean);assert '-N ubi_rootfs' in calls and '-N cambium_device_data' in calls
  assert source_bank.read_bytes()==before and (r/'dev/ubi9_0').read_bytes()==kernel and (r/'dev/ubi9_1').read_bytes()==rootfs
  with tarfile.open(r/'dev/ubi9_3') as tf:
   manifest=tf.extractfile('MANIFEST').read().decode();assert 'art_sha256 '+artsha in manifest
   for path in afiles:assert tf.extractfile('files/'+path).read()==b'own OEM radio fixture'
  assert (r/'sys/class/ubi/ubi9_3/reserved_ebs').read_text()=='72'
  run(['arm','--yes']);e=json.loads((w/'env').read_text());assert e['image']==str(1-slot) and e['miami_persistent_slot']==str(slot)
print('PASS: actual installer read-only check, consent/mapping/mount/space/vault refusals; explicit install IDs; OEM/vault preservation; update preserves overlay/certs; unknown prior kernel refusal; failed arm rollback; both slot boot commands; write failure leaves OEM default')
