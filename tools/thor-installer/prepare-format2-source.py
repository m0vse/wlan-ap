#!/usr/bin/env python3
"""Prepare an unsealed Thor-only stock FORMAT2 source adapter for review."""
import argparse, hashlib, shutil, subprocess
from pathlib import Path
p=argparse.ArgumentParser()
for name in ('baseline','handoff','settings','output'):p.add_argument(name,type=Path)
p.add_argument('--handoff-sha256',required=True);p.add_argument('--settings-sha256',required=True)
a=p.parse_args()
assert not a.output.exists(),'refuse an existing output'
for path,digest in [(a.handoff,a.handoff_sha256),(a.settings,a.settings_sha256)]:
 assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,str(path)
a.output.mkdir()
for name in ['platform.sh','cambium-ab-upgrade.sh','prepare-upgrader.sh','thor-sysinstall.sh']:
 shutil.copy2(a.baseline/name,a.output/name)
shutil.copy2(a.handoff,a.output/'cambium-installer-handoff.sh')
shutil.copy2(a.settings,a.output/'cambium-installer-settings.sh')
def edit(name,old,new):
 path=a.output/name;s=path.read_text();assert s.count(old)==1,(name,old);path.write_text(s.replace(old,new))
edit('platform.sh','\t\tab_certificate_export || {','\t\t. /lib/upgrade/cambium-installer-handoff.sh || exit 1\n\t\tab_installer_export "$1" || { echo "Protected settings export failed" >&2; exit 1; }\n\t\tab_certificate_export || {')
edit('cambium-ab-upgrade.sh','\n# The image directory','\n. "${CAMBIUM_INSTALLER_HANDOFF_LIB:-/lib/upgrade/cambium-installer-handoff.sh}" || return 1\n\n# The image directory')
edit('cambium-ab-upgrade.sh','\tab_upgrade_preflight || return 1\n\tab_image_extract "$1" || return 1\n','\tab_upgrade_preflight || return 1\n\t[ "$AB_FAMILY:$AB_MODEL:$AB_LAYOUT" = thor:XV3-8:banks ] || return 1\n\tab_image_extract "$1" || return 1\n\tab_installer_validate_ram "$1" || return 1\n')
edit('cambium-ab-upgrade.sh','\tab_setenv_batch "$batch" || { rm -f "$batch"; ab_fail "cannot record the upgrade"; return 1; }','\tab_installer_pending "$batch" || { rm -f "$batch"; return 1; }\n\tab_setenv_batch "$batch" || { rm -f "$batch"; ab_fail "cannot record the upgrade"; return 1; }')
# Thor uses the generic banks writer. The pair hook is refused by the family table.
edit('cambium-ab-upgrade.sh','\tsync\n\n\tab_arm_trial ||','\tab_installer_install_settings "$1" || { ab_record_failure write-failed "protected settings staging failed"; return 1; }\n\tsync || return 1\n\n\tab_arm_trial ||')
# Generated outputs are intentionally not operator-ready: source/runtime ledgers,
# wrapper admission and new image contract must be assembled and reviewed first.
(a.output/'REVIEW-NOT-INSTALLABLE.txt').write_text('Thor stock FORMAT2 source adapter only. No IMAGE, seals, private settings or firmware.\nRequires exact stock source admission, shared metadata fallback, trusted OW_EXPECT context, transactional helper installation and complete RAM tool ledgers before operator use.\nPreserving OpenWiFi upgrades use their existing separate qualified route.\n')
for name in ('platform.sh','cambium-ab-upgrade.sh','cambium-installer-handoff.sh','cambium-installer-settings.sh'):
 subprocess.run(['sh','-n',str(a.output/name)],check=True)
print('Thor writer callbacks prepared; UNSEALED source-review fixture only')
