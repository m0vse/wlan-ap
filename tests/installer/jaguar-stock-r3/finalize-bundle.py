#!/usr/bin/env python3
"""Mechanically seal the pinned offline operator artifact; never inspect an AP."""
import hashlib
from pathlib import Path
import sys

bundle = Path(sys.argv[1]).resolve()
image = bundle / 'cambium_xv2-2t1-jaguar-2026.10.02.2-sysupgrade.bin'
digest = hashlib.sha256(image.read_bytes()).hexdigest()
assert digest == '3957cab679b6a01e928d4f755ed05e733aba3659c980de66c6ec7af7befbd3ba'
(bundle / 'IMAGE').write_text(image.name + '\n')
rows = []
for file in sorted(bundle.rglob('*')):
    assert not file.is_symlink(), str(file)
    if file.is_file() and file.name != 'SHA256SUMS':
        rows.append(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.relative_to(bundle)}\n')
(bundle / 'SHA256SUMS').write_text(''.join(rows))
print(f'Sealed {len(rows)} regular files; pinned image {digest}')
