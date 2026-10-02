import hashlib,json,pathlib,shutil,subprocess
release=pathlib.Path('/home/phil/openwifi-sage-build/release-sage-2026.10.02.6')
capture=json.loads((release/'capture.json').read_text())
for name in ('static-ram-closure.json','e410b-fit-ram-tests.json','e410-fit-ram-tests.json','stock-validator-tests.json','wrapper-tests.json','focused-capacity-tests.json'):
 evidence=json.loads((release/name).read_text());assert evidence['passed'],name
source=pathlib.Path('/tmp/sage6-stock-capacity-bundle')
bundle=release/'operator-sage-stock-2026.10.02.6-r3';shutil.copytree(source,bundle)
shutil.copy2('/tmp/sage6-README.txt',bundle/'README.txt')
for name in ('capture.json','static-ram-closure.json','e410b-fit-ram-tests.json','e410-fit-ram-tests.json','stock-validator-tests.json','wrapper-tests.json','focused-capacity-tests.json'):
 shutil.copy2(release/name,bundle/'evidence'/name)
receipt={'scope':'Stock2026.09.29.0 clean migration, E410/E410B; observed AP E410B; first hardware trial pending','image':capture,'legacy_source':'1dd0433','release_source':'9fe7f73a','fresh_counts':{'capacity_and_inactive_sequence':12,'actual_stock_validator':20,'wrapper':9,'e410_fit_ram':4,'e410b_fit_ram':4},'existing_transactions':'unchanged bridge functions; historical evidence retained, not rerun','no_AP_action':True,'no_nvram_or_running_pair_resize':True,'no_private_trust_activation':True}
(bundle/'FINAL-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=sorted(p for p in bundle.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
assert not any(p.is_symlink() for p in bundle.rglob('*'))
(bundle/'SHA256SUMS').write_text(''.join(h(p)+'  '+str(p.relative_to(bundle))+'\n' for p in files))
subprocess.run(['sha256sum','-c','SHA256SUMS'],cwd=bundle,check=True,stdout=subprocess.DEVNULL)
archive=release/(bundle.name+'.tar.gz')
subprocess.run(['tar','-czf',str(archive),'-C',str(release),bundle.name],check=True)
result={'archive':str(archive),'bytes':archive.stat().st_size,'sha256':h(archive),'manifest_sha256':h(bundle/'SHA256SUMS'),'manifest_entries':len(files),'image_sha256':capture['sha256'],'hardware_trial':False}
(release/'BUNDLE-RECEIPT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
