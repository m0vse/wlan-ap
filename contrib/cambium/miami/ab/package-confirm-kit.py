#!/usr/bin/env python3
"""Package only the reviewed OEM confirmation reader/helper dependencies."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

p = argparse.ArgumentParser()
p.add_argument('--helper-source', type=Path, required=True)
p.add_argument('--framework-source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
assert not a.output.exists(), 'Refusing to overwrite a confirmation kit'
head = lambda path: subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=path, text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain', '--',
    'contrib/cambium/miami/ab/confirm-oem-entry.sh', 'contrib/cambium/miami/ab/oem-entry-source.tsv'],
    cwd=a.helper_source, text=True).strip(), 'Helper must be committed'
assert head(a.framework_source) == '964dea9653ec0ad1bc3eb485ace1974d9d6a368b'
a.output.mkdir()
(a.output / 'shared').mkdir()
for name in ('common', 'protection', 'network'):
    shutil.copyfile(a.framework_source / f'tools/oem-migration/unified/lib/{name}.sh',
                    a.output / f'shared/oem-{name}.sh')
shutil.copytree(a.framework_source / 'tools/oem-migration/unified/profiles/X7-35X',
                a.output / 'profiles/X7-35X')
source = a.helper_source / 'contrib/cambium/miami/ab'
assert (source / 'oem-entry-source.tsv').read_bytes() == (a.output / 'profiles/X7-35X/source.tsv').read_bytes()
shutil.copyfile(source / 'confirm-oem-entry.sh', a.output / 'confirm-oem-entry.sh')
subprocess.run(['sh', '-n', str(a.output / 'confirm-oem-entry.sh')], check=True)
entries = {str(f.relative_to(a.output)): {'bytes': f.stat().st_size,
           'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
           for f in sorted(a.output.rglob('*')) if f.is_file()}
receipt = {'purpose': 'Explicit retained-OEM boot confirmation only; no firmware images or installer writes',
           'helper_source_commit': head(a.helper_source), 'framework_source_commit': head(a.framework_source),
           'device_id': 'cambium_x7-35x', 'files': entries}
(a.output / 'confirmation-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
entries['confirmation-receipt.json'] = {'sha256': hashlib.sha256((a.output / 'confirmation-receipt.json').read_bytes()).hexdigest()}
(a.output / 'SHA256SUMS').write_text(''.join(v['sha256'] + '  ' + k + '\n' for k, v in entries.items()))
print(a.output)
