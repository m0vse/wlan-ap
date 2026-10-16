#!/usr/bin/env python3
"""Actual common writer/arming + Miami renderer; synthetic hardware boundaries.
Does not qualify physical flash, bridge boot, certificates or controller health.
"""
from pathlib import Path
import os,tempfile,subprocess,json,tarfile
from prepare_source import prepare_package
repo=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='miami-writer-flow-') as td:
 r=Path(td).resolve();p=prepare_package(repo,r/'prepared');dev=r/'dev';dev.mkdir();bin=r/'bin';bin.mkdir();state=r/'state';dt=r/'dt/cambium-platform';dt.mkdir(parents=True);boot=r/'boot-id';boot.write_text('12345678-1234-1234-1234-123456789abc\n')
 actor=bin/'envactor';actor.write_text('''#!/usr/bin/env python3
import os,json,sys
from pathlib import Path
p=Path(os.environ['STATE']);e=json.loads(p.read_text());a=sys.argv[1:]
if a[0]=='get':print(e.get(a[1],''))
else:
 if a[2]:e[a[1]]=a[2]
 else:e.pop(a[1],None)
 p.write_text(json.dumps(e))
''');actor.chmod(0o755)
 driver=r''' . "$UPGRADER"
. "$MODULE"
ab_identity(){ AB_ACTIVE=$SLOT AB_TARGET=$((1-SLOT)) AB_ACTIVE_MTD=$((2+SLOT)) AB_TARGET_MTD=$((3-SLOT)) AB_ACTIVE_UBI=ubi0 AB_ENV=miami AB_FAMILY=miami AB_MODEL=X7-35X AB_SKU=0000002c AB_LAYOUT=banks AB_MARKER=1 AB_VAULT=1 AB_VAULT_LEBS=72 AB_CERTIFICATE_LEBS=64 AB_BANK_LEBS=724 AB_ROOT_MAGIC=hsqs AB_SLOT0_OFFSET=0xc0000 AB_SLOT1_OFFSET=0x60c0000 AB_IMAGE_DIR=sysupgrade-cambiumnetworks_miami-ab-slot$AB_TARGET AB_FIT=config@mi01.6-acadia-ab-slot$AB_TARGET; }
ab_getenv(){ envactor get "$1"; };ab_setenv(){ [ "$FAIL" != persist ] || return 1;envactor set "$1" "${2:-}"; }
ab_setenv_batch(){ if [ "$FAIL" = arm ] && grep -q "miami_ab_state armed" "$1";then return 1;fi;while read -r key value;do envactor set "$key" "$value";done < "$1"; }
ab_running_slot(){ echo "$SLOT"; };ab_mtd_writable(){ :; };ab_miami_ab_profile(){ :; }

ab_miami_storage_context(){ :; }
ab_miami_certificate_mount(){ return 1; }
ab_miami_snapshot_identity(){ [ "$FAIL" != snapshot ]; }
ab_miami_upgrade_geometry(){
 [ "$FAIL" != preflight ] || return 1
 if [ "$(ab_getenv miami_ab_state)" = writing ];then echo boundary >> "$LOG";[ "$FAIL" != boundary ] || return 1;fi
}
ab_certificate_validate_snapshot(){ [ "$FAIL" != snapshot ]; }
ab_prepare_bank(){ echo format >> "$LOG";[ "$FAIL" != format ] || return 1;AB_TARGET_UBI=ubi1;
 mkdir -p "$AB_UBI_SYS/ubi0" "$AB_UBI_SYS/ubi1" "$AB_UBI_SYS/ubi0_3" "$AB_UBI_SYS/ubi1_3" "$AB_UBI_SYS/ubi1_2"
 echo "$AB_ACTIVE_MTD" > "$AB_UBI_SYS/ubi0/mtd_num"; echo "$AB_TARGET_MTD" > "$AB_UBI_SYS/ubi1/mtd_num"
 echo cambium_device_data > "$AB_UBI_SYS/ubi0_3/name"; echo cambium_device_data > "$AB_UBI_SYS/ubi1_3/name"
 echo rootfs_data > "$AB_UBI_SYS/ubi1_2/name"; touch "$AB_DEV/ubi1_2"
}
ubiupdatevol(){ echo "write:$1" >> "$LOG";case "$FAIL:$1" in kernel:*_0|root:*_1|vault:*_3) return 1;;esac;cp "$2" "$1";[ "$FAIL:$1" != readback:$AB_DEV/ubi1_1 ] || echo corrupt > "$1"; }
ab_certificate_restore(){ echo certificates >> "$LOG";[ "$FAIL" != certificates ]; }
mount(){ echo configuration >> "$LOG"; echo "$4" > "$STATE.mountpoint";[ "$FAIL" != configuration ] && [ "$3" = "$AB_DEV/ubi1_2" ]; }
umount(){ for f in "$1"/*; do [ ! -f "$f" ] || command mv "$f" "$STATE.saved-config"; done; }

hexdump(){ echo d00dfeed; }
sync(){ :; }
cambium_ab_do_upgrade "$IMAGE"
'''
 n=0
 for slot in (0,1):
  directory=f'sysupgrade-cambiumnetworks_miami-ab-slot{1-slot}';src=r/directory;src.mkdir(exist_ok=True)
  (src/'kernel').write_bytes(bytes.fromhex('d00dfeed')+f'\0\1config@mi01.6-acadia-ab-slot{1-slot}\0'.encode());(src/'root').write_bytes(b'hsqsfixture')
  image=r/'image.tar'
  with tarfile.open(image,'w') as tar:tar.add(src,arcname=directory)
  (dev/'ubi0_3').write_bytes(b'original vault');(r/'config').write_bytes(b'private configuration')
  for fail in ('preflight','snapshot','persist','boundary','format','kernel','root','readback','vault','certificates','configuration','arm','success'):
   log=r/'log';log.write_text('')
   prior=f"nand device 0 && setenv mtdids nand0=nand0 && setenv mtdparts 'mtdparts=nand0:0x6000000@{'0xc0000' if slot==0 else '0x60c0000'}(fs)' && ubi part fs && ubi read 0x60000000 kernel && setenv bootargs console=ttyMSM0,115200n8 ubi.mtd={'rootfs' if slot==0 else 'rootfs_1'} root=/dev/ubiblock0_1 rootfstype=squashfs rootwait && bootm 0x60000000#config@mi01.6-acadia-ab-slot{slot}"
   state.write_text(json.dumps({'bootcmd':f'run miami_boot{slot}','image':str(slot),'changing_bootcmd':'1',f'miami_boot{slot}':prior,'miami_ab_confirmed':str(slot),'miami_ab_state':'confirmed','miami_ab_seed_boot_id':boot.read_text().strip()}))
   env={**os.environ,'LC_ALL':'C','PATH':str(bin)+':'+os.environ['PATH'],'CAMBIUM_AB_MODULES':str(r/'none'),'CAMBIUM_AB_LIB':str(p/'files/cambium-ab.sh'),'UPGRADER':str(p/'files/cambium-ab-upgrade.sh'),'MODULE':str(repo/'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh'),'AB_BOOT_ID':str(boot),'AB_DT':str(dt.parent),'AB_DEV':str(dev),'AB_WORK':str(r/'work'),'AB_LOG':str(r/'upgrade.log'),'IMAGE':str(image),'SLOT':str(slot),'FAIL':fail,'STATE':str(state),'LOG':str(log),'UPGRADE_BACKUP':str(r/'config'),'BACKUP_FILE':'sysupgrade.tgz','AB_UBI_SYS':str(r/'ubi')}
   for u,mtd in [('ubi0',2+slot),('ubi1',3-slot)]:
    d=r/'ubi'/u;d.mkdir(parents=True,exist_ok=True);(d/'mtd_num').write_text(str(mtd))
    for idx,name in [(2,'rootfs_data'),(3,'cambium_device_data')]:
     v=r/'ubi'/(u+'_'+str(idx));v.mkdir(parents=True,exist_ok=True);(v/'name').write_text(name)
   (r/'config').write_bytes(b'private configuration')
   result=subprocess.run(['sh','-c',driver],env=env,capture_output=True,text=True)
   assert (result.returncode==0)==(fail=='success'),(slot,fail,result.stdout,result.stderr)
   e=json.loads(state.read_text());ops=log.read_text()
   assert e[f'miami_boot{slot}']==prior and (dev/'ubi0_3').read_bytes()==b'original vault'
   if fail!='success':
    assert e['bootcmd']==f'run miami_boot{slot}'
    assert ('miami_ab_version' in e)==(fail=='arm'),(slot,fail,e,result.stdout,result.stderr,ops)
   else:
    assert e['miami_ab_version']=='1' and 'miami_bridge_state' not in e and e['miami_ab_state']=='armed'
    assert e['bootcmd'].startswith(f'setenv bootcmd run miami_boot{slot} && setenv image {slot}') and 'saveenv && run' in e['bootcmd']
    assert ops.index('boundary')<ops.index('format')<ops.index('certificates')<ops.index('configuration')
   if fail in ('preflight','snapshot','persist','boundary'):assert 'format' not in ops and 'write:' not in ops
   n+=1
 print(f'PASS: {n} actual healthy-seed preflight/first-upgrade/common writer/source-default/late-version/arm-failure cases, both slots; hardware and certificate-restoration boundaries are actors')
