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
upgrade=(pkg/'files/cambium-ab-upgrade.sh').read_text()
new=function(upgrade,'ab_restore_config')
dispatch=function(upgrade,'ab_restore_upgrade_config')
writer=function(upgrade,'cambium_ab_do_upgrade')
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
 for scenario in ('success','missing-volume','wrong-volume-id','wrong-target','missing-device','mount-failure','move-failure','unmount-failure','missing-active','invalid-active','hash-before','hash-after','hash-mismatch','sync-failure','target-active-ubi-alias','target-active-mtd-alias'):
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
AB_FAMILY=miami; AB_MODEL=X7-35X; AB_ENV=miami; AB_ACTIVE={active}; AB_TARGET={1-active}; AB_KERNEL=fixture_kernel; AB_ROOT=fixture_root; AB_TARGET_PART=rootfs_test; AB_VAULT=0; AB_KERNEL_SIZE=1; AB_ROOT_SIZE=1; AB_LEB=126976; UPGRADE_BACKUP='{backup}'; AB_TEST_KERNEL='{r}/kernel'; AB_TEST_ROOT='{r}/root'
BACKUP_FILE=sysupgrade.tgz; CASE={scenario}; LOG='{log}'; TRACE='{trace}'; SAVED='{saved}'
[ "$CASE" != missing-active ] || unset AB_ACTIVE_UBI
[ "$CASE" != invalid-active ] || AB_ACTIVE_UBI=garbage
[ "$CASE" != target-active-ubi-alias ] || AB_TARGET_UBI=$AB_ACTIVE_UBI
[ "$CASE" != target-active-mtd-alias ] || AB_TARGET_MTD=$AB_ACTIVE_MTD
sha256sum() {{ case "$CASE:$1" in hash-before:*config.tgz|hash-after:*sysupgrade.tgz) return 1;; esac; if [ "$CASE" = hash-mismatch ] && [ "${{1##*/}}" = sysupgrade.tgz ]; then printf '%064d  %s\\n' 0 "$1"; return 0; fi; command sha256sum "$@"; }}
mount() {{ echo "mount:$3" >> "$LOG"; echo "$4" > "$TRACE"; [ "$CASE" != mount-failure ] && [ "$3" = "$AB_DEV/ubi1_2" ]; }}
mv() {{ echo move >> "$LOG"; [ "$CASE" != move-failure ] || return 1; command mv "$@"; }}
sync() {{ echo sync >> "$LOG"; [ "$CASE" != sync-failure ]; }}
umount() {{ echo unmount >> "$LOG"; [ "$CASE" != unmount-failure ] || return 1; for x in "$1"/*; do [ ! -f "$x" ] || command mv "$x" "$SAVED/"; done; }}
ab_upgrade_preflight() {{ :; }}
ab_image_extract() {{ :; }}
ab_certificate_lebs() {{ echo 0; }}
ab_persist_prior_boot() {{ echo prior >> "$LOG"; }}
ab_setenv_batch() {{ :; }}
ab_prepare_bank() {{ :; }}
ab_step() {{ :; }}
ab_verify_volume() {{ :; }}
ab_hook() {{ return 1; }}
ab_record_failure() {{ echo failure >> "$LOG"; }}
ab_arm_trial() {{ echo ARM >> "$LOG"; }}
'''+real_resolvers+new+dispatch+writer+f'''\nif cambium_ab_do_upgrade fixture-image; then rc=0; else rc=1; fi
exit "$rc"
'''
   run=subprocess.run(['sh','-c',script],capture_output=True,text=True)
   ops=log.read_text() if log.exists() else ''
   assert (run.returncode==0)==(scenario=='success'),(active,scenario,run.returncode,run.stdout,run.stderr,ops)
   assert ('ARM' in ops)==(scenario=='success')
   if scenario=='success':assert (saved/'sysupgrade.tgz').read_bytes()==b'configuration fixture\n' and not backup.exists()
   if scenario in ('missing-volume','wrong-volume-id','wrong-target','missing-device','missing-active','invalid-active','hash-before','target-active-ubi-alias','target-active-mtd-alias'):assert 'mount:' not in ops
   if trace.exists():
    d=Path(trace.read_text().strip())
    # Only clean this test's exact generated mountpoint after mocked unmount.
    if d.exists():
     assert str(d).startswith('/tmp/cambium-ab-config.') and not d.is_symlink()
     for f in d.iterdir(): f.unlink()
     d.rmdir()
   cases.append({'case':f'fixed-{active}-to-{1-active}-{scenario}','result':'PASS','armed':scenario=='success'})
for family,model in [('sage','E410'),('jaguar','XV2-2'),('cheetah','XV2-21X'),('thor','XV3-8'),('gambit','E400'),('miami','other-model')]:
 for failure in (False,True):
  with tempfile.TemporaryDirectory(prefix='ab-config-dispatch-') as td:
   r=Path(td);backup=r/'config.tgz';backup.write_bytes(b'configuration fixture\n');log=r/'trace'
   script=f'''set -eu
AB_FAMILY={family}; AB_MODEL={model}; AB_TARGET_PART=exact_inactive_part; UPGRADE_BACKUP='{backup}'; AB_ENV={family}; AB_VAULT=0; AB_ACTIVE=0; AB_TARGET=1; AB_TARGET_UBI=ubi1; AB_KERNEL=fixture_kernel; AB_ROOT=fixture_root; AB_KERNEL_SIZE=1; AB_ROOT_SIZE=1; LOG='{log}'
ab_restore_config() {{ echo WRONG_MIAMI >> "$LOG"; return 1; }}
nand_restore_config() {{ [ -f "$1" ] && [ "$CI_UBIPART" = exact_inactive_part ] || return 1; echo generic >> "$LOG"; [ {int(failure)} = 0 ]; }}
ab_upgrade_preflight() {{ :; }};ab_image_extract() {{ :; }};ab_certificate_lebs() {{ echo 0; }};ab_persist_prior_boot() {{ :; }};ab_setenv_batch() {{ :; }};ab_prepare_bank() {{ :; }};ab_step() {{ :; }};ab_verify_volume() {{ :; }};ab_hook() {{ return 1; }};ab_record_failure() {{ echo failure >> "$LOG"; }};sync() {{ :; }};ab_arm_trial() {{ echo ARM >> "$LOG"; }}
'''+dispatch+writer+'''\nif cambium_ab_do_upgrade fixture-image; then exit 0; else exit 1; fi\n'''
   result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
   trace=log.read_text() if log.exists() else ''
   assert (result.returncode==0)==(not failure),(family,model,failure,trace,result.stderr)
   assert 'generic' in trace and 'WRONG_MIAMI' not in trace
   assert ('ARM' in trace)==(not failure)
   cases.append({'case':f'non-miami-{family}-{model}-failure-{failure}','result':'PASS','armed':not failure})
for family,model in [('',''),('miami','other-model'),('thor','X7-35X'),('jaguar','X7-35X')]:
 script=f'''set -eu
AB_FAMILY='{family}'; AB_MODEL='{model}'
mount() {{ echo UNEXPECTED_MOUNT; return 1; }}
'''+new+'''\nif ab_restore_config fixture; then exit 0; else exit 1; fi\n'''
 result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
 assert result.returncode!=0 and not result.stdout and not result.stderr,(family,model,result.stdout,result.stderr)
 cases.append({'case':f'direct-helper-wrong-family-{family}-{model}','result':'PASS','armed':False})
receipt={'candidate_sha256':hashlib.sha256((pkg/'files/cambium-ab-upgrade.sh').read_bytes()).hexdigest(),'scope':'Original real generic parsing/volume helpers reproduce one-direction failure; actual current writer, exact-Miami dispatch and common resolvers/restore with mount/move/unmount boundaries synthetic; non-Miami generic filesystem semantics unchanged and not newly qualified. No hardware operations.','cases':cases}
Path(os.environ.get('TEST_RECEIPT',str(b/'restore-test-receipt.json'))).write_text(json.dumps(receipt,indent=2)+'\n');print(f'PASS {len(cases)} actual backup-present restore/writer/dispatch cases: two Miami directions, alias/hash/mount/move/unmount/sync failures; generic family dispatch unchanged')
