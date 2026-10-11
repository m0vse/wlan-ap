from pathlib import Path
import os,importlib.util,subprocess,shutil,json
base=Path(os.environ['CHEETAH_BUILD_ROOT']);review=base/'cheetah-format2-stock-bridge';bridge=Path(os.environ.get('CHEETAH_GENERATED_BRIDGE',str(review/'generated-v4')))
spec=importlib.util.spec_from_file_location('settings',Path(os.environ['WLAN_AP_SOURCE_DIR'])/'tools/oem-migration/recovery/scripts/tests/test_cambium_installer_settings.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
results=[]
for fault in ['none','active-target','mtd-mismatch','volume-mismatch','pending-job','pending-image','mount','sync','umount','upper-link']:
 f=module.SettingsTests();f.setUp()
 try:
  v=f.values;v.update(family='cheetah',model='XV2-21X',source_operation='production-stock-openwrt-migration',source_release='2026.09.29.0');f.put('binding.tsv',''.join(f'{k}\t{value}\n' for k,value in v.items()));f.manifest()
  (f.sys/'ubi0/mtd_num').write_text('10');(f.sys/'ubi1').mkdir();(f.sys/'ubi1/mtd_num').write_text('12' if fault=='mtd-mismatch' else '11');(f.sys/'ubi1_2').mkdir();(f.sys/'ubi1_2/name').write_text('wrong' if fault=='volume-mismatch' else 'rootfs_data')
  sentinel=f.root/'source-sentinel';sentinel.write_text('source bank and existing identity')
  env=dict(os.environ,OW_STAGE_ADMISSION='qualified',OW_SETTINGS_OWNER=str(os.getuid()),OW_SETTINGS_SYS=str(f.sys),AB_UBI_SYS=str(f.sys),OW_SETTINGS_MOUNTS=str(f.mounts),CAMBIUM_INSTALLER_SETTINGS_LIB=str(bridge/'cambium-installer-settings.sh'),AB_INSTALLER_VALIDATED=str(f.input),FAULT=fault,TEST_ROOT=str(f.root),TEST_MOUNTS=str(f.mounts),TEST_IMAGE=v['image_sha256'])
  names={'serial':'SERIAL','family':'FAMILY','model':'MODEL','source_operation':'OPERATION','source_release':'RELEASE','source_contract_sha256':'CONTRACT','source_slot':'SOURCE','target_slot':'TARGET','job_id':'JOB'};env.update({'OW_EXPECT_'+names[k]:value for k,value in v.items() if k in names})
  script='''. "$1" || exit 1
ow_settings_tree "$AB_INSTALLER_VALIDATED" || exit 1
record() { printf '%s\n' "$1" >> "$TEST_ROOT/trace"; }
ab_identity() { AB_ENV=cheetah; AB_FAMILY=cheetah; AB_MODEL=XV2-21X; AB_ACTIVE=0; AB_TARGET=1; AB_QUALIFIED=1; AB_LAYOUT=banks; AB_ACTIVE_MTD=10; AB_TARGET_MTD=11; AB_TARGET_UBI=ubi1; [ "$FAULT" != active-target ] || AB_ACTIVE_MTD=11; }
get_mac_label_dt() { echo 00:04:56:ab:cd:ef; }
get_mac_label() { echo 00:04:56:ab:cd:ef; }
ab_ubi_volume() { [ "$1:$2" = ubi1:rootfs_data ] && echo ubi1_2; }
ab_getenv() { case "$1" in *_target) echo 1;; *_job) if [ "$FAULT" = pending-job ]; then echo wrong; else echo "$OW_EXPECT_JOB"; fi;; *_image) if [ "$FAULT" = pending-image ]; then echo wrong; else echo "$TEST_IMAGE"; fi;; esac; }
mount() {
 record mount; [ "$FAULT" != mount ] || return 1
 printf '%s' "$4" > "$TEST_ROOT/mountpoint"
 printf '/dev/ubi1_2 %s ubifs rw 0 0\n' "$4" > "$TEST_MOUNTS"
 [ "$FAULT" != upper-link ] || ln -s "$TEST_ROOT" "$4/upper"
 return 0
}
sync() { record sync; [ "$FAULT" != sync ]; }
umount() {
 record umount; [ "$FAULT" != umount ] || return 1
 mkdir -p "$TEST_ROOT/bank-store"
 [ ! -e "$1/upper" ] && [ ! -L "$1/upper" ] || mv "$1/upper" "$TEST_ROOT/bank-store/upper"
 : > "$TEST_MOUNTS"
}
ab_installer_install_settings "$2"
'''
  r=subprocess.run(['sh','-c',script,'fixture',str(bridge/'cambium-installer-handoff.sh'),str(f.image)],env=env,capture_output=True,text=True)
  assert (r.returncode==0)==(fault=='none'),(fault,r.returncode,r.stderr)
  assert sentinel.read_text()=='source bank and existing identity';assert 'X'*64 not in r.stdout+r.stderr
  if fault=='none':
   dest=f.root/'bank-store/upper/root/.cambium-installer-settings';assert {p.name:p.read_bytes() for p in dest.iterdir()}=={p.name:p.read_bytes() for p in f.input.iterdir()}
  if fault in ['active-target','mtd-mismatch','pending-job','pending-image']:assert not (f.root/'trace').exists()
  results.append({'fault':fault,'passed':True})
 finally:
  pointer=f.root/'mountpoint'
  if pointer.exists():
   path=Path(pointer.read_text());assert str(path).startswith('/tmp/cambium-settings-target.');shutil.rmtree(path,ignore_errors=True)
  f.doCleanups()
receipt={'passed':True,'cases':results,'scope':'Actual Cheetah banks install-settings dispatch and central stager; mount/ENV/sync/unmount boundaries isolated, temp filesystem settings writes only; no AP/bank writes.'};(review/'bank-stage-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
