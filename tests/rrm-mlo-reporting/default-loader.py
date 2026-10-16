#!/usr/bin/env python3
"""Real target module loading; only native/status/sysfs IO is synthetic."""
from pathlib import Path
import argparse, json, subprocess, tempfile
p=argparse.ArgumentParser()
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--root',type=Path,required=True)
p.add_argument('--generated',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--installed',action='store_true',help='Use the image helper instead of source')
p.add_argument('--expect-old-failure',action='store_true')
a=p.parse_args(); root=a.root.resolve(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
module_dir=root/'usr/share/rrmd' if a.installed else a.repo.resolve()/'feeds/ucentral/rrmd/files/usr/share/rrmd'
# QEMU's root prefix resolves the hardcoded packaged /usr/share/ucentral path.
# Deliberately NO health search path on the command line, NO require('mlo_health')
# before collect(), and NO io.health injection. Actual helper/import fs execute.
program=r'''
let fs=require('fs'),views=require('mlo_views'),cfg=json(fs.readfile(ARGV[0]));
let n=0;function check(v,label){assert(v,label);n++;}
check(index(REQUIRE_SEARCH_PATH,'/usr/share/ucentral/*.uc')<0,'health path not provided by test');
check(!exists(modules,'mlo_health'),'health module not preloaded');
let sections=filter(keys(cfg),s=>cfg[s]['.type']=='wifi-iface'&&cfg[s].mld=='ml0_0');
let five=filter(sections,s=>cfg[cfg[s].device].band=='5g')[0],six=filter(sections,s=>cfg[cfg[s].device].band=='6g')[0];
let first='02:00:00:00:00:11',second='02:00:00:00:00:22',mld='02:00:00:00:00:10';
// Use a simple synthetic SSID so fixture status does not call the health module.
cfg[five].ssid=cfg[six].ssid=cfg.ml0_0.ssid='Loader fixture';
let links=[{link_id:0,mac:first,wiphy_freq:5745,wiphy_tx_power_level:1400},{link_id:7,mac:second,wiphy_freq:6275,wiphy_tx_power_level:2300}];
let raw={ifname:'ml0_0',iftype:3,wiphy:1,mac:mld,ssid:'Loader fixture',mlo_links:links};
let count=0,io={interface:()=>raw,phy_index:p=>p=='phy01'?1:null,radio_phy:r=>1,
 status:(dev,id)=>{count++;let section=id==0?five:six;
 return {state:'ENABLED',phy:'phy01.'+cfg[cfg[section].device].radio,freq:id==0?'5745':'6275',channel:id==0?'149':'65',
 'bss[0]':dev,'bssid[0]':id==0?first:second,'ssid[0]':'Loader fixture','mld_addr[0]':mld,'mld_link_id[0]':''+id};}};
let result=views.collect({ml0_0:{}},cfg,io);
check(length(result.ml0_0)==2,'production default loader proves both MLO links');
check(exists(modules,'mlo_health')&&type(modules.mlo_health.collect)=='function','actual health module loaded by name');
check(count==2,'actual proof requests both bounded status boundaries');
check(result.ml0_0[0].mlo_link_id===0&&result.ml0_0[1].mlo_link_id===7,'explicit zero and non-radio link IDs preserved');
check(result.ml0_0[0].wiphy_tx_power_level==1400&&result.ml0_0[1].wiphy_tx_power_level==2300,'both independent native power readings preserved');
let paths=length(REQUIRE_SEARCH_PATH);views.collect({ml0_0:{}},cfg,io);
check(length(REQUIRE_SEARCH_PATH)==paths,'repeated collection does not grow search path');
check(length(views.collect({wlan0:{}},{},{}))==0,'legacy path remains independent');
printf('PASS %d production-default module-loader controls; real target ucode and health module, synthetic native/status/sysfs IO\n',n);
'''
with tempfile.TemporaryDirectory(prefix='rrm-default-loader-') as t:
 script=Path(t)/'test.uc';script.write_text(program)
 (out/'test-program.synthetic.uc').write_text(program)
 cmd=['qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),'-L',str(root/'usr/lib/ucode'),'-L',str(module_dir/'*.uc'),str(script),str(a.generated.resolve())]
 result=subprocess.run(cmd,text=True,capture_output=True)
 (out/'default-loader.log').write_text(result.stdout+result.stderr)
 if a.expect_old_failure:
  assert result.returncode!=0 and 'production default loader proves both MLO links' in result.stderr,(result.stdout,result.stderr)
  print('PASS actual deployed helper negative control: production default loader fails')
 else:
  assert result.returncode==0,(result.stdout,result.stderr)
  print(result.stdout,end='')
