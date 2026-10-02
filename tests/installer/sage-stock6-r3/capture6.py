import hashlib,json,pathlib,subprocess,tarfile,tempfile
repo=pathlib.Path('/home/phil/openwifi-sage-build/wlan-ap');base=repo.parent
assert (base/'sage-2026.10.02.6-build.exit').read_text().strip()=='0'
release=base/'release-sage-2026.10.02.6';release.mkdir(exist_ok=True)
image=release/'cambium-sage-sage-2026.10.02.6-sysupgrade.bin'
subprocess.run(['cp',str(repo/'openwrt/bin/targets/ipq40xx/generic/openwrt-ipq40xx-generic-cambium-sage-squashfs-sysupgrade.bin'),str(image)],check=True)
work=pathlib.Path(tempfile.mkdtemp(prefix='sage6-capacity-image.'))
subprocess.run(['tar','-xf',str(image),'-C',str(work)],check=True)
parts=list(work.glob('sysupgrade-*/root'));assert len(parts)==1
r=subprocess.run([str(repo/'openwrt/staging_dir/host/bin/unsquashfs4'),'-d',str(work/'root'),str(parts[0])],capture_output=True,text=True)
assert r.returncode==0 or (r.returncode==2 and 'create character device' in r.stderr),r.stderr
(release/'root-extraction.log').write_text(r.stdout+r.stderr)
root=work/'root'; version=(root/'etc/openwrt_release').read_text();assert 'TIP-sage-2026.10.02.6-9fe7f73a' in version,version
assert 'AB_SAGE_ROOT_LEBS=285' in (root/'lib/functions/cambium-ab-sage.sh').read_text()
old=pathlib.Path('/tmp/openwifi-sage-discovery-validation.mh1qojwo/root')
for p in ['lib/functions/cambium-ab.sh','lib/upgrade/cambium-ab.sh','lib/upgrade/cambium-ab-certificates.sh','lib/upgrade/platform.sh','lib/functions/cambium-sage.sh','usr/bin/cloud_discovery','usr/bin/est_client','usr/share/ucentral/dfs_cac.uc','usr/share/ucentral/health.uc','usr/share/ucentral/state.uc','etc/uci-defaults/19_cambium_openwifi_identity','usr/bin/mount_certs','usr/bin/store_certs']:
 assert (root/p).read_bytes()==(old/p).read_bytes(),p
assert parts[0].stat().st_size<=285*126976
subprocess.run([str(repo/'openwrt/staging_dir/host/bin/fwtool'),'-i',str(release/'image-metadata.json'),str(image)],check=True)
meta=json.loads((release/'image-metadata.json').read_text());assert 'cambiumnetworks,e410b' in meta['supported_devices']
with tarfile.open(image) as t:
 k=next(m for m in t if m.name.endswith('/kernel'));kernel=hashlib.sha256(t.extractfile(k).read()).hexdigest()
with tarfile.open(base/'release-sage-2026.10.02.5/cambium-sage-sage-2026.10.02.5-sysupgrade.bin') as t:
 k=next(m for m in t if m.name.endswith('/kernel'));assert kernel==hashlib.sha256(t.extractfile(k).read()).hexdigest()
modules=list((old/'lib/modules').rglob('*.ko'))
for p in modules:assert p.read_bytes()==(root/p.relative_to(old)).read_bytes()
result={'image':str(image),'root':str(root),'release':str(release),'version':'TIP-sage-2026.10.02.6-9fe7f73a','bytes':image.stat().st_size,'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'root_bytes':parts[0].stat().st_size,'root_capacity':285*126976,'kernel_sha256':kernel,'unchanged_modules':len(modules),'unchanged_existing_features':True,'hardware_trial':False}
(release/'capture.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
