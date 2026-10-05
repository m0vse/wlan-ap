from pathlib import Path
import argparse,shutil
p=argparse.ArgumentParser();p.add_argument('repository',type=Path);p.add_argument('destination',type=Path);a=p.parse_args();a.destination.mkdir(parents=True,exist_ok=False)
files={
 'ucentral-installer-identity':'feeds/tip/certificates/files/usr/libexec/ucentral-installer-identity',
 'ucentral-installer-boot':'feeds/tip/certificates/files/usr/libexec/ucentral-installer-boot',
 'ucentral-installer-firstboot':'feeds/tip/certificates/files/usr/libexec/ucentral-installer-firstboot',
 'ucentral-restore-operational-gateway':'feeds/tip/certificates/files/usr/libexec/ucentral-restore-operational-gateway',
 'discovery_policy.uc':'feeds/tip/cloud_discovery/files/usr/share/ucentral/discovery_policy.uc',
 'mount_certs':'feeds/tip/certificates/files/usr/bin/mount_certs',
 'est_client':'feeds/tip/cloud_discovery/files/usr/bin/est_client',
 'cloud_discover.init':'feeds/tip/cloud_discovery/files/etc/init.d/cloud_discover'}
for target,source in files.items():shutil.copy2(a.repository/source,a.destination/target)
