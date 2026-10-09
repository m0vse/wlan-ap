#!/usr/bin/env python3
"""Execute shared physical/backup checks against the retained Thor profile."""
from pathlib import Path
import argparse
import os
import subprocess
import tempfile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('common_lib', nargs='?', type=Path, default=Path(__file__).resolve().parents[1] / 'lib')
    a = ap.parse_args()
    source = Path(__file__).resolve().parents[1] / 'profiles/XV3-8'
    helpers = {}
    for name in ('protection.sh', 'critical-backup.sh'):
        p = a.common_lib / name
        if not p.is_file(): ap.error(f'missing shared helper {p}')
        helpers[name] = p.read_bytes()
    count = 0
    with tempfile.TemporaryDirectory(prefix='thor-profile-') as td:
        top = Path(td).resolve(); lib = top / 'lib'; lib.mkdir()
        for name, content in helpers.items(): (lib / name).write_bytes(content)
        for target in (0, 1):
            root = top / str(target); root.mkdir()
            sys = root / 'sys'; sys.mkdir()
            rows = (source / f'mtd-slot{target}.tsv').read_text().splitlines()
            for domain in ('nor0', 'nand0'): (root / domain).mkdir()
            for index, line in enumerate(rows):
                name, domain, offset, size, kind, erase, write, role = line.split('\t')
                node = sys / f'mtd{index}'; node.mkdir()
                for key, value in dict(name=name, offset=offset, size=size, type=kind, erasesize=erase, writesize=write).items():
                    (node / key).write_text(value)
                (node / 'device').symlink_to(root / domain)
            script = '. "$LIB/protection.sh"; oem_physical_inventory "$PROFILE" "$SYS" "$OUT"'
            env = dict(os.environ, LIB=str(lib), PROFILE=str(source / f'mtd-slot{target}.tsv'), SYS=str(sys),
                       OUT=str(root / 'physical.tsv'), CRITICAL=str(source / 'critical.tsv'))
            result = subprocess.run(['sh', '-c', script], env=env, capture_output=True, text=True, timeout=5)
            assert result.returncode == 0, result.stderr
            output = (root / 'physical.tsv').read_text().splitlines()
            assert len(output) == 26
            names = [line.split('\t')[0] for line in rows]
            for slot, name in ((0, 'rootfs'), (1, 'rootfs_1')):
                index = names.index(name); expected = 'target' if slot == target else 'active-oem'
                assert output[index].split('\t')[3] == expected
            count += 1
            backup_script = '. "$LIB/critical-backup.sh"; oem_backup_plan_check "$CRITICAL"'
            result = subprocess.run(['sh', '-c', backup_script], env=env, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                # Current common cap is 64 KiB. This real 128 KiB profile must
                # remain refused until the common owner closes that mismatch.
                safe = root / 'critical-three.tsv'
                safe.write_text(''.join(line+'\n' for line in (source/'critical.tsv').read_text().splitlines()
                                        if not line.startswith('BOOTCONFIG')))
                result_three = subprocess.run(['sh', '-c', backup_script], env={**env, 'CRITICAL': str(safe)},
                                              capture_output=True, text=True, timeout=5)
                assert result_three.returncode == 0, result_three.stderr
                print(f'PENDING target {target}: shared backup cap refuses actual 128 KiB BOOTCONFIG; no truncation/bypass')
            else:
                print(f'PASS target {target}: full actual critical backup profile accepted')
            # Converted NOR tail geometry cannot pass the OEM config profile.
            node = sys / f'mtd{names.index("config")}'
            (node / 'size').write_text(str(0x950000))
            result = subprocess.run(['sh', '-c', script], env=env, capture_output=True, text=True, timeout=5)
            assert result.returncode != 0
            count += 1
    print(f'PASS: {count} actual shared physical profile checks; 26 partitions, both targets, converted-config mismatch refused')
    print('Scope: synthetic sysfs uses real retained partition metadata; not full live master inventory or physical write/boot qualification')


if __name__ == '__main__': main()
