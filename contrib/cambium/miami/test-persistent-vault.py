#!/usr/bin/env python3
"""Actual radio-loader persistent vault context and RAM isolation."""
from pathlib import Path
import tempfile,subprocess,struct,os
repo=Path(__file__).resolve().parents[3]
s=(repo/'feeds/tip/cambium-miami-radio/files/miami-board-data').read_text()
start=s.index('persistent_vault_locate() {');end=s.index('\nmanifest_value()',start);functions=s[start:end]
with tempfile.TemporaryDirectory(prefix='miami-persistent-vault-') as td:
 r=Path(td)
 for n,name,flags in [(2,'rootfs','0xc00'),(3,'rootfs_1','0x800')]:
  d=r/f'sys/class/mtd/mtd{n}';d.mkdir(parents=True);(d/'name').write_text(name);(d/'size').write_text('100663296');(d/'flags').write_text(flags)
 (r/'proc/device-tree/cambium-platform').mkdir(parents=True);slot=r/'proc/device-tree/cambium-platform/storage-slot';slot.write_bytes(struct.pack('>I',0))
 (r/'sys/class/ubi/ubi0').mkdir(parents=True);(r/'sys/class/ubi/ubi0/mtd_num').write_text('2');(r/'sys/class/ubi/ubi0/ro_mode').write_text('0')
 d=r/'sys/class/ubi/ubi0_3';d.mkdir();(d/'name').write_text('cambium_device_data');(d/'reserved_ebs').write_text('72')
 functions=functions.replace('/sys/',str(r)+'/sys/').replace('/proc/',str(r)+'/proc/').replace('VAULT_DEV=/dev/ubi0_3','VAULT_DEV='+str(r)+'/dev/ubi0_3')
 prelude='''VAULT_NAME=cambium_device_data; WORK=/tmp/fixture; BANK_OWNED=0
 board(){ echo "${TEST_BOARD:-cambiumnetworks,x7-35x}"; }; sku(){ echo "${TEST_SKU:-0000002c}"; }; running_part(){ echo "${TEST_PART:-rootfs}"; }
 hexdump(){ python3 -c 'import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_bytes().hex(),end="")' "$4"; }
 wait_node(){ :; }; vault_read(){ return "${FAIL_READ:-0}"; }; vault_check(){ return "${FAIL_CHECK:-0}"; }
 bank_attach(){ echo forbidden attach >&2;return 1; }; bank_release(){ echo forbidden detach >&2;return 1; }
'''
 # Actual MTD helpers, with paths relocated into the fixture.
 a=s.index('mtd_by_name() {');b=s.index('# Nothing creates',a);prelude+=s[a:b].replace('/sys/',str(r)+'/sys/')
 def run(ok=True,extra=None):
  p=subprocess.run(['sh','-c',prelude+functions+'\nvault_locate && [ "$BANK_OWNED:$BANK_UBI:$VAULT_DEV" = "0:0:'+str(r)+'/dev/ubi0_3" ]'],env=dict(os.environ,**(extra or {})),capture_output=True,text=True)
  assert (p.returncode==0)==ok,(p.stdout,p.stderr);assert 'forbidden' not in p.stderr
 run()
 for extra in [{'TEST_BOARD':'wrong'},{'TEST_SKU':'0000002d'},{'TEST_PART':'rootfs_1'},{'FAIL_READ':'1'},{'FAIL_CHECK':'2'}]:run(False,extra)
 for path,wrong,right in [(r/'sys/class/mtd/mtd3/flags','0xc00','0x800'),(r/'sys/class/mtd/mtd2/size','1','100663296'),(r/'sys/class/ubi/ubi0/mtd_num','3','2'),(r/'sys/class/ubi/ubi0/ro_mode','1','0'),(d/'reserved_ebs','8','72')]:
  path.write_text(wrong);run(False);path.write_text(right)
 slot.write_bytes(struct.pack('>I',1));run(False);(r/'sys/class/mtd/mtd2/flags').write_text('0x800');(r/'sys/class/mtd/mtd3/flags').write_text('0xc00');(r/'sys/class/ubi/ubi0/mtd_num').write_text('3');run(True,{'TEST_PART':'rootfs_1'})
print('PASS: actual persistent vault path exact slot/model/SKU/geometry/active ubi0/72LEB; no attach/detach/write; sibling writable/wrong active/foreign/corrupt vault refuses; both slots')
