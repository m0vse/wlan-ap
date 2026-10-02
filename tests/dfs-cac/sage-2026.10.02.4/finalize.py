import hashlib,json,pathlib
b=pathlib.Path(__file__).resolve().parent
image=b/'cambium-sage-sage-2026.10.02.4-sysupgrade.bin'
assert image.stat().st_size==13865290
assert hashlib.sha256(image.read_bytes()).hexdigest()=='654b1a383a01295d88d4c9a990fd8eb7e344b47ea1c9e2449db6e333cf41c008'
for name,count in [('sage4-classifier-tests.json',42),('sage4-cac-subprocess-tests.json',5),('sage4-health-healing-tests.json',23),('sage4-built-image-tests.json',8),('sage4-target-cli-tests.json',2),('sage3-to4-managed-archive-tests.json',4),('sage3-to4-e410-validator-tests.json',12),('sage3-to4-e410b-validator-tests.json',12),('sage4-shared-store-allocator-tests.json',13),('sage4-shared-store-prerequisite-tests.json',22)]:
    r=json.loads((b/name).read_text()); assert r['passed'] and r['count']==count,name
for name in ('sage3-to4-ram-tests.json','sage4-static-ram-closure.json'):
    assert json.loads((b/name).read_text())['passed'],name
rows=[]
for p in sorted(b.iterdir()):
    assert not p.is_symlink()
    if p.is_file() and p.name!='SHA256SUMS':
        rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
(b/'SHA256SUMS').write_text(''.join(rows))
print(json.dumps({'files':len(rows),'manifest_sha256':hashlib.sha256((b/'SHA256SUMS').read_bytes()).hexdigest()}))
