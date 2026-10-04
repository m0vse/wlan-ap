#!/usr/bin/env python3
"""Index a private recovery archive without exposing captured file contents.

Original source-host files are not modified. Identical archive copies can be
deduplicated by hardlinking to a content-addressed object in this same archive.
This establishes integrity/provenance, never device compatibility or admission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def publish(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.index-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def index(root, deduplicate=False):
    root = root.resolve(strict=True)
    mode = root.stat()
    if mode.st_uid != 0 or stat.S_IMODE(mode.st_mode) != 0o700:
        raise ValueError('archive must be root-owned mode 0700')
    sources = root / 'sources'
    objects = root / 'objects'
    objects.mkdir(mode=0o700, exist_ok=True)
    files, checksum_results = [], []
    unique = {}
    for path in sorted(sources.rglob('*')):
        if path.is_symlink():
            raise ValueError('source symlink is not an archive object')
        if not path.is_file():
            continue
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('source is not a regular archive file')
        sha = digest(path)
        size = path.stat().st_size
        rel = str(path.relative_to(root))
        role = 'historical-reference-unclassified'
        if path.name.startswith('._') or path.name == '.DS_Store':
            role = 'filesystem-metadata'
        elif 'ART' in path.name or 'art.' in path.name:
            role = 'device-unique-calibration'
        elif 'env' in path.name.lower() or 'manufactur' in path.name.lower():
            role = 'device-unique-identity-or-boot-metadata'
        elif path.suffix == '.cimg':
            role = 'shared-vendor-container-provenance-pending'
        elif 'rootfs' in path.name or 'mtd' in path.name:
            role = 'historical-raw-image-may-contain-unique-data'
        elif path.name == 'image.crt':
            role = 'public-signer-reference-provenance-pending'
        files.append({'path': rel, 'size': size, 'sha256': sha, 'role': role,
                      'device_binding': 'unverified', 'restore_authorized': False})
        unique.setdefault(sha, {'size': size, 'sources': []})['sources'].append(rel)
        if deduplicate:
            obj = objects / sha
            if obj.exists():
                if obj.is_symlink() or not obj.is_file() or digest(obj) != sha:
                    raise ValueError('content object collision or corruption')
            else:
                os.link(path, obj)
            if path.stat().st_ino != obj.stat().st_ino:
                replacement = path.with_name('.dedup-' + path.name)
                if replacement.exists():
                    raise ValueError('unfinished dedup replacement exists')
                os.link(obj, replacement)
                os.replace(replacement, path)
            path.chmod(0o600)
    hashes = {entry['path']: entry['sha256'] for entry in files}
    for path in sorted(sources.rglob('*')):
        if path.name.startswith('._'):
            continue
        if not path.is_file() or path.name not in ('SHA256SUMS', 'backup.sha256') and not path.name.endswith(('-SHA256SUMS', '.sha256')):
            continue
        for line in path.read_text(errors='replace').splitlines():
            match = re.fullmatch(r'([0-9a-fA-F]{64}) [ *](.+)', line)
            if not match:
                if not line.strip() or line.lstrip().startswith('#'):
                    continue
                checksum_results.append({'manifest': str(path.relative_to(root)), 'status': 'unparsed-record'})
                continue
            expected, name = match.groups()
            named = Path(name)
            resolution = 'original-relative-path'
            if named.is_absolute() and named.parent == Path('/tmp'):
                # AP capture manifests retain their temporary source path.
                # Only the exact basename in this manifest's directory is
                # eligible; never search other devices by matching digest.
                named = Path(named.name)
                name = named.name
                resolution = 'same-directory-original-ap-tmp-path'
            if named.is_absolute() or '..' in named.parts:
                checksum_results.append({'manifest': str(path.relative_to(root)), 'status': 'unsafe-or-original-absolute-path'})
                continue
            target = str((path.parent / named).relative_to(root))
            actual = hashes.get(target)
            # The relay prefixes uploaded files but retains bare names inside
            # their manifest. Resolve only the matching manifest's own prefix;
            # never bind a different device merely because its digest matches.
            if actual is None and path.name.endswith('-SHA256SUMS'):
                prefix = path.name[:-len('SHA256SUMS')]
                prefixed = str((path.parent / (prefix + name)).relative_to(root))
                if prefixed in hashes:
                    target, actual = prefixed, hashes[prefixed]
                    resolution = 'same-directory-relay-prefix'
            checksum_results.append({'manifest': str(path.relative_to(root)), 'file': target,
                                     'resolution': resolution,
                                     'status': 'missing' if actual is None else 'pass' if actual == expected.lower() else 'mismatch'})
    report = {'schema': 'cambium.private-recovery-index.v1', 'files': files,
              'content_objects': unique, 'original_checksum_results': checksum_results,
              'note': 'Integrity is not device matching, vendor authenticity or permission to restore.'}
    publish(root / 'index.json', json.dumps(report, indent=2) + '\n')
    publish(root / 'SHA256SUMS', ''.join(f"{entry['sha256']}  {entry['path']}\n" for entry in files))
    return {'files': len(files), 'unique_objects': len(unique),
            'logical_bytes': sum(entry['size'] for entry in files),
            'unique_bytes': sum(entry['size'] for entry in unique.values()),
            'original_checksums': {status: sum(x['status'] == status for x in checksum_results)
                                   for status in sorted({x['status'] for x in checksum_results})}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--deduplicate', action='store_true')
    args = parser.parse_args()
    print(json.dumps(index(args.root, args.deduplicate), sort_keys=True))
