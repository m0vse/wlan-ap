#!/usr/bin/env python3
"""Actual b6 core+module+guard+installer-health; hardware/ENV/network actors.
No live device. Counts validate the rollback software path, not a hardware boot.
"""
from pathlib import Path
import subprocess,tempfile,os,json
from prepare_source import prepare_package
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-b6-composition-') as td:
 r=Path(td).resolve();modules=r/'modules';modules.mkdir();sys=r/'mtd';sys.mkdir();ubi=r/'ubi';ubi.mkdir();dt=r/'dt/cambium-platform';dt.mkdir(parents=True);bin=r/'bin';bin.mkdir();dev=r/'dev';dev.mkdir()
 # Replay the shipped shared guard/core body through0168, without0169.
 package=r/'package/cambium/cambium-ab/files';package.mkdir(parents=True)
 for patch in sorted((repo/'patches-25.12').glob('*.patch')):
  if patch.name[:4].isdigit() and int(patch.name[:4])>168:continue
  lines=patch.read_text().splitlines(keepends=True);starts=[i for i,l in enumerate(lines) if l.startswith('--- ') and i+1<len(lines) and lines[i+1].startswith('+++ ')]
  parts=[]
  for j,i in enumerate(starts):
   if not lines[i+1].split()[1].startswith('b/package/cambium/cambium-ab/files/'):continue
   part=lines[i:starts[j+1] if j+1<len(starts) else len(lines)]
   for k,l in enumerate(part):
    if l.startswith(('diff --git ','-- \n')):part=part[:k];break
   parts.append(''.join(part))
  if parts:
   q=r/'selected.patch';q.write_text(''.join(parts));subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(q)],cwd=r,check=True,capture_output=True)
 for target,source in [(modules/'cambium-ab-miami.sh','feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),(r/'health.sh','feeds/tip/certificates/files/lib/functions/cambium-installer-health.sh')]:
  target.write_bytes(subprocess.check_output(['git','show','b6d1a26f:'+source],cwd=repo))
 system=r/'system.sh';system.write_text('board_name(){ echo cambiumnetworks,x7-35x; }\nget_mac_label_dt(){ echo 02:00:00:00:00:01; }\nget_mac_label(){ echo 02:00:00:00:00:01; }\n')
 rows=[]
 names={2:'rootfs',3:'rootfs_1',4:'0:NVRAM',5:'crashLog',6:'0:SBL1',7:'0:SBL1_1',11:'0:APPSBL',18:'0:APPSBLENV',19:'0:APPSBL_1',20:'0:ART',21:'mfginfo',27:'rootfs'}
 for n,name in names.items():
  d=sys/f'mtd{n}';d.mkdir();kind='ubi' if n==27 else ('nand' if n<6 else 'nor')
  for k,v in [('name',name),('type',kind),('flags','0x400' if n==2 else '0xc00' if n==18 else '0')]: (d/k).write_text(v)
  size='06000000' if n in (2,3) else '00010000';erase='00020000' if n in (2,3) else '00010000'
  rows.append(f'mtd{n}: {size} {erase} "{name}"\n')
 (r/'proc-mtd').write_text('dev: size erasesize name\n'+''.join(rows));(r/'cmdline').write_text('ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs rootwait')
 (dt/'board-sku').write_bytes((44).to_bytes(4,'big'));(dt/'storage-slot').write_bytes(bytes(4))
 (ubi/'ubi0').mkdir();(ubi/'ubi0/mtd_num').write_text('2')
 for n,name in [(0,'kernel'),(1,'rootfs'),(4,'certificates')]:
  d=ubi/f'ubi0_{n}';d.mkdir();(d/'name').write_text(name);(d/'reserved_ebs').write_text('64' if n==4 else '39')
 (dev/'ubiblock0_1').touch();(r/'vault-status').write_text('vault')
 (r/'mounts').write_text(f'/dev/ubi0_2 /overlay ubifs rw 0 0\n{dev}/ubi0_4 /certificates ubifs rw 0 0\n')
 actors={
 'uci':'''#!/bin/sh
case "$*" in
'-q show network') echo network.up0v0=interface;;
'-q get network.up0v0.proto') echo dhcp;;
'-q get network.up0v0.device') echo up.4090;;
esac
''',
 'ip':'''#!/bin/sh
case "$*" in
'-4 address show dev up.4090') [ "$HEALTHY" = 1 ] && echo 'inet 192.0.2.1/24';;
'-4 route show default dev up.4090') echo 'default via 192.0.2.254 dev up.4090';;
esac
''',
 'ping':'#!/bin/sh\n[ "$HEALTHY" = 1 ]\n','sleep':'#!/bin/sh\nexit 0\n','logger':'#!/bin/sh\nexit 0\n'}
 for name,text in actors.items():p=bin/name;p.write_text(text);p.chmod(0o755)
 # Limit health retries only. Actual health body/hook dispatch remain present.
 guard=r/'guard';text=(package/'cambium-ab-guard').read_text();text=text.replace('wait_healthy() {','wait_healthy() {\n\tAB_HEALTH_TRIES=1',1);guard.write_text(text)
 script='''
. "$GUARD"
ab_getenv(){ python3 -c 'import json,sys,os;print(json.load(open(os.environ["STATE"])).get(sys.argv[1],""))' "$1"; }
ab_setenv(){ echo FORBIDDEN_BOOT_WRITE;exit 90; }
ab_setenv_batch(){ python3 -c 'import json,sys,os;from pathlib import Path;p=Path(os.environ["STATE"]);e=json.loads(p.read_text());[(e.update({l.split(" ",1)[0]:l.split(" ",1)[1]}) if " " in l else e.pop(l,None)) for l in Path(sys.argv[1]).read_text().splitlines()];p.write_text(json.dumps(e))' "$1"; }
do_reboot(){ echo FORBIDDEN_REBOOT;exit 91; }
ab_family && ab_identity && ab_miami_storage_context && ab_miami_certificate_mount || exit 92
ab_hook healthy_extra && ab_hook installer_confirmed_context || exit 93
# Completed native onboarding is not erased by conversion flags.
installer_healthy || exit 94
main
'''
 env={**os.environ,'PATH':str(bin)+':'+os.environ['PATH'],'GUARD':str(guard),'CAMBIUM_SYSTEM_FUNCTIONS':str(system),'CAMBIUM_AB_LIB':str(package/'cambium-ab.sh'),'CAMBIUM_AB_MODULES':str(modules),'CAMBIUM_INSTALLER_HEALTH_LIB':str(r/'health.sh'),'AB_GUARD_SOURCE_ONLY':'1','STATE':str(r/'state'),'AB_PROC_MTD':str(r/'proc-mtd'),'AB_MTD_SYS':str(sys),'AB_UBI_SYS':str(ubi),'AB_DT':str(dt.parent),'AB_DEV':str(dev),'AB_CMDLINE':str(r/'cmdline'),'AB_PROC_MOUNTS':str(r/'mounts'),'CAMBIUM_BDF_STATUS':str(r/'vault-status')}
 n=0
 for version,state,target in [('', 'bootstrap','1'),('', 'writing','1'),('', 'write-failed','1'),('1','writing','1'),('1','write-failed','1'),('1','trial-started','1'),('1','rolled-back',''),('1','confirmed','')]:
  for healthy in ('0','1'):
   prior="nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@0xc0000(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd=rootfs root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-slot0"
   before={'bootcmd':'run miami_boot0','image':'0','changing_bootcmd':'1','miami_boot0':prior,'miami_persistent_restore':'setenv bootcmd bootipq && setenv changing_bootcmd && saveenv','miami_persistent_load':prior+'; reset','miami_persistent_slot':'0','miami_ab_version':version,'miami_ab_state':state,'miami_ab_target':target,'miami_ab_confirmed':'0'}
   (r/'state').write_text(json.dumps(before));p=subprocess.run(['sh','-c',script],env={**env,'HEALTHY':healthy},capture_output=True,text=True)
   assert p.returncode in (0,1) and 'FORBIDDEN' not in p.stdout+p.stderr,(version,state,healthy,p.returncode,p.stdout,p.stderr)
   after=json.loads((r/'state').read_text());assert all(after.get(k)==before[k] for k in ['bootcmd','image','miami_boot0'])
   if version=='1' and state=='trial-started':assert after['miami_ab_state']=='rolled-back'
   n+=1
 print(f'PASS: {n} actual b6 core/module/guard/installer-health cases; real family callbacks/mount mapping with hardware/ENV/network actors; prior-only source retained')
