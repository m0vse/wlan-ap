#!/usr/bin/env python3
"""Actual .1 preinit and first normal upgrade actor; inert media tools only.
Fresh OEM source has no opposite-slot OpenWiFi overlay. No AP/init/ELF runs.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
PINS={'family':'ef900bf87427b09bb2ba741c2f0b8d46220fcab9babbe0698e153f35768e9094','preinit':'3c27e4c08b4faacf389e2ede3562051d55553b0fd32a8f68afec973ab3ed0368'}
def source(kind):
 data=(HERE/f'tests/fixtures/sage-2026.10.07.1-{kind}.source').read_bytes()
 if hashlib.sha256(data).hexdigest()!=PINS[kind]:raise AssertionError('actual .1 consumer changed')
 return data.decode()
def functions(text,names):
 return '\n'.join(re.search(r'^'+re.escape(name)+r'\(\) \{\n.*?^\}',text,re.M|re.S)[0] for name in names)

BACKEND=r'''
import json,os,sys
from pathlib import Path
root=Path(os.environ['ROOT']);sysdir=root/'sys';dev=root/'dev';cmd,args=sys.argv[1],sys.argv[2:];active=int(os.environ['ACTIVE']);target=1-active
with (root/'events').open('a') as log:log.write(cmd+' '+json.dumps(args)+'\n')
def node(i):return sysdir/f'ubi0_{i}'
def free(delta):
 p=sysdir/'ubi0/avail_eraseblocks';p.write_text(str(int(p.read_text())+delta))
if cmd=='ubimkvol':
 assert args[0]==str(dev/'ubi0') and '-n' not in args
 name=args[args.index('-N')+1]
 assert name in ('certificates',f'rootfs_data{target}')
 assert not any((p/'name').read_text()==name for p in sysdir.glob('ubi0_*'))
 i=next(i for i in range(128) if not node(i).exists())
 blocks=int(args[args.index('-S')+1]) if '-S' in args else int(args[args.index('-s')+1])//126976
 assert blocks==(20 if name=='certificates' else 67)
 node(i).mkdir()
 for k,v in dict(name=name,reserved_ebs=blocks,usable_eb_size=126976,type='dynamic',corrupted=0,upd_marker=0).items():(node(i)/k).write_text(str(v))
 (dev/f'ubi0_{i}').write_bytes(b'');free(-blocks)
elif cmd=='ubirsvol':
 assert args[:2]==[str(dev/'ubi0'),'-n']
 i=int(args[2]);assert i==2*target+1
 blocks=int(args[4])//126976;assert blocks==285
 previous=int((node(i)/'reserved_ebs').read_text());(node(i)/'reserved_ebs').write_text(str(blocks));free(previous-blocks)
elif cmd=='ubiupdatevol':
 trunc=args[0]=='-t';path=Path(args[1] if trunc else args[0]);i=int(path.name.split('_')[1]);name=(node(i)/'name').read_text()
 assert name in (f'linux{target}',f'rootfs{target}',f'rootfs_data{target}')
 path.write_bytes(b'' if trunc else Path(args[1]).read_bytes())
elif cmd=='mount':
 assert args[:2]==['-t','ubifs'];i=int(Path(args[2]).name.split('_')[1]);assert (node(i)/'name').read_text()==f'rootfs_data{target}'
elif cmd!='umount':raise AssertionError(cmd)
'''

class VolumeIdTests(unittest.TestCase):
 def invoke(self,active,stock=False):
  holder=tempfile.TemporaryDirectory();self.addCleanup(holder.cleanup);root=Path(holder.name)
  sysdir=root/'sys';dev=root/'dev';bin=root/'bin'
  for p in (sysdir,dev,bin,sysdir/'ubi0'):p.mkdir()
  volumes={0:('linux0',34),1:('rootfs0',285 if active==0 else (305 if stock else 372)),2:('linux1',34),3:('rootfs1',285 if active==1 else (305 if stock else 372)),4:('nvram',167 if stock else 187),6-active:(f'rootfs_data{active}',67)}
  if stock:volumes[6-(1-active)]=(f'rootfs_data{1-active}',67)
  for i,(name,blocks) in volumes.items():
   p=sysdir/f'ubi0_{i}';p.mkdir()
   for k,v in dict(name=name,reserved_ebs=blocks,usable_eb_size=126976,type='dynamic',corrupted=0,upd_marker=0).items():(p/k).write_text(str(v))
   (dev/f'ubi0_{i}').write_bytes(('source '+name).encode())
  for k,v in dict(mtd_num=9,eraseblock_size=126976,avail_eraseblocks=1004-sum(v[1] for v in volumes.values())).items():(sysdir/'ubi0'/k).write_text(str(v))
  (root/'mounts').write_text(f'{dev}/ubi0_{6-active} /overlay ubifs rw 0 0\n')
  (root/'root').write_bytes(b'hsqsnonflashable incoming root');(root/'kernel').write_bytes(b'nonflashable incoming kernel')
  (root/'backend.py').write_text(BACKEND)
  for command in ('ubimkvol','ubiupdatevol','ubirsvol','mount','umount'):
   p=bin/command;p.write_text('#!/bin/sh\nexec python3 "$ROOT/backend.py" '+command+' "$@"\n');p.chmod(0o755)
  code=functions(source('preinit'),('generate_cambium_sage_certificate_volume',))+ '\n'+functions(source('family'),('ab_sage_inactive_root','ab_sage_prepare_overlay','ab_sage_write_target'))
  mocks=r'''
ab_identity() { AB_FAMILY=sage; AB_LAYOUT=pair; AB_QUALIFIED=1; AB_CERTIFICATE_LEBS=0; AB_ACTIVE_MTD=9; AB_TARGET_MTD=9; AB_ACTIVE_UBI=ubi0; AB_LEB=126976; }
ab_ubi_volume() {
 local p found= count=0
 for p in "$AB_UBI_SYS/$1"_*; do
  [ -r "$p/name" ] && [ "$(cat "$p/name")" = "$2" ] || continue
  found=${p##*/};count=$((count+1))
 done
 [ "$count" = 1 ] && printf '%s\n' "$found"
}
ab_step() { shift; "$@"; }
ab_ubi_node() { return 0; }
ab_getenv() { return 1; }
ab_setenv_batch() { cp "$1" "$ROOT/env-batch"; }
ab_record_failure() { echo "$*" >&2; return 1; }
ab_verify_volume() { [ "$(head -c "$3" "$1" | sha256sum | cut -d' ' -f1)" = "$(sha256sum < "$2" | cut -d' ' -f1)" ]; }
sync() { return 0; }
ab_identity
AB_TARGET=$((1-AB_ACTIVE));AB_SAGE_ROOT_LEBS=285;AB_SAGE_DATA_LEBS=67
AB_ROOT=$ROOT/root;AB_KERNEL=$ROOT/kernel;AB_KERNEL_SIZE=$(wc -c < "$AB_KERNEL");AB_ROOT_SIZE=$(wc -c < "$AB_ROOT")
generate_cambium_sage_certificate_volume || exit 1
cert=$(ab_ubi_volume ubi0 certificates) || exit 1
printf 'native identity placeholder' > "$AB_DEV/$cert"
sha256sum "$AB_DEV/$cert" > "$ROOT/cert-before"
generate_cambium_sage_certificate_volume || exit 1
ab_sage_write_target || exit 1
sha256sum "$AB_DEV/$cert" > "$ROOT/cert-after"
cmp -s "$ROOT/cert-before" "$ROOT/cert-after" || exit 1
printf 'certificate=%s\nnew_overlay=%s\n' "$cert" "$AB_SAGE_DATA_VOL"
'''
  env=dict(os.environ,ROOT=str(root),ACTIVE=str(active),AB_ACTIVE=str(active),AB_DEV=str(dev),AB_UBI_SYS=str(sysdir),AB_PROC_MOUNTS=str(root/'mounts'),AB_BLOCK_SYS=str(root/'block'),AB_NEWROOT=str(root/'newroot'),PATH=str(bin)+':'+os.environ['PATH'])
  protected={p:p.read_bytes() for p in (dev/f'ubi0_{2*active}',dev/f'ubi0_{2*active+1}',dev/f'ubi0_{6-active}',dev/'ubi0_4')}
  result=subprocess.run(['sh','-c',code+'\n'+mocks],env=env,capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(protected,{p:p.read_bytes() for p in protected})
  return dict(row.split('=',1) for row in result.stdout.splitlines())
 def test_fresh_oem_both_slots_dynamic_cert_then_first_normal_upgrade(self):
  for active in (0,1):
   result=self.invoke(active)
   self.assertEqual(result['certificate'],f'ubi0_{5+active}')
   self.assertEqual(result['new_overlay'],'ubi0_7')
 def test_both_legacy_overlays_cert7_is_preserved_and_other_overlay_reused(self):
  for active in (0,1):
   result=self.invoke(active,True)
   self.assertEqual(result['certificate'],'ubi0_7')
   self.assertEqual(result['new_overlay'],f'ubi0_{6-(1-active)}')

if __name__=='__main__':unittest.main()
