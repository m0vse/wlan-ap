#!/usr/bin/env python3
"""Generate approved tuples from a SHA-verified offline release, never an AP."""
import hashlib, sys
from pathlib import Path
root, bundle = map(Path, sys.argv[1:])
paths=set()
for pattern in ('lib/*.sh','lib/functions/*.sh','lib/upgrade/*.sh'):
    paths.update('/'+str(p.relative_to(root)) for p in root.glob(pattern))
paths.update(['/sbin/sysupgrade','/usr/libexec/validate_firmware_image','/lib/upgrade/stage2','/lib/upgrade/do_stage2','/usr/share/libubox/jshn.sh','/etc/openwrt_release','/etc/cambium-openwrt-release','/usr/sbin/cambium-board-data','/lib/upgrade/cambium-ab-certificates.sh'])
replacements={'/lib/functions/cambium-ab.sh':'cambium-ab.sh','/lib/upgrade/cambium-ab.sh':'cambium-ab-upgrade.sh','/lib/upgrade/cambium-ab-certificates.sh':'cambium-ab-certificates.sh','/lib/functions/cambium-ab-jaguar.sh':'modules/cambium-ab-jaguar.sh','/lib/upgrade/platform.sh':'platform.sh'}
paths.update(replacements)
# Release metadata is separately parsed against a qualified namespace/minimum;
# do not couple a reviewed updater implementation to one release label.
paths.difference_update(['/etc/openwrt_release','/etc/cambium-openwrt-release'])
paths.add('/lib/config/uci.sh')
out=bundle/'source-sets';out.mkdir(parents=True,exist_ok=True)
(out/'required-paths').write_text(''.join(p+'\n' for p in sorted(paths)))
for name, installed in [('outgoing-stock-2026.09.30.102.set',False),('installed-bridge.set',True)]:
    rows=[]
    for p in sorted(paths):
        f=bundle/replacements[p] if installed and p in replacements else root/p.lstrip('/')
        if f.is_symlink(): raise SystemExit('Unsupported symlink in source closure: '+p)
        if f.exists() and not f.is_file(): raise SystemExit('Nonregular source: '+p)
        digest=hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else '-'
        rows.append(f'{digest} {p}\n')
    (out/name).write_text(''.join(rows))
print('Approved closure paths:',len(paths))
