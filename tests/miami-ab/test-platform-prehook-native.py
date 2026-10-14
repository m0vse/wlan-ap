#!/usr/bin/env python3
"""Fresh native pre-upgrade entry; synthetic media/ENV, real identity crypto.

Requires Linux root, native built shell libraries and frozen physical profile.
No identity/preflight/export callback stubs and no persistent writer invocation.
"""
from pathlib import Path
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from prepare_source import prepare_package

p=argparse.ArgumentParser()
p.add_argument('--native-libraries',type=Path,required=True)
p.add_argument('--physical-profile',type=Path,required=True)
a=p.parse_args()
if os.geteuid()!=0 or not sys.platform.startswith('linux'):
    raise SystemExit('Requires Linux root for native private ownership checks')
repo=Path(__file__).resolve().parents[2]
platform=(repo/'feeds/qca-wifi-7/ipq53xx/base-files/lib/upgrade/platform.sh').read_text()
hook=platform[platform.index('platform_pre_upgrade() {'):]
module=(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh').read_text()
cases=0
with tempfile.TemporaryDirectory(prefix='miami-fresh-prehook-') as td:
    base=Path(td);package=prepare_package(repo,base/'prepared')
    for slot in (0,1):
        r=base/f'slot{slot}'
        def write(name,data):
            path=r/name;path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data if isinstance(data,bytes) else str(data).encode());return path
        def rooted(text):
            text=re.sub(r'/(?:proc/|sys/|lib/|usr/share/|tmp/|dev/|etc/|certificates)',lambda m:str(r)+m.group(0),text)
            return text.replace(str(r)+'/dev/null','/dev/null')
        for name in ('functions.sh','system.sh','jshn.sh'):
            dest={'functions.sh':'lib/functions.sh','system.sh':'lib/functions/system.sh','jshn.sh':'usr/share/libubox/jshn.sh'}[name]
            write(dest,rooted((a.native_libraries/name).read_text()))
        for name in ('cambium-ab.sh','cambium-ab-certificates.sh'):
            dest=('lib/functions/' if name=='cambium-ab.sh' else 'lib/upgrade/')+name
            write(dest,rooted((package/'files'/name).read_text()))
        write('lib/upgrade/cambium-ab.sh',rooted((package/'files/cambium-ab-upgrade.sh').read_text()))
        write('lib/functions/cambium-ab-miami.sh',rooted(module))
        write('tmp/sysinfo/board_name','cambiumnetworks,x7-35x\n')
        dt='proc/device-tree/'
        for name,data in [('cambium-platform/board-sku',(44).to_bytes(4,'big')),('cambium-platform/storage-slot',slot.to_bytes(4,'big')),('cambium-platform/storage-policy',b'ab\0'),('cambium-platform/upgrade-policy',(1).to_bytes(4,'big')),('aliases/label-mac-device',b'ethernet-label'),('ethernet-label/mac-address',bytes.fromhex('020000000001'))]:write(dt+name,data)
        write('proc/sys/kernel/random/boot_id','12345678-1234-1234-1234-123456789abc\n')
        active='rootfs' if slot==0 else 'rootfs_1';write('proc/cmdline',f'ubi.mtd={active} root=/dev/ubiblock0_1')
        labels={};rows=[]
        for line in a.physical_profile.read_text().splitlines():
            name,domain,offset,size,kind,erase,width,role=line.split('\t')
            if role=='container':continue
            n=len(rows);labels[name]=n
            if kind=='nor':erase='65536'
            flags=1024 if name in ('rootfs','rootfs_1','0:APPSBLENV') else 0
            for key,value in [('name',name),('type',kind),('offset',offset),('size',size),('erasesize',erase),('writesize',width),('flags',flags)]:write(f'sys/class/mtd/mtd{n}/{key}',value)
            parent=r/'devices'/kind;parent.mkdir(parents=True,exist_ok=True)
            (r/f'sys/class/mtd/mtd{n}/device').symlink_to(parent)
            rows.append(f'mtd{n}: {int(size):08x} {int(erase):08x} "{name}"\n')
        write('proc/mtd','dev: size erasesize name\n'+''.join(rows));write('sys/class/ubi/ubi0/mtd_num',labels[active])
        for n,name,reserved in ((0,'kernel',39),(1,'rootfs',178),(3,'cambium_device_data',72),(4,'certificates',64)):
            write(f'sys/class/ubi/ubi0_{n}/name',name);write(f'sys/class/ubi/ubi0_{n}/reserved_ebs',reserved)
        write('proc/mounts',f'overlay / overlay rw 0 0\n{r}/dev/ubi0_4 {r}/certificates ubifs rw 0 0\n')
        store=r/'certificates';journal=store/'.installer-import';journal.mkdir(parents=True);store.chmod(0o700);journal.chmod(0o700)
        def crypto(*args):subprocess.run(['openssl',*map(str,args)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',r/'ca.key')
        crypto('req','-new','-x509','-key',r/'ca.key','-subj','/CN=Synthetic CA','-days','2','-out',store/'operational.ca','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign')
        crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',store/'key.pem')
        crypto('req','-new','-key',store/'key.pem','-subj','/CN=020000000001','-out',r/'request')
        write('extensions','basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=clientAuth\n')
        crypto('x509','-req','-in',r/'request','-CA',store/'operational.ca','-CAkey',r/'ca.key','-CAcreateserial','-days','2','-out',store/'operational.pem','-extfile',r/'extensions')
        shutil.copyfile(store/'operational.pem',store/'cert.pem');crypto('pkey','-in',store/'key.pem','-pubout','-outform','DER','-out',r/'public.der')
        spki=hashlib.sha256((r/'public.der').read_bytes()).hexdigest()
        write('certificates/.installer-import/transaction.json',json.dumps({'accepted':True,'committed':True,'spki':spki}))
        write('certificates/.installer-import/completion.json',json.dumps({'binding':{'serial':'020000000001','family':'miami','model':'X7-35X','spki_sha256':spki}}))
        for path in store.rglob('*'):
            if path.is_file():path.chmod(0o600)
        tools=r/'bin';tools.mkdir()
        actor=write('bin/fw_printenv','''#!/usr/bin/env python3
import json,os,sys
v=json.load(open(os.environ['ENV_FIXTURE']));name=sys.argv[sys.argv.index('-n')+1]
if name not in v:sys.exit(1)
print(v[name])
''');actor.chmod(0o755)
        jf=write('bin/jsonfilter','''#!/usr/bin/env python3
import json,sys
a=sys.argv[1:];v=json.load(open(a[a.index('-i')+1])) if '-i' in a else json.load(sys.stdin)
for k in a[a.index('-e')+1].removeprefix('@.').split('.'):v=v[k]
print(json.dumps(v) if isinstance(v,(bool,int)) else v)
''');jf.chmod(0o755)
        forbidden=write('bin/fw_setenv','#!/bin/sh\necho UNEXPECTED_ENV_WRITE >&2\nexit 99\n');forbidden.chmod(0o755)
        prior=subprocess.check_output(['sh','-c','. "$1"; AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000; ab_miami_slot_command "$2" ab','fixture',str(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),str(slot)],text=True).strip()
        original={'bootcmd':f'run miami_boot{slot}','image':str(slot),f'miami_boot{slot}':rooted(prior),'changing_bootcmd':'1','miami_ab_confirmed':str(slot),'miami_ab_state':'confirmed','miami_ab_seed_boot_id':'12345678-1234-1234-1234-123456789abc'}
        state=write('env.json',json.dumps(original))
        prefix=rooted('''. /lib/functions.sh
. /lib/functions/system.sh
. /lib/functions/cambium-ab.sh
. /lib/upgrade/cambium-ab.sh
''')
        for variant,fault,good in [('old','',False),('new','',True),('new','old-boot',False),('new','wrong-key',False)]:
            state.write_text(json.dumps({**original,**({'miami_ab_seed_boot_id':'old-boot'} if fault=='old-boot' else {})}))
            key=(store/'key.pem').read_bytes()
            if fault=='wrong-key':crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',store/'key.pem')
            text=hook if variant=='new' else hook.replace('ab_identity && ab_miami_upgrade_preflight','ab_family && ab_miami_upgrade_preflight')
            driver=write('driver.sh',prefix+'\n'+rooted(text)+'\n[ "${AB_ACTIVE+x}:${AB_ACTIVE_MTD+x}" = : ] || exit 98\nplatform_pre_upgrade synthetic-image\n')
            before={str(q.relative_to(store)):q.read_bytes() for q in store.rglob('*') if q.is_file()}
            result=subprocess.run(['sh',*(['-x'] if os.environ.get('PREHOOK_TRACE') else []),str(driver)],env={**os.environ,'PATH':str(tools)+':'+os.environ['PATH'],'ENV_FIXTURE':str(state),'AB_DEV':str(r/'dev')},capture_output=True,text=True)
            assert (result.returncode==0)==good,(slot,variant,fault,result.stdout,result.stderr)
            if variant=='old' and slot==0:assert '/mtd/flags' in result.stderr,result.stderr
            assert 'UNEXPECTED_ENV_WRITE' not in result.stderr and json.loads(state.read_text())==({**original,**({'miami_ab_seed_boot_id':'old-boot'} if fault=='old-boot' else {})})
            assert before=={str(q.relative_to(store)):q.read_bytes() for q in store.rglob('*') if q.is_file()}
            (store/'key.pem').write_bytes(key);cases+=1
print(f'PASS: {cases} fresh native platform hook cases, both slots; old initialization failure reproduced, corrected entry/export passes, stale boot and wrong key refused; synthetic I/O, real crypto, no writes')
