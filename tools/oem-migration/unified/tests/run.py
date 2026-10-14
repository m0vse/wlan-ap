#!/usr/bin/env python3
"""One source-test command; no AP devices, builds or external network."""
from pathlib import Path
import argparse, json, os, subprocess, sys, tempfile
from prepare_family_source import prepare_thor
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--thor-inputs',type=Path,help='Private JSON manifest for the retained Thor actual-data tests; never commit the manifest or assets')
options=parser.parse_args()
thor_inputs={}
required=('runtime_root','provider','image','bdf','settings','kernel','rootfs')
if options.thor_inputs:
    supplied=json.loads(options.thor_inputs.read_text())
    if set(supplied)!=set(required):parser.error('Thor manifest must contain exactly: '+', '.join(required))
    for key in required:
        path=Path(supplied[key])
        if not path.is_absolute():path=options.thor_inputs.resolve().parent/path
        if not (path.is_dir() if key in ('runtime_root','provider') else path.is_file()):parser.error('Unavailable Thor input: '+key)
        thor_inputs[key]=path.resolve()
asset_tests={
    'family-thor-forward.py':('image','bdf','settings'),
    'family-thor-layout.py':(),
    'family-thor-restore.py':('kernel','rootfs'),
    'family-thor-roundtrip.py':('kernel','rootfs','image','bdf','settings'),
}
not_run=[]

def run(label,args):
    print(label,flush=True)
    subprocess.run(args,cwd=ROOT,check=True)

run('Common exact-model, transaction and helper tests',[sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v'])
for script in sorted(HERE.glob('family-*.py')):
    if script.name in asset_tests:
        if not thor_inputs:
            not_run.append(script.name)
            print('NOT RUN: '+script.name+' requires --thor-inputs with its reviewed private assets.',flush=True)
            continue
        args=[HERE.parent/'lib',thor_inputs['runtime_root'],thor_inputs['provider']]
        args.extend(thor_inputs[key] for key in asset_tests[script.name])
        run('Family actual-data fixture: '+script.name,[sys.executable,str(script),*[str(arg) for arg in args]])
    elif script.name == 'family-thor-boot.py':
        with tempfile.TemporaryDirectory(prefix='unified-thor-source-') as directory:
            prepared = prepare_thor(ROOT, Path(directory))
            run('Family source fixture: '+script.name,[sys.executable,str(script),str(prepared)])
    elif script.name in ('family-thor-inspection.py', 'family-thor-existing-child.py'):
        run('Family source fixture: '+script.name,[sys.executable,str(script),str(HERE.parent/'lib')])
    else:
        run('Family source fixture: '+script.name,[sys.executable,str(script)])
for script in sorted(HERE.glob('test-*.py')):
    run('Family inspection fixture: '+script.name,[sys.executable,str(script)])
run('Actual existing Sage recovery/writer/settings regressions',[sys.executable,'-m','unittest','discover','-s','tools/oem-migration/recovery/scripts/tests','-v'])
run('Actual one-shot rendered command regressions',[sys.executable,'tests/ab-one-shot/test-trial.py'])
for script in ('tests/ab-one-shot/test-jaguar-oem.py',
               'tests/ab-one-shot/test-jaguar-bootcount.py',
               'tests/cheetah-bootcount/test-legacy-counter.py',
               'tests/thor/one-shot-current/test-oem-counter.py'):
    run('Retained OEM counter safety: '+script,[sys.executable,script])
linux=ROOT/'tests/installer/overlay-root-permissions/test-unprivileged-traversal.py'
if sys.platform.startswith('linux') and os.geteuid()==0 and linux.is_file():
    run('Private Linux OverlayFS UID81 traversal/secret-denial regression',[sys.executable,str(linux)])
else:
    print('NOT RUN here: real Linux private OverlayFS/UID81 test requires Linux root + isolated mount namespace.',flush=True)
if not_run:
    print('Source-only layers completed; actual-data Thor transaction layers were NOT RUN. This is not an all-family migration-readiness result.',flush=True)
else:
    print('Source and supplied actual-data layers completed.',flush=True)
print('Hardware power-loss, model onboarding and first sysupgrade are separate acceptance.',flush=True)
