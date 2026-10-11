from pathlib import Path
import json,re,sys
root=Path(sys.argv[1])
out=Path(sys.argv[2])
db=root/'lib/apk/db/installed'
assert db.is_file(), 'actual APK database absent'
packages={}
for block in db.read_text().split('\n\n'):
    fields={line[:1]:line[2:] for line in block.splitlines() if len(line)>2 and line[1]==':' and line[0] in 'PVA'}
    if 'P' in fields:
        assert fields['P'] not in packages, 'duplicate installed package record'
        packages[fields['P']]={'version':fields.get('V'),'architecture':fields.get('A')}
expected={'cambium-ab':'16','cambium-gambit-support':'6','certificates':'3','cloud_discovery':'4','ucentral-schema':'2026.08.26~d1e90a04-r13'}
for name,version in expected.items():
    assert packages.get(name,{}).get('version')==version,(name,packages.get(name),version)
for name in ['kmod-ath9k','kmod-ath10k-ct','ath10k-firmware-qca988x-ct','openssl-util','ucentral-client','rtty-openssl']:
    assert name in packages, 'required package missing: '+name
assert not any('openwisp' in name for name in packages), 'legacy management package present'
release=(root/'etc/openwrt_release').read_text()
reported=re.search(r"^DISTRIB_TIP='([^']+)'$",release,re.M)[1]
assert 'TIP-gambit-2026.10.02.12-f08f3456' in reported,reported
record={'reported_revision':reported,'database':str(db),'package_count':len(packages),'key_packages':{name:packages[name] for name in expected},'required_radio_and_crypto_packages':{name:packages[name] for name in ['kmod-ath9k','kmod-ath10k-ct','ath10k-firmware-qca988x-ct','openssl-util','ucentral-client','rtty-openssl']},'qualified_models':['E400'],'sku':6,'kernel':'6.12.85','hardware_acceptance':False,'installer_ready':False,'production_pki_ready':False}
out.write_text(json.dumps(record,indent=2)+'\n')
print('PASS: actual APK database versions, required packages and exact reported revision')
print('PACKAGED_AUDIT='+str(out))
