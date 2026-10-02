"""Actual installer source/minimum/runtime gate; private extracted-root fixtures."""
import hashlib,json,os,pathlib,shutil,subprocess,sys,tempfile
bundle,source=map(lambda p:pathlib.Path(p).resolve(),sys.argv[1:])
work=pathlib.Path(tempfile.mkdtemp(prefix='xe34-compatible-contract.'));cases=[]
prepare=(bundle/'prepare-upgrader.sh').read_text()
functions=prepare[prepare.index('metadata_fingerprint()'):prepare.index("\nBRIDGE_ROOT=''")]
for name in ('baseline','newer-compatible','below-minimum','malformed-release','wrong-family','wrong-target','TIP-marker','changed-updater','changed-runtime','extra-script','installed-bridge','mixed-bridge','metadata-drift'):
 root=work/name;shutil.copytree(source,root,symlinks=True)
 metadata=root/'etc/cambium-openwrt-release';release=root/'etc/openwrt_release'
 if name=='newer-compatible':metadata.write_text(metadata.read_text().replace('2026.09.30.102','2026.10.03.1'))
 if name=='below-minimum':metadata.write_text(metadata.read_text().replace('2026.09.30.102','2026.09.30.101'))
 if name=='malformed-release':metadata.write_text(metadata.read_text()+"PATH='unsafe'\n")
 if name=='wrong-family':metadata.write_text(metadata.read_text().replace("'Jaguar'","'Sage'"))
 if name=='wrong-target':release.write_text(release.read_text().replace('qualcommax/ipq60xx','ipq40xx/generic'))
 if name=='TIP-marker':release.write_text(release.read_text()+"DISTRIB_TIP_VERSION='jaguar-2026.10.02.3'\n")
 if name=='changed-updater':p=root/'lib/upgrade/stage2';p.write_bytes(p.read_bytes()+b'\nunknown-source\n')
 if name=='changed-runtime':p=root/'bin/busybox';p.write_bytes(p.read_bytes()+b'changed')
 if name=='extra-script':(root/'lib/upgrade/unknown.sh').write_text('echo NEVER_EXECUTED\n')
 if name in ('installed-bridge','mixed-bridge'):
  items=[('cambium-ab.sh','lib/functions/cambium-ab.sh'),('cambium-ab-upgrade.sh','lib/upgrade/cambium-ab.sh'),('cambium-ab-certificates.sh','lib/upgrade/cambium-ab-certificates.sh'),('modules/cambium-ab-jaguar.sh','lib/functions/cambium-ab-jaguar.sh'),('platform.sh','lib/upgrade/platform.sh')]
  for item,path in (items if name=='installed-bridge' else items[:1]):shutil.copy2(bundle/item,root/path)
 checker=(bundle/'source-set-check.sh').read_text().replace('ow_source_set_matches()', 'ow_actual_source_set_matches()')
 redirected=functions.replace('for path in /lib/',f'for path in {root}/lib/').replace(' /lib/',f' {root}/lib/').replace('grep -Fxq "$path"',f'grep -Fxq "${{path#"{root}"}}"')
 driver=work/(name+'.sh')
 driver.write_text('set -eu\nbundle='+str(bundle)+'\nBRIDGE_ROOT='+str(root)+'\n'+checker+'\now_source_set_matches() { ow_actual_source_set_matches "$1" "$2" "$BRIDGE_ROOT"; }\n'+(bundle/'minimum-release-contract.sh').read_text()+'\n'+(bundle/'runtime-implementation-contract.sh').read_text()+'\n'+redirected+'\nsource_gate\n'+('sed -i s/2026.09.30.102/2026.10.03.1/ "$BRIDGE_ROOT/etc/cambium-openwrt-release"\nrelease_gate\n' if name=='metadata-drift' else ''))
 result=subprocess.run(['sh',str(driver)],capture_output=True,text=True)
 expected=name in ('baseline','newer-compatible','installed-bridge')
 assert (result.returncode==0)==expected,(name,result.stdout,result.stderr)
 assert 'NEVER_EXECUTED' not in result.stdout
 cases.append({'case':name,'accepted':expected,'passed':True})
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'scope':'Actual complete updater/minimum/runtime gates; private extracted roots; no AP scripts sourced or executed, no bank operations.'},indent=2))
