#!/usr/bin/env python3
"""Seal only the separately qualified immutable .1 preserving artifact."""
import hashlib,json,pathlib,sys
bundle=pathlib.Path(sys.argv[1]).resolve()
image=bundle/(bundle/'IMAGE').read_text().strip()
assert image.name=='cambium_xv2-2t1-jaguar-2026.10.02.3-sysupgrade.bin'
assert image.stat().st_size==21770647
assert hashlib.sha256(image.read_bytes()).hexdigest()=='9237bac70039fbdaffbb013018dd9c6c9328830e0a4f8f4babe375fd4044821d'
assert hashlib.sha256((bundle/'prepare-upgrader.sh').read_bytes()).hexdigest()=='f38a01bd5398582688ba0d605f684dce5fb40ceba4ebde3178d69a99ddedc8d7'
for name,count in [('jaguar-preserve-r3-validator-tests.json',24),('jaguar-preserve-r3-xv2-validator-tests.json',24),('jaguar-preserve-r3-combined-tests.json',18),('jaguar-preserve-from1-r2-wrapper-tests.json',9),('jaguar-preserve-from1-r2-legacy-store-tests.json',33),('jaguar-preserve-r3-recovery-tests.json',21),('jaguar-preserve-r1-transaction-tests.json',32)]:
 result=json.loads((bundle/name).read_text());assert result['passed'] and result['count']==count,name
source_report=json.loads((bundle/'jaguar-preserve-from1-r2-legacy-store-tests.json').read_text())
assert hashlib.sha256((bundle/'preservation-check.sh').read_bytes()).hexdigest()==source_report['source_check_sha256']
assert hashlib.sha256((bundle/'cambium-ab-certificates.sh').read_bytes()).hexdigest()==source_report['canonical_helper_sha256']
wrapper_report=json.loads((bundle/'jaguar-preserve-from1-r2-wrapper-tests.json').read_text())
assert hashlib.sha256((bundle/'jaguar-sysinstall.sh').read_bytes()).hexdigest()==wrapper_report['wrapper_sha256']
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
