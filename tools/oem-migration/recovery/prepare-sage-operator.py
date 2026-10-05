#!/usr/bin/env python3
"""Generate an unsealed exact-model OEM operator tuple from reviewed vendor root.

No firmware, secrets, model qualification override, checksum seal or AP change.
Candidate digests are explicit inputs; generation does not claim qualification.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
REVIEWED_ROOT_TAR='58b26e51f393be45db5437db454a510c81379a277b1cff373e414f6678df89cf'
TOOLS=('sh id awk cat od tr sed wc head cut readlink ls sha256sum dd df mkdir cp sync '
       'dirname mktemp chmod rm rmdir mv mount umount sort fw_printenv fw_setenv '
       '?hexdump ubiupdatevol ubirmvol ubimkvol').split()

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def validate_pins(pins):
    if any(not isinstance(p,str) or not re.fullmatch('[0-9a-f]{64}',p) for p in pins):
        raise ValueError('all three independently pinned candidate digests are required')

def verify_runtime_members(root,archive,ledger):
    # The authenticated vendor TAR pin fixes all source bytes. Check every
    # selected executable/library/link against it, not just /etc/version.
    with tarfile.open(archive,'r:') as tar:
        members={m.name.removeprefix('./').rstrip('/'):m for m in tar.getmembers()}
        for row in ledger.read_text().splitlines():
            kind,value,name=row.split();rel=name.lstrip('/');member=members.get(rel)
            if kind=='A':
                if member is not None:raise ValueError('runtime absence contradicts vendor TAR: '+name)
                continue
            if member is None:raise ValueError('runtime component absent from vendor TAR: '+name)
            if kind=='L':
                if not member.issym() or member.linkname!=value:raise ValueError('runtime link mismatch: '+name)
            else:
                if not(member.isfile() or member.islnk()):raise ValueError('nonregular runtime member: '+name)
                stream=tar.extractfile(member)
                if stream is None:raise ValueError('unreadable runtime member')
                h=hashlib.sha256()
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
                if h.hexdigest()!=value:raise ValueError('runtime bytes differ from vendor TAR: '+name)
                if (root/rel).stat().st_mode & 0o7777 != member.mode:raise ValueError('runtime mode mismatch: '+name)

def generate(root,archive,out,model,pins):
    validate_pins(pins)
    if model not in ('E410','E410B'):raise ValueError('exact model is not supported by this source recipe')
    if archive.is_symlink() or not archive.is_file():raise ValueError('source TAR must be a regular file')
    root=root.resolve(strict=True);archive=archive.resolve(strict=True);out=out.resolve()
    if out==root or out.is_relative_to(root):raise ValueError('output must not modify verified OEM root')
    # Verify and parse the same private immutable snapshot, not a mutable path.
    with tempfile.TemporaryDirectory(prefix='sage-operator-source-') as tmp:
        frozen=Path(tmp)/'rootfs.tar'
        shutil.copyfile(archive,frozen)
        if digest(frozen)!=REVIEWED_ROOT_TAR:
            raise ValueError('source TAR is not the independently reviewed Sage 4.2.3.3-r10 set')
        return _generate_frozen(root,frozen,out,model,pins)

def _generate_frozen(root,archive,out,model,pins):
    out.mkdir(parents=True,exist_ok=False)
    scripts=HERE/'scripts'
    for name in ('cambium-oem-sage-install.sh','cambium-oem-sage-prepare.sh','cambium-oem-sage-storage-check.sh','cambium-oem-sage-context.sh','cambium-oem-models.tsv'):
        shutil.copy2(scripts/name,out/name)
    launcher=out/'cambium-oem-sage-install.sh'
    text=launcher.read_text()
    test_if='if [ "${COS_OPERATOR_SOURCE_ONLY:-0}" != 1 ]; then\n'
    test_return='[ "${COS_OPERATOR_SOURCE_ONLY:-0}" != 1 ] || return 0\n'
    if text.count(test_if)!=1 or text.count(test_return)!=1:raise ValueError('unexpected test seam shape')
    text=text.replace(test_if,'',1).replace('\nfi\n. "$cos_here/lib','\n. "$cos_here/lib',1).replace(test_return,'',1)
    launcher.write_text(text)
    (out/'lib').mkdir()
    for name in ('cambium-sage-pair-write.sh','cambium-installer-settings.sh','cambium-oem-sage-transaction.sh','cambium-oem-sage-source.sh','cambium-oem-sage-boot.sh'):
        shutil.copy2(scripts/'lib'/name,out/'lib'/name)
    common=REPO/'tests/installer/common-minimum-v1'
    shutil.copy2(common/'runtime-implementation-contract.sh',out/'runtime-implementation-contract.sh')
    sets=out/'source-sets';sets.mkdir()
    seeds=sets/'runtime.seeds';seeds.write_text('\n'.join(TOOLS)+'\n')
    ledger=sets/'runtime-implementation.set'
    subprocess.run(['python3',str(common/'make-runtime-implementation-set.py'),str(root),str(ledger),str(seeds),'40'],check=True,stdout=subprocess.DEVNULL)
    # Release evidence is part of the same immutable source tuple.
    version=root/'etc/version'
    if version.is_symlink() or not version.is_file():raise ValueError('missing regular vendor release evidence')
    with ledger.open('a') as stream:stream.write('F '+digest(version)+' /etc/version\n')
    verify_runtime_members(root,archive,ledger)
    version_fields=dict(line.split('=',1) for line in version.read_text().splitlines() if '=' in line)
    if version_fields.get('PRODUCT')!='sage' or version_fields.get('VERSION')!='4.2.3.3-r10':raise ValueError('incorrect OEM source release')
    product='PL-E410XXX'+('A' if model=='E410' else 'B')+'-EU'
    (out/'operator-model').write_text(model+'\n'+product+'\n')
    (out/'operator-artifact-pins').write_text('\n'.join(pins)+'\n')
    # Bind implementation, source root provenance, exact model and runtime.
    source_rows=[]
    for p in sorted(out.rglob('*')):
        if p.is_file() and p.name!='operator-artifact-pins':source_rows.append(digest(p)+' '+str(p.relative_to(out))+'\n')
    contract=hashlib.sha256((REVIEWED_ROOT_TAR+'\n'+''.join(source_rows)).encode()).hexdigest()
    (out/'source-contract').write_text('4.2.3.3-r10\n'+contract+'\n')
    (out/'REVIEW-NOT-INSTALLABLE.txt').write_text('No image or SHA256SUMS seal. Production model statuses remain unchanged. Qualify exact source/model/hardware, candidate FIT/root/package closure and native acceptance before publication. Supply an independently published SHA256SUMS digest before sourcing any bundle helper. No trial exemption or automatic deployment.\n')
    for script in out.rglob('*.sh'):subprocess.run(['sh','-n',str(script)],check=True)
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('oem_root',type=Path);p.add_argument('reviewed_root_tar',type=Path);p.add_argument('new_output',type=Path)
    p.add_argument('--model',required=True,choices=['E410','E410B'])
    p.add_argument('--image-sha256',required=True);p.add_argument('--kernel-sha256',required=True);p.add_argument('--root-sha256',required=True)
    a=p.parse_args()
    print(generate(a.oem_root,a.reviewed_root_tar,a.new_output,a.model,[a.image_sha256,a.kernel_sha256,a.root_sha256]))
