#!/usr/bin/env python3
"""Package verified, already-retained build images; never reads a device."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--evidence', type=Path, required=True)
a = p.parse_args()
commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=a.source, text=True).strip()
assert commit == '9699910d9cf5c6a51aac564189ade97a0363d38d'
final = a.evidence / 'miami-ab-seed-9699910d'
inspection = json.loads((final / 'ab-image-inspection.json').read_text())
assert set(inspection['slots']) == {'0', '1'}
for slot in inspection['slots'].values():
    assert slot['owned_helpers_match_source']
    assert slot['tar_root_matches_with_zero_1024_byte_padding']
old = a.evidence / 'miami-b6d1a26f-retained-images'
prior = final / 'prior-b6'
assert not prior.exists(), 'Refusing to replace retained evidence'
prior.mkdir()
pins = [
    '9c22c101aad1325ca0e1cfac9c52a3d84b3c3a5bfc46a99667dc491c3765712b',
    'dcf685056218b88a8685ea2c60c8cc0fceef5a39dcc168691541f9fb90e4a255',
]
files = {}
for slot in (0, 1):
    for kind, suffix, size, digest in (
        ('kernel', 'kernel.itb', 4855880, pins[slot]),
        ('rootfs', 'rootfs.squashfs', 22502074, '1ecd75a5487c1a014d05adce627bf746b163df7b3f275deff258c77d9564dae9'),
    ):
        source = old / f'openwrt-ipq53xx-cambiumnetworks_miami-persistent-slot{slot}-squashfs-{suffix}'
        data = source.read_bytes()
        assert len(data) == size and hashlib.sha256(data).hexdigest() == digest
        name = f'miami-persistent-slot{slot}-{suffix}'
        shutil.copyfile(source, prior / name)
        files[name] = {'sha256': digest, 'bytes': size, 'slot': slot, 'kind': kind}
receipt = {'source_commit': 'b6d1a26f8aec83e9c8e87eb67e440fc7376a0245',
           'family': 'miami', 'model': 'X7-35X', 'certificate_lebs': 64,
           'vault_lebs': 72, 'images': files,
           'purpose': 'Prior image pins reconstructed from verified retained build payloads'}
path = prior / 'persistent-bundle.json'
path.write_text(json.dumps(receipt, indent=2) + '\n')
subprocess.run(['python3', str(a.source / 'contrib/cambium/miami/build-persistent-bundle.py'),
                '--images', str(final / 'images'), '--output', str(final / 'provider'),
                '--source-commit', commit, '--prior-bundle', str(path), '--ab-seed'], check=True)
