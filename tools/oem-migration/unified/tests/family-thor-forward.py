#!/usr/bin/env python3
"""Whole forward transaction with actual .8 bytes/settings/allocator and file actors."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import json, re


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('common_lib',type=Path);ap.add_argument('runtime_root',type=Path);ap.add_argument('provider',type=Path)
    ap.add_argument('image',type=Path);ap.add_argument('bdf',type=Path);ap.add_argument('settings',type=Path);ap.add_argument('--positive-only',action='store_true');ap.add_argument('--source-slot',type=int,choices=(0,1),default=1)
    ap.add_argument('--env-only',action='store_true')
    a=ap.parse_args();base=Path(__file__).resolve().parents[1]; count=0
    with tempfile.TemporaryDirectory(prefix='thor-layout-') as td:
        top=Path(td).resolve();shared=top/'shared';shared.mkdir()
        for n in ('common.sh','protection.sh'): (shared/n).write_bytes((a.common_lib/n).read_bytes())

        def fixture(fail=0,unattached=False,cert=False,drift=""):
            slot=a.source_slot;target_slot=1-slot
            root=top/f'case-{slot}-{fail}-{unattached}-{cert}';shutil.rmtree(root,ignore_errors=True);root.mkdir(mode=0o700)
            bundle=root/'bundle';shutil.copytree(a.provider,bundle)
            runtime=bundle/'runtime';runtime.mkdir()
            for n,p in [('cambium-ab.sh','cambium-ab/files/cambium-ab.sh'),('cambium-ab-upgrade.sh','cambium-ab/files/cambium-ab-upgrade.sh'),('cambium-ab-thor.sh','cambium-thor-support/files/cambium-ab-thor.sh')]:
                (runtime/n).write_bytes((a.runtime_root/'package/cambium'/p).read_bytes())
            radio=bundle/'payloads/shared-radio';radio.mkdir();asset=radio/'thor-bdwlan.b215.accton';asset.write_bytes(a.bdf.read_bytes())
            (bundle/'payloads/XV3-8/image.bin').write_bytes(a.image.read_bytes())
            (bundle/'lib').mkdir();(bundle/'lib/cambium-installer-settings.sh').write_text(a.settings.read_text())
            (bundle/'adapters').mkdir();(bundle/'adapters/thor-handoff.sh').write_bytes((base/'adapters/thor-handoff.sh').read_bytes())
            (bundle/'profiles/XV3-8/vault-assets.tsv').write_bytes((base/'profiles/XV3-8/vault-assets.tsv').read_bytes())
            files=[p for p in bundle.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
            (bundle/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle)}\n' for p in sorted(files)))
            profile=(bundle/f'profiles/XV3-8/mtd-slot{target_slot}.tsv').read_text().splitlines();names=[]
            sys=root/'sys/class/mtd';sys.mkdir(parents=True);dev=root/'dev';dev.mkdir()
            for domain in ('nor0','nand0'): (root/domain).mkdir()
            for i,line in enumerate(profile):
                name,domain,off,size,kind,erase,write,role=line.split('\t');names.append(name);node=sys/f'mtd{i}';node.mkdir()
                for key,val in dict(name=name,offset=off,size=size,type=kind,erasesize=erase,writesize=write).items(): (node/key).write_text(val)
                (node/'device').symlink_to(root/domain)
                (dev/f'mtd{i}').write_bytes(b'synthetic-raw-target')
                (dev/f'mtd{i}ro').write_bytes(bytes(int(size)) if name in ('0:ART','mfginfo','0:APPSBLENV','0:BOOTCONFIG','0:BOOTCONFIG1') else b'synthetic-readonly-region')
            target=names.index('rootfs' if target_slot==0 else 'rootfs_1');source=names.index('rootfs' if slot==0 else 'rootfs_1');art=names.index('0:ART');envindex=names.index('0:APPSBLENV')
            data=bytearray((dev/f'mtd{art}ro').read_bytes());data[64:70]=bytes.fromhex('001122334455');(dev/f'mtd{art}ro').write_bytes(data)
            ubi=root/'sys/class/ubi';ubi.mkdir()
            for u,mtd,rootname in (('ubi6',source,'ubi_rootfs'),('ubi8',target,'ubi_rootfs')):
                (ubi/u).mkdir()
                for key,val in dict(mtd_num=mtd,eraseblock_size=126976,min_io_size=2048,dev='250:0').items(): (ubi/u/key).write_text(str(val))
                (dev/u).write_bytes(b'')
                for child,name in ((0,'kernel'),(1,rootname)):
                    (ubi/f'{u}_{child}').mkdir()
                    for key,val in dict(name=name,upd_marker=0,corrupted=0,dev=f'250:{child+1}').items(): (ubi/f'{u}_{child}'/key).write_text(str(val))
                    (dev/f'{u}_{child}').write_bytes(b'synthetic-old-image')
            if unattached:
                for path in list(ubi.glob('ubi8*')):shutil.rmtree(path)
            work=root/'work';work.mkdir(mode=0o700);crit=work/'critical';crit.mkdir(mode=0o700)
            for line in (bundle/'profiles/XV3-8/critical.tsv').read_text().splitlines():
                kind,label,_,_=line.split('\t');(crit/f'{kind}.bin').write_bytes((dev/f'mtd{names.index(label)}ro').read_bytes())
            (crit/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(crit.glob('*.bin'))))
            (crit/'OFFDEVICE_VERIFIED').write_text(hashlib.sha256((crit/'SHA256SUMS').read_bytes()).hexdigest()+'\n')
            (root/'etc').mkdir();(root/'etc/version').write_text(''.join(line.replace('\t','=')+'\n' for line in (base/'profiles/XV3-8/source.tsv').read_text().splitlines()))
            (root/'tmp').mkdir();(root/'tmp/fw_env.config').write_text(f'/dev/mtd{envindex} 0x0 0x10000 0x10000 1\n')
            proc=root/'proc';(proc/'self').mkdir(parents=True);(proc/'cmdline').write_text(('ubi.mtd=rootfs' if slot==0 else 'ubi.mtd=rootfs_1')+' root=ubi6:ubi_rootfs');(proc/'mounts').write_text('');(proc/'self/mountinfo').write_text('')
            (dev/'urandom').write_bytes(bytes(range(64)))
            (root/'environment.json').write_text(json.dumps({'image':str(slot),'bootcmd':'aq_load_fw&&bootipq','factory_keep':'untouched','serial#':'factory-serial','factory.region':'EU','vendor-option':'preserve-me'}))
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
 if (dev/('mtd'+os.environ['TARGET'])).read_bytes()!=b'formatted-fixture-only':
  for i,name in ((0,'kernel'),(1,'ubi_rootfs')):
   for k,v in dict(name=name,upd_marker=0,corrupted=0,dev=f'250:{i+1}').items():put(ubi/f'ubi8_{i}'/k,v)
  if os.environ.get('CERT_TARGET')=='1':
   for k,v in dict(name='certificates',upd_marker=0,corrupted=0,dev='250:5').items():put(ubi/'ubi8_4'/k,v)
elif cmd=='ubimkvol':
 i=int(a[a.index('-n')+1]);name=a[a.index('-N')+1];size=int(a[a.index('-s')+1]) if '-s' in a else 400*126976
 for key,val in dict(name=name,reserved_ebs=(size+126975)//126976,data_bytes=size,dev=f'250:{i+1}',upd_marker=0,corrupted=0).items():put(ubi/f'ubi8_{i}'/key,val)
elif cmd=='mknod':Path(a[0]).write_bytes(b'fixture-node')
elif cmd=='ubiupdatevol':Path(a[0]).write_bytes(Path(a[1]).read_bytes())
elif cmd=='fw_setenv':
 data=json.loads((root/'environment.json').read_text());file=Path(a[a.index('-s')+1])
 for line in file.read_text().splitlines():
  k,_,v=line.partition(' ')
  if v:data[k]=v
  else:data.pop(k,None)
 if file.name=='thor-source.tsv':
  if os.environ['DRIFT']=='env-punctuation-changed':data['factory.region']='external-drift'
  elif os.environ['DRIFT']=='env-punctuation-removed':data.pop('serial#')
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
else:sys.exit(99)
''');actor.chmod(0o700)
            for cmd in ('ubidetach','ubiformat','ubiattach','ubimkvol','mknod','ubiupdatevol','fw_setenv','fw_printenv','mount','umount','sync','ls'): (tools/cmd).symlink_to('actor')
            env=dict(os.environ,PATH=str(tools)+':'+os.environ['PATH'],COMMON=str(shared),ADAPTER=str(base/'adapters/thor.sh'),OEM_SYS_ROOT=str(root),OEM_SKU='00000013',OEM_MODEL='XV3-8',OEM_SUPPORTED_RELEASE='7.2-r1',OEM_FAMILY='thor',OEM_CONTROLLER='controller.example',OEM_BUNDLE=str(bundle),OEM_WORK=str(work),TARGET=str(target),SOURCE=str(source),SLOT=str(slot),FAIL_OPERATION=str(fail),CERT_TARGET='1' if cert else '0',DRIFT=drift)
            return root,env,names

        script=r'''
. "$COMMON/common.sh"; . "$COMMON/protection.sh"; . "$ADAPTER"
# Physical node interfaces alone are file actors. Image/parts pins are actual.
oem_thor_art_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd${1}ro"; }
oem_thor_mtd_target_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd$OEM_TARGET_MTD"; }
oem_thor_target_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/${OEM_TARGET_UBI}_$1"; }
oem_thor_character_matches(){ :; }
reboot(){ exit 99; }; wget(){ exit 99; }; curl(){ exit 99; }
oem_adapter_migrate 'TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT'
'''
        def run(root,env,ok):
            nonlocal count
            protected={str(p):p.read_bytes() for p in (root/'dev').glob('mtd*ro')}
            protected.update({str(p):p.read_bytes() for p in (root/'dev').glob('ubi6*')})
            r=subprocess.run(['sh','-c',script],env=env,text=True,capture_output=True,timeout=180)
            assert (r.returncode==0)==ok,(r.returncode,r.stdout,r.stderr[-4500:])
            assert protected=={p:Path(p).read_bytes() for p in protected}
            count+=1;return r
        root,env,names=fixture();r=run(root,env,True)
        assert 'handoff=one-shot-armed' in r.stdout
        data=__import__('json').loads((root/'environment.json').read_text())
        assert 'thor_ab_version' not in data and data['thor_installer_target']==str(1-a.source_slot)
        assert data['factory_keep']=='untouched' and f'saveenv && run thor_boot{1-a.source_slot}' in data['bootcmd']
        assert {k:data[k] for k in ('serial#','factory.region','vendor-option')}=={'serial#':'factory-serial','factory.region':'EU','vendor-option':'preserve-me'}
        # Check this newly constructed vault with the unchanged shipped .8
        # consumer. Only its final command invocation and hardware readers are
        # isolated; board_files/manifest/hash checks execute byte-for-byte.
        vault=root/'vault-check';vault.mkdir()
        subprocess.run(['tar','-xf',str(root/'dev/ubi8_3'),'-C',str(vault)],check=True)
        consumer=(base/'tests/fixtures/thor-2026.10.05.8/usr/sbin/cambium-board-data').read_text()
        consumer=consumer.rsplit('main "$@"',1)[0]
        (root/'vault-consumer.sh').write_text(consumer)
        (root/'functions.sh').write_text('')
        (root/'system.sh').write_text("board_name(){ echo cambiumnetworks,xv3-8; }\nfind_mtd_index(){ echo "+str(names.index('0:ART'))+"; }\n")
        check=r'''
. "$VAULT_CONSUMER"
ab_dt_sku(){ echo 00000013; }
vault_check "$VAULT_CHECK"
'''
        checkenv={**env,'VAULT_CONSUMER':str(root/'vault-consumer.sh'),'VAULT_CHECK':str(vault),'CAMBIUM_FUNCTIONS':str(root/'functions.sh'),'CAMBIUM_SYSTEM_FUNCTIONS':str(root/'system.sh'),'CAMBIUM_AB_LIB':str(root/'bundle/runtime/cambium-ab.sh'),'CAMBIUM_AB_MODULES':str(root/'absent-modules'),'AB_DEV':str(root/'dev')}
        (root/f"dev/mtd{names.index('0:ART')}").write_bytes((root/f"dev/mtd{names.index('0:ART')}ro").read_bytes())
        subprocess.run(['sh','-c',check],env=checkenv,check=True,capture_output=True)
        # Replay the shipped identity's actual context command and native
        # pending-boot script on the writer's real staged binding/ENV triplet.
        shipped=base/'tests/fixtures/thor-2026.10.05.8'
        identity=(shipped/'usr/libexec/ucentral-installer-identity').read_text()
        context=json.loads(re.search(r'^const CONTEXT_COMMAND = (".*");$',identity,re.M)[1])
        bridge=root/'incoming-core.sh';bridge.write_text('ab_family(){ AB_ENV=thor; }; ab_identity(){ ab_family; AB_FAMILY=thor; AB_MODEL=XV3-8; AB_ACTIVE=$((1-SLOT)); }; ab_getenv(){ fw_printenv -c fixture -n "$1"; }\n')
        system=root/'incoming-system.sh';system.write_text('get_mac_label_dt(){ echo 00:11:22:33:44:55; }; get_mac_label(){ echo 00:11:22:33:44:55; }\n')
        context=context.replace('/lib/functions/system.sh',str(system)).replace('/lib/functions/cambium-ab.sh',str(bridge))
        result=subprocess.run(['sh','-c',context],env=env,capture_output=True,text=True,check=True)
        binding=dict(line.split('\t',1) for line in (root/'overlay-store/upper/root/.cambium-installer-settings/binding.tsv').read_text().splitlines())
        assert result.stdout.strip().split('\t')==[binding['serial'],'thor','XV3-8',str(1-a.source_slot),binding['target_slot'],binding['job_id'],binding['image_sha256']]
        boot=(shipped/'usr/libexec/ucentral-installer-boot').read_text().replace('/lib/functions/system.sh',str(system)).replace('/lib/functions/cambium-ab.sh',str(bridge))
        subprocess.run(['sh','-c',boot,'incoming','pending'],env=env,check=True,capture_output=True)
        trace=(root/'trace').read_text().splitlines()
        assert trace[0].startswith('sync')
        source_save=next(i for i,v in enumerate(trace) if v.startswith('fw_setenv') and v.endswith('thor-source.tsv'))
        first_detach=next(i for i,v in enumerate(trace) if v.startswith('ubidetach'))
        assert source_save < first_detach
        assert sum(v.startswith('ubiupdatevol') for v in trace)==3
        operations=int((root/'counter').read_text())
        print('Thor forward positive path passed',flush=True)
        for drift in ('env-punctuation-changed','env-punctuation-removed'):
            root,env,names=fixture(drift=drift);run(root,env,False)
            assert json.loads((root/'environment.json').read_text())['bootcmd']=='aq_load_fw&&bootipq'
            assert not any(v.startswith('ubiformat') for v in (root/'trace').read_text().splitlines())
        if a.env_only:
            print('PASS: forward unchanged punctuation keys and changed/removed refusal, slot',a.source_slot)
            return
        if a.positive_only:
            print('PASS: whole forward and exact incoming vault/context/pending consumers, current source')
            return
        print('Sweeping',operations,'failure points',flush=True)
        def failed_case(fail):
            root,env,names=fixture(fail)
            try:
                r=run(root,env,False)
                data=json.loads((root/'environment.json').read_text())
                assert data['bootcmd']=='aq_load_fw&&bootipq',(fail,data['bootcmd'])
                assert data['factory_keep']=='untouched'
                assert 'T'*64 not in r.stdout+r.stderr+((root/'trace').read_text() if (root/'trace').exists() else '')
            finally:shutil.rmtree(root)
        with ThreadPoolExecutor(max_workers=4) as workers:list(workers.map(failed_case,range(1,operations+1)))
        root,env,names=fixture(unattached=True);run(root,env,True)
        trace=(root/'trace').read_text().splitlines()
        assert sum(v.startswith('ubiattach') for v in trace)==2
        root,env,names=fixture(unattached=True,cert=True);run(root,env,False)
        assert not any(v.startswith('ubiformat') for v in (root/'trace').read_text().splitlines())
        assert json.loads((root/'environment.json').read_text())['bootcmd']=='aq_load_fw&&bootipq'
        print(f'PASS: {count} whole forward cases, failures at all {operations} persistent/process steps; no premature arm')
        print('Scope: actual image/parts/BDF pins, settings producer/stager, physical/source/ENV checks and allocator; device/mount/fwtools are actors. No AP, EST, build or boot action.')

if __name__=='__main__':main()
