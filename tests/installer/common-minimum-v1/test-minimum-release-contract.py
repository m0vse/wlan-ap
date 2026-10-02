#!/usr/bin/env python3
"""Nonexecuting minimum metadata parser controls, all family/route floors."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

helper = Path(sys.argv[1]).resolve()
work = Path(tempfile.mkdtemp(prefix='minimum-release-contract.', dir='/tmp'))
families = {'sage': ('2026.09.29.0', '2026.10.02.1', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4'),
            'jaguar': ('2026.09.29.0', None, 'qualcommax/ipq60xx', 'aarch64_cortex-a53'),
            'thor': ('2026.09.29.0', '2026.10.02.8', 'qualcommax/ipq807x', 'aarch64_cortex-a53'),
            'cheetah': ('2026.09.29.0', '2026.10.02.11', 'qualcommax/ipq50xx', 'aarch64_cortex-a53'),
            'gambit': ('2026.10.02.0', '2026.10.02.12', 'ath79/nand', 'mips_24kc')}
reports = []
shell = json.loads(os.environ.get('MINIMUM_TEST_SHELL_JSON', '["sh"]'))
def run(family, namespace, minimum, target, arch, case, good, mutation=None, version=None):
    root = work / (family + '-' + namespace + '-' + case)
    (root / 'etc').mkdir(parents=True)
    policy = root / 'policy'
    policy.write_text(f'{namespace} {family} {minimum} {target} {arch}\n')
    version = version or minimum
    values = {'DISTRIB_ID': 'OpenWrt', 'DISTRIB_RELEASE': '25.12.3', 'DISTRIB_REVISION': 'r32912-6639b15f62',
              'DISTRIB_TARGET': target, 'DISTRIB_ARCH': arch, 'DISTRIB_DESCRIPTION': 'OpenWrt 25.12.3 r32912-6639b15f62'}
    stock = {'CAMBIUM_FAMILY': family.title(), family.upper() + '_BUILD_ID': version,
             'CAMBIUM_SOURCE_COMMIT': 'a' * 40, 'OPENWRT_UPSTREAM_COMMIT': 'b' * 40}
    if namespace == 'tip':
        values.update(DISTRIB_TIP_VERSION=family + '-' + version,
                      DISTRIB_TIP=values['DISTRIB_DESCRIPTION'] + ' / TIP-' + family + '-' + version + '-1234abcd')
    if mutation:
        mutation(values, stock)
    release = root / 'etc/openwrt_release'
    release.write_text(''.join(f"{k}='{v}'\n" for k, v in values.items()))
    stock_file = root / 'etc/cambium-openwrt-release'
    if namespace == 'stock' or case == 'mixed-route':
        stock_file.write_text(''.join(f"{k}='{v}'\n" for k, v in stock.items()))
    if case == 'duplicate-key':
        release.write_text(release.read_text() + "DISTRIB_ID='OpenWrt'\n")
    if case == 'shell-statement':
        release.write_text(release.read_text() + 'echo EXECUTED > ' + str(root / 'unsafe-marker') + '\n')
    if case == 'symlink-release':
        release.rename(root / 'original')
        release.symlink_to(root / 'original')
    if case == 'missing-release':
        release.unlink()
    if case == 'oversize-release':
        release.write_text(release.read_text() + '#' + 'x' * 16384 + '\n')
    if case == 'unquoted':
        release.write_text(release.read_text().replace("DISTRIB_ID='OpenWrt'", 'DISTRIB_ID=OpenWrt'))
    if case == 'shell-control-key':
        release.write_text(release.read_text() + "PATH='/tmp/unsafe'\n")
    script = '. "$1"; ow_release_contract_check "$2" "$3"'
    result = subprocess.run(shell + ['-c', script, 'fixture', str(helper), str(policy), str(root)], capture_output=True, text=True)
    assert (result.returncode == 0) == good, (family, namespace, case, result.stderr)
    assert not (root / 'unsafe-marker').exists(), case
    reports.append({'family': family, 'namespace': namespace, 'case': case, 'accepted': result.returncode == 0, 'passed': True})

for family, (stock_floor, tip_floor, target, arch) in families.items():
    for namespace, minimum in (('stock', stock_floor), ('tip', tip_floor)):
        if minimum is None:
            continue # No invented Jaguar preserving route.
        run(family, namespace, minimum, target, arch, 'minimum', True)
        run(family, namespace, minimum, target, arch, 'newer-date-and-source', True,
            lambda v, s: s.update(CAMBIUM_SOURCE_COMMIT='c' * 40), version='2026.10.03.0')
        run(family, namespace, minimum, target, arch, 'below-date', False, version='2026.09.28.999')
        run(family, namespace, minimum, target, arch, 'numeric-revision', True, version='2026.10.02.100')
for namespace, minimum in (('stock', '2026.09.29.0'), ('tip', '2026.10.02.1')):
    for case in ('duplicate-key', 'shell-statement', 'symlink-release', 'missing-release', 'oversize-release', 'unquoted', 'shell-control-key'):
        run('sage', namespace, minimum, 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', case, False)
    for version in ('devel', '2026.13.01.0', '2026.02.29.0', '2026.09.31.0', '2026.10.2.0', '2026.10.02.-1', '2026.10.02.01', '2026.10.02.1000000'):
        run('sage', namespace, minimum, 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'malformed-' + version, False, version=version)
    run('sage', namespace, minimum, 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'wrong-target', False, lambda v, s: v.update(DISTRIB_TARGET='ath79/nand'))
    run('sage', namespace, minimum, 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'wrong-arch', False, lambda v, s: v.update(DISTRIB_ARCH='mips_24kc'))
run('sage', 'stock', '2026.09.29.0', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'wrong-family', False, lambda v, s: s.update(CAMBIUM_FAMILY='Jaguar'))
run('sage', 'stock', '2026.09.29.0', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'TIP-on-stock', False, lambda v, s: v.update(DISTRIB_TIP_VERSION='sage-2026.10.02.1'))
run('sage', 'tip', '2026.10.02.1', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'mixed-route', False)
run('sage', 'tip', '2026.10.02.1', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'wrong-family', False, lambda v, s: v.update(DISTRIB_TIP_VERSION='thor-2026.10.02.8'))
run('sage', 'tip', '2026.10.02.1', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'inconsistent-full', False, lambda v, s: v.update(DISTRIB_TIP=v['DISTRIB_TIP'].replace('2026.10.02.1', '2026.10.02.2')))
run('sage', 'tip', '2026.10.02.1', 'ipq40xx/generic', 'arm_cortex-a7_neon-vfpv4', 'bad-source-suffix', False, lambda v, s: v.update(DISTRIB_TIP=v['DISTRIB_TIP'][:-8] + 'zzzzzzzz'))
print(json.dumps({'passed': True, 'count': len(reports), 'cases': reports, 'fixture': str(work),
                  'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
                  'shell': shell,
                  'scope': 'Shared metadata data-parser fixtures under stated shell and PATH-selected awk/wc; no sourced AP metadata, implementation approval, AP operations or hardware proof'}, indent=2))
