#!/usr/bin/env python3
"""Run actual shared inactive-slot extraction on the combined payload both ways."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, tarfile, tempfile
from prepare_source import prepare_package

p = argparse.ArgumentParser()
p.add_argument('--image', type=Path, required=True)
p.add_argument('--receipt', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[2]
receipt = json.loads(a.receipt.read_text())
assert hashlib.sha256(a.image.read_bytes()).hexdigest() == receipt['sha256']
with tempfile.TemporaryDirectory(prefix='miami-standard-test-') as td:
    r = Path(td)
    package = prepare_package(repo, r / 'prepared')
    dt = r / 'dt/cambium-platform';dt.mkdir(parents=True)
    (dt / 'storage-policy').write_bytes(b'ab\0')
    (dt / 'upgrade-policy').write_bytes((1).to_bytes(4, 'big'))
    driver = '''
. "$UPGRADE"
ab_board cambiumnetworks,x7-35x || exit 1
AB_ACTIVE=$SLOT AB_TARGET=$((1-SLOT))
ab_image_extract "$IMAGE" || exit 1
printf '%s\n' "$AB_IMAGE_DIR"
'''
    for source in (0, 1):
        (dt / 'storage-slot').write_bytes(source.to_bytes(4, 'big'))
        env = {**os.environ, 'CAMBIUM_AB_LIB': str(package / 'files/cambium-ab.sh'),
               'CAMBIUM_AB_MODULES': str(repo / 'feeds/tip/cambium-miami-persistent/files'),
               'UPGRADE': str(package / 'files/cambium-ab-upgrade.sh'), 'AB_DT': str(dt.parent),
               'AB_WORK': str(r / f'work{source}'), 'SLOT': str(source), 'IMAGE': str(a.image)}
        result = subprocess.run(['sh', '-c', driver], env=env, capture_output=True, text=True)
        target = 1-source
        directory = f'sysupgrade-cambiumnetworks_miami-ab-slot{target}'
        assert result.returncode == 0 and result.stdout.strip() == directory, (result.stdout, result.stderr)
        for leaf in ('kernel', 'root'):
            data = (Path(env['AB_WORK']) / directory / leaf).read_bytes()
            assert hashlib.sha256(data).hexdigest() == receipt['members'][directory + '/' + leaf]['sha256']
        assert not (Path(env['AB_WORK']) / f'sysupgrade-cambiumnetworks_miami-ab-slot{source}').exists()
        for fault in ('missing-target', 'wrong-fit'):
            bad = r / f'bad-{source}-{fault}.tar'
            with tarfile.open(a.image) as incoming, tarfile.open(bad, 'w') as out:
                for member in incoming.getmembers():
                    if fault == 'missing-target' and member.name.startswith(directory):continue
                    if fault == 'wrong-fit' and member.name == directory + '/kernel':
                        data = incoming.extractfile(f'sysupgrade-cambiumnetworks_miami-ab-slot{source}/kernel')
                        old = incoming.getmember(f'sysupgrade-cambiumnetworks_miami-ab-slot{source}/kernel')
                        member.size = old.size
                        out.addfile(member, data)
                    else:out.addfile(member, incoming.extractfile(member) if member.isfile() else None)
            result = subprocess.run(['sh', '-c', driver], env={**env, 'IMAGE': str(bad)}, capture_output=True, text=True)
            assert result.returncode != 0, (source, fault)
print('PASS: actual inactive-slot extraction both directions, exact selected payloads, wrong FIT and missing target refused; physical preflight is separate')
