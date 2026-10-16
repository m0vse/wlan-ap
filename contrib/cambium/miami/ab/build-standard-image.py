#!/usr/bin/env python3
"""Combine inspected boot variants into one ordinary inactive-slot upgrade tar."""
from pathlib import Path
import argparse, hashlib, io, json, subprocess, tarfile, tempfile

p = argparse.ArgumentParser()
p.add_argument('--images', type=Path, required=True)
p.add_argument('--inspection', type=Path, required=True)
p.add_argument('--fwtool', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--firmware-version', required=True)
a = p.parse_args()
assert not a.output.exists(), 'Refusing to replace an existing image'
report = json.loads(a.inspection.read_text())
metadata = []
members = {}
with tempfile.TemporaryDirectory(prefix='miami-standard-image-') as td:
    work = Path(td)
    for slot in (0, 1):
        name = f'openwrt-ipq53xx-cambiumnetworks_miami-ab-slot{slot}-squashfs-sysupgrade.tar'
        source = a.images / name
        pin = report['slots'][str(slot)]['images'][name]
        assert source.stat().st_size == pin['bytes'] and hashlib.sha256(source.read_bytes()).hexdigest() == pin['sha256']
        assert a.firmware_version in report['slots'][str(slot)]['release']
        path = work / f'metadata{slot}.json'
        subprocess.run([str(a.fwtool), '-i', str(path), str(source)], check=True)
        item = json.loads(path.read_text())
        assert item['supported_devices'] == ['cambiumnetworks,x7-35x']
        assert item['version']['board'] == f'cambiumnetworks_miami-ab-slot{slot}'
        metadata.append(item)
        directory = f'sysupgrade-cambiumnetworks_miami-ab-slot{slot}'
        with tarfile.open(source) as tar:
            for leaf in ('CONTROL', 'kernel', 'root'):
                file = tar.getmember(directory + '/' + leaf)
                assert file.isfile()
                members[file.name] = (tar.extractfile(file).read(), file.mode, file.mtime)
    left, right = metadata
    right['version']['board'] = left['version']['board']
    assert left == right, 'Per-slot metadata differs beyond board variant'
    left['version']['board'] = 'cambiumnetworks_miami-ab'
    metadata_path = work / 'metadata.json'
    metadata_path.write_text(json.dumps(left, separators=(',', ':')) + '\n')
    with tarfile.open(a.output, 'w', format=tarfile.USTAR_FORMAT) as tar:
        for slot in (0, 1):
            info = tarfile.TarInfo(f'sysupgrade-cambiumnetworks_miami-ab-slot{slot}')
            info.type = tarfile.DIRTYPE;info.mode = 0o755
            tar.addfile(info)
        for name, (data, mode, mtime) in sorted(members.items()):
            info = tarfile.TarInfo(name);info.mode = mode;info.mtime = mtime;info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    subprocess.run([str(a.fwtool), '-I', str(metadata_path), str(a.output)], check=True)
    recovered = work / 'recovered.json'
    subprocess.run([str(a.fwtool), '-i', str(recovered), str(a.output)], check=True)
    assert json.loads(recovered.read_text()) == left
    with tarfile.open(a.output) as tar:
        for name, (data, _, _) in members.items():assert tar.extractfile(name).read() == data
    receipt = {'firmware_version': a.firmware_version, 'device_id': 'cambium_x7-35x',
               'selection': 'Existing shared upgrader chooses opposite of running DT storage-slot',
               'bytes': a.output.stat().st_size, 'sha256': hashlib.sha256(a.output.read_bytes()).hexdigest(),
               'metadata': left, 'members': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                                            for name, (data, _, _) in members.items()}}
    a.output.with_suffix(a.output.suffix + '.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(a.output)
