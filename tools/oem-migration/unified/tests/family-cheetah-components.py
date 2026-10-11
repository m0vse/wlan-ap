#!/usr/bin/env python3
"""Actual factory/slot and local-volume code; synthetic devices, real bytes."""
from pathlib import Path
import tempfile,os,subprocess,hashlib,json,shlex
base=Path(__file__).resolve().parents[1];common=Path(os.environ.get('OEM_TEST_COMMON_DIR',str(base/'lib')))
cases=[]
with tempfile.TemporaryDirectory(prefix='cheetah-components.') as temp:
 for slot in [0,1]:
  for fault in ['none','padded-byte-count','bad-mfg','wrong-version','image-conflict','bad-bank-geometry','bad-payload-hash','wrong-parent','bad-child-name','busy-child','volume-too-small','writer-error','short-readback','corrupt-readback','server-gone','resize-success','resize-no-space','resize-writer-error','resize-bad-readback','resize-static','resize-wrong-parent']:
   work=Path(temp).resolve()/(str(slot)+'-'+fault);work.mkdir();sysroot=work/'capture';(sysroot/'etc').mkdir(parents=True);(sysroot/'proc').mkdir();(sysroot/'dev').mkdir();(sysroot/'sys/class/mtd').mkdir(parents=True);(sysroot/'sys/class/ubi').mkdir(parents=True)
   (sysroot/'etc/version').write_text('VERSION=fixture-oem-7.1.1\n');(sysroot/'proc/cmdline').write_text('console=ttyMSM0 ubi.mtd='+('rootfs' if slot==0 else 'rootfs_1')+' rootwait\n')
   rows=[(2,'rootfs','nand',100663296,131072,2048),(3,'rootfs_1','nand',100663296,131072,2048),(10,'mfginfo','nor',65536,4096,1),(16,'0:APPSBLENV','nor',65536,4096,1)]
   for idx,name,kind,size,erase,write in rows:
    p=sysroot/'sys/class/mtd'/('mtd'+str(idx));p.mkdir()
    for key,value in [('name',name),('type',kind),('size',size),('erasesize',erase),('writesize',write)]:(p/key).write_text(str(value)+'\n')
   (sysroot/'dev/mtd10ro').write_bytes(bytes.fromhex('05ca01000c00')+b'0123456789ab'+b'fixture-padding')
   if fault=='bad-mfg':(sysroot/'dev/mtd10ro').write_bytes(b'badheader000000000000')
   if fault=='bad-bank-geometry':(sysroot/'sys/class/mtd/mtd3/size').write_text('100663295\n')
   envfile=work/'env';envfile.write_text('bootcmd=bootipq\nimage='+str(1-slot if fault=='image-conflict' else slot)+'\nethaddr=synthetic-preserved\n')
   cache=work/'cache';cache.mkdir();payload=cache/'kernel.itb';payload.write_bytes(b'Actual synthetic kernel bytes\0'+bytes(range(64)));digest=hashlib.sha256(payload.read_bytes()).hexdigest();size=payload.stat().st_size
   if fault=='volume-too-small' or fault.startswith('resize-'):payload.write_bytes(b'x'*126977);digest=hashlib.sha256(payload.read_bytes()).hexdigest();size=payload.stat().st_size
   ubi=sysroot/'sys/class/ubi/ubi7';ubi.mkdir();(sysroot/'dev/ubi7').write_bytes(b'synthetic-control');(ubi/'avail_eraseblocks').write_text('0\n' if fault=='resize-no-space' else '3\n');(ubi/'mtd_num').write_text(str(2 if 1-slot==0 else 3)+'\n');child=sysroot/'sys/class/ubi/ubi7_0';child.mkdir()
   for key,value in [('type','static' if fault=='resize-static' else 'dynamic'),('name','other' if fault=='bad-child-name' else 'kernel'),('upd_marker',1 if fault=='busy-child' else 0),('corrupted',0),('reserved_ebs',1),('usable_eb_size',126976)]:(child/key).write_text(str(value)+'\n')
   target=sysroot/'dev/ubi7_0';target.write_bytes(b'previous-inactive-kernel')
   protected=work/'protected';protected.mkdir()
   for name in ['ART','MFG','active-bank','ENV','certificates','vault']:(protected/name).write_bytes(('OWN:'+name).encode())
   before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected.iterdir()};envbefore=envfile.read_bytes()
   inventory=work/'ranges';inventory.write_text('2\t524288\t100663296\t'+('active-oem' if slot==0 else 'target')+'\tnand0\n3\t101187584\t100663296\t'+('active-oem' if slot==1 else 'target')+'\tnand0\n10\t1769472\t65536\tidentity\tnor0\n16\t3866624\t65536\tenvironment\tnor0\n')
   parent=2 if 1-slot==0 else 3;plan=work/'plan';plan.write_text('ubi-update\t'+str(parent)+'\t0\tkernel\n');
   if fault.startswith('resize-'):plan.write_text(plan.read_text()+'ubi-resize\t'+str(parent)+'\t0\tkernel\n')
   trace=work/'trace';driver=work/'driver'
   driver.write_text('''#!/bin/sh
. "$COMMON/common.sh"
. "$COMMON/protection.sh"
. "$ADAPTER"
fw_printenv(){
 if [ "$#" = 2 ];then cat "$TEST_ENV";return;fi
 awk -F= -v key="$4" '$1==key{print substr($0,index($0,"=")+1);n++}END{exit n!=1}' "$TEST_ENV"
}
wc(){
 if [ "$FAULT" = padded-byte-count ] && [ "$1" = -c ];then
  count=$(command wc -c);printf '    %s\\n' "$count"
 else command wc "$@";fi
}
ubiupdatevol(){
 printf 'write\n' >> "$TRACE"
 [ "$FAULT" != writer-error ] || return 1
 case "$FAULT" in short-readback) head -c 5 "$2" > "$1";; corrupt-readback) printf corrupt > "$1";; *) cp "$2" "$1";; esac
}
ubirsvol(){
 printf 'resize\\n' >> "$TRACE"
 [ "$FAULT" != resize-writer-error ] || return 1
 [ "$FAULT" != resize-bad-readback ] || return 0
 printf '%s\\n' "$(( $5 / 126976 ))" > "$OEM_SYS_ROOT/sys/class/ubi/ubi7_0/reserved_ebs"
}
fw_setenv(){ printf forbidden-env >> "$TRACE";return 99; }
curl(){ printf forbidden-network >> "$TRACE";return 99; }
wget(){ printf forbidden-network >> "$TRACE";return 99; }
oem_adapter_inspect || exit 11
oem_adapter_boot_preflight || exit 12
case "$FAULT" in resize-*) oem_cheetah_grow_local_kernel "$PAYLOAD" "$SIZE" "$DIGEST" || exit 14;; esac
oem_cheetah_update_local_child 0 kernel "$PAYLOAD" "$SIZE" "$DIGEST" || exit 13
''')
   env={**os.environ,'COMMON':str(common),'ADAPTER':str(base/'adapters/cheetah.sh'),'OEM_FAMILY':'cheetah','OEM_MODEL':'XV2-21X','OEM_SKU':'00000023','OEM_SYS_ROOT':str(sysroot),'OEM_WORK':str(work),'OEM_SUPPORTED_RELEASE':'older-version' if fault=='wrong-version' else 'fixture-oem-7.1.1','TEST_ENV':str(envfile),'FAULT':fault,'TRACE':str(trace),'PAYLOAD':str(payload),'SIZE':str(size),'DIGEST':'0'*64 if fault=='bad-payload-hash' else digest,'OEM_PROTECTED_RANGES':str(inventory),'OEM_WRITE_PLAN':str(plan),'OEM_CHEETAH_TARGET_MTD':str(2 if parent==3 else 3) if fault in ['wrong-parent','resize-wrong-parent'] else str(parent),'OEM_CHEETAH_TARGET_UBI':'ubi7'}
   p=subprocess.run(shlex.split(os.environ.get('OEM_TEST_SHELL','sh'))+[str(driver)],env=env,capture_output=True,text=True)
   success=fault in ['none','padded-byte-count','server-gone','resize-success'];assert (p.returncode==0)==success,(slot,fault,p.returncode,p.stderr)
   assert envfile.read_bytes()==envbefore and {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected.iterdir()}==before
   ops=trace.read_text() if trace.exists() else '';assert 'forbidden' not in ops
   if success:assert target.read_bytes()==payload.read_bytes() and ops==('resize\nwrite\n' if fault=='resize-success' else 'write\n')
   elif fault not in ['writer-error','short-readback','corrupt-readback','resize-writer-error','resize-bad-readback']:assert not trace.exists()
   cases.append({'slot':slot,'fault':fault,'passed':True,'actual_cached_bytes_checked':True,'prior_and_unique_bytes_unchanged':True})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'scope':'Actual Cheetah selector, kernel grow and updater plus actual common range/child helpers. Synthetic NOR/NAND/sysfs/ENV and trapped UBI tool; real file bytes/hash/readback. Manual-reset predicate follows clarified ABI. No production OEM version/payload admission, boot arm or hardware/power-loss claim.'},indent=2))
