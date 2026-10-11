#!/usr/bin/env python3
"""Reuse actual A/B allocator with file actors; never formats a real device."""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import tempfile


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('common_lib',type=Path);ap.add_argument('runtime_root',type=Path);ap.add_argument('provider',type=Path)
    a=ap.parse_args();base=Path(__file__).resolve().parents[1]; count=0
    with tempfile.TemporaryDirectory(prefix='thor-layout-') as td:
        top=Path(td).resolve();shared=top/'shared';shared.mkdir()
        for n in ('common.sh','protection.sh'): (shared/n).write_bytes((a.common_lib/n).read_bytes())

        def fixture(fail=0):
            root=top/'case';shutil.rmtree(root,ignore_errors=True);root.mkdir(mode=0o700)
            bundle=root/'bundle';shutil.copytree(a.provider,bundle)
            runtime=bundle/'runtime';runtime.mkdir()
            for n,p in [('cambium-ab.sh','cambium-ab/files/cambium-ab.sh'),('cambium-ab-upgrade.sh','cambium-ab/files/cambium-ab-upgrade.sh'),('cambium-ab-thor.sh','cambium-thor-support/files/cambium-ab-thor.sh')]:
                (runtime/n).write_bytes((a.runtime_root/'package/cambium'/p).read_bytes())
            radio=bundle/'payloads/shared-radio';radio.mkdir();asset=radio/'fixture-bdf';asset.write_bytes(b'synthetic-shared-BDF')
            (bundle/'profiles/XV3-8/vault-assets.tsv').write_text(f'lib/firmware/IPQ8074/bdwlan.b215.accton\tpayloads/shared-radio/fixture-bdf\t{asset.stat().st_size}\t{hashlib.sha256(asset.read_bytes()).hexdigest()}\n')
            files=[p for p in bundle.rglob('*') if p.is_file() and p.name!='SHA256SUMS']
            (bundle/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(bundle)}\n' for p in sorted(files)))
            profile=(bundle/'profiles/XV3-8/mtd-slot0.tsv').read_text().splitlines();names=[]
            sys=root/'sys/class/mtd';sys.mkdir(parents=True);dev=root/'dev';dev.mkdir()
            for domain in ('nor0','nand0'): (root/domain).mkdir()
            for i,line in enumerate(profile):
                name,domain,off,size,kind,erase,write,role=line.split('\t');names.append(name);node=sys/f'mtd{i}';node.mkdir()
                for key,val in dict(name=name,offset=off,size=size,type=kind,erasesize=erase,writesize=write).items(): (node/key).write_text(val)
                (node/'device').symlink_to(root/domain)
                (dev/f'mtd{i}').write_bytes(b'synthetic-raw-target')
                (dev/f'mtd{i}ro').write_bytes(bytes(int(size)) if name in ('0:ART','mfginfo','0:APPSBLENV','0:BOOTCONFIG','0:BOOTCONFIG1') else b'synthetic-readonly-region')
            target=names.index('rootfs');source=names.index('rootfs_1');art=names.index('0:ART');envindex=names.index('0:APPSBLENV')
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
            work=root/'work';work.mkdir(mode=0o700);crit=work/'critical';crit.mkdir(mode=0o700)
            for line in (bundle/'profiles/XV3-8/critical.tsv').read_text().splitlines():
                kind,label,_,_=line.split('\t');(crit/f'{kind}.bin').write_bytes((dev/f'mtd{names.index(label)}ro').read_bytes())
            (crit/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in sorted(crit.glob('*.bin'))))
            (crit/'OFFDEVICE_VERIFIED').write_text(hashlib.sha256((crit/'SHA256SUMS').read_bytes()).hexdigest()+'\n')
            (root/'etc').mkdir();(root/'etc/version').write_text('VERSION=7.2-r1\n')
            (root/'tmp').mkdir();(root/'tmp/fw_env.config').write_text(f'/dev/mtd{envindex} 0x0 0x10000 0x10000 1\n')
            proc=root/'proc';(proc/'self').mkdir(parents=True);(proc/'cmdline').write_text('ubi.mtd=rootfs_1 root=ubi6:ubi_rootfs');(proc/'mounts').write_text('');(proc/'self/mountinfo').write_text('')
            tools=root/'bin';tools.mkdir()
            actor=tools/'actor'
            actor.write_text(r'''#!/usr/bin/env python3
import os,sys,json,shutil
from pathlib import Path
root=Path(os.environ['OEM_SYS_ROOT']);state=root/'counter';n=int(state.read_text())+1 if state.exists() else 1;state.write_text(str(n))
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
elif cmd=='ubimkvol':
 i=int(a[a.index('-n')+1]);name=a[a.index('-N')+1];size=int(a[a.index('-s')+1]) if '-s' in a else 400*126976
 for key,val in dict(name=name,reserved_ebs=(size+126975)//126976,data_bytes=size,dev=f'250:{i+1}',upd_marker=0,corrupted=0).items():put(ubi/f'ubi8_{i}'/key,val)
elif cmd=='mknod':Path(a[0]).write_bytes(b'fixture-node')
else:sys.exit(99)
''');actor.chmod(0o700)
            for cmd in ('ubidetach','ubiformat','ubiattach','ubimkvol','mknod'): (tools/cmd).symlink_to('actor')
            env=dict(os.environ,PATH=str(tools)+':'+os.environ['PATH'],COMMON=str(shared),ADAPTER=str(base/'adapters/thor.sh'),OEM_SYS_ROOT=str(root),OEM_SKU='00000013',OEM_MODEL='XV3-8',OEM_SUPPORTED_RELEASE='7.2-r1',OEM_BUNDLE=str(bundle),OEM_WORK=str(work),TARGET=str(target),SOURCE=str(source),FAIL_OPERATION=str(fail))
            return root,env,names

        script=r'''
. "$COMMON/common.sh"; . "$COMMON/protection.sh"; . "$ADAPTER"
# Image policy is separately tested/owner-verified; physical device interfaces
# are file actors. Actual source inspection, bundle/ranges/idle and allocator run.
oem_thor_published_image_valid(){ :; }
oem_thor_art_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd${1}ro"; }
oem_thor_mtd_target_node(){ printf '%s\n' "$OEM_SYS_ROOT/dev/mtd$OEM_TARGET_MTD"; }
oem_thor_character_matches(){ :; }
fw_printenv(){ printf 'image=1\nbootcmd=aq_load_fw&&bootipq\n'; }
fw_setenv(){ exit 99; }; reboot(){ exit 99; }; wget(){ exit 99; }; curl(){ exit 99; }
oem_thor_prepare_native_layout "$OEM_SYS_ROOT/fixture-image"
'''
        def run(root,env,ok):
            nonlocal count
            protected={str(p):p.read_bytes() for p in (root/'dev').glob('mtd*ro')}
            protected.update({str(p):p.read_bytes() for p in (root/'dev').glob('ubi6*')})
            r=subprocess.run(['sh','-c',script],env=env,text=True,capture_output=True,timeout=40)
            assert (r.returncode==0)==ok,(r.returncode,r.stdout,r.stderr)
            assert protected=={p:Path(p).read_bytes() for p in protected}
            count+=1;return r
        root,env,names=fixture();r=run(root,env,True);assert r.stdout.strip()=='ubi8'
        operations=int((root/'counter').read_text())
        for fail in range(1,operations+1):
            root,env,names=fixture(fail);run(root,env,False)
        for fault in ('bad-receipt','extra-cert','busy','wrong-offset','missing-radio'):
            root,env,names=fixture()
            if fault=='bad-receipt':(root/'work/critical/OFFDEVICE_VERIFIED').write_text('0'*64)
            elif fault=='extra-cert':p=root/'sys/class/ubi/ubi8_4';p.mkdir();(p/'name').write_text('certificates')
            elif fault=='busy':(root/'proc/mounts').write_text('/dev/ubi8_1 /target squashfs ro 0 0\n')
            elif fault=='wrong-offset':(root/f'sys/class/mtd/mtd{names.index("rootfs")}/offset').write_text('1')
            elif fault=='missing-radio':(root/'bundle/payloads/shared-radio/fixture-bdf').unlink()
            run(root,env,False);assert not (root/'counter').exists()
        print(f'PASS: {count} real allocator/wrapper cases; {operations} operation failure points; active/OEM/ART/MFG/ENV/boot bytes unchanged')
        print('Scope: actual cached runtime allocator, source/range/idle/receipt logic; process/device/image-pin boundaries are file actors. No real erase, mounts, native issuer, boot, download or firmware build.')


if __name__=='__main__':main()
