#!/usr/bin/env python3
"""Authenticate a reviewed Sage vendor container and prepare shared artifacts.

Workstation-only. Never executes vendor code, extracts a filesystem onto the
host, writes an AP, qualifies a model, or produces a boot selector.
"""
import argparse
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tempfile

LIMIT = 128 * 1024 * 1024
FIELDS = {'MANIFEST_VERSION', 'IMAGE_FORMAT', 'SUPPORTED_PRODUCTS',
          'IMAGE_VERSION', 'IMAGE_UBOOT_VERSION'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(name):
    if name in ('.', './'):
        return '.'
    if name.startswith('./'):
        name = name[2:]
    if not name or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/')):
        raise ValueError('unsafe or noncanonical archive path')
    return name


def inspect_tar(data):
    records, members = [], {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as archive:
        for member in archive:
            name = normalized(member.name.rstrip('/') if member.isdir() else member.name)
            if name in members:
                raise ValueError('duplicate archive path')
            if not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
                raise ValueError('unexpected special archive member')
            reviewed_owners = {'mnt/flash/home/admin': (1001, 1002),
                               'run/dbus': (1000, 1000), 'var/www': (33, 33)}
            expected_owner = reviewed_owners.get(name, (0, 0))
            if (member.uid, member.gid) != expected_owner or (expected_owner != (0, 0) and not member.isdir()):
                raise ValueError('unreviewed archive ownership')
            if member.size < 0 or member.size > LIMIT:
                raise ValueError('oversized archive member')
            members[name] = member
        for name, member in members.items():
            for parent in PurePosixPath(name).parents:
                ancestor = members.get(str(parent))
                if ancestor is not None and not ancestor.isdir():
                    raise ValueError('archive member descends through a link or file')
            entry = {'path': name, 'mode': member.mode, 'size': member.size,
                     'uid': member.uid, 'gid': member.gid}
            if member.isfile():
                entry.update(type='file', sha256=sha(archive.extractfile(member).read()))
            elif member.isdir():
                entry.update(type='directory')
            elif member.issym():
                # Absolute links are normal in vendor roots. No member may be
                # written through them (checked against the complete tree).
                if '\x00' in member.linkname or not member.linkname:
                    raise ValueError('invalid symlink target')
                entry.update(type='symlink', target=member.linkname)
            else:
                target = normalized(member.linkname)
                if target not in members or not members[target].isfile():
                    raise ValueError('hardlink does not name a regular archive member')
                entry.update(type='hardlink', target=target)
            records.append(entry)
        kernel = members.get('kernel.itb')
        version = members.get('etc/version')
        if kernel is None or not kernel.isfile() or version is None or not version.isfile():
            raise ValueError('missing regular kernel or release evidence')
        kernel_bytes = archive.extractfile(kernel).read()
        if kernel_bytes[:4] != bytes.fromhex('d00dfeed') or len(kernel_bytes) > 34 * 126976:
            raise ValueError('invalid or oversized Sage FIT payload')
        release = archive.extractfile(version).read().decode('ascii')
        for field, expected in [('PRODUCT', 'sage'), ('VERSION', '4.2.3.3-r10')]:
            values = re.findall(r'^' + field + r'=(.*)$', release, re.M)
            if values != [expected]:
                raise ValueError('unreviewed or ambiguous root release')
    return records, kernel_bytes


def unpack(content):
    marker = b'------END MANIFEST\n------BEGIN IMAGE\n'
    if not content.startswith(b'------BEGIN MANIFEST\n') or content.count(marker) != 1:
        raise ValueError('unreviewed vendor container framing')
    header, compressed = content.split(marker, 1)
    if len(header) > 65536:
        raise ValueError('oversized vendor manifest')
    fields = {}
    for line in header.decode('ascii').splitlines()[1:]:
        if not line or line.startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if not separator or key not in FIELDS or key in fields:
            raise ValueError('unreviewed or ambiguous vendor manifest field')
        fields[key] = value
    if set(fields) != FIELDS or fields['MANIFEST_VERSION'] != '1' or fields['IMAGE_FORMAT'] != '2' or fields['IMAGE_VERSION'] != '4.2.3.3-r10' or fields['IMAGE_UBOOT_VERSION'] != '1.0.13a':
        raise ValueError('unreviewed vendor release/format')
    if fields['SUPPORTED_PRODUCTS'] != 'E410:E600:E430:E700:E510':
        raise ValueError('unreviewed Sage product set')
    decoder = lzma.LZMADecompressor(memlimit=LIMIT)
    data = decoder.decompress(compressed, max_length=LIMIT + 1)
    if len(data) > LIMIT or not decoder.eof or decoder.unused_data:
        raise ValueError('oversized, truncated or trailing compressed image')
    return fields, data


def prepare(args):
    # Exact A/B qualification is still separate from this shared vendor family.
    if args.model not in ('E410', 'E410B'):
        raise ValueError('model has no reviewed recovery preparation route')
    for value in (args.container_sha256, args.signer_sha256):
        if not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('invalid trusted digest')
    container = args.container.read_bytes()
    if len(container) > 64 * 1024 * 1024 or sha(container) != args.container_sha256:
        raise ValueError('vendor container differs from trusted digest')
    cert = subprocess.run(['openssl', 'x509', '-in', str(args.signer), '-outform', 'DER'], check=True, capture_output=True).stdout
    if sha(cert) != args.signer_sha256:
        raise ValueError('independent signer differs from trusted fingerprint')
    # Output is private and isolated. The signer is supplied independently,
    # never extracted from this candidate as its own trust proof.
    with tempfile.TemporaryDirectory(prefix='sage-authenticated-') as temporary:
        verified = Path(temporary) / 'content'
        subprocess.run(['openssl', 'smime', '-binary', '-verify', '-nointern',
                        '-CAfile', str(args.signer), '-certfile', str(args.signer),
                        '-in', str(args.container), '-inform', 'DER', '-out', str(verified)],
                       check=True, capture_output=True)
        fields, root_tar = unpack(verified.read_bytes())
    records, kernel = inspect_tar(root_tar)
    manifest = {'schema': 'openwifi.sage-shared-oem-recovery.v1',
                'exact_model': args.model, 'vendor_manifest': fields,
                'vendor_container_sha256': sha(container), 'signer_der_sha256': sha(cert),
                'artifacts': {'kernel.itb': sha(kernel), 'rootfs.tar': sha(root_tar)},
                'members': records, 'production_qualified': False,
                'bootloader_write': False,
                'note': 'Clean signed vendor tree; never run its updater. Requires qualified inactive UBIFS writer, readback, reset/defaults and guarded boot.'}
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name, data in [('kernel.itb', kernel), ('rootfs.tar', root_tar),
                       ('manifest.json', (json.dumps(manifest, indent=2) + '\n').encode())]:
        with (args.output / name).open('xb') as stream:
            os.chmod(stream.name, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    fd = os.open(args.output, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {'model': args.model, 'members': len(records), 'production_qualified': False,
            'kernel_sha256': sha(kernel), 'rootfs_tar_sha256': sha(root_tar)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', required=True)
    parser.add_argument('--container', type=Path, required=True)
    parser.add_argument('--container-sha256', required=True)
    parser.add_argument('--signer', type=Path, required=True)
    parser.add_argument('--signer-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    try:
        print(json.dumps(prepare(parser.parse_args()), sort_keys=True))
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError, lzma.LZMAError) as error:
        raise SystemExit('Recovery preparation refused: ' + str(error))
