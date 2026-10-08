#!/usr/bin/env python3
"""Actual generated provider/cache/native seed and in-process secret transport.

Root Linux only. Regular-file UBI/env tools are mocked; OverlayFS is real in a
private namespace. No AP, issuer, network fetch or firmware build is involved.
"""
#!/usr/bin/env python3
"""Exercise actual OEM installer against mutable UBI/environment fixtures."""
from pathlib import Path
import os,json,subprocess,tempfile,hashlib,tarfile,io,struct,shutil
if os.geteuid()!=0:raise SystemExit('Root required')
repo=Path(__file__).resolve().parents[3]
source=Path(os.environ['GENERATED_INSTALLER']).read_text().replace('\nR=\n','\nR=${CAMBIUM_OEM_INSTALL_ROOT:-}\n')
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
 helper=w/'installer';helper.write_text(source.replace('mode=${1:-}', pins+'\nmode=${1:-}',1))
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
if any('X'*64 in x or 'Y'*64 in x for x in sys.argv) or any('X'*64 in v or 'Y'*64 in v for v in os.environ.values()):raise AssertionError('Secret leaked into child process')
if cmd=='sync':sys.exit()
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
 for cmd in ['sync','strace','fw_printenv','fw_setenv','wget','ubirmvol','ubimkvol','ubiupdatevol','ubiattach','ubidetach']:
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
 driver=w/'driver.sh';keyfile=w/'request-key'
 driver.write_text('set -eu\nset +x\nbackend=$1;shift\nif [ -s "$FIXTURE_KEY_FILE" ];then IFS= read -r protected_key < "$FIXTURE_KEY_FILE";set -- "$@" --enrolment-key "$protected_key";fi\n. "$backend"\n')
 def run(args,ok=True,extra=None):
  args=list(args);keyfile.unlink(missing_ok=True)
  if '--enrolment-key' in args:
   i=args.index('--enrolment-key');key=args[i+1];args=args[:i]+args[i+2:]
   keyfile.write_text(key+'\n');keyfile.chmod(0o600)
  request_env=dict(env,FIXTURE_KEY_FILE=str(keyfile),**(extra or {}))
  argv=['sh',str(driver),str(helper),*args]
  assert not any('X'*64 in x or 'Y'*64 in x for x in argv+list(request_env.values()))
  before=(w/'calls').read_text()
  p=subprocess.run(argv,env=request_env,capture_output=True,text=True)
  assert 'X'*64 not in p.stdout+p.stderr and 'Y'*64 not in p.stdout+p.stderr
  assert (p.returncode==0)==ok,(p.stdout,p.stderr)
  return (w/'calls').read_text()[len(before):]
 args=['install','--yes','--replace-openwrt','--backed-up']
 cache=w/'cache';cache.mkdir(mode=0o700);cache.chmod(0o700)
 env.update(CAMBIUM_INSTALL_CACHE_DIR=str(cache),CAMBIUM_INSTALL_LOCAL_ONLY='1',CAMBIUM_INSTALL_SERVER='http://server-is-gone.invalid')
 for slot in (0,1):
  for key,data in [('kernel',kernel),('rootfs',rootfs)]:
   p=cache/f'miami-{slot}-{key}';p.write_bytes(data);p.chmod(0o600)
  name=f'miami-persistent-slot{slot}-pair.json'
  p=cache/name;p.write_bytes((Path(os.environ['GENERATED_INSTALLER']).parent/name).read_bytes());p.chmod(0o600)
 # Full generated-script arm with actual packaged FORMAT2 producer/adapter.
 native_overlay=w/'native-overlay';native_overlay.mkdir()
 (r/'etc/version').write_text('VERSION=7.2-r1\n')
 env.update(OW_SETTINGS_OWNER=str(os.getuid()),OW_SETTINGS_SYS=str(r/'sys/class/ubi'),OW_SETTINGS_DEV=str(r/'dev'),OW_SETTINGS_MOUNTS=str(r/'proc/mounts'),FIXTURE_OVERLAY=str(native_overlay))
 for name,body in {'get_esn': '#!/bin/sh\nprintf "020000000001\\n"\n[ "${FAIL_ESN:-0}" = 0 ]\n', 'ls': '#!/usr/bin/env python3\nimport os,stat,sys\np=sys.argv[-1];s=os.lstat(p);print(stat.filemode(s.st_mode),s.st_nlink,s.st_uid,s.st_gid,s.st_size,"Jan 1 00:00",p)\n', 'mount': '#!/usr/bin/env python3\nfrom pathlib import Path\nimport os,sys,shutil\np=Path(sys.argv[-1]); source=Path(os.environ["FIXTURE_OVERLAY"])\nfor entry in source.iterdir():shutil.copytree(entry,p/entry.name)\nPath(os.environ["OW_SETTINGS_MOUNTS"]).write_text(sys.argv[-2]+" "+str(p)+" ubifs rw 0 0\\n")\n', 'umount': '#!/usr/bin/env python3\nfrom pathlib import Path\nimport os,sys,shutil\np=Path(sys.argv[-1]);dest=Path(os.environ["FIXTURE_OVERLAY"])\nfor entry in dest.iterdir():shutil.rmtree(entry)\nfor entry in p.iterdir():shutil.copytree(entry,dest/entry.name)\nPath(os.environ["OW_SETTINGS_MOUNTS"]).write_text("")\n'}.items():
  p=b/name;p.write_text(body);p.chmod(0o700)
 for name in ['miami-persistent-slot0-pair.json','miami-persistent-slot1-pair.json']:
  (r/'tmp'/name).write_bytes((Path(os.environ['GENERATED_INSTALLER']).parent/name).read_bytes())
 for slot in (0,1):
  for controller in ['controller.default.test','controller.override.test']:
   for entry in native_overlay.iterdir():shutil.rmtree(entry)
   initial(slot);run(args)
   calls=run(['arm','--yes','--enrolment-key','X'*64],extra={'CAMBIUM_ENROLMENT_SERVER':controller})
   assert 'wget' not in calls and 'X'*64 not in calls
   seed=native_overlay/'upper/root/.cambium-installer-settings'
   assert (native_overlay/'upper').stat().st_mode&0o777==0o755
   assert (native_overlay/'upper/root').stat().st_mode&0o777==0o700
   assert seed.stat().st_mode&0o777==0o700
   assert all(p.stat().st_mode&0o777==0o600 for p in seed.iterdir())
   assert json.loads((seed/'gateway.json').read_text())['server']==controller
   state=json.loads((w/'env').read_text());assert state['miami_installer_target']==str(slot)
   before={p.name:p.read_bytes() for p in seed.iterdir()}
   subprocess.run(['python3',str(Path(__file__).with_name('test-produced-overlay.py')),str(native_overlay/'upper')],check=True)
   def restore_fixture_boot():
    state=json.loads((w/'env').read_text());state['bootcmd']='bootipq';state.pop('changing_bootcmd',None);(w/'env').write_text(json.dumps(state))
   restore_fixture_boot()
   run(['arm','--yes','--enrolment-key','X'*64],extra={'CAMBIUM_ENROLMENT_SERVER':controller})
   assert before=={p.name:p.read_bytes() for p in seed.iterdir()}
   restore_fixture_boot();env_before=(w/'env').read_bytes()
   run(['arm','--yes','--enrolment-key','Y'*64],False,{'CAMBIUM_ENROLMENT_SERVER':controller})
   assert env_before==(w/'env').read_bytes() and before=={p.name:p.read_bytes() for p in seed.iterdir()}
   run(['arm','--yes','--enrolment-key','X'*64],False,{'CAMBIUM_ENROLMENT_SERVER':'bad;hostname'})
   assert env_before==(w/'env').read_bytes() and before=={p.name:p.read_bytes() for p in seed.iterdir()}
   descriptor=cache/f'miami-persistent-slot{slot}-pair.json';saved=descriptor.read_bytes();descriptor.write_bytes(saved[:-1])
   run(['arm','--yes','--enrolment-key','X'*64],False,{'CAMBIUM_ENROLMENT_SERVER':controller})
   assert env_before==(w/'env').read_bytes() and before=={p.name:p.read_bytes() for p in seed.iterdir()}
   descriptor.write_bytes(saved);descriptor.chmod(0o600)
 print('PASS: four cached native-arm contexts; in-process key/no argv/env/log exposure; private modes, same-job retry, foreign key/hostname/descriptor refusal; actual OverlayFS UID81 access/denial')
