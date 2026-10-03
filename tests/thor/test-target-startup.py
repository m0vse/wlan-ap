#!/usr/bin/env python3
"""Actual target ucode/UCI startup, isolated files, hardware boundary stubs only."""
from pathlib import Path
import tempfile,shutil,subprocess,json,re,sys,os
root,old,fixtures=map(Path,sys.argv[1:4]); work=Path(tempfile.mkdtemp(prefix='thor-target-startup-')); reports=[]
def target(case,script,args=()):
 return subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),'-L',str(case/'usr/share/ucentral'),str(script),*args],capture_output=True,text=True)
def setup(label,image,mode='dual-4x4',bad=False):
 case=work/label;case.mkdir()
 for p in ('etc/config','etc/config-shadow','etc/ucentral','rom/etc/ucentral','sys/module/ath11k/parameters','tmp/sysinfo','usr/bin','sbin','certificates','lib','bin'): (case/p).mkdir(parents=True,exist_ok=True)
 shutil.copytree(image/'usr/share/ucentral',case/'usr/share/ucentral',symlinks=True)
 for p in (image/'etc/config').iterdir():
  if p.is_file():shutil.copy2(p,case/'etc/config'/p.name)
 for name in ('network','system','wireless','ucentral'):
  shutil.copy2(fixtures/(name+'.fixture'),case/'etc/config'/name)
 shutil.copytree(case/'etc/config',case/'etc/config-shadow',dirs_exist_ok=True)
 (case/'etc/board.json').write_text(json.dumps({'model':{'id':'cambiumnetworks,xv3-8','name':'Cambium XV3-8'},'network':{'wan':{'device':'lan-multigig'},'lan':{'device':'lan'}}}))
 for name,value in [('platform','ap'),('compatible','cambium_xv3-8')]: (case/'etc/ucentral'/name).write_text(value)
 for name in ('version.json','schema.json'):shutil.copy2(image/'etc/ucentral'/name,case/'etc/ucentral'/name)
 (case/'tmp/sysinfo/board_name').write_text('cambiumnetworks,xv3-8\n')
 (case/'sys/module/ath11k/parameters/xv3_8_hw_mode').write_text(mode+'\n')
 shutil.copy2(image/'etc/ucentral/ucentral.cfg.0000000001',case/'rom/etc/ucentral/ucentral.cfg.0000000001')
 phys={'soc@0/c000000.wifi':{'band':['2G'],'tx_ant_avail':15,'rx_ant_avail':15},'soc@0/c000000.wifi+1':{'band':['5G'],'tx_ant_avail':255 if mode=='single-8x8' else 15,'rx_ant_avail':255 if mode=='single-8x8' else 15},'pci/scanner':{'band':['5G'],'tx_ant_avail':1,'rx_ant_avail':1}}
 if mode=='dual-4x4':phys['soc@0/c000000.wifi+2']={'band':['5G'],'tx_ant_avail':240,'rx_ant_avail':240}
 if bad:phys['soc@0/c000000.wifi+1']['tx_ant_avail']=1
 phy=(image/'usr/share/ucentral/wifi/phy.uc').read_text();tail=phy[phy.index('let serving = lookup_phys();'):]
 (case/'usr/share/ucentral/wifi/phy.uc').write_text("let fs=require('fs'); function lookup_phys(){return "+json.dumps(phys)+";}\n"+tail)
 def map_paths(s):
  return re.sub(r'/(?:usr/share/ucentral/|etc/|tmp/|sys/|rom/|certificates(?:/|\b))',lambda m:str(case)+m.group(),s)
 for p in (case/'usr/share/ucentral').rglob('*.uc'):
  s=map_paths(p.read_text()).replace('/sbin/uci',str(case/'sbin/uci'))
  s=s.replace('uci.cursor()',f"uci.cursor('{case}/etc/config', '{case}/tmp/.uci')")
  p.write_text(s)
 # External ubus/PHY hardware boundary only; all parser/policy/template/UCI code executes.
 for name in ('capabilities.uc','ucentral.uc'):
  p=case/'usr/share/ucentral'/name;s=p.read_text();shebang,body=s.split('\n',1)
  p.write_text(shebang+"\nmodules.ubus={connect:()=>({call:()=>null})};\n"+body)
 wrapper=case/'usr/bin/ucode';wrapper.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/usr/bin/ucode" -L "{case}/usr/share/ucentral" "$@"\n');wrapper.chmod(0o755)
 uci=case/'sbin/uci';uci.write_text(f'#!/bin/sh\nexec /usr/bin/qemu-aarch64 -L "{root}" "{root}/sbin/uci" "$@"\n');uci.chmod(0o755)
 cap=case/'usr/share/ucentral/capabilities.uc';cap.write_text(cap.read_text().replace('#!/usr/bin/ucode','#!'+str(wrapper),1));cap.chmod(0o755)
 (case/'sbin/wifi').write_text('#!/bin/sh\n[ "$1" = config ]\n');(case/'sbin/wifi').chmod(0o755)
 (case/'bin/logger').write_text('#!/bin/sh\nexit 0\n');(case/'bin/logger').chmod(0o755)
 detect=case/'usr/share/ucentral/wifi_detect.sh';detect.write_text(f'#!/bin/sh\ncp "{case}/etc/config/wireless" "{case}/tmp/config-shadow/"\n');detect.chmod(0o755)
 startup=case/'startup.sh';startup.write_text(map_paths((image/'usr/libexec/ucentral-network').read_text()).replace('/sbin/wifi',str(case/'sbin/wifi')).replace('/usr/bin/ucode',str(wrapper)))
 return case
for mode in ('dual-4x4','single-8x8'):
 case=setup(mode,root,mode)
 p=target(case,case/'usr/share/ucentral/capabilities.uc')
 assert p.returncode==0,(mode,p.stderr)
 capa=json.loads((case/'etc/ucentral/capabilities.json').read_text());assert len(capa['wifi'])==(3 if mode=='dual-4x4' else 2)
 assert capa['network']['wan']==['lan-multigig'] and all('scanner' not in k for k in capa['wifi'])
 reports.append({'case':mode+'-actual-capabilities-dynamic-policy','passed':True})
 p=subprocess.run(['sh',str(case/'startup.sh')],capture_output=True,text=True,env=dict(os.environ,PATH=str(case/'bin')+':'+os.environ['PATH']))
 if p.returncode:raise AssertionError((mode,p.stdout,p.stderr,(case/'etc/ucentral/network-boot.failure').read_text() if (case/'etc/ucentral/network-boot.failure').exists() else 'no failure diagnostic'))
 assert (case/'tmp/ucentral-network.ready').stat().st_size>0
 assert not (case/'tmp/ucentral-uci.errors').read_text()
 p=subprocess.run([str(case/'sbin/uci'),'-c',str(case/'etc/config'),'-t',str(case/'tmp/.uci'),'-q','get','network.up0v0.proto'],capture_output=True,text=True);assert p.stdout.strip()=='dhcp'
 p=subprocess.run([str(case/'sbin/uci'),'-c',str(case/'etc/config'),'-t',str(case/'tmp/.uci'),'show','network'],capture_output=True,text=True)
 assert 'lan-multigig' in p.stdout and 'network.lan=' not in p.stdout
 reports.append({'case':mode+'-actual-S18-render-UCI-dynamic-DHCP-no-legacy-LAN','passed':True})
case=setup('bad-chains',root,bad=True);p=target(case,case/'usr/share/ucentral/capabilities.uc');assert p.returncode!=0 and 'chain capability' in p.stderr;assert not (case/'etc/ucentral/capabilities.json').exists();reports.append({'case':'incorrect-chains-refuse-capability-ready','passed':True})
case=setup('frozen8-negative',old);p=target(case,case/'usr/share/ucentral/capabilities.uc');assert p.returncode!=0 and "No module named 'thor-topology-policy'" in p.stderr;reports.append({'case':'actual-frozen8-dynamic-module-defect-reproduced','passed':True})
# Execute the actual radio-template function that uses the same dynamic loader.
radio=(root/'usr/share/ucentral/templates/radio.uc').read_text();fn=re.search(r'(?ms)^\tfunction match_mimo\(.*?^\t}',radio).group()
case=work/'dual-4x4';probe=case/'radio-policy.uc';fn=fn.replace('/tmp/sysinfo/board_name',str(case/'tmp/sysinfo/board_name'))
probe.write_text("let radio={mimo:'4x4'};\n"+fn+"\nassert(match_mimo(15,'4x4')==15); let rejected=false; radio.mimo='8x8';try{match_mimo(15,'8x8');}catch(e){rejected=true;}assert(rejected);assert(match_mimo(255,'8x8')==255);print('radio policy passed\\n');")
p=target(case,probe);assert p.returncode==0,(p.stdout,p.stderr);reports.append({'case':'actual-radio-template-dynamic-load-and-chain-limits','passed':True})
print(json.dumps({'passed':True,'count':len(reports),'cases':reports,'fixture':str(work),'scope':'Actual target interpreter/UCI and complete capabilities/S18/schema renderer; filesystem redirected, hardware ubus/PHY/wifi detection stubbed; no kernel/AP boot or DHCP transport proof'},indent=2))
