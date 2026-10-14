#!/usr/bin/env python3
"""Read-only qualified-parent and critical-source check; never contact an AP."""
import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--family', required=True, choices=('sage', 'jaguar', 'cheetah', 'thor', 'miami'))
parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
args = parser.parse_args()
repo = args.repo.resolve()
here = Path(__file__).resolve().parent
baseline = json.loads((here / 'qualified-family-bases.json').read_text())
parents = baseline['families']
ledger = json.loads((here / 'protected-source.json').read_text())
pins = {**ledger['common']}
if args.family == 'miami':
    pins.update(ledger['miami_supplement'])
failures = []
parent = parents[args.family]
ancestry = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', parent, 'HEAD'], capture_output=True)
if ancestry.returncode:
    failures.append('Qualified family parent is absent or no longer an ancestor: ' + parent)
if args.family != 'miami':
    shared = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', baseline['shared_public_base'], 'HEAD'], capture_output=True)
    if shared.returncode:
        failures.append('Reviewed shared source baseline is missing')
for name, expected in ledger['protected_trees'].items():
    tree = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD:' + name], capture_output=True, text=True)
    dirty = subprocess.run(['git', '--no-optional-locks', '-c', 'core.filemode=true', '-C', str(repo), 'diff', '--no-ext-diff', '--quiet', 'HEAD', '--', name], capture_output=True)
    if tree.returncode or tree.stdout.strip() != expected or dirty.returncode:
        failures.append('Protected boot/client/fault source tree differs: ' + name)
for name, expected in pins.items():
    path = repo / name
    if path.is_symlink() or not path.is_file():
        failures.append('Missing/nonregular protected source: ' + name)
        continue
    result = subprocess.run(['git', '-C', str(repo), 'hash-object', '--no-filters', str(path)], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() != expected:
        failures.append('Protected source differs; review required: ' + name)
revision = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True)
print(json.dumps({'family': args.family, 'revision': revision.stdout.strip(), 'qualified_parent': parent,
                  'protected_files': len(pins), 'protected_trees': len(ledger['protected_trees']), 'passed': not failures, 'failures': failures}, separators=(',', ':')))
raise SystemExit(bool(failures))
