#!/usr/bin/env python3
"""One source-test command; no AP devices, builds or external network."""
from pathlib import Path
import os, subprocess, sys, tempfile
from prepare_family_source import prepare_thor
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent

def run(label,args):
    print(label,flush=True)
    subprocess.run(args,cwd=ROOT,check=True)

run('Common exact-model, transaction and helper tests',[sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v'])
for script in sorted(HERE.glob('family-*.py')):
    if script.name == 'family-thor-boot.py':
        with tempfile.TemporaryDirectory(prefix='unified-thor-source-') as directory:
            prepared = prepare_thor(ROOT, Path(directory))
            run('Family source fixture: '+script.name,[sys.executable,str(script),str(prepared)])
    else:
        run('Family source fixture: '+script.name,[sys.executable,str(script)])
for script in sorted(HERE.glob('test-*.py')):
    run('Family inspection fixture: '+script.name,[sys.executable,str(script)])
run('Actual existing Sage recovery/writer/settings regressions',[sys.executable,'-m','unittest','discover','-s','tools/oem-migration/recovery/scripts/tests','-v'])
run('Actual one-shot rendered command regressions',[sys.executable,'tests/ab-one-shot/test-trial.py'])
linux=ROOT/'tests/installer/overlay-root-permissions/test-unprivileged-traversal.py'
if sys.platform.startswith('linux') and os.geteuid()==0 and linux.is_file():
    run('Private Linux OverlayFS UID81 traversal/secret-denial regression',[sys.executable,str(linux)])
else:
    print('NOT RUN here: real Linux private OverlayFS/UID81 test requires Linux root + isolated mount namespace.',flush=True)
print('Source tests completed. Hardware power-loss, model onboarding and first sysupgrade are separate acceptance.',flush=True)
