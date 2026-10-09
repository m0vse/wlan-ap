#!/usr/bin/env python3
"""Actual patched Thor command generators; simulated bootloader boundaries.

Usage: python3 family-thor-boot.py PREPARED_OPENWRT_ROOT
Prepared root contains the current package/cambium sources, including common patch 0179.
No device, firmware build, network or bootloader operation is performed.
"""
from pathlib import Path
import argparse
import json
import os
import shlex
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    a = parser.parse_args()
    repo = Path(__file__).resolve().parents[4]
    results = []
    with tempfile.TemporaryDirectory(prefix='thor-boot-contract-') as tmp:
        work = Path(tmp)
        tree = work / 'source/package/cambium/cambium-ab/files'
        tree.mkdir(parents=True)
        source_base = a.baseline / 'package/cambium'
        for package in ('cambium-ab', 'cambium-thor-support'):
            shutil.copytree(source_base / package, work / 'source/package/cambium' / package, dirs_exist_ok=True)
        patch = repo / 'patches-25.12/0181-cambium-thor-gate-oem-save-and-check-bank-routing.patch'
        subprocess.run(['patch', '--fuzz=0', '-p1', '-d', str(work / 'source'),
                        '-i', str(patch)], check=True, capture_output=True)
        assert (tree / 'cambium-ab.sh').read_bytes() == (source_base / 'cambium-ab/files/cambium-ab.sh').read_bytes()
        assert (tree.parent / 'Makefile').read_bytes() == (source_base / 'cambium-ab/Makefile').read_bytes()
        module = work / 'source/package/cambium/cambium-thor-support/files/cambium-ab-thor.sh'
        protected = work / 'protected'
        protected.mkdir()
        for name in ('previous-bank', 'ART', 'MFG', 'PHY', 'BOOTCONFIG0',
                     'BOOTCONFIG1', 'certificates', 'vault'):
            (protected / name).write_bytes(('synthetic-own-' + name).encode())
        original = {p.name: p.read_bytes() for p in protected.iterdir()}
        driver = work / 'driver.sh'
        driver.write_text(r'''
. "$CORE"
. "$UPGRADE"
. "$MODULE"
AB_FAMILY=thor AB_ENV=thor AB_ACTIVE=$PRIOR AB_TARGET=$((1-PRIOR))
AB_FIT=config@hk02 AB_SLOT1_OFFSET=0x6000000
AB_STOCK_BOOTCMD='aq_load_fw&&bootipq'
AB_LAYOUT=banks AB_MARKER=1 AB_VAULT=1 AB_TARGET_MTD=9 AB_ACTIVE_UBI=ubi7
ab_getenv() {
 case "$1" in
 bootcmd) printf '%s\n' "$PRIOR_DEFAULT";;
 thor_ab_version) [ "$MODE" != oem ] && echo 1;;
 thor_ab_confirmed) echo "$CONFIRMED";;
 changing_bootcmd) echo "$MARKER";;
 thor_ab_state) echo confirmed;;
 thor_boot0|thor_boot1)
  if [ "$BAD_BOOT_VAR" = "$1" ]; then echo 'nand load wrong-bank'; return; fi
  slot=${1#thor_boot}
  [ "$BAD_LEGACY_ROUTING" != "$1" ] || slot=$((1-slot))
  cmd=$(ab_thor_boot_command "$slot") || return 1
  case "$LEGACY_BOOT_SLOT:$slot" in both:*|0:0|1:1)
   case "$cmd" in 'aq_load_fw && '*) cmd="aq_load_fw; ${cmd#aq_load_fw && }";; esac
  esac
  printf '%s\n' "$cmd";;
 thor_stable0|thor_stable1)
  if [ "$BAD_BOOT_VAR" = "$1" ]; then echo 'run wrong-default'; return; fi
  slot=${1#thor_stable}; ab_stable_command "$slot" "$((1-slot))";;
 esac
}
ab_bank_hex() { echo 0x6000000; }
if [ "$ACTION" = prior-callback ]; then
 expected=$(ab_thor_boot_command "$AB_ACTIVE") || exit 1
 stored=$(ab_getenv "thor_boot$AB_ACTIVE") || exit 1
 case "$CALLBACK_FAULT" in
 expected-bank) expected=$(ab_thor_boot_command "$AB_TARGET");;
 unknown) stored='unqualified command';;
 suffix) stored="$stored; run arbitrary";;
 esac
 ab_hook prior_boot_valid && ab_thor_prior_boot_valid "$stored" "$expected" || exit 1
 printf '%s\n' CALLBACK_PASSED > "$TRACE"
 exit 0
fi
if [ "$ACTION" = preflight ] || [ "$MODE" = upgrade ]; then
 ab_identity() { return 0; }
 ab_certificate_lebs() { echo 20; }
 ab_mtd_writable() { return 0; }
 ab_ubi_volume() { echo ubi7_3; }
 ab_upgrade_preflight || exit 1
 if [ "$ACTION" = preflight ]; then
  printf '%s\n' PREFLIGHT_PASSED > "$TRACE"
  exit 0
 fi
fi
if [ "$MODE" = oem ]; then
 command=$(ab_thor_guarded_command "$AB_TARGET") || exit 1
elif [ "$MODE" = deny-oem-fallback ]; then
 ab_thor_guarded_command "$AB_TARGET"
 exit $?
else
 command=$(ab_trial_command "$AB_ACTIVE" "$AB_TARGET") || exit 1
fi
if [ "$ACTION" = generate ]; then printf '%s\n' "$command"; exit 0; fi
bootcmd=ARMED_CANDIDATE
event() { printf '%s\n' "$*" >> "$TRACE"; }
setenv() {
 name=$1; shift
 event "set-$name"
 [ "$FAULT" != "set-$name" ] || return 1
 [ "$name" != bootcmd ] || bootcmd="$*"
 return 0
}
saveenv() {
 event save
 [ "$FAULT" != save ] || return 1
 printf '%s\n' "$bootcmd" > "$DURABLE"
}
run() {
 event "run-$1"
 if [ "$1" = "thor_boot$AB_TARGET" ]; then
  [ "$FAULT" != candidate-load ] || return 1
  # Simulates bootm not returning: no Linux confirmation is simulated.
  exit 0
 fi
 [ "$1" = "thor_boot$AB_ACTIVE" ]
}
aq_count=0
aq_load_fw() {
 aq_count=$((aq_count+1)); event phy
 [ "$FAULT" != phy ] || [ "$aq_count" -gt 1 ]
}
nand() { event nand; return 0; }
ubi() {
 event "ubi-$1"
 [ "$FAULT" != candidate-load ] || [ "$1" != read ]
}
bootm() { event candidate; exit 0; }
bootipq() { event previous-oem; return 0; }
eval "$command"
''')
        base = {**os.environ, 'CORE': str(tree / 'cambium-ab.sh'),
                'UPGRADE': str(tree / 'cambium-ab-upgrade.sh'),
                'CAMBIUM_AB_LIB': str(tree / 'cambium-ab.sh'),
                'CAMBIUM_AB_CERTIFICATE_LIB': str(work / 'absent-certificate-helper'),
                'MODULE': str(module), 'TRACE': str(work / 'trace'),
                'DURABLE': str(work / 'durable'), 'MARKER': '1', 'FAULT': '',
                'ACTION': 'execute', 'BAD_BOOT_VAR': '', 'LEGACY_BOOT_SLOT': '',
                'BAD_LEGACY_ROUTING': '', 'CALLBACK_FAULT': ''}

        def run_case(name, prior, mode='upgrade', fault='', override=None, accepted=True):
            env = {**base, 'PRIOR': str(prior), 'CONFIRMED': str(prior), 'MODE': mode,
                   'PRIOR_DEFAULT': 'aq_load_fw&&bootipq' if mode == 'oem' else f'run thor_stable{prior}',
                   'FAULT': fault, **(override or {})}
            for namefile in ('trace', 'durable'):
                (work / namefile).unlink(missing_ok=True)
            result = subprocess.run(['sh', str(driver)], env=env, text=True,
                                    capture_output=True, timeout=5)
            assert (result.returncode == 0) == accepted, (name, result.stdout, result.stderr)
            trace = (work / 'trace').read_text().splitlines() if (work / 'trace').exists() else []
            saved = (work / 'durable').read_text().strip() if (work / 'durable').exists() else None
            assert {p.name: p.read_bytes() for p in protected.iterdir()} == original
            results.append(name)
            return trace, saved

        for prior in (0, 1):
            candidate = 1 - prior
            for prefix in ('', 'both'):
                trace, saved = run_case(f'0184-callback-{prior}-{"legacy" if prefix else "current"}-accepted', prior,
                                       override={'ACTION': 'prior-callback', 'LEGACY_BOOT_SLOT': prefix})
                assert trace == ['CALLBACK_PASSED'] and saved is None
            for fault in ('expected-bank', 'unknown', 'suffix'):
                trace, saved = run_case(f'0184-callback-{prior}-{fault}-refused', prior,
                                       override={'ACTION': 'prior-callback', 'CALLBACK_FAULT': fault}, accepted=False)
                assert not trace and saved is None
            for prefix in ('', 'both'):
                trace, saved = run_case(f'0184-callback-{prior}-wrong-bank-{"legacy" if prefix else "current"}-refused', prior,
                                       override={'ACTION': 'prior-callback', 'LEGACY_BOOT_SLOT': prefix,
                                                 'BAD_LEGACY_ROUTING': f'thor_boot{prior}'}, accepted=False)
                assert not trace and saved is None
            legacy = {'CORE': str(source_base / 'cambium-ab/files/cambium-ab.sh'),
                      'UPGRADE': str(source_base / 'cambium-ab/files/cambium-ab-upgrade.sh'),
                      'CAMBIUM_AB_LIB': str(source_base / 'cambium-ab/files/cambium-ab.sh'),
                      'MODULE': str(source_base / 'cambium-thor-support/files/cambium-ab-thor.sh')}
            trace, saved = run_case(f'current-common-OW-{prior}-failed-save-no-candidate',
                                   prior, fault='save', override=legacy)
            assert f'run-thor_boot{candidate}' not in trace and saved is None
            trace, saved = run_case(f'baseline-OEM-{prior}-failed-save-still-loads-defect-reproduced',
                                   prior, mode='oem', fault='save', override=legacy)
            assert 'candidate' in trace and saved is None
            trace, saved = run_case(f'OW-{prior}-to-{candidate}-save-before-load', prior)
            assert saved == f'run thor_boot{prior}'
            assert 'bootipq' not in saved
            assert trace.index('save') < trace.index(f'run-thor_boot{candidate}')
            assert trace.count(f'run-thor_boot{candidate}') == 1
            for legacy_slot in ('both', '0', '1'):
                for default in (f'run thor_stable{prior}', f'run thor_boot{prior}'):
                    trace, saved = run_case(f'OW-{prior}-legacy-{legacy_slot}-{default}-accepted', prior,
                                           override={'LEGACY_BOOT_SLOT': legacy_slot, 'PRIOR_DEFAULT': default})
                    assert saved == f'run thor_boot{prior}'
                    assert trace.count(f'run-thor_boot{candidate}') == 1
            for slot in (0, 1):
                trace, saved = run_case(f'OW-{prior}-legacy-wrong-bank-{slot}-refused', prior,
                                       override={'ACTION': 'preflight', 'LEGACY_BOOT_SLOT': 'both',
                                                 'BAD_LEGACY_ROUTING': f'thor_boot{slot}'}, accepted=False)
                assert not trace and saved is None
            for fault in ('set-bootcmd', 'set-image', 'set-thor_ab_state', 'save'):
                trace, saved = run_case(f'OW-{prior}-{fault}-no-candidate', prior, fault=fault)
                assert f'run-thor_boot{candidate}' not in trace and saved is None
                assert trace[-1] == f'run-thor_boot{prior}'
            trace, saved = run_case(f'OW-{prior}-candidate-load-fails-to-prior', prior, fault='candidate-load')
            assert trace[-1] == f'run-thor_boot{prior}' and saved == f'run thor_boot{prior}'
            for label, override in [('unknown-default', {'PRIOR_DEFAULT': 'unqualified-command'}),
                                    ('wrong-confirmed', {'CONFIRMED': str(candidate)}),
                                    ('missing-marker', {'MARKER': ''})]:
                trace, saved = run_case(f'OW-{prior}-{label}-refused', prior, override=override, accepted=False)
                assert not trace and saved is None
            trace, saved = run_case(f'OW-{prior}-cannot-use-OEM-fallback', prior,
                                   mode='deny-oem-fallback', accepted=False)
            assert not trace and saved is None
            trace, saved = run_case(f'OEM-{prior}-save-before-load', prior, mode='oem')
            assert saved == 'aq_load_fw&&bootipq'
            assert trace.index('save') < trace.index('ubi-read') < trace.index('candidate')
            for fault in ('set-bootcmd', 'set-changing_bootcmd', 'save', 'phy', 'candidate-load'):
                trace, saved = run_case(f'OEM-{prior}-{fault}-no-candidate', prior, mode='oem', fault=fault)
                assert 'candidate' not in trace and trace[-1] == 'previous-oem'
                if fault.startswith('set-') or fault == 'save':
                    assert 'ubi-read' not in trace and saved is None
            trace, saved = run_case(f'OW-{prior}-actual-upgrade-preflight', prior,
                                   override={'ACTION': 'preflight'})
            assert trace == ['PREFLIGHT_PASSED'] and saved is None
            for label, override in [('wrong-confirmed', {'CONFIRMED': str(candidate)}),
                                    ('wrong-prior-default', {'PRIOR_DEFAULT': 'bootipq'}),
                                    ('missing-marker', {'MARKER': ''})]:
                trace, saved = run_case(f'OW-{prior}-prewrite-{label}', prior,
                                       override={'ACTION': 'preflight', **override}, accepted=False)
                assert not trace and saved is None
            trace, saved = run_case(f'OW-{prior}-first-OEM-conversion-still-denied', prior,
                                   mode='oem', override={'ACTION': 'preflight'}, accepted=False)
            assert not trace and saved is None
            trace, saved = run_case(f'OW-{prior}-prior-only-rollback-default-accepted', prior,
                                   override={'PRIOR_DEFAULT': f'run thor_boot{prior}'})
            assert saved == f'run thor_boot{prior}'
            assert trace.count(f'run-thor_boot{candidate}') == 1
            for variable in ('thor_boot0', 'thor_boot1', 'thor_stable0', 'thor_stable1'):
                trace, saved = run_case(f'OW-{prior}-misdirected-{variable}-prewrite-refused', prior,
                                       override={'ACTION': 'preflight', 'BAD_BOOT_VAR': variable}, accepted=False)
                assert not trace and saved is None
        print(json.dumps({'passed': True, 'count': len(results), 'cases': results,
                          'scope': 'Actual prepared current common core unchanged, patched Thor module and preflight, and POSIX-shell command structure. Bootloader commands, save/load results and nonreturning kernel are simulated; no real ENV, flash, watchdog or native health commit. Synthetic previous-bank/ART/MFG/PHY/BOOTCONFIG/certificates/vault bytes unchanged.'}, indent=2))


if __name__ == '__main__':
    main()
