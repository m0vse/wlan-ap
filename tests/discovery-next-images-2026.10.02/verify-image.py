"""Built image source/package/version and unchanged feature contract."""
import hashlib,json,pathlib,re,sys
root,old,image,metadata,out=map(pathlib.Path,sys.argv[1:6]);family,revision=sys.argv[6:8]
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected='sage-2026.10.02.5-a631587a' if family=='sage' else 'jaguar-2026.10.02.4-6dbb803b'
assert revision==expected
release=(root/'etc/openwrt_release').read_text()
assert "DISTRIB_TIP='OpenWrt 25.12.3 r32912-6639b15f62 / TIP-"+expected+"'" in release
assert "DISTRIB_TIP_VERSION='"+expected.rsplit('-',1)[0]+"'" in release
assert (root/'etc/openwrt_version').read_text().startswith('ApNos-'+expected.rsplit('-',1)[1])
for path,digest in {'usr/bin/cloud_discovery':'393db5ddd8312e1db1d35949e85d44ffea1f2316184f6444f45ba922b242e41c','usr/bin/est_client':'dc6c5b2a6f9fdcf55a114798160253205328a2daf575dadc80ab7af8457c905a','usr/share/ucentral/discovery_policy.uc':'c99f49a331be655b886897f17dadb3c53ffaf194d757194151182fe76e3228f0'}.items():
 assert h(root/path)==digest,path
database=(root/'lib/apk/db/installed').read_text()
package=next(s for s in database.split('\n\n') if '\nP:cloud_discovery\n' in '\n'+s+'\n')
assert '\nV:6\n' in '\n'+package+'\n',package
paths=['lib/functions/cambium-ab.sh','lib/upgrade/cambium-ab.sh','lib/upgrade/platform.sh','lib/upgrade/cambium-ab-certificates.sh','usr/sbin/mount_certs','usr/sbin/store_certs','usr/share/ucentral/cmd_upgrade.uc','usr/share/ucentral/dfs_cac.uc','usr/share/ucentral/health.uc','usr/share/ucentral/state.uc','etc/init.d/cloud_discover','etc/init.d/ucentral','etc/uci-defaults/19_cambium_openwifi_identity']
paths+=['lib/functions/cambium-sage.sh'] if family=='sage' else ['lib/functions/cambium-ab-jaguar.sh']
paths+=[str(p.relative_to(old)) for p in (old/'etc/uci-defaults').glob('*cambium*')]
paths+=[str(p.relative_to(old)) for p in (old/'usr/share/ucentral/templates').glob('*network*')]
paths+=[str(p.relative_to(old)) for p in (old/'lib/preinit').glob('*certificate*')]
unchanged={}
for p in sorted(set(paths)):
 if not (old/p).exists():continue
 assert h(root/p)==h(old/p),('existing feature changed',p)
 unchanged[p]=h(root/p)
meta=json.loads(metadata.read_text());supported=meta['supported_devices']
required=['cambiumnetworks,e410','cambiumnetworks,e410b'] if family=='sage' else ['cambiumnetworks,xv2-2','cambiumnetworks,xv2-2t1','cambiumnetworks,xe3-4']
assert all(m in supported for m in required),supported
assert meta['compat_version']=='1.0'
identity=(root/'etc/uci-defaults/19_cambium_openwifi_identity').read_text()
aliases=['cambium_e410','cambium_e410b'] if family=='sage' else ['cambium_xv2-2','cambium_xv2-2t1','cambium_xe3-4']
assert all(m in identity for m in aliases),identity
assert 'compatible=cambium-sage' not in identity
out.write_text(json.dumps({'passed':True,'revision':'OpenWrt 25.12.3 r32912-6639b15f62 / TIP-'+expected,'image_bytes':image.stat().st_size,'image_sha256':h(image),'package':'cloud_discovery6','supported_devices':supported,'model_aliases':aliases,'unchanged_feature_files':unchanged,'scope':'Actual extracted image/version/package/script/metadata and retained feature byte checks; no live controller/EST/AP or hardware acceptance.'},indent=2)+'\n')
