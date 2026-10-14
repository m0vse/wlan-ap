#!/usr/bin/env python3
"""Real crypto and actual post-pivot snapshot identity, synthetic device facts."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
repo=Path(__file__).resolve().parents[2]
fixture=repo/'contrib/cambium/miami/test-readiness.py'
text=fixture.read_text().split("    for slot in ('0','1'):",1)[0]
extra=r'''
    from prepare_source import prepare_package
    import tarfile
    package=prepare_package(module.parents[4],root/'prepared')
    archive=root/'snapshot.tar';descriptor=root/'snapshot.descriptor';boot=root/'boot-id';boot.write_text('12345678-1234-1234-1234-123456789abc\n')
    mounts=root/'mounts';mounts.write_text('tmpfs / tmpfs rw 0 0\n')
    def seal(slot=0):
        with tarfile.open(archive,'w') as tar:
            for entry in store.iterdir():tar.add(entry,arcname='./'+entry.name)
        archive.chmod(0o600)
        descriptor.write_text(f'12345678-1234-1234-1234-123456789abc:miami:X7-35X:0000002c:{slot}:{1-slot}:{2+slot}:{3-slot}\n'+hashlib.sha256(archive.read_bytes()).hexdigest()+'\n');descriptor.chmod(0o600)
    driver=r"""
. "$CERT_LIB"
. "$MODULE"
AB_FAMILY=miami AB_MODEL=X7-35X AB_SKU=0000002c AB_ACTIVE=$SLOT AB_TARGET=$((1-SLOT)) AB_ACTIVE_MTD=$((2+SLOT)) AB_TARGET_MTD=$((3-SLOT)) AB_LAYOUT=banks AB_LEB=126976
ab_certificate_lebs(){ echo 64; };ab_fail(){ return 1; }
get_mac_label_dt(){ echo 02:00:00:00:00:01; }
ab_miami_snapshot_identity
"""
    snapshot_env={**env,'MODULE':str(module),'CERT_LIB':str(package/'files/cambium-ab-certificates.sh'),'AB_CERTIFICATE_ARCHIVE':str(archive),'AB_CERTIFICATE_DESCRIPTOR':str(descriptor),'AB_BOOT_ID':str(boot),'AB_PROC_MOUNTS':str(mounts)}
    def check(good,slot=0):
        original={str(p.relative_to(store)):p.read_bytes() for p in store.rglob('*') if p.is_file()}
        saved=archive.read_bytes()
        result=subprocess.run(['sh','-c',driver],env={**snapshot_env,'SLOT':str(slot)},capture_output=True,text=True)
        assert (result.returncode==0)==good,(result.stdout,result.stderr)
        assert original=={str(p.relative_to(store)):p.read_bytes() for p in store.rglob('*') if p.is_file()} and archive.read_bytes()==saved
    n=0
    for slot in (0,1):
        seal(slot);check(True,slot);n+=1
        original=boot.read_bytes();boot.write_text('other-boot\n');check(False,slot);n+=1;boot.write_bytes(original)
        descriptor.chmod(0o644);check(False,slot);n+=1;descriptor.chmod(0o600)
        saved=archive.read_bytes();archive.write_bytes(saved[:-1]);check(False,slot);n+=1;archive.write_bytes(saved)
    transaction['accepted']=False;(journal/'transaction.json').write_text(json.dumps(transaction));seal();check(False);n+=1
    transaction['accepted']=True;transaction['committed']=False;(journal/'transaction.json').write_text(json.dumps(transaction));seal();check(False);n+=1
    transaction['committed']=True;(journal/'transaction.json').write_text(json.dumps(transaction))
    saved=(store/'key.pem').read_bytes();crypto('genpkey','-algorithm','EC','-pkeyopt','ec_paramgen_curve:prime256v1','-out',store/'key.pem');seal();check(False);n+=1;(store/'key.pem').write_bytes(saved)
    seal();mounts.write_text('overlayfs:/overlay / overlay rw 0 0\n');check(False);n+=1
    print(f'PASS: {n} actual post-pivot snapshot/current-boot/accepted-journal/real-crypto cases; same key/CA/completion retained, no rebinding')
'''
exec(compile(text+extra,str(fixture),'exec'),{'__file__':str(fixture)})
