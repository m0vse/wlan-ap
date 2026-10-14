#!/usr/bin/env python3
"""Full radio locator + actual shared core/module/native libraries; synthetic I/O."""
from pathlib import Path
import argparse, hashlib, io, os, subprocess, tarfile, tempfile
from prepare_source import prepare_package

p = argparse.ArgumentParser()
p.add_argument('--native-libraries', type=Path, required=True)
p.add_argument('--physical-profile', type=Path, required=True)
p.add_argument('--radio-source', type=Path)
a = p.parse_args()
repo = Path(__file__).resolve().parents[2]
radio = (a.radio_source or repo / 'feeds/tip/cambium-miami-radio/files/miami-board-data').read_text()
radio = radio[:radio.rfind('\ncase "${1:-}" in')]
module = (repo / 'feeds/tip/cambium-miami-persistent/files/cambium-ab-miami.sh').read_text()
native = {name: (a.native_libraries / name).read_text() for name in ('system.sh', 'functions.sh', 'jshn.sh')}
cases = 0
with tempfile.TemporaryDirectory(prefix='miami-native-vault-') as td:
    base = Path(td)
    package = prepare_package(repo, base / 'prepared')
    core = (package / 'files/cambium-ab.sh').read_text()
    for slot in (0, 1):
        for mode, fault, good in (
            ('legacy', '', True), ('ab', '', True), ('legacy-rw', '', False),
            ('ab', 'missing-library', False), ('ab', 'sku', False),
            ('ab', 'multicast-mac', False), ('ab', 'protected-writable', False),
            ('ab', 'bank-offset', False), ('ab', 'vault-hash', False),
        ):
            cases += 1
            r = base / f'case{cases}'
            def write(name, value):
                path = r / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(value if isinstance(value, bytes) else str(value).encode())
                return path
            def rooted(text):
                for prefix in ('/proc/', '/sys/', '/lib/', '/usr/share/', '/tmp/', '/dev/'):
                    text = text.replace(prefix, '@ROOT@' + prefix)
                return text.replace('@ROOT@', str(r))
            write('lib/functions.sh', rooted(native['functions.sh']))
            write('usr/share/libubox/jshn.sh', rooted(native['jshn.sh']))
            if fault != 'missing-library':write('lib/functions/system.sh', rooted(native['system.sh']))
            write('lib/functions/cambium-ab.sh', rooted(core))
            write('lib/functions/cambium-ab-miami.sh', rooted(module))
            dt = 'proc/device-tree/'
            write(dt + 'compatible', b'cambiumnetworks,x7-35x\0')
            write(dt + 'cambium-platform/board-sku', (43 if fault == 'sku' else 44).to_bytes(4, 'big'))
            write(dt + 'cambium-platform/storage-slot', slot.to_bytes(4, 'big'))
            if mode == 'ab':
                write(dt + 'cambium-platform/storage-policy', b'ab\0')
                write(dt + 'cambium-platform/upgrade-policy', (1).to_bytes(4, 'big'))
            write(dt + 'aliases/label-mac-device', b'ethernet-label')
            write(dt + 'ethernet-label/mac-address', bytes.fromhex('030000000001' if fault == 'multicast-mac' else '020000000001'))
            part = 'rootfs' if slot == 0 else 'rootfs_1'
            write('proc/cmdline', f'ubi.mtd={part} root=/dev/ubiblock0_1')
            (r / 'devices/nand').mkdir(parents=True)
            (r / 'devices/nor').mkdir()
            rows = []
            labels = {}
            for line in a.physical_profile.read_text().splitlines():
                name, domain, offset, size, kind, erase, width, role = line.split('\t')
                if role == 'container':continue
                n = len(rows)
                labels[name] = n
                if kind == 'nor':erase = '65536'
                flags = 1024 if name in ('rootfs', 'rootfs_1') else 3072 if name == '0:APPSBLENV' else 0
                if mode == 'legacy' and name != part and name in ('rootfs', 'rootfs_1'):flags = 0
                if fault == 'protected-writable' and name == '0:ART':flags = 1024
                if fault == 'bank-offset' and name == 'rootfs':offset = '0'
                for key, val in [('name', name), ('type', kind), ('offset', offset), ('size', size), ('erasesize', erase), ('writesize', width), ('flags', flags)]:
                    write(f'sys/class/mtd/mtd{n}/{key}', val)
                (r / f'sys/class/mtd/mtd{n}/device').symlink_to(r / f'devices/{kind}')
                rows.append(f'mtd{n}: {int(size):08x} {int(erase):08x} "{name}"\n')
            write('proc/mtd', 'dev: size erasesize name\n' + ''.join(rows))
            write('sys/class/ubi/ubi0/mtd_num', labels[part])
            write('sys/class/ubi/ubi0/ro_mode', '0')
            for n, name in ((0, 'kernel'), (1, 'rootfs'), (3, 'cambium_device_data')):
                write(f'sys/class/ubi/ubi0_{n}/name', name)
                write(f'sys/class/ubi/ubi0_{n}/reserved_ebs', 72 if n == 3 else 39)
            art = write(f'dev/mtd{labels["0:ART"]}', b'owned synthetic calibration')
            manifest = f'format 1\nboard cambiumnetworks,x7-35x\nsku 0000002c\nart_sha256 {hashlib.sha256(art.read_bytes()).hexdigest()}\n'
            files = ['lib/firmware/IPQ5332/WIFI_FW/' + name for name in ('q6_fw0.mdt', 'q6_fw1.mdt', 'iu_fw.mdt', 'bdwlan.b12-acadia', 'regdb.bin-acadia')]
            files += ['lib/firmware/qcn9224/WIFI_FW/bdwlan.b1019-acadia']
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode='w') as tar:
                for name in files:
                    data = b'synthetic radio data'
                    digest = hashlib.sha256(data).hexdigest()
                    manifest += f'file {name} {len(data)} {digest}\n'
                    if fault == 'vault-hash' and name == files[0]:data = b'wrong radio contents'
                    info = tarfile.TarInfo('files/' + name);info.size = len(data);tar.addfile(info, io.BytesIO(data))
                data = manifest.encode();info = tarfile.TarInfo('MANIFEST');info.size = len(data);tar.addfile(info, io.BytesIO(data))
            write('dev/ubi0_3', archive.getvalue())
            driver = write('driver.sh', rooted(radio) + '\nmkdir -p "$WORK"\npersistent_vault_locate\n')
            assert not (r / 'tmp/sysinfo').exists()
            result = subprocess.run(['sh', str(driver)], env=os.environ, capture_output=True, text=True)
            assert (result.returncode == 0) == good, (slot, mode, fault, result.stderr[-2500:])
print(f'PASS: {cases} full locator/core/module/native-library cases with sysinfo absent; device files synthetic, no shared callback stubs')
