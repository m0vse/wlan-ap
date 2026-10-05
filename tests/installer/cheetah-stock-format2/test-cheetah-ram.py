from pathlib import Path
import os,subprocess,tempfile,json,hashlib
base=Path(os.environ['CHEETAH_BUILD_ROOT']);review=base/'cheetah-format2-stock-bridge';generated=Path(os.environ.get('CHEETAH_GENERATED_BRIDGE',str(review/'generated-v3')));old=base/'outgoing-source/rootfs';bb=old/'bin/busybox'
stage=(old/'lib/upgrade/stage2').read_text();function=stage[stage.index('switch_to_ramfs()'):stage.index('\nkill_remaining()')]
platform=(generated/'platform.sh').read_text();check=platform[platform.index('platform_check_image()'):platform.index('platform_pre_upgrade()')];assert 'ab_installer_validate_ram' not in check
pre=platform[platform.index('platform_pre_upgrade()'):platform.index('platform_do_upgrade()')];assert pre.index('ab_installer_ramfs')<pre.index('ab_installer_validate_ram')<pre.index('ab_certificate_export')
with tempfile.TemporaryDirectory(prefix='cheetah-format2-ram.') as t:
 root=Path(t);(root/'ram').mkdir();core=root/'core';core.touch();trace=root/'copy';data=root/'data';boundary=root/'boundary'
 assignments='\n'.join(line for line in platform.splitlines() if line.startswith('RAMFS_COPY_'))
 script='''. "$HANDOFF" || exit 1
command() {
 [ "$1" = -v ] || return 1
 case "$2" in /*) path=$2;; *)
  for d in /usr/sbin /usr/bin /sbin /bin; do
   if [ -e "$OLD_ROOT$d/$2" ]; then printf '%s\\n' "$d/$2"; return 0; fi
  done
  return 1;;
 esac
 [ -e "$OLD_ROOT$path" ] && printf '%s\\n' "$path"
}
install_bin() { printf '%s\\n' "$1" >> "$COPY_LIST"; }
install_file() { printf '%s\\n' "$@" >> "$DATA_LIST"; }
supivot() { printf blocked > "$BOUNDARY"; return 1; }
v() { :; }
'''+assignments+'''\nab_installer_ramfs
'''+function+'\nswitch_to_ramfs\n'
 env=dict(os.environ,HANDOFF=str(generated/'cambium-installer-handoff.sh'),CAMBIUM_INSTALLER_SETTINGS_LIB=str(generated/'cambium-installer-settings.sh'),OLD_ROOT=str(old),COPY_LIST=str(trace),DATA_LIST=str(data),BOUNDARY=str(boundary),RAM_ROOT=str(root/'ram'))
 result=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(old),str(bb),'ash','-c',script],env=env,capture_output=True,text=True)
 assert result.returncode==1 and boundary.exists(),(result.returncode,result.stderr)
 names={Path(p).name for p in trace.read_text().splitlines()}
 required={'ls','awk','sh','wc','readlink','sha256sum','cat','mkdir','cp','chmod','sync','mv','tar','tr','mktemp','mount','umount','rmdir','fw_printenv'};assert required<=names,sorted(required-names);assert 'stat' not in names
 copied=set(data.read_text().splitlines());files={'/tmp/cambium-installer-settings.tar','/tmp/cambium-installer-settings.descriptor','/lib/upgrade/cambium-installer-handoff.sh','/lib/upgrade/cambium-installer-settings.sh',};assert files<=copied,files-copied
 receipt={'passed':True,'stock_stage2_sha256':hashlib.sha256((old/'lib/upgrade/stage2').read_bytes()).hexdigest(),'extra_tool_count':len(required),'required_data':sorted(files),'scope':'Actual stock ARM64 switch_to_ramfs control flow and generated assignments, copy operations recorded and pivot blocked; no bank/mount/AP operation.'}
 (review/'ram-copy-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
