from pathlib import Path
import tempfile,subprocess,hashlib,json,os
import sys
repo=Path(__file__).resolve().parents[2]
from prepare_source import prepare_package
prepared=tempfile.TemporaryDirectory(prefix='miami-config-source-')
b=Path(prepared.name)
pkg=prepare_package(repo,b/'prepared')
def function(text,name):
 a=text.index(name+'() {');return text[a:text.index('\n}',a)+2]+'\n'
core=(pkg/'files/cambium-ab.sh').read_text()
real_resolvers=function(core,'ab_ubi_for_mtd')+function(core,'ab_ubi_volume')
new=function((pkg/'files/cambium-ab-upgrade.sh').read_text(),'ab_restore_config')
legacy=(repo/'feeds/qca-wifi-7/ipq53xx/base-files/lib/upgrade/nand.sh').read_text()
old_helpers=''.join(function(legacy,x) for x in ('ubi_sysfs_root','nand_find_ubi','nand_find_volume','nand_restore_config'))
find='''find_mtd_index() {
 local PART="$(grep "\\\"$1\\\"" /proc/mtd | awk -F: '{print $1}')"
 local INDEX="${PART##mtd}"
 echo ${INDEX}
}
'''
cases=[]
# Reproduce the original helper failure with real parsing and volume helpers.
for active in (0,1):
 with tempfile.TemporaryDirectory(dir='/private/tmp',prefix='miami-config-legacy-') as td:
  r=Path(td);sys=r/'sys';sys.mkdir();proc=r/'mtd';proc.write_text('mtd2: 06000000 00020000 "rootfs"\nmtd3: 06000000 00020000 "rootfs_1"\nmtd27: 0158e000 0001f000 "rootfs"\nmtd32: 0158e000 0001f000 "rootfs"\n')
  for u,m in [('ubi0',2+active),('ubi1',3-active)]:
   (sys/u).mkdir();(sys/u/'mtd_num').write_text(str(m));v=sys/(u+'_2');v.mkdir();(v/'name').write_text('rootfs_data')
  helpers=(find+old_helpers).replace('/proc/mtd',str(proc)).replace('/sys/class/ubi',str(sys))
  script='''set +e
ubi_mknod(){ :; };sync(){ :; };mkdir(){ :; };rmdir(){ :; };mv(){ :; };umount(){ :; }
mount(){ echo "MOUNT:$3"; [ "$3" = /dev/ubi1_2 ]; }
'''+helpers+f'\nCI_UBIPART={"rootfs_1" if active==0 else "rootfs"}; CI_ROOTPART=rootfs; BACKUP_FILE=sysupgrade.tgz\nnand_restore_config fixture\n'
  run=subprocess.run(['sh','-c',script],capture_output=True,text=True)
  assert (run.returncode==0)==(active==0),(active,run.stdout,run.stderr)
  assert ('MOUNT:/dev/\n' in run.stdout)==(active==1),run.stdout
  cases.append({'case':f'original-{active}-to-{1-active}','result':'PASS reproduced '+('successful lookup' if active==0 else 'empty /dev/ mount failure')})
for active in (0,1):
 for scenario in ('success','missing-volume','wrong-volume-id','wrong-target','missing-device','mount-failure','move-failure','unmount-failure','missing-active','invalid-active','hash-before','hash-after'):
  with tempfile.TemporaryDirectory(dir='/private/tmp',prefix='miami-config-fixed-') as td:
   r=Path(td);sys=r/'sys';sys.mkdir();dev=r/'dev';dev.mkdir();saved=r/'saved';saved.mkdir();log=r/'log';backup=r/'config.tgz';backup.write_bytes(b'configuration fixture\n')
   for u,m in [('ubi0',2+active),('ubi1',3-active)]:
    (sys/u).mkdir();(sys/u/'mtd_num').write_text(str(m))
    idx=3 if scenario=='wrong-volume-id' and u=='ubi1' else 2
    v=sys/(u+'_'+str(idx));v.mkdir();(v/'name').write_text('absent' if scenario=='missing-volume' and u=='ubi1' else 'rootfs_data')
    if scenario!='missing-device' or u!='ubi1': (dev/(u+'_'+str(idx))).write_text('')
   trace=r/'mount-path';target='ubi9' if scenario=='wrong-target' else 'ubi1'
   script=f'''set -eu
AB_UBI_SYS='{sys}'; AB_DEV='{dev}'; AB_TARGET_MTD={3-active}; AB_TARGET_UBI={target}; AB_ACTIVE_UBI=ubi0; AB_ACTIVE_MTD={2+active}
BACKUP_FILE=sysupgrade.tgz; CASE={scenario}; LOG='{log}'; TRACE='{trace}'; SAVED='{saved}'
[ "$CASE" != missing-active ] || unset AB_ACTIVE_UBI
[ "$CASE" != invalid-active ] || AB_ACTIVE_UBI=garbage
sha256sum() {{ case "$CASE:$1" in hash-before:*config.tgz|hash-after:*sysupgrade.tgz) return 1;; esac; command sha256sum "$@"; }}
mount() {{ echo "mount:$3" >> "$LOG"; echo "$4" > "$TRACE"; [ "$CASE" != mount-failure ] && [ "$3" = "$AB_DEV/ubi1_2" ]; }}
mv() {{ echo move >> "$LOG"; [ "$CASE" != move-failure ] || return 1; command mv "$@"; }}
sync() {{ echo sync >> "$LOG"; }}
umount() {{ echo unmount >> "$LOG"; [ "$CASE" != unmount-failure ] || return 1; for x in "$1"/*; do [ ! -f "$x" ] || command mv "$x" "$SAVED/"; done; }}
'''+real_resolvers+new+f'''\nif ab_restore_config '{backup}'; then rc=0; else rc=1; fi
[ "$rc" != 0 ] || echo ARM >> "$LOG"
exit "$rc"
'''
   run=subprocess.run(['sh','-c',script],capture_output=True,text=True)
   ops=log.read_text() if log.exists() else ''
   assert (run.returncode==0)==(scenario=='success'),(active,scenario,run.returncode,run.stdout,run.stderr,ops)
   assert ('ARM' in ops)==(scenario=='success')
   if scenario=='success':assert (saved/'sysupgrade.tgz').read_bytes()==b'configuration fixture\n' and not backup.exists()
   if scenario in ('missing-volume','wrong-volume-id','wrong-target','missing-device','missing-active','invalid-active','hash-before'):assert 'mount:' not in ops
   if trace.exists():
    d=Path(trace.read_text().strip())
    # Only clean this test's exact generated mountpoint after mocked unmount.
    if d.exists():
     assert str(d).startswith('/tmp/cambium-ab-config.') and not d.is_symlink()
     for f in d.iterdir(): f.unlink()
     d.rmdir()
   cases.append({'case':f'fixed-{active}-to-{1-active}-{scenario}','result':'PASS','armed':scenario=='success'})
receipt={'candidate_sha256':hashlib.sha256((pkg/'files/cambium-ab-upgrade.sh').read_bytes()).hexdigest(),'scope':'Original real generic parsing/volume helpers reproduce one-direction failure; new real common resolvers/restore with only mount/move/unmount boundaries synthetic. No hardware operations.','cases':cases}
(b/'restore-test-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
