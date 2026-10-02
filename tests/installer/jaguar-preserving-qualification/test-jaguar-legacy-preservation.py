#!/usr/bin/env python3
"""Old-bank context + runtime crypto + canonical read-only tmpfs snapshot."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile
bundle=pathlib.Path(sys.argv[1]);target=pathlib.Path(sys.argv[2]);work=pathlib.Path(tempfile.mkdtemp(prefix='jaguar-legacy-preservation-tests.'));reports=[]
for prefix in ('runtime','old'):
 subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=synthetic-'+prefix+'-fixture','-keyout',str(work/(prefix+'-key.pem')),'-out',str(work/(prefix+'-cert.pem'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
names=('mounted-valid','named-mounted-valid','unmounted-ubifs','unmounted-erased','missing-volume','missing-volume-and-directory','smaller-old-volume','larger-old-volume','runtime-overrides-old-store','wrong-active-mtd','wrong-target-policy','wrong-geometry','invalid-volume-number','zero-volume','oversized-volume','unmounted-corrupt-magic','read-only-mount-refusal','wrong-mounted-bank','duplicate-mount','wrong-mounted-type','missing-volume-but-mounted','symlink-store','unsafe-store-entry','missing-runtime-key','missing-runtime-cert','symlink-runtime-key','symlink-runtime-cert','malformed-runtime-cert','mismatched-runtime-pair','world-readable-runtime-key','wrong-runtime-owner','missing-both-runtime','snapshot-binding-tamper')
accepted={'mounted-valid','named-mounted-valid','unmounted-ubifs','unmounted-erased','missing-volume','missing-volume-and-directory','smaller-old-volume','larger-old-volume','runtime-overrides-old-store'}
for name in names:
 root=work/name;store=root/'store';runtime=root/'runtime';store.mkdir(parents=True);runtime.mkdir();(root/'bin').mkdir()
 for directory,prefix in ((store,'old'),(runtime,'runtime')):
  for f in ('key.pem','cert.pem'):shutil.copy2(work/(prefix+'-'+f),directory/f)
  (directory/'key.pem').chmod(0o600)
 (store/'gateway.json').write_text('{"policy":"old"}\n');(runtime/'gateway.json').write_text('{"policy":"current"}\n')
 (runtime/'operational.pem').write_text('synthetic operational data\n')
 if name in ('missing-volume','missing-volume-and-directory','unmounted-erased'):
  shutil.rmtree(store)
  if name!='missing-volume-and-directory':store.mkdir()
 if name=='symlink-store':store=root/'linked';store.symlink_to(root/'store')
 if name=='unsafe-store-entry':(store/'unsafe.pem').symlink_to('/etc/passwd')
 if name in ('missing-runtime-key','missing-runtime-cert','missing-both-runtime'):
  for f in ('key.pem','cert.pem'):
   if name=='missing-both-runtime' or name=='missing-runtime-'+f.split('.')[0]:(runtime/f).unlink()
 if name in ('symlink-runtime-key','symlink-runtime-cert'):
  f='key.pem' if name.endswith('key') else 'cert.pem';(runtime/f).unlink();(runtime/f).symlink_to(work/('runtime-'+f))
 if name=='malformed-runtime-cert':(runtime/'cert.pem').write_text('not a certificate\n')
 if name=='mismatched-runtime-pair':shutil.copy2(work/'old-key.pem',runtime/'key.pem');(runtime/'key.pem').chmod(0o600)
 if name=='world-readable-runtime-key':(runtime/'key.pem').chmod(0o644)
 sysfs=root/'sys';(sysfs/'ubi0').mkdir(parents=True);(sysfs/'ubi0_4').mkdir()
 (sysfs/'ubi0/mtd_num').write_text('1' if name=='wrong-active-mtd' else '0')
 reserved={'smaller-old-volume':'19','larger-old-volume':'67','invalid-volume-number':'invalid','zero-volume':'0','oversized-volume':'725'}.get(name,'20')
 (sysfs/'ubi0_4/reserved_ebs').write_text(reserved);(sysfs/'ubi0_4/usable_eb_size').write_text('131072' if name=='wrong-geometry' else '126976')
 dev=root/'dev';dev.mkdir();(dev/'ubi0_4').write_bytes(b'\xff'*4 if name=='unmounted-erased' else b'BAD!' if name=='unmounted-corrupt-magic' else b'\x31\x18\x10\x06')
 mounted=name in ('mounted-valid','named-mounted-valid','wrong-mounted-bank','duplicate-mount','wrong-mounted-type','missing-volume-but-mounted')
 device='ubi0:certificates' if name=='named-mounted-valid' else str(dev/('ubi1_4' if name=='wrong-mounted-bank' else 'ubi0_4'))
 record=device+' '+str(store)+' '+('squashfs' if name=='wrong-mounted-type' else 'ubifs')+' rw 0 0\n'
 mounts=root/'mounts';mounts.write_text(record*2 if name=='duplicate-mount' else record if mounted else '')
 (root/'boot').write_text('synthetic-boot\n');calls=root/'calls';calls.touch()
 for command in ('openssl','hexdump'):
  binary=target/('usr/bin/openssl' if command=='openssl' else 'bin/busybox')
  shim=root/'bin'/command;shim.write_text('#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "'+str(target)+'" "'+str(binary)+'" '+('hexdump ' if command=='hexdump' else '')+'"$@"\n');shim.chmod(0o755)
 def snapshot():
  result={}
  for directory in (root/'store',runtime):
   if directory.exists():
    for p in directory.rglob('*'):
     if p.is_symlink():result[str(p.relative_to(root))]=('link',os.readlink(p))
     elif p.is_file():result[str(p.relative_to(root))]=(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mode)
  return result
 before=snapshot()
 driver='''set -eu
. "$1/cambium-ab-certificates.sh"
. "$1/preservation-check.sh"
AB_LAYOUT=banks; AB_FAMILY=jaguar; AB_MODEL=XV2-2T1; AB_SKU=0000001f
AB_ACTIVE=0; AB_TARGET=1; AB_ACTIVE_MTD=0; AB_TARGET_MTD=1; AB_ACTIVE_UBI=ubi0; AB_TARGET_UBI=ubi1; AB_LEB=126976; AB_BANK_LEBS=724
ab_identity() { return 0; }; ab_fail() { echo "$*" >&2; return 1; }
ab_certificate_lebs() { [ "$TEST_CASE" != wrong-target-policy ] && echo 20 || echo 0; }
ab_ubi_volume() { case "$TEST_CASE" in missing-volume*) return 1;; *) echo ubi0_4;; esac; }
mount() {
 printf '%s\\n' "mount:$*" >> "$TEST_CALLS"
 [ "$1" = -t ] && [ "$2" = ubifs ] && [ "$3" = -o ] && [ "$4" = ro ] && [ "$5" = "$AB_DEV/ubi0_4" ] || return 99
 [ "$TEST_CASE" != read-only-mount-refusal ] || return 1
 cp -a "$AB_CERTIFICATE_STORE/." "$6/"
}
umount() { printf '%s\\n' "umount:$*" >> "$TEST_CALLS"; }
ubimkvol() { echo forbidden-allocation >> "$TEST_CALLS"; exit 99; }; ubirsvol() { echo forbidden-resize >> "$TEST_CALLS"; exit 99; }
ubiformat() { echo forbidden-format >> "$TEST_CALLS"; exit 99; }; fw_setenv() { echo forbidden-env >> "$TEST_CALLS"; exit 99; }
jaguar_certificate_source_check
jaguar_runtime_identity_check
ab_certificate_export
if [ "$TEST_CASE" = snapshot-binding-tamper ]; then printf invalid > "$AB_CERTIFICATE_DESCRIPTOR"; fi
ab_certificate_validate_snapshot
case " $RAMFS_COPY_DATA " in *" $AB_CERTIFICATE_ARCHIVE "*) ;; *) exit 1;; esac
case " $RAMFS_COPY_DATA " in *" $AB_CERTIFICATE_DESCRIPTOR "*) ;; *) exit 1;; esac
'''
 env=dict(os.environ,PATH=str(root/'bin')+':'+os.environ['PATH'],AB_UBI_SYS=str(sysfs),AB_PROC_MOUNTS=str(mounts),AB_CERTIFICATE_STORE=str(store),AB_CERTIFICATE_RUNTIME=str(runtime),AB_CERTIFICATE_OWNER=str(os.getuid()+1 if name=='wrong-runtime-owner' else os.getuid()),AB_DEV=str(dev),AB_BOOT_ID=str(root/'boot'),AB_CERTIFICATE_ARCHIVE=str(root/'archive'),AB_CERTIFICATE_DESCRIPTOR=str(root/'descriptor'),TEST_CASE=name,TEST_CALLS=str(calls))
 p=subprocess.run(['sh','-c',driver,'fixture',str(bundle)],env=env,capture_output=True,text=True)
 expected=name in accepted
 assert (p.returncode==0)==expected,(name,p.returncode,p.stdout,p.stderr)
 assert before==snapshot(),(name,'source store/runtime modified')
 assert 'forbidden-' not in calls.read_text(),name
 if expected:
  inspect=root/'snapshot';inspect.mkdir();subprocess.run(['tar','-xf',str(root/'archive'),'-C',str(inspect)],check=True)
  for f in ('key.pem','cert.pem','gateway.json','operational.pem'):assert (inspect/f).read_bytes()==(runtime/f).read_bytes(),(name,f)
  assert (inspect/'key.pem').stat().st_mode & 0o777==0o600
  if name in ('unmounted-erased','missing-volume','missing-volume-and-directory'):assert not calls.read_text(),(name,'unexpected mount')
  if name.startswith('unmounted-') and name!='unmounted-erased':assert ' -o ro ' in calls.read_text(),name
 reports.append({'case':name,'passed':True,'accepted':expected,'source_store_and_runtime_unchanged':True,'no_allocation_resize_format_env_or_target_write':True})
print(json.dumps({'passed':True,'count':len(reports),'cases':reports,'source_check_sha256':hashlib.sha256((bundle/'preservation-check.sh').read_bytes()).hexdigest(),'canonical_helper_sha256':hashlib.sha256((bundle/'cambium-ab-certificates.sh').read_bytes()).hexdigest(),
 'scope':'Actual revised source/runtime checks and unchanged canonical export/boot-bank snapshot validation, actual frozen ARM64 OpenSSL/hexdump via QEMU, synthetic credentials, read-only active-volume mount/identity stubs. No AP credentials, actual mount, allocation, resize, target bank, flash or reboot.'},indent=2))
