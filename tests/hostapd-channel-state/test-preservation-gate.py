#!/usr/bin/env python3
"""Exercise the real preservation command against isolated working files."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--family', required=True, choices=('sage', 'jaguar', 'cheetah', 'thor', 'miami'))
p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
a = p.parse_args()
repo = a.repo.resolve()
here = Path(__file__).resolve().parent
ledger = json.loads((here / 'protected-source.json').read_text())
pins = {**ledger['common'], **(ledger['miami_supplement'] if a.family == 'miami' else {})}
gitdir = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--absolute-git-dir'], text=True).strip()
with tempfile.TemporaryDirectory(prefix='source-preservation-gate-') as tmp:
    root = Path(tmp)
    tree_files = subprocess.check_output(['git', '-C', str(repo), 'ls-tree', '-r', '--name-only', 'HEAD', '--', *ledger['protected_trees']], text=True).splitlines()
    for name in set(pins) | set(tree_files):
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, dest, follow_symlinks=False)
    # Read existing immutable ancestry; hash only the disposable working files.
    # The verifier has no Git write commands and cannot alter this repository.
    env = {**os.environ, 'GIT_DIR': gitdir, 'GIT_WORK_TREE': str(root)}
    def run():
        result = subprocess.run([sys.executable, str(here / 'test-source-preservation.py'), '--family', a.family, '--repo', str(root)], env=env, capture_output=True, text=True)
        report = json.loads(result.stdout)
        assert (result.returncode == 0) == report['passed'], result.stderr
        return report
    assert run()['passed']
    for tree in ledger['protected_trees']:
        name = next(n for n in tree_files if n.startswith(tree + '/') and not (root / n).is_symlink())
        protected = root / name
        data = protected.read_bytes()
        protected.write_bytes(data + b'\n# unreviewed prior-fix replacement\n')
        assert not run()['passed'], 'Protected package-tree drift was accepted'
        protected.write_bytes(data)
    protected = root / tree_files[0]
    mode = protected.stat().st_mode & 0o777
    protected.chmod(mode ^ 0o111)
    assert not run()['passed'], 'Executable-mode drift was accepted'
    protected.chmod(mode)
    target = root / 'feeds/ucentral/ucentral-schema/files/usr/share/ucentral/radio_operating.uc'
    original = target.read_bytes()
    target.write_bytes(original + b'\n// unreviewed replacement\n')
    assert not run()['passed'], 'Working-file drift was hidden by valid ancestry'
    target.unlink()
    assert not run()['passed'], 'Deleted protected source was accepted'
    target.symlink_to(repo / target.relative_to(root))
    assert not run()['passed'], 'A symlink was accepted in place of protected source'
    target.unlink()
    target.write_bytes(original)
    unrelated = root / 'unrelated-private-settings'
    unrelated.write_text('synthetic unrelated settings\n')
    assert run()['passed'], 'Unrelated private work must remain untouched'
print('PASS 9 actual preservation-command controls: qualified source, three package trees, executable mode, critical drift/deletion/symlink and unrelated work; no AP or Git writes')
