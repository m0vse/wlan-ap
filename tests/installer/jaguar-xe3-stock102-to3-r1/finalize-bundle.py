"""Seal reviewed installer files and immutable image; no AP operations."""
import hashlib,pathlib,sys
bundle=pathlib.Path(sys.argv[1]).resolve()
image=bundle/(bundle/'IMAGE').read_text().strip()
assert image.name=='cambium_xe3-4-jaguar-2026.10.02.3-sysupgrade.bin'
assert len(image.read_bytes())==21770647
assert hashlib.sha256(image.read_bytes()).hexdigest()=='9237bac70039fbdaffbb013018dd9c6c9328830e0a4f8f4babe375fd4044821d'
rows=[]
for p in sorted(bundle.rglob('*')):
 assert not p.is_symlink(),str(p)
 if p.is_file() and p.name!='SHA256SUMS':rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(bundle))+'\n')
(bundle/'SHA256SUMS').write_text(''.join(rows))
print('Sealed',len(rows),'files; manifest',hashlib.sha256((bundle/'SHA256SUMS').read_bytes()).hexdigest())
