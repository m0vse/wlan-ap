#!/usr/bin/env python3
"""Execute real shared capabilities/boot renderer/UCI in isolated Miami fixtures.
Hardware inventory/sysfs/ubus boundaries are mocked; no AP or network changes.
"""
from pathlib import Path
import tempfile,shutil,subprocess,json,re,sys,os
root,fixture,out=map(Path,sys.argv[1:4])
source_overlay='--source-overlay' in sys.argv[4:]
persistent='--persistent' in sys.argv[4:]
repo=Path(__file__).resolve().parents[3]
out.mkdir(parents=True,exist_ok=True)
case=Path(tempfile.mkdtemp(prefix='native-startup-',dir=out))
for p in ('etc/config','etc/config-shadow','etc/ucentral','rom/etc/ucentral','tmp/sysinfo','usr/bin','sbin','certificates','lib','bin'):(case/p).mkdir(parents=True,exist_ok=True)
shutil.copytree(root/'usr/share/ucentral',case/'usr/share/ucentral',symlinks=True)
for p in (root/'etc/config').iterdir():
 if p.is_file():shutil.copy2(p,case/'etc/config'/p.name)
for name in ('network','system','wireless','ucentral'):shutil.copy2(fixture/(name+'.fixture'),case/'etc/config'/name)
wireless='''config wifi-device 'radio0'
 option type 'mac80211'
 option path 'soc@0/c000000.wifi'
 option band '2g'
 option country 'GB'
 option disabled '1'
config wifi-device 'radio1'
 option type 'mac80211'
 option path 'pci/0001:01:00.0'
 option band '5g'
 option country 'GB'
 option disabled '1'
config wifi-device 'radio2'
 option type 'mac80211'
 option path 'pci/0001:01:00.0+1'
 option band '6g'
 option country 'GB'
 option disabled '1'
'''
(case/'etc/config/wireless').write_text(wireless)
shutil.copytree(case/'etc/config',case/'etc/config-shadow',dirs_exist_ok=True)
(case/'etc/board.json').write_text(json.dumps({'model':{'id':'cambiumnetworks,x7-35x','name':'Cambium X7-35X'},'network':{'wan':{'device':'eth0'}}}))
(case/'etc/ucentral/ucentral.defaults').write_text('{"country":"GB"}')
(case/'etc/ucentral/country').write_text('GB')
compatible=(repo/'feeds/tip/cambium-miami-radio/files/compatible') if source_overlay else (root/'etc/ucentral/compatible')
shutil.copy2(compatible,case/'etc/ucentral/compatible')
for name in ('version.json','schema.json'):shutil.copy2(root/'etc/ucentral'/name,case/'etc/ucentral'/name)
platform=(repo/'feeds/tip/cambium-miami-radio/files/platform') if source_overlay else (root/'etc/ucentral/platform')
shutil.copy2(platform,case/'etc/ucentral/platform')
# Site-specific fixture data belongs in the private test overlay, never the package.
if not persistent:(case/'certificates/ucentral.defaults').write_text('{"country":"GB"}')
(case/'usr/libexec').mkdir(parents=True,exist_ok=True)
ready_source=(repo/'feeds/tip/cambium-miami-radio/files/miami-radio-ready') if source_overlay else (root/'usr/libexec/miami-radio-ready')
(case/'usr/libexec/miami-radio-ready').write_text(ready_source.read_text().replace('/etc/ucentral/',str(case/'etc/ucentral')+'/'))
(case/'usr/libexec/miami-radio-ready').chmod(0o755)
(case/'tmp/sysinfo/board_name').write_text('cambiumnetworks,x7-35x\n')
shutil.copy2(root/'etc/ucentral/ucentral.cfg.0000000001',case/'etc/ucentral/ucentral.cfg.0000000001')
(case/'proc').mkdir()
(case/'proc/mounts').write_text('overlay / overlay rw 0 0\n' if persistent else 'tmpfs / tmpfs rw 0 0\n')
if persistent:
 (case/'proc/device-tree/cambium-platform').mkdir(parents=True)
 (case/'proc/device-tree/cambium-platform/storage-slot').write_bytes(bytes(4))
 # Hardware mount/label context is covered by the separate actual-core fixture.
 # This renderer fixture replaces only that external context boundary.
 (case/'usr/libexec/miami-country-defaults').write_text('#!/bin/sh\nprintf "GB\\n"\n')
 (case/'usr/libexec/miami-country-defaults').chmod(0o755)
 shutil.copy2(case/'etc/ucentral/ucentral.cfg.0000000001',case/'rom/etc/ucentral/ucentral.cfg.0000000001')

ram_hook=(root/'etc/uci-defaults/01-miami-ram-bootstrap').read_text()
ram_paths=['/tmp/sysinfo','/proc/mounts','/rom/etc/ucentral','/etc/ucentral']
ram_hook=re.sub('|'.join(re.escape(p) for p in ram_paths),lambda m:str(case/m.group().lstrip('/')),ram_hook)
subprocess.run(['sh','-c',ram_hook],check=True)
assert (case/'rom/etc/ucentral/ucentral.cfg.0000000001').read_bytes()==(case/'etc/ucentral/ucentral.cfg.0000000001').read_bytes()
phys={'soc@0/c000000.wifi':{'band':['2G'],'tx_ant_avail':3,'rx_ant_avail':3},'pci/0001:01:00.0':{'band':['5G','6G'],'tx_ant_avail':7,'rx_ant_avail':7},'pci/0001:01:00.0+1':{'band':['5G','6G'],'tx_ant_avail':7,'rx_ant_avail':7}}
phy=(case/'usr/share/ucentral/wifi/phy.uc').read_text()
assert 'let serving = lookup_phys();' in phy
(case/'usr/share/ucentral/wifi/phy.uc').write_text("let fs=require('fs'); function lookup_phys(){return "+json.dumps(phys)+";}\n"+phy[phy.index('let serving = lookup_phys();'):])
def map_paths(s):return re.sub(r'/(?:usr/share/ucentral/|usr/libexec/|etc/|tmp/|sys/|proc/|rom/|certificates(?:/|\b))',lambda m:str(case)+m.group(),s)
for p in (case/'usr/share/ucentral').rglob('*.uc'):
 s=map_paths(p.read_text()).replace('/sbin/uci',str(case/'sbin/uci'))
 s=s.replace('let conn = ubus ? ubus.connect() : null;', "let conn = { call: () => die('unexpected renderer RPC') };")
 s=s.replace('uci.cursor()',f"uci.cursor('{case}/etc/config', '{case}/tmp/.uci')")
 p.write_text(s)
for name in ('base','ethernet'):
 p=case/f'usr/share/ucentral/libs/{name}.uc'
 if p.exists():p.write_text(p.read_text().replace('/bin/ubus','/bin/true'))
wrapper=case/'usr/bin/ucode';wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/usr/bin/ucode" -L "{case}/usr/share/ucentral" "$@"\n');wrapper.chmod(0o755)
uci=case/'sbin/uci';uci.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/sbin/uci" "$@"\n');uci.chmod(0o755)
cap=case/'usr/share/ucentral/capabilities.uc';cap.write_text(cap.read_text().replace('#!/usr/bin/ucode','#!'+str(wrapper),1));cap.chmod(0o755)
(case/'sbin/wifi').write_text('#!/bin/sh\n[ "$1" = config ]\n');(case/'sbin/wifi').chmod(0o755)
(case/'bin/fw_printenv').write_text('#!/bin/sh\nexit 1\n');(case/'bin/fw_printenv').chmod(0o755)
(case/'bin/logger').write_text('#!/bin/sh\nexit 0\n');(case/'bin/logger').chmod(0o755)
detect=case/'usr/share/ucentral/wifi_detect.sh';detect.write_text(f'#!/bin/sh\ncp "{case}/etc/config/wireless" "{case}/tmp/config-shadow/"\n');detect.chmod(0o755)
startup_source=(repo/'feeds/ucentral/ucentral-schema/files/usr/libexec/ucentral-network') if source_overlay else (root/'usr/libexec/ucentral-network')
jsonfilter=case/'bin/jsonfilter';jsonfilter.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/usr/bin/jsonfilter" "$@"\n');jsonfilter.chmod(0o755)
startup=case/'startup.sh';startup.write_text(map_paths(startup_source.read_text()).replace('/sbin/wifi',str(case/'sbin/wifi')).replace('/usr/bin/ucode',str(wrapper)))
proc=subprocess.run(['sh',str(startup)],capture_output=True,text=True,env=dict(os.environ,PATH=str(case/'bin')+':'+os.environ['PATH']))
if proc.returncode:
 raise AssertionError((proc.returncode,proc.stderr,(case/'etc/ucentral/network-boot.failure').read_text() if (case/'etc/ucentral/network-boot.failure').exists() else '',case))
assert (case/'tmp/ucentral-network.ready').stat().st_size>0
capa=json.loads((case/'etc/ucentral/capabilities.json').read_text());assert len(capa['wifi'])==3 and capa['network']['wan']==['eth0'] and capa['platform']=='ap' and capa['country']=='GB' and capa['compatible']=='cambium_x7-35x'
proc=subprocess.run([str(uci),'-c',str(case/'etc/config'),'-t',str(case/'tmp/.uci'),'show','network'],capture_output=True,text=True,check=True)
network=proc.stdout
assert '.proto=\'dhcp\'' in network
assert 'network.lan=' not in network
assert 'bridge-vlan' in network and '8021q' in network
assert '101' not in network
assert "'eth0'" in network
(case/'rendered-network.uci').write_text(network)
if persistent:assert list((case/'certificates').iterdir())==[], 'capabilities populated empty certificate store'

report={'passed':True,'scope':'persistent compiled target' if persistent else ('source overlay' if source_overlay else 'compiled target'), 'validation':'actual target interpreter, UCI, shared capabilities and S18 bootstrap renderer; hardware boundary mocked; not kernel/DHCP transport acceptance','board':'X7-35X','radios':3,'management':'eth0 through renderer bridge-VLAN/8021q DHCP, no legacy LAN or VLAN101','fixture':str(case)}
(out/'native-startup-result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
