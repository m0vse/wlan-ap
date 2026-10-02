"""Byte verification of unchanged kernel/driver payloads against prior image."""
import hashlib,json,pathlib,sys,tarfile
family=sys.argv[1];revision='2026.10.02.5' if family=='sage' else '2026.10.02.4'
release=pathlib.Path('/home/phil/openwifi-'+family+'-build/release-'+family+'-'+revision)
capture=json.loads((release/'capture.json').read_text());root=pathlib.Path(capture['root'])
oldroot=pathlib.Path('/tmp/openwifi-sage4-validation.MpnQnl/root' if family=='sage' else '/tmp/openwifi-jaguar3-validation.WcB5nJ/root')
oldimage=pathlib.Path('/home/phil/openwifi-sage-build/release-sage-2026.10.02.4/cambium-sage-sage-2026.10.02.4-sysupgrade.bin' if family=='sage' else '/home/phil/openwifi-jaguar-build/operator-jaguar-openwifi-from.1-2026.10.02.3-r2/cambium_xv2-2t1-jaguar-2026.10.02.3-sysupgrade.bin')
def kernel(path):
 with tarfile.open(path) as archive:
  members=[m for m in archive if m.name.endswith('/kernel')];assert len(members)==1
  return hashlib.sha256(archive.extractfile(members[0]).read()).hexdigest()
before=kernel(oldimage);after=kernel(pathlib.Path(capture['image']));assert before==after,(family,before,after)
drivers={}
for p in (oldroot/'lib/modules').rglob('*.ko'):
 relative=p.relative_to(oldroot);new=root/relative
 assert new.is_file(),str(relative)
 a=hashlib.sha256(p.read_bytes()).hexdigest();b=hashlib.sha256(new.read_bytes()).hexdigest();assert a==b,str(relative)
 drivers[str(relative)]=a
(release/'unchanged-kernel-drivers.json').write_text(json.dumps({'passed':True,'kernel_fit_sha256':after,'unchanged_modules':len(drivers),'module_hashes':drivers,'scope':'Actual unchanged kernel FIT (including selected DTBs) and all prior kernel modules byte-for-byte; no AP execution.'},indent=2)+'\n')
print('PASS',family,'unchanged kernel and',len(drivers),'modules')
