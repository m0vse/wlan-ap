#!/usr/bin/env python3
"""Whole native-to-OEM return with pinned vendor parts; file actors only."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('common_lib',type=Path);ap.add_argument('runtime_root',type=Path);ap.add_argument('provider',type=Path)
    ap.add_argument('kernel',type=Path);ap.add_argument('rootfs',type=Path)
    a=ap.parse_args();base=Path(__file__).resolve().parents[1]; count=0
    with tempfile.TemporaryDirectory(prefix='thor-layout-') as td:
        top=Path(td).resolve();shared=top/'shared';shared.mkdir()
        for n in ('common.sh','protection.sh'): (shared/n).write_bytes((a.common_lib/n).read_bytes())

        def fixture(fail=0,slot=1,unattached=False,drift=""):
            root=top/f'case-{slot}-{fail}-{unattached}-{drift}';shutil.rmtree(root,ignore_errors=True);root.mkdir(mode=0o700)
            bundle=root/'bundle';shutil.copytree(a.provider,bundle)
            runtime=bundle/'runtime';runtime.mkdir()
            for n,p in [('cambium-ab.sh','cambium-ab/files/cambium-ab.sh'),('cambium-ab-upgrade.sh','cambium-ab/files/cambium-ab-upgrade.sh'),('cambium-ab-thor.sh','cambium-thor-support/files/cambium-ab-thor.sh')]:
                (runtime/n).write_bytes((a.runtime_root/'package/cambium'/p).read_bytes())
            (bundle/'adapters').mkdir();(bundle/'adapters/thor.sh').write_text((base/'adapters/thor.sh').read_text()+'''\noem_thor_art_node(){ printf '%s\\n' "$OEM_SYS_ROOT/dev/mtd${1}ro"; }\noem_thor_mtd_target_node(){ printf '%s\\n' "$OEM_SYS_ROOT/dev/mtd$OEM_TARGET_MTD"; }\noem_thor_target_node(){ printf '%s\\n' "$OEM_SYS_ROOT/dev/${OEM_TARGET_UBI}_$1"; }\n''')
            oem=bundle/'payloads/XV3-8/oem';oem.mkdir();(oem/'kernel.bin').write_bytes(a.kernel.read_bytes());(oem/'rootfs.bin').write_bytes(a.rootfs.read_bytes())
            for profile_slot in (0,1): (bundle/f'profiles/XV3-8/mtd-openwifi-slot{profile_slot}.tsv').write_bytes((base/f'profiles/XV3-8/mtd-openwifi-slot{profile_slot}.tsv').read_bytes())
            # Mock only the DT binary-reader interface, retaining ab_identity.
            with (runtime/'cambium-ab.sh').open('a') as f:f.write("\nab_dt_sku(){ printf '00000013\\n'; }\n")
            files=[p for p in bundle.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
            (bundle/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle)}\n' for p in sorted(files)))
            profile=(bundle/f'profiles/XV3-8/mtd-openwifi-slot{1-slot}.tsv').read_text().splitlines();names=[]
            sys=root/'sys/class/mtd';sys.mkdir(parents=True);dev=root/'dev';dev.mkdir()
            for domain in ('nor0','nand0'): (root/domain).mkdir()
            for i,line in enumerate(profile):
                name,domain,off,size,kind,erase,write,role=line.split('\t');names.append(name);node=sys/f'mtd{i}';node.mkdir()
                for key,val in dict(name=name,offset=off,size=size,type=kind,erasesize=erase,writesize=write,flags=1024 if role in ('target','active-oem','environment') else 0).items(): (node/key).write_text(str(val))
                (node/'device').symlink_to(root/domain)
                (dev/f'mtd{i}').write_bytes(b'synthetic-raw-target')
                (dev/f'mtd{i}ro').write_bytes(bytes(int(size)) if name in ('0:ART','mfginfo','0:APPSBLENV','0:BOOTCONFIG','0:BOOTCONFIG1') else b'synthetic-readonly-region')
            target=names.index('rootfs' if slot==1 else 'rootfs_1');source=names.index('rootfs_1' if slot==1 else 'rootfs');art=names.index('0:ART');envindex=names.index('0:APPSBLENV')
            data=bytearray((dev/f'mtd{art}ro').read_bytes());data[64:70]=bytes.fromhex('001122334455');(dev/f'mtd{art}ro').write_bytes(data)
            ubi=root/'sys/class/ubi';ubi.mkdir()
            for u,mtd in (('ubi6',source),('ubi8',target)):
                (ubi/u).mkdir()
                for key,val in dict(mtd_num=mtd,eraseblock_size=126976,min_io_size=2048,dev='250:0').items(): (ubi/u/key).write_text(str(val))
                (dev/u).write_bytes(b'')
                for child,name,size in ((0,'kernel',112),(1,'rootfs',120),(2,'rootfs_data',464),(3,'cambium_device_data',8),(4,'certificates',20)):
                    (ubi/f'{u}_{child}').mkdir()
                    for key,val in dict(name=name,upd_marker=0,corrupted=0,dev=f'250:{child+1}',reserved_ebs=size).items(): (ubi/f'{u}_{child}'/key).write_text(str(val))
                    (dev/f'{u}_{child}').write_bytes(('synthetic-own-'+name).encode())
            if unattached:
                for path in list(ubi.glob('ubi8*')):shutil.rmtree(path)
            work=root/'work';work.mkdir(mode=0o700);crit=work/'critical';crit.mkdir(mode=0o700)
            for line in (bundle/'profiles/XV3-8/critical.tsv').read_text().splitlines():
                kind,label,_,_=line.split('\t');(crit/f'{kind}.bin').write_bytes((dev/f'mtd{names.index(label)}ro').read_bytes())
            (crit/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(crit.glob('*.bin'))))
            (crit/'OFFDEVICE_VERIFIED').write_text(hashlib.sha256((crit/'SHA256SUMS').read_bytes()).hexdigest()+'\n')
            (root/'etc').mkdir();(root/'etc/openwrt_release').write_text("DISTRIB_TIP_VERSION='thor-2026.10.05.8'\n");(root/'etc/version').write_text(''.join(line.replace('\t','=')+'\n' for line in (base/'profiles/XV3-8/source.tsv').read_text().splitlines()))
            (root/'tmp').mkdir();(root/'tmp/cambium-ab-fw_env.config').write_text(f'/dev/mtd{envindex} 0x0 0x10000 0x10000 1\n')
            proc=root/'proc';(proc/'self').mkdir(parents=True);(proc/'cmdline').write_text(('ubi.mtd=rootfs_1' if slot==1 else 'ubi.mtd=rootfs')+' root=ubi6:rootfs');(proc/'mtd').write_text(''.join(f'mtd{i}: {int(row.split(chr(9))[3]):08x} {int(row.split(chr(9))[5]):08x} \"{names[i]}\"\n' for i,row in enumerate(profile)));(proc/'device-tree').mkdir();(proc/'device-tree/compatible').write_bytes(b'cambiumnetworks,xv3-8\0');(proc/'mounts').write_text('');(proc/'self/mountinfo').write_text('')
            (dev/'urandom').write_bytes(bytes(range(64)))
            (root/'environment.json').write_text(__import__('json').dumps({'image':str(slot),'bootcmd':f'run thor_stable{slot}','factory_keep':'untouched','changing_bootcmd':'1','thor_ab_confirmed':str(slot),'thor_ab_state':'confirmed','thor_ab_version':'1'}))
            tools=root/'bin';tools.mkdir()
            actor=tools/'actor'
            actor.write_text(r'''#!/usr/bin/env python3
import os,sys,json,shutil
from pathlib import Path
root=Path(os.environ['OEM_SYS_ROOT']);cmd=Path(sys.argv[0]).name;a=sys.argv[1:]
if cmd=='ls':
 import subprocess
 r=subprocess.run(['/bin/ls']+a,capture_output=True,text=True);out=r.stdout
 if '-ldn' in a:
  fields=out.split();fields[0]=fields[0][:10];fields[2]='0';out=' '.join(fields)+'\n'
 print(out,end='');sys.exit(r.returncode)
if cmd=='fw_printenv':
 data=json.loads((root/'environment.json').read_text())
 if '-n' in a:
  key=a[a.index('-n')+1]
  if key not in data:sys.exit(1)
  print(data[key])
 else:
  for k,v in data.items():print(k+'='+v)
 sys.exit(0)
state=root/'counter';n=int(state.read_text())+1 if state.exists() else 1;state.write_text(str(n))
cmd=Path(sys.argv[0]).name;a=sys.argv[1:]
with (root/'trace').open('a') as f:f.write(cmd+' '+' '.join(a)+'\n')
if n==int(os.environ['FAIL_OPERATION']):sys.exit(1)
ubi=root/'sys/class/ubi';dev=root/'dev'
def put(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(str(v))
if cmd=='ubidetach':
 for p in list(ubi.glob('ubi8*')):shutil.rmtree(p)
elif cmd=='ubiformat':Path(a[0]).write_bytes(b'formatted-fixture-only')
elif cmd=='ubiattach':
 put(ubi/'ubi8/mtd_num',os.environ['TARGET']);put(ubi/'ubi8/dev','250:0');(dev/'ubi8').write_bytes(b'')
 for i,name,size in ((0,'kernel',112),(1,'rootfs',120),(2,'rootfs_data',464),(3,'cambium_device_data',8),(4,'certificates',20)):
  for k,v in dict(name=name,reserved_ebs=size,upd_marker=0,corrupted=0,dev=f'250:{i+1}').items():put(ubi/f'ubi8_{i}'/k,v)
elif cmd=='ubimkvol':
 i=int(a[a.index('-n')+1]);name=a[a.index('-N')+1];size=int(a[a.index('-s')+1]) if '-s' in a else 400*126976
 for key,val in dict(name=name,reserved_ebs=(size+126975)//126976,data_bytes=size,dev=f'250:{i+1}',upd_marker=0,corrupted=0).items():put(ubi/f'ubi8_{i}'/key,val)
elif cmd=='mknod':Path(a[0]).write_bytes(b'fixture-node')
elif cmd=='ubiupdatevol':Path(a[0]).write_bytes(Path(a[1]).read_bytes())
elif cmd=='fw_setenv':
 data=json.loads((root/'environment.json').read_text())
 if '-s' in a:
  for line in Path(a[a.index('-s')+1]).read_text().splitlines():
   k,_,v=line.partition(' ')
   if v:data[k]=v
   else:data.pop(k,None)
 else:
  if len(a)>3:data[a[2]]=a[3]
  else:data.pop(a[2],None)
 (root/'environment.json').write_text(json.dumps(data))
elif cmd=='mount':
 mnt=Path(a[-1]);store=root/'overlay-store';store.mkdir(exist_ok=True)
 for p in store.iterdir():
  if p.is_dir():shutil.copytree(p,mnt/p.name,dirs_exist_ok=True)
  else:shutil.copy2(p,mnt/p.name)
 ro='-o' in a and a[a.index('-o')+1]=='ro'
 (root/'proc/mounts').write_text(a[-2]+' '+str(mnt)+' ubifs '+('ro' if ro else 'rw')+' 0 0\n')
elif cmd=='umount':
 mnt=Path(a[-1]);store=root/'overlay-store';shutil.rmtree(store);shutil.copytree(mnt,store)
 for p in mnt.iterdir():
  if p.is_dir():shutil.rmtree(p)
  else:p.unlink()
 (root/'proc/mounts').write_text('')
elif cmd=='sync':pass
elif cmd=='ubirmvol':shutil.rmtree(ubi/f"ubi8_{a[a.index('-n')+1]}")
elif cmd=='ubirename':put(ubi/'ubi8_1/name',a[2])
elif cmd=='ubirsvol':put(ubi/'ubi8_1/reserved_ebs',int(a[a.index('-s')+1])//126976)
else:sys.exit(99)
''');actor.chmod(0o700)
            for cmd in ('ubidetach','ubiformat','ubiattach','ubimkvol','mknod','ubiupdatevol','fw_setenv','fw_printenv','mount','umount','sync','ls','ubirmvol','ubirename','ubirsvol'): (tools/cmd).symlink_to('actor')
            env=dict(os.environ,PATH=str(tools)+':'+os.environ['PATH'],COMMON=str(shared),ADAPTER=str(base/'adapters/restore-thor.sh'),OEM_SYS_ROOT=str(root),OEM_SKU='00000013',OEM_MODEL='XV3-8',OEM_SUPPORTED_RELEASE='thor-2026.10.05.8',OEM_FAMILY='thor',OEM_CONTROLLER='controller.example',OEM_BUNDLE=str(bundle),OEM_WORK=str(work),TARGET=str(target),SOURCE=str(source),SLOT=str(slot),FAIL_OPERATION=str(fail),DRIFT=drift)
            # Late drift is external to the writer, after successful metadata
            # readback and immediately before its actual final guard body.
            adapter=root/'restore-actor.sh'
            adapter.write_text((base/'adapters/restore-thor.sh').read_text().replace('oem_restore_thor_final_candidate()', 'oem_restore_thor_final_candidate_actual()')+r'''
oem_restore_thor_final_candidate() {
 python3 "$OEM_SYS_ROOT/drift.py" || return 1
 oem_restore_thor_final_candidate_actual
}
''')
            (root/'drift.py').write_text(r'''
import os,json
from pathlib import Path
r=Path(os.environ['OEM_SYS_ROOT']);kind=os.environ['DRIFT'];d=json.loads((r/'environment.json').read_text())
if kind in ('kernel','root'):
 p=r/('dev/ubi8_'+('0' if kind=='kernel' else '1'));b=bytearray(p.read_bytes());b[0]^=1;p.write_bytes(b)
elif kind=='identity':(r/'dev/ubi8_4').write_bytes(b'external-identity-drift')
elif kind=='env-unlisted':d['factory_keep']='external-drift'
elif kind.startswith('arm-'):d['thor_restore_'+kind[4:]]='external-drift'
(r/'environment.json').write_text(json.dumps(d))
''')
            env['ADAPTER']=str(adapter)
            return root,env,names

        script=r'''
. "$COMMON/common.sh"; . "$COMMON/protection.sh"; . "$ADAPTER"
oem_thor_art_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd${1}ro"; }
oem_thor_target_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/${OEM_TARGET_UBI}_$1"; }
reboot(){ exit 99; }; wget(){ exit 99; }; curl(){ exit 99; }
oem_restore_thor_load || exit 1
# Character nodes are the sole storage-boundary substitution.
oem_thor_art_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd${1}ro"; }
oem_thor_target_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/${OEM_TARGET_UBI}_$1"; }
# Re-loading authenticated source retains the node actors via explicit hooks
# only in this fixture adapter copy.
oem_restore_migrate
'''
        def run(root,env,ok):
            nonlocal count
            protected={str(p):p.read_bytes() for p in (root/'dev').glob('mtd*ro')}
            protected.update({str(p):p.read_bytes() for p in (root/'dev').glob('ubi6*')})
            protected.update({str(root/f'dev/ubi8_{i}'):(root/f'dev/ubi8_{i}').read_bytes() for i in (3,4)})
            r=subprocess.run(['sh','-c',script],env=env,text=True,capture_output=True,timeout=180)
            assert (r.returncode==0)==ok,(r.returncode,r.stdout,r.stderr[-4500:])
            if env['DRIFT']=='identity':protected.pop(str(root/'dev/ubi8_4'))
            assert protected=={p:Path(p).read_bytes() for p in protected}
            count+=1;return r
        # Exact old slot command is produced by the authenticated real module.
        def boot_environment(root,env):
            cmd='. "$OEM_BUNDLE/runtime/cambium-ab.sh"; . "$OEM_BUNDLE/runtime/cambium-ab-thor.sh"; ab_thor_board cambiumnetworks,xv3-8; ab_thor_boot_command "$SLOT"'
            boot=subprocess.check_output(['sh','-c',cmd],env=env,text=True).strip()
            data=__import__('json').loads((root/'environment.json').read_text());data['thor_boot'+env['SLOT']]=boot;data['thor_stable'+env['SLOT']]=f'run thor_boot{env["SLOT"]}; run thor_boot{1-int(env["SLOT"])}';(root/'environment.json').write_text(__import__('json').dumps(data))
        for slot in (0,1):
            root,env,names=fixture(slot=slot);boot_environment(root,env);r=run(root,env,True)
            assert 'handoff=one-shot-oem-armed' in r.stdout
            data=__import__('json').loads((root/'environment.json').read_text())
            assert data['thor_ab_confirmed']==str(slot) and data['factory_keep']=='untouched'
            assert 'saveenv && run thor_restore_oem' in data['bootcmd']
            operations=int((root/'counter').read_text())
            # Execute the shipped .8 rollback record and stable-default
            # restoration body on the actual source-only wrapper just saved.
            frozen=base/'tests/fixtures/thor-2026.10.05.8'
            (root/'system.sh').write_text('')
            guard=r'''
. "$GUARD"
AB_ENV=thor AB_ACTIVE=$SLOT
record_rollback 'candidate did not boot' || exit 1
commit_trial "$SLOT" || exit 1
'''
            genv={**env,'GUARD':str(frozen/'usr/sbin/cambium-ab-guard'),'CAMBIUM_SYSTEM_FUNCTIONS':str(root/'system.sh'),'CAMBIUM_AB_LIB':str(frozen/'lib/functions/cambium-ab.sh'),'CAMBIUM_AB_MODULES':str(frozen/'lib/functions'),'CAMBIUM_INSTALLER_HEALTH_LIB':str(frozen/'lib/functions/cambium-installer-health.sh'),'AB_GUARD_SOURCE_ONLY':'1','AB_ENV_CONFIG':str(root/'dummy')}
            subprocess.run(['sh','-c',guard],env=genv,check=True,capture_output=True)
            restored=__import__('json').loads((root/'environment.json').read_text())
            assert restored['bootcmd']==f'run thor_stable{slot}'
            assert restored[f'thor_stable{slot}']==f'run thor_boot{slot}'
            print('Thor restore slot',slot,'positive passed; sweeping',operations,'failure points',flush=True)
            def failed_case(fail):
                root,env,names=fixture(fail,slot)
                try:
                    boot_environment(root,env);r=run(root,env,False)
                    data=__import__('json').loads((root/'environment.json').read_text())
                    assert data['bootcmd'] in (f'run thor_stable{slot}',f'run thor_boot{slot}'),(fail,data['bootcmd'])
                    assert data['factory_keep']=='untouched' and data['thor_ab_confirmed']==str(slot)
                finally:shutil.rmtree(root)
            with ThreadPoolExecutor(max_workers=4) as workers:list(workers.map(failed_case,range(1,operations+1)))
            root,env,names=fixture(slot=slot,unattached=True);boot_environment(root,env);run(root,env,True)
            for drift in ('kernel','root','identity','env-unlisted','arm-target','arm-state','arm-prior','arm-oem'):
                root,env,names=fixture(slot=slot,drift=drift);boot_environment(root,env);run(root,env,False)
                d=__import__('json').loads((root/'environment.json').read_text())
                assert d['bootcmd']==f'run thor_boot{slot}' and d[f'thor_stable{slot}']==f'run thor_boot{slot}'
        print(f'PASS: {count} whole OEM-return cases, failures at all {operations} persistent/process steps; active bank and both identity children unchanged')
        print('Scope: actual vendor pins, common physical/ENV/idle checks and source writer. DT reader/device/fwtools are actors. No AP, factory reset, boot, build or identity export.')

if __name__=='__main__':main()
