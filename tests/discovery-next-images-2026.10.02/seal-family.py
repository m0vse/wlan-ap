"""Seal completed, verified next-release image and evidence; no publication."""
import hashlib,json,pathlib,sys
family=sys.argv[1];version='2026.10.02.5' if family=='sage' else '2026.10.02.4'
release=pathlib.Path('/home/phil/openwifi-'+family+'-build/release-'+family+'-'+version)
contract=json.loads((release/'image-contract.json').read_text());capture=json.loads((release/'capture.json').read_text())
results={}
for p in sorted(release.glob('*tests.json')):
 report=json.loads(p.read_text());assert report['passed'],str(p)
 results[p.name]=report.get('count',len(report.get('cases',[])))
assert results['built-discovery-tests.json']==35
assert results['outgoing-managed-archive-tests.json']==4
boards=['e410','e410b'] if family=='sage' else ['xv2-2','xv2-2t1','xe3-4']
for board in boards:
 assert results['normal-outgoing-'+board+'-validator-tests.json']==12
 assert results['outgoing-'+board+'-retained-ram-tests.json']==4
kernel=json.loads((release/'unchanged-kernel-drivers.json').read_text());assert kernel['passed']
assert json.loads((release/'incoming-static-ram-closure.json').read_text())['passed']
assert 'PASS: four complete target compilations' in (release/'built-target-runtime-tests.log').read_text()
image=pathlib.Path(capture['image']);assert hashlib.sha256(image.read_bytes()).hexdigest()==contract['image_sha256']
receipt={'offline_verified':True,'family':family,'revision':contract['revision'],'source_commit':'a631587a322f15f12dbacfba079be37acfaabf3f' if family=='sage' else '6dbb803b','image':image.name,'image_bytes':image.stat().st_size,'image_sha256':contract['image_sha256'],'published_model_aliases':contract['model_aliases'],'cloud_discovery_release':6,'actual_image_controls':results,'target_runtime_controls':7,'unchanged_kernel_fit_sha256':kernel['kernel_fit_sha256'],'unchanged_kernel_modules':kernel['unchanged_modules'],'retained_feature_files':contract['unchanged_feature_files'],'normal_outgoing_version':'.4' if family=='sage' else '.3','normal_route':'existing managed UI command; all four keep-flag combinations retain configuration, identity and custom trust through sysupgrade-f; no-n/no extra bridge','prerequisites':'qualified confirmed hardware, compat1.0, valid current durable credentials/store and existing protected layout/vault/capacity checks','source_only_crypto_and_boundary_evidence':'a631587a tests/discovery-renewal-r6 (9 real synthetic OpenSSL and11 EST persistence boundary controls; not reclassified as actual image network tests)','build':'clean base-files and cloud_discovery only then make-j4; no setup/rebase/upstream or profile changes','limitations':['No AP actions, physical RAM pivot, boot, rollback or power-loss acceptance','No live successful EST or private-PKI trust activation','Two per-file certificate renames not a multi-file power-loss transaction','Temporary per-AP discovery containment unchanged; only operator decides when to upgrade/enable'],'publication':'ready for model-specific verified publication only; frozen prior images and FMS untouched'}
(release/'FINAL-RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
rows=[]
for p in sorted(release.iterdir()):
 assert p.is_file() and not p.is_symlink(),str(p)
 if p.name!='SHA256SUMS':rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n')
(release/'SHA256SUMS').write_text(''.join(rows))
print(json.dumps({'release':str(release),'revision':contract['revision'],'image_sha256':contract['image_sha256'],'image_bytes':image.stat().st_size,'manifest_entries':len(rows),'manifest_sha256':hashlib.sha256((release/'SHA256SUMS').read_bytes()).hexdigest()},indent=2))
