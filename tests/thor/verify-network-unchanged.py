#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,subprocess
new,old=map(Path,sys.argv[1:3]);reports=[]
paths=('etc/board.d/02_network','lib/netifd/proto/dhcp.sh','lib/netifd/dhcp.script','lib/functions/network.sh','etc/init.d/network','usr/libexec/ucentral-network','usr/sbin/cambium-ab-guard','sbin/netifd','usr/sbin/bridger','usr/sbin/udhcpsnoop','etc/init.d/bridger','etc/init.d/dhcpsnoop','usr/share/ucentral/templates/base.uc','usr/share/ucentral/templates/ethernet.uc','usr/share/ucentral/templates/interface/bridge-vlan.uc','usr/share/ucentral/templates/interface.uc','etc/ucentral/ucentral.cfg.0000000001','usr/share/ucentral/thor_topology_policy.uc','usr/share/ucentral/wifi/phy.uc','usr/share/ucentral/templates/radio.uc')
for path in paths:
 a,b=new/path,old/path
 assert a.is_file() and b.is_file(),path
 same=a.read_bytes()==b.read_bytes()
 if path not in ('sbin/netifd','usr/sbin/bridger','usr/sbin/udhcpsnoop'): assert same,path
 reports.append({'path':path,'sha256':hashlib.sha256(a.read_bytes()).hexdigest(),'previous_sha256':hashlib.sha256(b.read_bytes()).hexdigest(),'unchanged':same,'kind':'rebuilt-daemon-inventory' if path in ('sbin/netifd','usr/sbin/bridger','usr/sbin/udhcpsnoop') else 'unchanged-settings-or-script'})
stage=Path('/home/phil/openwifi-thor-build')
assert (stage/'thor9-build.config').read_bytes()==(stage/'thor10-build.config').read_bytes()
print(json.dumps({'passed':True,'count':len(reports),'unchanged_settings_count':17,'daemon_inventory_count':3,'build_config_unchanged':True,'files':reports,'scope':'17 Ethernet/DHCP/startup/guard/factory/topology settings and scripts byte-identical to frozen .9; three rebuilt daemons inventoried exactly; full build config identical. Runtime binary hashes may differ and require additional complete offline-qualified runtime manifest'},indent=2))
