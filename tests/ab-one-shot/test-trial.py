#!/usr/bin/env python3
"""Execute rendered boot scripts with disposable environment/load boundaries.

This is a shell control-flow and durable-state model, not real U-Boot execution,
watchdog qualification, flash durability or physical power-loss acceptance.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import re
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]

def load_created_core():
    text = (REPO / 'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
    marker = '+++ b/package/cambium/cambium-ab/files/cambium-ab.sh\n'
    section = text.split(marker, 1)[1].split('\ndiff --git ', 1)[0]
    return ''.join(line[1:] + '\n' for line in section.splitlines() if line.startswith('+'))

def prepare_recipe(root):
    relative = 'package/cambium/cambium-ab/Makefile'
    initial = (REPO/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text().split('+++ b/'+relative+'\n',1)[1].split('\ndiff --git ',1)[0]
    recipe = root/relative
    recipe.write_text(''.join(x[1:]+'\n' for x in initial.splitlines() if x.startswith('+')))
    # Replay all prerequisites for both files, preserving complete hunks and
    # their terminal newlines instead of hand-picking release-counter edits.
    core_relative = 'package/cambium/cambium-ab/files/cambium-ab.sh'
    for path in sorted((REPO/'patches-25.12').glob('*.patch')):
        number = int(path.name[:4])
        if not 124 < number < 179:
            continue
        subprocess.run(['git', 'apply', '--include='+relative,
                        '--include='+core_relative, str(path)],
                       cwd=root, check=True, capture_output=True)
    assert 'PKG_RELEASE:=17\n' in recipe.read_text()
    return recipe

def run_script(script, prior, fail='', reset=False):
    with tempfile.TemporaryDirectory(prefix='ab-trial-script-') as td:
        p = Path(td)
        harness = r'''
setenv() {
 key=$1; shift
 echo "set:$key" >> "$TRACE"
 [ "$FAIL" != "$key" ] || return 1
 value="$*"
 case "$key" in bootcmd) bootcmd=$value;; image) image=$value;; *) trial_state=$value;; esac
}
saveenv() {
 echo save >> "$TRACE"
 [ "$FAIL" != save ] || return 1
 printf '%s\n' "$bootcmd" "$image" > "$DURABLE"
}
run() {
 # Only boot functions from the exact rendered command are invoked.
 case "$1" in
 *_boot"$PRIOR") echo prior >> "$TRACE"; return 0;;
 *_boot*) echo candidate >> "$TRACE";
   [ "$FAIL" != load ] || return 1
   # Kernel entry/hang means no further shell code; reboot uses durable ENV.
   exit 0;;
 *) echo unexpected >> "$TRACE"; return 1;;
 esac
}
'''
        env = dict(os.environ, TRACE=str(p/'trace'), DURABLE=str(p/'saved'), PRIOR=str(prior), FAIL=fail)
        r = subprocess.run(['sh', '-c', harness + '\n' + script], env=env, capture_output=True, text=True)
        calls = (p/'trace').read_text().splitlines() if (p/'trace').exists() else []
        saved = (p/'saved').read_text().splitlines() if (p/'saved').exists() else []
        if reset and saved:
            after = subprocess.run(['sh','-c',harness + '\n' + saved[0]], env=env, capture_output=True, text=True)
            assert after.returncode == 0, after.stderr
            reboot_calls = (p/'trace').read_text().splitlines()[len(calls):]
            assert reboot_calls == ['prior'], reboot_calls
        return calls, saved

def check_command(script, prior, guarded_oem=False):
    count = 0
    state_match = re.search(r'\bsetenv ([A-Za-z0-9_]+_ab_state) trial-started\b', script)
    assert state_match, script
    state = state_match[1]
    if guarded_oem:
        # The reviewed bootcount contract deliberately holds at the prompt if
        # counter/default persistence fails. Calling bootipq in that state can
        # switch to the wrong bank. This is distinct from the native core's
        # direct OpenWiFi prior-slot fallback; do not weaken that assertion.
        assert script.startswith('if setenv bootcount 0 && '), script
        assert '&& saveenv; then run sage_boot' in script, script
        assert script.endswith('; fi'), script
    failures = (('bootcount',) if 'setenv bootcount ' in script else ()) + ('bootcmd', 'image', 'state', 'save', 'load', '')
    for failure in failures:
        fail = state if failure == 'state' else failure
        calls, saved = run_script(script, prior, fail, reset=True)
        if failure in ('bootcount','bootcmd','image','state','save'):
            checkpoint = 'save' if failure == 'save' else 'set:' + fail
            assert checkpoint in calls, (failure, calls)
            assert 'candidate' not in calls, (failure, calls)
            if guarded_oem:
                assert 'prior' not in calls and calls[-1] == checkpoint, (failure, calls)
            else:
                assert calls[-1] == 'prior', (failure, calls)
            assert not saved, (failure, saved)
        else:
            assert calls.index('save') < calls.index('candidate'), calls
            assert saved[0].endswith('_boot' + str(prior)), saved
            assert saved[1] == str(prior), saved
            if failure == 'load': assert calls[-1] == 'prior', calls
        count += 1
    return count

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', type=Path, help='Also test an actual prepared or legacy core')
    args = parser.parse_args()
    total = 0
    with tempfile.TemporaryDirectory(prefix='ab-trial-core-') as td:
        root = Path(td)
        core = root/'package/cambium/cambium-ab/files/cambium-ab.sh'
        core.parent.mkdir(parents=True)
        core.write_text(load_created_core())
        recipe = prepare_recipe(root)
        old = subprocess.check_output(['sh','-c','. "$CORE"; AB_ENV=sage; ab_trial_command 0 1'], env=dict(os.environ, CORE=str(core), CAMBIUM_AB_MODULES=str(root/'no-modules')), text=True).strip()
        try:
            check_command(old, 0)
        except AssertionError:
            pass
        else:
            raise AssertionError('negative control did not detect unsafe original armer')
        subprocess.run(['git', 'apply', str(REPO/'patches-25.12/0179-cambium-ab-persist-prior-before-trial.patch')], cwd=root, check=True, capture_output=True)
        assert 'PKG_RELEASE:=18\n' in recipe.read_text()
        sources = [core] + ([args.core.resolve()] if args.core else [])
        for source in sources:
            for family in ('sage','jaguar','cheetah','thor','gambit','miami'):
                for prior in (0,1):
                    env = dict(os.environ, CORE=str(source), AB_ENV=family, PRIOR=str(prior), CAMBIUM_AB_MODULES=str(root/'no-modules'))
                    rendered = subprocess.check_output(['sh','-c','. "$CORE"; ab_trial_command "$PRIOR" "$((1-PRIOR))"'], env=env, text=True).strip()
                    total += check_command(rendered, prior)
        # Test actual outgoing-Sage armer rendering, not a copied expected string.
        path = REPO/'tools/oem-migration/recovery/scripts/tests/test_cambium_oem_sage_boot.py'
        spec = importlib.util.spec_from_file_location('sage_arm_test', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        arm = module.SageBootTests()
        for model in ('E410','E410B'):
            for prior in (0,1):
                result, state, _ = arm.run_arm(prior, model)
                assert result.returncode == 0, result.stderr
                assert state['sage_stable'+str(prior)] == 'run sage_boot'+str(prior)
                total += check_command(state['bootcmd'], prior, guarded_oem=True)
                # A real failed setter must not be hidden by an independently
                # successful save. Keep this mutation as a negative control.
                unsafe = state['bootcmd'].replace('&& saveenv; then', '; saveenv; then')
                unsafe_calls, unsafe_saved = run_script(unsafe, prior, 'bootcmd')
                assert 'candidate' in unsafe_calls and unsafe_saved, unsafe_calls
        # Actual reverse armer: mock only its already separately tested physical
        # preflights and environment I/O, and preserve its rendered script.
        for prior in (0,1):
            envdir = root/f'reverse-{prior}'; envdir.mkdir()
            script = r'''
. "$LIB"
CSR_ACTIVE=$PRIOR CSR_ENV_CONFIG=fixture
csr_preflight(){ :; }; csr_boot_preflight(){ :; }; csr_configuration_empty_check(){ :; }
csr_source_selector_check(){ :; }
fw_setenv(){ shift 2; if [ "$1" = -s ]; then
 while read -r key value; do printf '%s' "$value" > "$ENV/$key"; done < "$2"
 else printf '%s' "$2" > "$ENV/$1"; fi; }
fw_printenv(){ shift 3; cat "$ENV/$1"; }
sync(){ :; }
csr_arm_oem >/dev/null || exit 1
cat "$ENV/bootcmd"
'''
            env = dict(os.environ, LIB=str(REPO/'tools/oem-migration/recovery/scripts/lib/cambium-sage-oem-recovery.sh'), ENV=str(envdir), PRIOR=str(prior))
            rendered = subprocess.check_output(['sh','-c',script], env=env, text=True).strip()
            assert (envdir/f'sage_stable{prior}').read_text() == f'run sage_boot{prior}'
            total += check_command(rendered, prior, guarded_oem=True)
    print(f'PASS: {total} rendered-script cases; native fallback or guarded OEM safe stop; successful save restores prior-only next boot')
    print('Scope: mocked shell/environment/load boundaries; not real U-Boot, watchdog or physical power-cut proof')

if __name__ == '__main__': main()
