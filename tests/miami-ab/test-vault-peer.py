#!/usr/bin/env python3
"""Actual own-vault locator; synthetic MTD/UBI and archive-check actors."""
from pathlib import Path
import os,tempfile,subprocess
repo=Path(__file__).resolve().parents[2];source=(repo/'feeds/tip/cambium-miami-radio/files/miami-board-data').read_text();start=source.index('persistent_vault_locate() {');end=source.index('\n}\n',start)+3;body=source[start:end]
with tempfile.TemporaryDirectory(prefix='miami-vault-peer-') as td:
 r=Path(td).resolve();(r/'proc/device-tree/cambium-platform').mkdir(parents=True);(r/'sys/class/mtd').mkdir(parents=True);(r/'sys/class/ubi/ubi0').mkdir(parents=True);(r/'sys/class/ubi/ubi0_3').mkdir();(r/'lib/functions').mkdir(parents=True)
 (r/'sys/class/ubi/ubi0/ro_mode').write_text('0');(r/'sys/class/ubi/ubi0_3/name').write_text('cambium_device_data');(r/'sys/class/ubi/ubi0_3/reserved_ebs').write_text('72')
 for n in (2,3):(r/f'sys/class/mtd/mtd{n}').mkdir();(r/f'sys/class/mtd/mtd{n}/size').write_text('100663296')
 # Exact shared storage/geometry callbacks are boundaries here, independently
 # inspected/tested elsewhere. Rejecting either must block writable peers.
 (r/'lib/functions/cambium-ab.sh').write_text('ab_identity(){ AB_ACTIVE_MTD=$((2+SLOT)) AB_TARGET_MTD=$((3-SLOT)); };ab_miami_ab_profile(){ [ "$PROFILE" = ab ]; };ab_miami_storage_context(){ [ "$STORAGE" = ok ]; };ab_miami_upgrade_geometry(){ [ "$GEOMETRY" = ok ]; }\n')
 (r/'lib/functions/system.sh').write_text('# Library import is an explicit boundary in this callback-only test.\n')
 for prefix in ('/proc/','/sys/','/lib/'):body=body.replace(prefix,str(r)+prefix)
 driver='''
board(){ echo cambiumnetworks,x7-35x; };sku(){ echo 0000002c; }
running_part(){ if [ "$SLOT" = 0 ];then echo rootfs;else echo rootfs_1;fi; }
hexdump(){ printf '%08x\\n' "$SLOT"; }
mtd_by_name(){ case "$1" in rootfs) echo 2;;rootfs_1) echo 3;;esac; }
mtd_ro(){ [ "$1" = "$((3-SLOT))" ] && [ "$PEER" = ro ]; }
wait_node(){ :; };vault_read(){ :; };vault_check(){ :; }
VAULT_NAME=cambium_device_data WORK=/tmp/no-write
'''+body+'\npersistent_vault_locate\n'
 n=0
 for slot in (0,1):
  (r/'sys/class/ubi/ubi0/mtd_num').write_text(str(2+slot))
  for peer,profile,storage,geometry,good in [('ro','legacy','ok','ok',True),('rw','legacy','ok','ok',False),('rw','ab','ok','ok',True),('rw','ab','bad','ok',False),('rw','ab','ok','bad',False)]:
   e={**os.environ,'SLOT':str(slot),'PEER':peer,'PROFILE':profile,'STORAGE':storage,'GEOMETRY':geometry};p=subprocess.run(['sh','-c',driver],env=e,capture_output=True,text=True);assert (p.returncode==0)==good,(p.stdout,p.stderr);n+=1
 print(f'PASS: {n} actual own-vault locator cases; legacy RO retained, writable peer requires exact shared storage/geometry callbacks; no peer attach/read')
