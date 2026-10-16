#!/usr/bin/env python3
"""Record the exact public stock13 source tuple; never inspect AP secrets.

ROOT must be freshly extracted from the verified sysupgrade's root member.
This is evidence generation, not an approval of arbitrary supplied roots.
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
root, image = (Path(p).resolve() for p in sys.argv[1:])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
expected = 'f44fccdb8205e29c3cabd140a5bc9cfcac334d7e3a3c45eabb5d3f48f2968182'
assert sha(image) == expected, 'not the published stock13 sysupgrade'
metadata = (root/'etc/cambium-openwrt-release').read_text()
assert "SAGE_BUILD_ID='2026.10.13.0'" in metadata
assert "CAMBIUM_SOURCE_COMMIT='a4cfc361dcf941d0c4343ab51fd9513334292dd1'" in metadata
baseline = HERE.parent/'sage-stock6-r3/source-sets/outgoing-stock-2026.09.29.0.set'
paths = {line.split()[1] for line in baseline.read_text().splitlines()}
for pattern in ('lib/*.sh', 'lib/functions/*.sh', 'lib/upgrade/*.sh'):
    paths.update('/'+str(p.relative_to(root)) for p in root.glob(pattern))
rows = []
for name in sorted(paths):
    path = root/name.lstrip('/')
    assert not path.is_symlink(), name
    assert not path.exists() or path.is_file(), name
    rows.append((sha(path) if path.is_file() else '-')+' '+name+'\n')
sets = HERE/'source-sets'
sets.mkdir(exist_ok=True)
ledger = sets/'outgoing-stock-2026.10.13.0.set'
ledger.write_text(''.join(rows))
with tarfile.open(image) as archive:
    payload = archive.extractfile('sysupgrade-cambium_e410/root').read()
receipt = {
    'release': 'snapshot-2026.10.13.0',
    'repository': 'https://github.com/m0vse/cambium-openwrt',
    'source_commit': 'a4cfc361dcf941d0c4343ab51fd9513334292dd1',
    'sysupgrade_sha256': expected,
    'root_squashfs_sha256': hashlib.sha256(payload).hexdigest(),
    'source_set_sha256': sha(ledger),
    'source_members': len(rows),
    'admission': 'E410/E410B using the existing model/SKU gate',
    'source_fit_policy': 'active E410 stock13 config@ap.dk01.1-c2; target E410 config@5; dedicated E410B config@17 on both',
    'hardware_acceptance': False,
}
(HERE/'PUBLIC-SOURCE.json').write_text(json.dumps(receipt, indent=2)+'\n')
print(json.dumps(receipt, indent=2))
