#!/usr/bin/env python3
"""Run the OEM bank installer against isolated hardware/tool fixtures."""
from pathlib import Path
import tempfile, subprocess, os, hashlib, json, shutil, re
repo=Path(__file__).resolve().parents[3]
source=(repo/'contrib/cambium/miami/miami-oem-bank-test.sh').read_text()
assert not any(s in source for s in ['ubiformat ', 'ubirmvol ', 'flash_erase '])
data=b'miami-fit-fixture'*512; digest=hashlib.sha256(data).hexdigest()
with tempfile.TemporaryDirectory() as td:
 w=Path(td); r=w/'root'; b=w/'bin'; b.mkdir()
 for d in ['proc/device-tree/cambium-platform','sys/class/mtd','sys/class/ubi','sys/class/block','dev','etc','tmp']:(r/d).mkdir(parents=True,exist_ok=True)
 for n,name,size,off in [(2,'rootfs',100663296,786432),(3,'rootfs_1',100663296,101449728),(18,'0:APPSBLENV',65536,0)]:
  d=r/f'sys/class/mtd/mtd{n}';d.mkdir()
  for key,value in [('name',name),('size',size),('offset',off)]:(d/key).write_text(str(value))
  with (r/f'dev/mtd{n}ro').open('wb') as f:f.truncate(size)
 (r/'proc/device-tree/cambium-platform/board-sku').write_bytes(bytes.fromhex('0000002c'))
 (r/'proc/mounts').write_text('');(r/'etc/fw_env.config').write_text('/dev/mtd18 0 0x10000 0x10000\n')
 image=w/'fit';image.write_bytes(data)
 fixture_source=source
 for digest_pin,size_pin in re.findall(r'(?:auto|low)\) HASH=([0-9a-f]{64}) SIZE=(\d+)',source):
  fixture_source=fixture_source.replace(digest_pin,digest).replace(size_pin,str(len(data)))
 helper=w/'installer';helper.write_text(fixture_source)
 mock='''#!/usr/bin/env python3
import os,sys,json,shutil
from pathlib import Path
r=Path(os.environ['MIAMI_BANK_TEST_ROOT']); p=Path(os.environ['ENV_FILE']);e=json.loads(p.read_text());a=sys.argv[1:];cmd=Path(sys.argv[0]).name
if cmd=='strace':
 Path(a[a.index('-o')+1]).write_text('open("/etc/fw_env.config", 0) = 3\\nopen("/dev/mtd18", 0) = 4\\n');sys.exit()
if cmd=='fw_printenv':
 if not a:
  for k,v in e.items():print(k+'='+v)
 elif a[-1] in e:print((a[-1]+'=' if '-n' not in a else '')+e[a[-1]])
 else:sys.exit(1)
 sys.exit()
with open(os.environ['CALLS'],'a') as f:f.write(cmd+' '+' '.join(a)+'\\n')
if cmd=='fw_setenv':
 if os.environ.get('FAIL_KEY')==a[0]:sys.exit(1)
 if len(a)==1:e.pop(a[0],None)
 else:e[a[0]]=a[1]
 p.write_text(json.dumps(e))
elif cmd=='ubiattach':
 assert a[-1]==os.environ['TARGET_MTD']
 d=r/'sys/class/ubi/ubi9';d.mkdir();(d/'mtd_num').write_text(a[-1])
 for k,v in [('eraseblock_size','126976'),('avail_eraseblocks',os.environ.get('FREE','400')),('ro_mode','0')]: (d/k).write_text(v)
 for i,n in enumerate(['kernel','rootfs','rootfs_data','cambium_device_data']):
  d=r/f'sys/class/ubi/ubi9_{i}';d.mkdir();(d/'name').write_text(n);(d/'data_bytes').write_text('9000000')
 if (r/'dev/ubi9_4').exists():
  d=r/'sys/class/ubi/ubi9_4';d.mkdir();(d/'name').write_text('miami_openwifi_trial');(d/'data_bytes').write_text('9000000')
elif cmd=='ubidetach':
 assert a[-1]==os.environ['TARGET_MTD']
 for d in (r/'sys/class/ubi').glob('ubi9*'):shutil.rmtree(d)
elif cmd=='ubimkvol':
 assert a[0]==str(r/'dev/ubi9') and a[2]=='miami_openwifi_trial'
 d=r/'sys/class/ubi/ubi9_4';d.mkdir();(d/'name').write_text(a[2]);(d/'data_bytes').write_text(a[-1])
 (r/'dev/ubi9_4').touch()
elif cmd=='ubiupdatevol':
 assert a[0]==str(r/'dev/ubi9_4')
 shutil.copyfile(a[1],a[0])
else:raise AssertionError(cmd)
'''
 for cmd in ['strace','fw_printenv','fw_setenv','ubiattach','ubidetach','ubimkvol','ubiupdatevol']:
  p=b/cmd;p.write_text(mock);p.chmod(0o755)
 env=dict(os.environ,PATH=str(b)+':'+os.environ['PATH'],MIAMI_BANK_TEST_ROOT=str(r),ENV_FILE=str(w/'env'),CALLS=str(w/'calls'),TARGET_MTD='2')
 def initial(bank='rootfs_1',img='1'):
  (w/'env').write_text(json.dumps({'bootcmd':'bootipq','image':img,'mtdids':'original','mtdparts':'original','bootargs':'OEM-console'}));(r/'proc/cmdline').write_text('console=ttyMSM0,115200n8 ubi.mtd='+bank+' root=/dev/ubiblock0_1')
  (w/'calls').write_text('');env['TARGET_MTD']='2' if bank=='rootfs_1' else '3'
 def call(args,good=True,extra={}):
  p=subprocess.run(['sh',str(helper),*args],env=dict(env,**extra),text=True,capture_output=True)
  assert (p.returncode==0)==good,(args,p.returncode,p.stdout,p.stderr)
 initial();call(['check']);assert not (w/'calls').read_text()
 call(['stage',str(image),'auto','--yes'],False)
 initial('rootfs_1','0');call(['check'],False);assert not (w/'calls').read_text()
 initial();(r/'etc/openwrt_release').touch();call(['check'],False);(r/'etc/openwrt_release').unlink()
 call(['backup']);call(['stage',str(image),'auto','--yes','--backed-up'],False,{'FREE':'0'})
 assert 'ubiupdatevol' not in (w/'calls').read_text()
 call(['stage',str(image),'auto','--yes','--backed-up']);assert (r/'dev/ubi9_4').read_bytes()==data
 # Reusing a pinned FIT is allowed; unrelated data and active mounts are refused.
 call(['stage',str(image),'low','--yes','--backed-up'])
 (r/'proc/mounts').write_text('ubi9:rootfs_data /target ubifs rw 0 0\n')
 call(['stage',str(image),'auto','--yes','--backed-up'],False)
 (r/'proc/mounts').write_text('')
 (r/'dev/ubi9_4').write_bytes(b'foreign')
 call(['stage',str(image),'auto','--yes','--backed-up'],False)
 (r/'dev/ubi9_4').write_bytes(data)
 call(['arm','auto'],False);call(['arm','auto','--yes'],False,{'FAIL_KEY':'bootcmd'})
 e=json.loads((w/'env').read_text());assert e['bootcmd']=='bootipq' and 'changing_bootcmd' not in e
 call(['cleanup','--yes']);call(['arm','auto','--yes'])
 e=json.loads((w/'env').read_text());assert e['image']=='1'
 for failed in [False,True]:
  script=w/'boot';script.write_text('''setenv(){ key=$1; shift; if [ "$#" = 0 ];then unset "$key";else export "$key=$*";fi; }
 saveenv(){ env > "$SAVED"; echo save >> "$BOOT_CALLS"; }
 run(){ for key in "$@"; do eval 'script=${'"$key"'}'; eval "$script" || return;done; }
 nand(){ echo nand >> "$BOOT_CALLS";return 0; }
 ubi(){ echo "ubi $*" >> "$BOOT_CALLS"; if [ "$1" = read ];then return "$FAIL_READ";fi; }
 bootm(){ echo bootm >> "$BOOT_CALLS";exit 0; }
 reset(){ echo reset >> "$BOOT_CALLS";exit 0; }
 run miami_bank_restore && run miami_bank_load; reset
''')
  (w/'bootcalls').write_text('')
  subprocess.run(['sh',str(script)],env=dict(env,**e,SAVED=str(w/'saved'),BOOT_CALLS=str(w/'bootcalls'),FAIL_READ=str(int(failed))),check=True)
  calls=(w/'bootcalls').read_text().splitlines();assert calls[:2]==['save','nand'];assert calls[-1]==('reset' if failed else 'bootm')
  saved=dict(s.split('=',1) for s in (w/'saved').read_text().splitlines() if '=' in s)
  assert saved['bootcmd']=='bootipq' and 'changing_bootcmd' not in saved and saved['image']=='1' and saved['mtdparts']=='original'
 # Both OEM bank orientations are accepted; target is always the other bank.
 initial('rootfs','0');call(['check']);assert not (w/'calls').read_text()
 # A pre-existing target UBI is borrowed and must remain attached after staging.
 initial();subprocess.run([str(b/'ubiattach'),str(r/'dev/ubi_ctrl'),'-m','2'],env=env,check=True)
 (w/'calls').write_text('')
 call(['stage',str(image),'auto','--yes','--backed-up'])
 assert (r/'sys/class/ubi/ubi9').exists() and 'ubidetach' not in (w/'calls').read_text()
 (r/'sys/class/block/ubiblock9_4').touch()
 call(['arm','auto','--yes'],False)
 (r/'sys/class/block/ubiblock9_4').unlink()

print('PASS: OEM-only and bank consistency, read-only check/backup, no-space refusal, new-volume-only writes/readback, arm rollback, restore-before-NAND, load failure fallback, cleanup, both bank orientations, borrowed UBI preservation, mounted/unknown-volume and block-mapping refusal')
