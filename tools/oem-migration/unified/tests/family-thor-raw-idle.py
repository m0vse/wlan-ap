#!/usr/bin/env python3
"""Actual pre-attach direct raw alias guard; device-number ls is an actor."""
from pathlib import Path
import os,subprocess,tempfile
base=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='thor-raw-idle-') as td:
 root=Path(td).resolve();dev=root/'dev';dev.mkdir();sys=root/'sys/class';(sys/'mtd/mtd7').mkdir(parents=True);(sys/'block/mtdblock7').mkdir(parents=True)
 (sys/'mtd/mtd7/name').write_text('rootfs');(sys/'mtd/mtd7/dev').write_text('90:14');(sys/'block/mtdblock7/dev').write_text('31:7')
 proc=root/'proc';(proc/'self').mkdir(parents=True);(proc/'123/fd').mkdir(parents=True)
 for n in ('mtd7','mtd7ro','mtdblock7','unhelpful-name','mtd8'):(dev/n).write_bytes(b'synthetic')
 (dev/'alias').symlink_to(dev/'mtdblock7')
 script=r'''
. "$ADAPTER"
OEM_TARGET_MTD=7 OEM_SOURCE_MTD=0 OEM_PROTECTED_RANGES=$OEM_SYS_ROOT/ranges OEM_WORK=$OEM_SYS_ROOT/work
mkdir -p "$OEM_WORK"
printf '0\t0\t100663296\tactive-oem\tnand0\n7\t100663296\t100663296\ttarget\tnand0\n2\t0\t65536\tenvironment\tnor0\n' > "$OEM_PROTECTED_RANGES"
oem_thor_critical_check(){ :; }
oem_thor_mtd_target_node(){ echo "$OEM_SYS_ROOT/dev/mtd7"; }
ls(){
 if [ "$BY_NUMBER" = yes ]; then printf 'crw------- 1 0 0 90, 14 Jan 1 00:00 fd\n'
 else command ls "$@"; fi
}
ubiattach(){ printf attached > "$OEM_SYS_ROOT/attached"; mkdir -p "$OEM_SYS_ROOT/sys/class/ubi/ubi8"; echo 7 > "$OEM_SYS_ROOT/sys/class/ubi/ubi8/mtd_num"; }
oem_thor_target_attachment after-source-save
'''
 cases=[('idle','', '',None,False,True),('mounted-raw',str(dev/'mtd7')+' /busy jffs2 rw 0 0\n','',None,False,False),('mounted-block-alias',str(dev/'alias')+' /busy squashfs ro 0 0\n','',None,False,False),('mounted-number','','1 0 31:7 / /busy rw - squashfs hidden ro\n',None,False,False),('open-raw','','',dev/'mtd7',False,False),('open-ro','','',dev/'mtd7ro',False,False),('open-block-alias','','',dev/'alias',False,False),('open-number-alias','','',dev/'unhelpful-name',True,False),('other-device','','',dev/'mtd8',False,True)]
 for name,mounts,mountinfo,fd,number,ok in cases:
  (proc/'mounts').write_text(mounts);(proc/'self/mountinfo').write_text(mountinfo)
  f=proc/'123/fd/6';f.unlink(missing_ok=True)
  if fd:f.symlink_to(fd)
  (root/'attached').unlink(missing_ok=True)
  import shutil
  shutil.rmtree(sys/'ubi',ignore_errors=True)
  r=subprocess.run(['sh','-c',script],env={**os.environ,'ADAPTER':str(base/'adapters/thor.sh'),'OEM_SYS_ROOT':str(root),'BY_NUMBER':'yes' if number else 'no'},capture_output=True,text=True)
  assert (r.returncode==0)==ok,(name,r.stderr)
  assert (root/'attached').exists()==ok,name
 print(f'PASS: {len(cases)} pre-attach raw mount/FD alias cases; busy targets cause no attachment')
 print('Scope: actual raw/attachment guard, synthetic proc/sys and ls device-number actor; no device or ENV action.')
