#!/usr/bin/env python3
"""Generate unsealed Thor stock-only FORMAT2 source from its frozen ledger."""
import argparse,hashlib,importlib.util,shutil,subprocess
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('stock_common',REPO/'tools/stock-migration/prepare-bridge.py')
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generate(base,root,out,release):
 if release!='2026.09.29.0':raise ValueError('unqualified Thor stock release')
 original=base/'source-sets/outgoing-stock.set'
 for line in original.read_text().splitlines():
  h,n=line.split();p=root/n.lstrip('/')
  if p.is_symlink() or (h=='-' and p.exists()) or (h!='-' and (not p.is_file() or sha(p)!=h)):raise ValueError('outgoing source mismatch: '+n)
 if out.exists():raise ValueError('existing output refused')
 out.mkdir()
 for name in ['platform.sh','cambium-ab.sh','cambium-ab-upgrade.sh','prepare-upgrader.sh','thor-sysinstall.sh','source-set-check.sh','minimum-release-contract.sh','runtime-implementation-contract.sh','source-route.sh']:
  shutil.copy2(base/name,out/name)
 for d in ['routes','modules','release-policies']:shutil.copytree(base/d,out/d)
 shutil.copy2(REPO/'tools/stock-migration/cambium-installer-handoff.sh',out/'cambium-installer-handoff.sh')
 shutil.copy2(REPO/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh',out/'cambium-installer-settings.sh')
 p=out/'cambium-ab-upgrade.sh';p.write_text(common.stock_writer(p.read_text()))
 p=out/'platform.sh';text=p.read_text();anchor='platform_pre_upgrade() {\n';text=common.replace(text,anchor,anchor+'\tif command -v ab_family >/dev/null && ab_family; then\n\t\t. /lib/upgrade/cambium-installer-handoff.sh || exit 1\n\t\tab_installer_validate_ram \"$1\" || exit 1\n\tfi\n');text=text.replace("RAMFS_COPY_BIN='","RAMFS_COPY_BIN='"+' '.join(common.TOOLS)+' ',1);p.write_text(text)
 p=out/'prepare-upgrader.sh';s=p.read_text()
 s=common.replace(s,'--check|--install|--verify-installed)', '--check|--install|--verify-installed|--stage-auth)')
 s=common.replace(s,'if [ "$mode" = --verify-installed ]; then','if [ "$mode" = --verify-installed ] || [ "$mode" = --stage-auth ]; then')
 anchor='. "$bundle/source-route.sh"\n'
 s=common.replace(s,anchor,anchor+'ow_runtime_contract_check "$bundle/runtime-sets/stock.set" || die "unqualified outgoing executable closure"\n')
 s=common.replace(s,'SOURCE_ROUTE=$detected','[ "$detected" = stock ] || return 1\n SOURCE_ROUTE=$detected')
 anchor='export CAMBIUM_AB_CERTIFICATE_LIB="$bundle/routes/$route/cambium-ab-certificates.sh"\n'
 if anchor not in s:
  anchor=next(l+'\n' for l in s.splitlines() if l.startswith('export CAMBIUM_AB_CERTIFICATE_LIB='))
 s=common.replace(s,anchor,anchor+'export CAMBIUM_INSTALLER_HANDOFF_LIB="$bundle/cambium-installer-handoff.sh"\nexport CAMBIUM_INSTALLER_SETTINGS_LIB="$bundle/cambium-installer-settings.sh"\n. "$CAMBIUM_INSTALLER_HANDOFF_LIB" || die "handoff library unavailable"\nab_installer_refuse_pending || die "pending provenance or unreadable ENV"\n')
 s=common.replace(s,'platform.sh:/lib/upgrade/platform.sh"','platform.sh:/lib/upgrade/platform.sh cambium-installer-handoff.sh:/lib/upgrade/cambium-installer-handoff.sh cambium-installer-settings.sh:/lib/upgrade/cambium-installer-settings.sh"')
 start=s.index('checkwork=$(mktemp ');end=s.index("source_gate || die 'outgoing scripts changed during preflight'",start)
 s=s[:start]+s[end:]
 stage='''if [ "$mode" = --stage-auth ]; then
 [ "$#" = 4 ] || die 'protected settings directory required'
 ow_thor_installed_matches "$bundle" stock || die 'installed bridge mismatch'
 AB_INSTALLER_INPUT=$4
 OW_STAGE_ADMISSION=qualified
 ow_settings_tree "$AB_INSTALLER_INPUT" || die 'invalid private settings'
 OW_EXPECT_JOB=$OW_JOB
 OW_EXPECT_SERIAL=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f')
 OW_EXPECT_FAMILY=$AB_FAMILY OW_EXPECT_MODEL=$AB_MODEL
 [ "$AB_FAMILY:$AB_MODEL:$AB_LAYOUT" = thor:XV3-8:banks ] || die 'unqualified model'
 OW_EXPECT_SOURCE=$AB_ACTIVE OW_EXPECT_TARGET=$AB_TARGET
 OW_EXPECT_OPERATION=production-stock-openwrt-migration
 OW_EXPECT_RELEASE=$(sed -n '1p' "$bundle/source-contract")
 OW_EXPECT_CONTRACT=$(sed -n '2p' "$bundle/source-contract")
 ab_installer_export "$image" || die 'settings handoff refused'
 exit 0
fi
'''
 s=common.replace(s,'case "$mode" in\n --check)',stage+'case "$mode" in\n --check)')
 s=s.replace('only the five listed targets','only the seven listed targets')
 s=s.replace('requested image is not the frozen Thor .10 image','requested image differs from sealed candidate')
 p.write_text(s)
 p=out/'thor-sysinstall.sh';s=p.read_text()
 s=common.replace(s,'[ "$mode" = --install ] || exit 0','[ "$mode" = --install ] || exit 0\n[ "$route" = stock ] && [ "$#" = 3 ] || { echo "Stock install requires --stock and protected settings directory" >&2; exit 1; }')
 anchor='sh "$here/prepare-upgrader.sh" --verify-installed "$image" "$route"\n'
 s=common.replace(s,anchor,anchor+'sh "$here/prepare-upgrader.sh" --stage-auth "$image" stock "$3"\n')
 p.write_text(s)
 targets={'/lib/functions/cambium-ab.sh':'cambium-ab.sh','/lib/upgrade/cambium-ab.sh':'cambium-ab-upgrade.sh','/lib/upgrade/cambium-ab-certificates.sh':'routes/stock/cambium-ab-certificates.sh','/lib/functions/cambium-ab-thor.sh':'modules/cambium-ab-thor.sh','/lib/upgrade/platform.sh':'platform.sh','/lib/upgrade/cambium-installer-handoff.sh':'cambium-installer-handoff.sh','/lib/upgrade/cambium-installer-settings.sh':'cambium-installer-settings.sh'}
 required={l.split()[1] for l in original.read_text().splitlines()}|set(targets)
 sets=out/'source-sets';sets.mkdir()
 (sets/'required-paths').write_text(''.join(n+'\n' for n in sorted(required)))
 for name,installed in [('outgoing-stock.set',False),('installed-stock.set',True)]:
  rows=[]
  for n in sorted(required):
   p=out/targets[n] if installed and n in targets else root/n.lstrip('/')
   if p.is_symlink() or (p.exists() and not p.is_file()):raise ValueError('unsafe member '+n)
   rows.append((sha(p) if p.is_file() else '-')+' '+n+'\n')
  (sets/name).write_text(''.join(rows))
 runtime=out/'runtime-sets';runtime.mkdir()
 seeds=set(common.TOOLS+['sh','ln','ldd','sysupgrade','ubus','uci','jshn','jsonfilter','fwtool','/sbin/upgraded'])
 seeds.update('?'+n for n in common.STOCK_RAM_OPTIONAL if n not in seeds)
 (runtime/'stock.seeds').write_text('\n'.join(sorted(seeds))+'\n')
 subprocess.run(['python3',str(REPO/'tests/installer/common-minimum-v1/make-runtime-implementation-set.py'),str(root),str(runtime/'stock.set'),str(runtime/'stock.seeds'),'183'],check=True)
 contract=hashlib.sha256((sets/'outgoing-stock.set').read_bytes()+(runtime/'stock.set').read_bytes()).hexdigest()
 (out/'source-contract').write_text(release+'\n'+contract+'\n')
 (out/'REVIEW-NOT-INSTALLABLE.txt').write_text('Thor stock FORMAT2 source only: no firmware/IMAGE/checksum seal. Preserve OpenWiFi route separately. Final candidate/image qualification and operator seal required.\n')
 for p in out.glob('*.sh'):subprocess.run(['sh','-n',str(p)],check=True)
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['baseline','stock_root','output']:p.add_argument(n,type=Path)
 a=p.parse_args();print(generate(a.baseline.resolve(),a.stock_root.resolve(),a.output.resolve(),'2026.09.29.0'))
