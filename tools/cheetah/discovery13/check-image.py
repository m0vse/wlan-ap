import hashlib,json,sys
from pathlib import Path
root,tree=map(Path,sys.argv[1:]);source=tree/'feeds/tip/cloud_discovery';paths=['usr/bin/cloud_discovery','usr/bin/est_client','usr/share/ucentral/discovery_policy.uc','usr/share/ucentral/cloud_discovery.uc','etc/init.d/cloud_discover','etc/ucentral/discovery-policy.json'];cases=[]
for p in paths:
 assert (root/p).read_bytes()==(source/'files'/p).read_bytes(),p
 cases.append(dict(case='exact-canonical-'+p,passed=True,sha256=hashlib.sha256((root/p).read_bytes()).hexdigest()))
records=[dict(line.split(':',1) for line in block.splitlines() if ':' in line) for block in (root/'lib/apk/db/installed').read_text().split('\n\n')]
versions={r['P']:r['V'] for r in records if 'P' in r and 'V' in r}
assert versions['cloud_discovery']=='6';assert not (root/'usr/libexec/ucentral-private-pki').exists();cases.append(dict(case='release6-no-private-PKI-activation',passed=True))
old=Path('/tmp/cheetah-image-check.c1ktu4/rootfs')
for p in ['usr/share/ucentral/dfs_cac.uc','usr/share/ucentral/health.uc','usr/sbin/ucentral-state','lib/upgrade/platform.sh','lib/upgrade/cambium-ab.sh','lib/upgrade/cambium-ab-certificates.sh','lib/functions/cambium-ab.sh','lib/functions/cambium-ab-cheetah.sh','usr/share/ucentral/cmd_upgrade.uc']:
 assert (root/p).read_bytes()==(old/p).read_bytes(),p
 cases.append(dict(case='retain-qualified12-'+p,passed=True))
print(json.dumps(dict(passed=True,count=len(cases),cases=cases,package_versions={p:versions[p] for p in ['cloud_discovery','ucentral-schema','ucentral-state','coreutils-timeout','hostapd-utils','cambium-ab']},scope='Exact actual image package/script/policy/guard and unchanged qualified .12 DFS/A-B/tr/managed command bytes. No AP actions.'),indent=2))
