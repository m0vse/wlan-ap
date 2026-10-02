#!/usr/bin/env python3
"""Seal only the separately qualified immutable .1 preserving artifact."""
import hashlib,json,pathlib,sys
bundle=pathlib.Path(sys.argv[1]).resolve()
image=bundle/(bundle/'IMAGE').read_text().strip()
assert image.name=='cambium_xv2-2t1-jaguar-2026.10.02.3-sysupgrade.bin'
assert image.stat().st_size==21770647
assert hashlib.sha256(image.read_bytes()).hexdigest()=='9237bac70039fbdaffbb013018dd9c6c9328830e0a4f8f4babe375fd4044821d'
for name,count in [('jaguar-preserve-r3-validator-tests.json',24),('jaguar-preserve-r3-xv2-validator-tests.json',24),('jaguar-preserve-r3-combined-tests.json',18),('jaguar-preserve-r3-wrapper-tests.json',9),('jaguar-preserve-r3-store-tests.json',13),('jaguar-preserve-r3-recovery-tests.json',21),('jaguar-preserve-r1-transaction-tests.json',32)]:
 result=json.loads((bundle/name).read_text());assert result['passed'] and result['count']==count,name
report=json.loads((bundle/'jaguar-preserve-r1-transaction-tests.json').read_text())
assert hashlib.sha256((bundle/'bridge-transaction.sh').read_bytes()).hexdigest()==report['helper_sha256']
for path in (bundle/'image-evidence').glob('*.json'):
 assert json.loads(path.read_text())['passed'],str(path)
rows=[]
for path in sorted(bundle.rglob('*')):
 assert not path.is_symlink(),str(path)
 if path.is_file() and path.name!='SHA256SUMS':
  rows.append(hashlib.sha256(path.read_bytes()).hexdigest()+'  '+str(path.relative_to(bundle))+'\n')
(bundle/'SHA256SUMS').write_text(''.join(rows))
print(json.dumps({'files':len(rows),'manifest_sha256':hashlib.sha256((bundle/'SHA256SUMS').read_bytes()).hexdigest(),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}))
