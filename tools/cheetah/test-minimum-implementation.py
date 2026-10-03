#!/usr/bin/env python3
"""File-only composed metadata + reviewed implementation gate; no AP code."""
import hashlib,json,pathlib,shutil,subprocess,tempfile
base=pathlib.Path('/home/phil/openwifi-cheetah-build');work=pathlib.Path(tempfile.mkdtemp(prefix='cheetah-minimum.'));cases=[]
for route,source in [('stock',base/'outgoing-source/rootfs'),('preserve',pathlib.Path('/tmp/cheetah-image-check.dixkA1/rootfs'))]:
 suite=base/('operator-'+route+'-minimum-r6');payload=suite/'payload';required=(payload/'source-sets/required-paths').read_text().splitlines()
 for case,accepted in [('minimum',True),('above-minimum-metadata-only',True),('below-minimum',False),('malformed',False),('wrong-family',False),('wrong-target',False),('wrong-architecture',False),('mixed-route',False),('changed-sysupgrade',False),('changed-uci',False),('extra-upgrade',False),('extra-function',False),('dangling-extra',False),('metadata-shell',False),('metadata-PATH',False),('metadata-FORCE',False)]:
  root=work/(route+'-'+case);root.mkdir()
  for path in required+['/etc/openwrt_release','/etc/cambium-openwrt-release']:
   src=source/path.lstrip('/');dst=root/path.lstrip('/')
   if src.is_file():dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
  release=root/'etc/openwrt_release';stock=root/'etc/cambium-openwrt-release';meta=stock if route=='stock' else release
  old='2026.09.29.0' if route=='stock' else '2026.10.02.11'
  if case in ['above-minimum-metadata-only','below-minimum','malformed']:
   new={'above-minimum-metadata-only':'2026.10.03.100','below-minimum':'2026.09.28.999','malformed':'2026.13.03.0'}[case];meta.write_text(meta.read_text().replace(old,new))
  if case=='wrong-family':meta.write_text(meta.read_text().replace('Cheetah','Thor').replace('cheetah','thor'))
  if case=='wrong-target':release.write_text(release.read_text().replace('qualcommax/ipq50xx','qualcommax/ipq807x'))
  if case=='wrong-architecture':release.write_text(release.read_text().replace('aarch64_cortex-a53','mips_24kc'))
  if case=='mixed-route':
   if route=='stock':release.write_text(release.read_text()+"DISTRIB_TIP_VERSION='cheetah-2026.10.02.11'\n")
   else:stock.write_text("CAMBIUM_FAMILY='Cheetah'\nCHEETAH_BUILD_ID='2026.09.29.0'\n")
  if case.startswith('changed-'):
   dst=root/('sbin/sysupgrade' if case=='changed-sysupgrade' else 'lib/config/uci.sh');dst.write_bytes(dst.read_bytes()+b'\n# modified implementation\n')
  if case.startswith('extra-') or case=='dangling-extra':
   dst=root/('lib/functions/unreviewed.sh' if case=='extra-function' else 'lib/upgrade/unreviewed.sh')
   if case=='dangling-extra':dst.symlink_to('/missing-script')
   else:dst.write_text('exit 99\n')
  if case.startswith('metadata-') and case!='metadata-shell':release.write_text(release.read_text()+case[9:]+"='1'\n")
  if case=='metadata-shell':release.write_text(release.read_text()+'echo EXECUTED > '+str(root/'executed')+'\n')
  script='''set -eu
. "$1/minimum-release-contract.sh"
. "$1/payload/source-set-check.sh"
ow_release_contract_check "$1/release-policy" "$2"
for file in "$2"/lib/*.sh "$2"/lib/functions/*.sh "$2"/lib/upgrade/*.sh; do
 [ -e "$file" ] || [ -L "$file" ] || continue
 path=${file#"$2"}; grep -Fxq "$path" "$1/payload/source-sets/required-paths" || exit 1
done
for candidate in "$1"/payload/source-sets/outgoing-*.set; do
 if ow_source_set_matches "$candidate" "$1/payload/source-sets/required-paths" "$2"; then exit 0; fi
done
exit 1
'''
  result=subprocess.run(['sh','-c',script,'fixture',str(suite),str(root)],capture_output=True,text=True)
  assert (result.returncode==0)==accepted,(route,case,result.stderr)
  assert not (root/'executed').exists()
  cases.append(dict(route=route,case=case,accepted=accepted,passed=True))
 # Exercise the actual frontend in-invocation metadata fingerprint guard.
 root=work/(route+'-minimum');prepare=(suite/'prepare-upgrader.sh').read_text();start=prepare.index("RELEASE_METADATA_ID=''");end=prepare.index("BRIDGE_ROOT=''",start);functions=prepare[start:end]
 meta=root/('etc/cambium-openwrt-release' if route=='stock' else 'etc/openwrt_release');old='2026.09.29.0' if route=='stock' else '2026.10.02.11'
 script='. "$1/minimum-release-contract.sh"\nbundle=$1\nBRIDGE_ROOT=$2\n'+functions+'\nrelease_gate || exit 1\nsed -i "s/'+old+'/2026.10.03.100/g" "$3"\nif release_gate; then exit 1; fi\nRELEASE_METADATA_ID=\nrelease_gate\n'
 result=subprocess.run(['sh','-c',script,'fixture',str(suite),str(root),str(meta)],capture_output=True,text=True)
 assert result.returncode==0,(route,'metadata-drift',result.stderr)
 cases.append(dict(route=route,case='same-invocation-drift-refused-new-invocation-compatible',passed=True))
print(json.dumps(dict(passed=True,count=len(cases),cases=cases,fixture=str(work),scope='Offline authenticated release fixtures; composed minimum parser and full reviewed script source/membership gate. No hardware/layout simulation or live qualification.'),indent=2))
