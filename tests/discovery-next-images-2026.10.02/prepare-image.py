"""Capture completed build into a new release directory and private root."""
import hashlib,json,pathlib,subprocess,sys,tempfile
family=sys.argv[1];assert family in ('sage','jaguar')
revision='2026.10.02.5' if family=='sage' else '2026.10.02.4'
base=pathlib.Path('/home/phil/openwifi-'+family+'-build');repo=base/'wlan-ap'
assert (base/(family+'-'+revision+'-build.exit')).read_text().strip()=='0'
release=base/('release-'+family+'-'+revision);release.mkdir()
relative='bin/targets/ipq40xx/generic/openwrt-ipq40xx-generic-cambium-sage-squashfs-sysupgrade.bin' if family=='sage' else 'bin/targets/qualcommax/ipq60xx/openwrt-qualcommax-ipq60xx-cambiumnetworks_jaguar-persistent-squashfs-sysupgrade.bin'
image=release/('cambium-'+family+'-'+family+'-'+revision+'-sysupgrade.bin')
subprocess.run(['cp',str(repo/'openwrt'/relative),str(image)],check=True)
work=pathlib.Path(tempfile.mkdtemp(prefix='openwifi-'+family+'-discovery-validation.'))
subprocess.run(['tar','-xf',str(image),'-C',str(work)],check=True)
roots=list(work.glob('sysupgrade-*/root'));assert len(roots)==1
extract=subprocess.run([str(repo/'openwrt/staging_dir/host/bin/unsquashfs4'),'-d',str(work/'root'),str(roots[0])],capture_output=True,text=True)
assert extract.returncode==0 or (extract.returncode==2 and 'create character device' in extract.stderr and '/dev/console' in extract.stderr),(extract.returncode,extract.stderr)
(release/'root-extraction.log').write_text(extract.stdout+extract.stderr)
metadata=release/'image-metadata.json'
subprocess.run([str(repo/'openwrt/staging_dir/host/bin/fwtool'),'-i',str(metadata),str(image)],check=True)
package=work/'package';package.mkdir();(package/'files').symlink_to(work/'root')
(release/'IMAGE').write_text(image.name+'\n')
result={'family':family,'revision':revision,'release':str(release),'work':str(work),'root':str(work/'root'),'package':str(package),'image':str(image),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'image_bytes':image.stat().st_size}
(release/'capture.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
