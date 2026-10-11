#!/usr/bin/env python3
"""Build an unsealed staging-only bridge from a verified stock source tuple.

No image is copied, no checksum seal is inherited, and no AP is modified.
The release operator must qualify the outgoing runtime and candidate before
adding IMAGE/SHA256SUMS. Source roots must match the frozen outgoing ledger.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
COMMON = HERE.parent
TOOLS = ('awk cat chmod cmp cp date dirname find fw_printenv fw_setenv head '
         'hexdump ls mkdir mktemp mount mv readlink rm rmdir sed seq sha256sum '
         'sync tar tr ubiattach ubidetach ubiformat ubimkvol ubirmvol '
         'ubirsvol ubiupdatevol umount wc').split()

def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('unexpected source shape: ' + repr(old))
    return text.replace(old, new)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def generate(family, root, out, release):
    if not re.fullmatch(r'[A-Za-z0-9._~-]{1,64}', release):
        raise ValueError('unsafe release')
    if family != 'cheetah' or release != '2026.09.29.0':
        raise ValueError('only the qualified converted XV2-21X stock 2026.09.29.0 route is supported')
    frozen = HERE / 'frozen-stock-r6'
    ledgers = list((frozen/'source-sets').glob('outgoing-*.set'))
    if len(ledgers) != 1:
        raise ValueError('expected one qualified stock ledger')
    original = ledgers[0]
    for row in original.read_text().splitlines():
        sha, name = row.split()
        path = root / name.lstrip('/')
        if path.is_symlink() or (sha == '-' and path.exists()) or (sha != '-' and (not path.is_file() or digest(path) != sha)):
            raise ValueError('stock source ledger mismatch: ' + name)
    release_file = root/'etc/cambium-openwrt-release'
    if release not in release_file.read_text():
        raise ValueError('release not present in authenticated stock release metadata')
    subprocess.run(['sh', '-c', '. "$1"; ow_runtime_contract_check "$2" "$3"',
                    'qualified-runtime', str(frozen/'runtime-implementation-contract.sh'),
                    str(frozen/'runtime-implementation.set'), str(root)], check=True)
    out.mkdir(parents=True, exist_ok=False)
    for name in ('prepare-upgrader.sh', 'bridge-transaction.sh', f'{family}-sysinstall.sh',
                 'cambium-ab.sh', 'cambium-ab-upgrade.sh', 'cambium-ab-certificates.sh',
                 'platform.sh', 'source-set-check.sh'):
        shutil.copy2(frozen/name, out/name)
    shutil.copytree(frozen/'modules', out/'modules')
    if family == 'sage':
        shutil.copy2(frozen/'cambium-sage.sh', out/'cambium-sage.sh')
    shutil.copy2(COMMON/'cambium-installer-handoff.sh', out/'cambium-installer-handoff.sh')
    for name in ('minimum-release-contract.sh', 'runtime-implementation-contract.sh', 'runtime-implementation.set', 'release-policy'):
        shutil.copy2(frozen/name, out/name)
    shutil.copy2(REPO/'tools/oem-migration/recovery/scripts/lib/cambium-installer-settings.sh', out/'cambium-installer-settings.sh')

    writer = out/'cambium-ab-upgrade.sh'
    text = writer.read_text()
    text = '. "${CAMBIUM_INSTALLER_HANDOFF_LIB:-/lib/upgrade/cambium-installer-handoff.sh}" || return 1\n' + text
    anchor = '\tab_upgrade_preflight || return 1\n\tab_image_extract "$1" || return 1'
    text = replace(text, anchor, '\tab_installer_refuse_pending || return 1\n' + anchor + '\n\tab_installer_validate_ram "$1" || return 1')
    anchor = '\tab_setenv_batch "$batch" || { rm -f "$batch"; ab_fail "cannot record the upgrade"; return 1; }'
    text = replace(text, anchor, '\tab_installer_pending "$batch" || { rm -f "$batch"; return 1; }\n' + anchor)
    for indent in ('\t\t', '\t'):
        anchor = '\n' + indent + 'ab_arm_trial ||\n'
        text = replace(text, anchor, '\n' + indent + 'ab_installer_install_settings "$1" ||\n' + indent + '\t{ ab_record_failure write-failed "cannot stage installer settings; source remains default"; return 1; }' + anchor)
    writer.write_text(text)
    platform = out/'platform.sh'
    text = platform.read_text()
    anchor = 'platform_pre_upgrade() {\n\tif command -v ab_family >/dev/null && ab_family; then\n'
    # Only pre-upgrade hook: other platform hooks retain their original shape.
    text = text.replace(anchor, anchor + '\t\tab_installer_ramfs\n\t\tab_installer_validate_ram "$1" || exit 1\n', 1)
    text = text.replace("RAMFS_COPY_BIN='", "RAMFS_COPY_BIN='" + ' '.join(TOOLS) + ' ', 1)
    platform.write_text(text)
    transaction = out/'bridge-transaction.sh'
    text = transaction.read_text()
    text = text.replace('\nITEMS\n', '\ncambium-installer-handoff.sh /lib/upgrade/cambium-installer-handoff.sh\ncambium-installer-settings.sh /lib/upgrade/cambium-installer-settings.sh\nITEMS\n', 1)
    transaction.write_text(text)

    wrapper = out/'prepare-upgrader.sh'
    text = wrapper.read_text()
    text = replace(text, '--verify-installed|--recover)', '--verify-installed|--stage-auth|--recover)')
    anchor = 'export CAMBIUM_AB_CERTIFICATE_LIB="$bundle/cambium-ab-certificates.sh"\n'
    text = replace(text, anchor, anchor + 'export CAMBIUM_INSTALLER_HANDOFF_LIB="$bundle/cambium-installer-handoff.sh"\nexport CAMBIUM_INSTALLER_SETTINGS_LIB="$bundle/cambium-installer-settings.sh"\n')
    anchor = "[ \"${AB_CERTIFICATE_POLICY_VERSION:-0}\" = 1 ] || die 'canonical certificate allocation policy missing'\n"
    text = replace(text, anchor, anchor + 'ab_installer_refuse_pending || die "pending installer provenance or unreadable ENV; no fresh install permitted"\n')
    anchor = 'case "$mode" in\n --check)'
    stage = '''if [ "$mode" = --stage-auth ]; then
 [ "$#" = 3 ] || die 'protected settings directory required'
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" || die 'installed bridge mismatch'
 AB_INSTALLER_INPUT=$3
 OW_STAGE_ADMISSION=qualified
 ow_settings_tree "$AB_INSTALLER_INPUT" || die 'invalid private settings'
 OW_EXPECT_JOB=$OW_JOB
 OW_EXPECT_SERIAL=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f')
 OW_EXPECT_FAMILY=$AB_FAMILY OW_EXPECT_MODEL=$AB_MODEL
 OW_EXPECT_SOURCE=$AB_ACTIVE OW_EXPECT_TARGET=$AB_TARGET
 OW_EXPECT_OPERATION=production-stock-openwrt-migration
 OW_EXPECT_RELEASE=$(sed -n '1p' "$bundle/source-contract")
 OW_EXPECT_CONTRACT=$(sed -n '2p' "$bundle/source-contract")
 ab_installer_export "$image" || die 'settings handoff refused'
 exit 0
fi
'''
    text = replace(text, anchor, stage + anchor)
    text = text.replace('for binary in tr sysupgrade ', 'for binary in ' + ' '.join(TOOLS) + ' sysupgrade ', 1)
    wrapper.write_text(text)
    install = out/f'{family}-sysinstall.sh'
    text = install.read_text()
    anchor = 'sysupgrade -T "$image"\n'
    text = replace(text, anchor, '[ "$#" = 2 ] || { echo "--install requires protected settings directory" >&2; exit 1; }\nsh "$here/prepare-upgrader.sh" --stage-auth "$image" "$2"\n' + anchor)
    install.write_text(text)
    seeds = out/'runtime-seeds'
    seeds.write_text((frozen/'runtime-seeds').read_text()+'\n'+'\n'.join(TOOLS+['sh'])+'\n')
    subprocess.run(['python3', str(frozen/'make-runtime-implementation-set.py'), str(root),
                    str(out/'runtime-implementation.set'), str(seeds), '183'], check=True,
                   stdout=subprocess.DEVNULL)
    old_hashes = {row.split()[1] for row in (frozen/'runtime-implementation.set').read_text().splitlines()
                  if row.split()[0] in ('F', 'X')}
    for row in (out/'runtime-implementation.set').read_text().splitlines():
        kind, sha, name = row.split()
        if kind in ('F', 'X') and sha not in old_hashes:
            raise ValueError('new runtime implementation requires independent qualification: '+name)
    # New ledgers are generated from verified source bytes, never copied seals.
    replacements = {}
    for row in subprocess.check_output(['sh', '-c', '. "$1"; bridge_items', 'bridge', str(transaction)], text=True).splitlines():
        src, dst = row.split()
        replacements[dst] = src
    required = {row.split()[1] for row in original.read_text().splitlines()} | set(replacements)
    sets = out/'source-sets'
    sets.mkdir()
    (sets/'required-paths').write_text(''.join(p+'\n' for p in sorted(required)))
    for name, installed in ((original.name, False), ('installed-bridge.set', True)):
        rows = []
        for p in sorted(required):
            f = out/replacements[p] if installed and p in replacements else root/p.lstrip('/')
            if f.is_symlink() or (f.exists() and not f.is_file()):
                raise ValueError('unsafe source member: ' + p)
            rows.append((digest(f) if f.is_file() else '-') + ' ' + p + '\n')
        (sets/name).write_text(''.join(rows))
    (out/'source-contract').write_text(release+'\n'+digest(sets/original.name)+'\n')
    (out/'REVIEW-NOT-INSTALLABLE.txt').write_text('No image or checksum seal. Runtime closure and candidate image admission are required before publication. Fresh retry refuses any pending provenance; this tool does not reformat/rearm existing candidates.\n')
    for file in out.glob('*.sh'):
        subprocess.run(['sh', '-n', str(file)], check=True)
    return out

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('family', choices=['cheetah'])
    p.add_argument('stock_root', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--release', required=True)
    a = p.parse_args()
    print(generate(a.family, a.stock_root.resolve(), a.output.resolve(), a.release))
