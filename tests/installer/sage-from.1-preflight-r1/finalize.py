import hashlib,json,pathlib
bundle=pathlib.Path(__file__).resolve().parent
report=json.loads((bundle/'shared-store-tests.json').read_text())
assert report['passed'] and report['count']==22
rows=[]
for p in sorted(bundle.rglob('*')):
    assert not p.is_symlink()
    if p.is_file() and p.name!='SHA256SUMS':
        rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n')
(bundle/'SHA256SUMS').write_text(''.join(rows))
print(hashlib.sha256((bundle/'SHA256SUMS').read_bytes()).hexdigest())
