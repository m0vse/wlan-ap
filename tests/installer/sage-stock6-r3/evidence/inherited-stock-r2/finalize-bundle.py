#!/usr/bin/env python3
"""Mechanically seal the pinned offline operator artifact; never inspect an AP."""
import hashlib
from pathlib import Path
import sys

bundle = Path(sys.argv[1]).resolve()
image = bundle / 'cambium-sage-sage-2026.10.02.3-sysupgrade.bin'
digest = hashlib.sha256(image.read_bytes()).hexdigest()
assert digest == '2f86a4dd48bcc66912422fef411a4133c582c792b278b35ac5565444a92b495a'
(bundle / 'IMAGE').write_text(image.name + '\n')
rows = []
for file in sorted(bundle.rglob('*')):
    assert not file.is_symlink(), str(file)
    if file.is_file() and file.name != 'SHA256SUMS':
        rows.append(f'{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.relative_to(bundle)}\n')
(bundle / 'SHA256SUMS').write_text(''.join(rows))
print(f'Sealed {len(rows)} regular files; pinned image {digest}')
