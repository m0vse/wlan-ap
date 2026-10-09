#!/usr/bin/env python3
"""Package existing reviewed release assets; do not invent model approvals.

No build, deployment or device operation. Output is private because deployment
hostnames belong to the operator. Inputs contain no enrollment credentials.
"""
import argparse, hashlib, re, shutil, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def prepare(provider, expected, output, controller, download, backup):
    if not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('independent provider ledger digest required')
    if provider.is_symlink():raise ValueError('symlink provider')
    provider=provider.resolve(strict=True);output=output.resolve()
    if output==provider or output.is_relative_to(provider):raise ValueError('output overlaps provider')
    ledger=provider/'SHA256SUMS'
    if ledger.is_symlink() or not ledger.is_file() or sha(ledger)!=expected:raise ValueError('provider ledger mismatch')
    entries={}
    for row in ledger.read_text().splitlines():
        match=re.fullmatch('([0-9a-f]{64})  ([A-Za-z0-9_./-]+)',row)
        if not match:raise ValueError('bad provider checksum row')
        digest,name=match.groups()
        if name.startswith('/') or any(p in ('.','..') for p in name.split('/')) or name in entries:raise ValueError('unsafe provider member')
        source=provider/name
        if source.is_symlink() or not source.is_file() or source.resolve()!=source or sha(source)!=digest:raise ValueError('unverified provider member: '+name)
        entries[name]=digest
    if 'models.tsv' not in entries:raise ValueError('missing existing exact-model/source mapping')
    if not re.fullmatch('[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?',controller):raise ValueError('invalid controller hostname')
    for url in (download,backup):
        if not re.fullmatch('https?://[^\s@?#]+',url):raise ValueError('invalid operator URL')
    recognized={tuple(line.split('\t')[:3]) for line in (HERE/'models.tsv').read_text().splitlines() if line and not line.startswith('#')}
    mappings={}
    for filename in ('models.tsv','restore-models.tsv','restore-confirm-models.tsv','upgrade-models.tsv'):
        if filename not in entries:continue
        seen=set(); rows=[]
        for line in (provider/filename).read_text().splitlines():
            fields=line.split('\t')
            if len(fields)!=5 or tuple(fields[:3]) not in recognized or tuple(fields[:3]) in seen:raise ValueError('invalid or duplicate exact-model mapping')
            seen.add(tuple(fields[:3]));sku,family,model,adapter,version=fields
            if adapter not in ('-','sage','jaguar','cheetah','thor','miami') or not re.fullmatch('[A-Za-z0-9._~-]{1,64}',version):raise ValueError('invalid adapter or source version')
            prefix={'models.tsv':'','restore-models.tsv':'restore-','restore-confirm-models.tsv':'restore-','upgrade-models.tsv':'upgrade-'}[filename]
            if adapter!='-' and not (HERE/'adapters'/f'{prefix}{adapter}.sh').is_file():raise ValueError('adapter not implemented')
            rows.append(fields)
        mappings[filename]=rows
    reserved={'installer.sh','oem-restore-test.sh','check-sysupgrade-ready.sh','recognition.tsv','deployment.tsv'}
    if any(n in reserved or n.startswith(('adapters/','lib/')) for n in entries):raise ValueError('provider cannot replace framework code')
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    try:
        for name in entries:
            target=output/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            shutil.copyfile(provider/name,target);target.chmod(0o600)
            if sha(target)!=entries[name]:raise ValueError('provider changed while copying')
        for directory in ('lib','adapters'):
            (output/directory).mkdir(mode=0o700,exist_ok=True)
            for source in (HERE/directory).glob('*.sh'):
                shutil.copyfile(source,output/directory/source.name)
        # Framework-owned, reviewed existing Sage writer/stager/boot libraries;
        # a provider may supply payload/profile data, never replace this code.
        recovery=HERE.parent/'recovery/scripts/lib'
        for source in recovery.glob('*.sh'):
            shutil.copyfile(source,output/'lib'/source.name)
        runtime=HERE.parents[2]/'tests/installer/common-minimum-v1/runtime-implementation-contract.sh'
        shutil.copyfile(runtime,output/'lib/runtime-implementation-contract.sh')
        shutil.copyfile(HERE/'models.tsv',output/'recognition.tsv')
        (output/'deployment.tsv').write_text(f'controller\t{controller}\ndownload_url\t{download}\nbackup_url\t{backup}\n')
        rows=[]
        for path in sorted(output.rglob('*')):
            if path.is_file():path.chmod(0o600);rows.append(f'{sha(path)}  {path.relative_to(output)}\n')
        (output/'SHA256SUMS').write_text(''.join(rows));(output/'SHA256SUMS').chmod(0o600)
        pin=sha(output/'SHA256SUMS')
        for filename in ('installer.sh','oem-restore-test.sh','check-sysupgrade-ready.sh'):
            if not (HERE/filename).is_file():continue
            text=(HERE/filename).read_text().replace('RELEASE_PIN_NOT_CONFIGURED',pin)
            (output/filename).write_text(text);(output/filename).chmod(0o700)
        for path in output.rglob('*.sh'):subprocess.run(['sh','-n',str(path)],check=True)
        for canonical,legacy in [('cambium-oem-install','installer.sh'),('cambium-oem-restore-test','oem-restore-test.sh'),('cambium-ab-ready','check-sysupgrade-ready.sh')]:
            if (output/legacy).is_file():
                shutil.copyfile(output/legacy,output/canonical);(output/canonical).chmod(0o700)
        (output/'LAUNCHER-HASHES.txt').write_text(''.join(f'{sha(output/n)}  {n}\n' for n in ('cambium-oem-install','cambium-oem-restore-test','cambium-ab-ready') if (output/n).is_file()))
        (output/'LAUNCHER-HASHES.txt').chmod(0o600)
        return pin
    except Exception:
        # Leave the incomplete private output for diagnosis; never publish it.
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('provider',type=Path);p.add_argument('provider_sha256');p.add_argument('new_output',type=Path)
    p.add_argument('--controller',required=True);p.add_argument('--download-url',required=True);p.add_argument('--backup-url',required=True)
    a=p.parse_args();print(prepare(a.provider,a.provider_sha256,a.new_output,a.controller,a.download_url,a.backup_url))
