#!/usr/bin/env python3
"""Run actual patched schema discovery and shell resolver with mocked kernel inventory."""
from pathlib import Path
import argparse,difflib,json,re,subprocess,tempfile,shutil
parser=argparse.ArgumentParser()
parser.add_argument('--ucode',required=True)
parser.add_argument('--schema-source',type=Path,required=True)
parser.add_argument('--repo',type=Path)
parser.add_argument('--baseline-shell',type=Path)
a=parser.parse_args();repo=a.repo or Path(__file__).resolve().parents[3]
patch=repo/'feeds/ucentral/ucentral-schema/patches/097-sdk-wiphy-name-discovery.patch'
source=a.schema_source.read_text()
with tempfile.TemporaryDirectory(prefix='miami-phy-fixtures-') as td:
 work=Path(td);target=work/'renderer/wifi/phy.uc';target.parent.mkdir(parents=True);target.write_text(source)
 if 'function phy_name(phy)' not in source:
  p=subprocess.run(['patch','--fuzz=0','-p1','-i',str(patch)],cwd=work,capture_output=True,text=True)
  assert p.returncode==0 and 'fuzz' not in p.stdout,(p.stdout,p.stderr)
 patched=target.read_text()
 assert 'function phy_name(phy)' in patched
 ahb='platform/soc@0/c000000.wifi';pci='soc@0/18000000.pcie/pci0001:00/0001:00:00.0/0001:01:00.0'
 def run_schema(names,indices,reported='actual',board=None,expect_empty=False,before=False):
  inventory=[];dumps=[];wireless={}
  for n,(name,idx,band,freq,path) in enumerate(zip(names,indices,['2G','5G','6G'],[2437,5180,6135],[ahb,pci,pci])):
   physical=path if path.startswith('platform/') else 'platform/'+path
   inventory.append({'name':name,'index':idx,'dir':'/sys/devices/'+physical+'/ieee80211'})
   d={'wiphy':idx,'wiphy_antenna_tx':3,'wiphy_antenna_rx':3,'wiphy_antenna_avail_tx':3,'wiphy_antenna_avail_rx':3,'wiphy_bands':[{'freqs':[{'freq':freq}],'ht_capa':3,'vht_capa':4,'iftype_data':[{'iftypes':{'ap':True},'he_cap_phy':[6],'he_cap_mac':[0]}]}]}
   if reported=='actual':d['wiphy_name']=name
   elif reported!='missing':d['wiphy_name']=reported
   dumps.append(d)
   wireless['radio'+str(n)]={'.type':'wifi-device','path':path+('+1' if n==2 else '')}
  # Shuffle the kernel dump and filesystem order independently of radio indices.
  inventory.reverse();dumps.reverse()
  mocks='''let inventory = INVENTORY; let dumps = DUMPS; let board = BOARD; let wireless = WIRELESS;
let fs = {
 basename: p => split(p, '/')[length(split(p, '/'))-1],
 glob: function(p) {
  let out=[];
  for (let item in inventory)
   if (p == item.dir+'/phy*') push(out,item.dir+'/'+item.name);
  return out;
 },
 readfile: function(p) {
  if (p == '/etc/board.json') return sprintf('%J',board);
  if (p == '/tmp/sysinfo/board_name') return 'fixture';
  for (let item in inventory) if (p == item.dir+'/'+item.name+'/index') return ''+item.index;
  return null;
 }, open: () => null, stat: () => null
};
let cursor={get_all: () => wireless}; let nl={request: () => dumps,const:{},error: () => ''}; let def=nl.const;
'''
  for k,v in [('INVENTORY',inventory),('DUMPS',dumps),('BOARD',board or {}),('WIRELESS',wireless)]:mocks=mocks.replace(k,json.dumps(v))
  s=source if before else patched
  assert s.startswith("let fs = require('fs');")
  s=mocks+'\n'.join(s.splitlines()[5:])
  assert s.rstrip().endswith('return serving;')
  s=s.rsplit('return serving;',1)[0]+"printf('%J\\n', serving);\n"
  script=work/'fixture.uc';script.write_text(s)
  p=subprocess.run([a.ucode,str(script)],capture_output=True,text=True);assert p.returncode==0,(p.stdout,p.stderr)
  result=json.loads(p.stdout)
  if expect_empty:assert result=={},result
  elif not board:
   assert set(result)=={ahb,pci,pci+'+1'},result
   for path,band in zip([ahb,pci,pci+'+1'],['2G','5G','6G']):assert result[path]['band']==[band],result
  return result
 conventional=run_schema(['phy0','phy1','phy2'],[0,1,2])
 assert conventional==run_schema(['phy0','phy1','phy2'],[0,1,2],before=True)
 run_schema(['phy00','phy01','phy03'],[0,1,2])
 run_schema(['phy00','phy03','phy01'],[4,9,17])
 run_schema(['phy0','phy2','phy10'],[0,2,10],reported='missing')
 run_schema(['phy-ahb','phy_pci5','phy.pci6'],[0,1,2])
 for invalid in ['missing','',None,False,42,{},[], '../phy0','phy 0','.', '..', '/phy0', 'phy0\n']:
  run_schema(['phy0','phy1','phy2'],[0,1,2],reported=invalid)
 run_schema(['phy0','phy1','phy2'],[0,1,2],reported='phy-does-not-exist',expect_empty=True)
 # Modern board keys must intersect the actual named netlink WIPHY.
 for name,band,freq,path in [('phy00','2G',2437,ahb),('phy01','5G',5180,pci),('phy03','6G',6135,pci+'+1')]:
  board={'wlan':{name:{'path':path,'info':{'antenna_tx':3,'antenna_rx':3,'bands':{band:{'modes':['HE20']}},'radios':[{'index':0,'bands':{band:{}},'freq_ranges':[[freq*1000,freq*1000]]}]}}}}
  r=run_schema(['phy00','phy01','phy03'],[0,1,2],board=board)
  assert list(r)==[path+':'+band] and r[path+':'+band]['channels'],r
 print('PASS: actual schema discovery; conventional baseline unchanged; SDK leading-zero/sparse/reordered names; absent/empty/invalid numeric fallback; board/sysfs keys and both PCI radios')

 shell_path=repo/'feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh'
 shell=shell_path.read_text();fn=shell[shell.index('miami_phy_by_path() {'):shell.index('mac80211_check_ap() {')]
 baseline=a.baseline_shell.read_text() if a.baseline_shell else subprocess.check_output(['git','show','0c862a7f:'+str(shell_path.relative_to(repo))],cwd=repo,text=True)
 baseline=baseline[baseline.index('find_phy() {'):baseline.index('mac80211_check_ap() {')]
 tree=work/'sysfs';sysfs=tree/'sys/class/ieee80211';sysfs.mkdir(parents=True)
 (tree/'tmp/sysinfo').mkdir(parents=True);boardname=tree/'tmp/sysinfo/board_name';boardname.write_text('cambiumnetworks,x7-35x\n')
 def add(name,idx,path):
  p=sysfs/name;p.mkdir();device=tree/'sys/devices'/path;device.mkdir(parents=True,exist_ok=True);(p/'device').symlink_to(device);(p/'index').write_text(str(idx)+'\n')
 add('phy00',4,ahb);add('phy03',17,'platform/'+pci);add('phy01',9,'platform/'+pci)
 def shell_run(path,ok=True,expected=None,original=False,iwinfo='Usage: mock'):
  s=baseline if original else fn
  for old in ['/sys/class/ieee80211','/sys/devices/','/tmp/sysinfo/board_name']:s=s.replace(old,str(tree/old.lstrip('/'))+('/' if old.endswith('/') else ''))
  stubs="rename_board_phy_by_name() { :; }; rename_board_phy_by_path() { :; }; iwinfo() { printf '%s\\n' \"$IWINFO_RESULT\"; };\n"
  script=work/'resolver.sh';script.write_text(stubs+s+'\npath=$1; phy=; macaddr=; find_phy; result=$?; printf "%s\\n" "$phy"; exit "$result"\n')
  p=subprocess.run(['sh',str(script),path],capture_output=True,text=True,env={'PATH':__import__('os').environ['PATH'],'IWINFO_RESULT':iwinfo})
  assert (p.returncode==0)==ok,(path,p.stdout,p.stderr,p.returncode)
  if expected is not None:assert p.stdout.strip()==expected,(path,p.stdout)
  return p.returncode,p.stdout
 shell_run(ahb,expected='phy00');shell_run(ahb.removeprefix('platform/'),expected='phy00')
 shell_run(pci,expected='phy01');shell_run('platform/'+pci,expected='phy01');shell_run(pci+'+1',expected='phy03')
 for suffix in ['+2','+x','+01','+-1']:shell_run(pci+suffix,ok=False)
 (sysfs/'phy03/index').write_text('9\n');shell_run(pci,ok=False);shell_run(pci+'+1',ok=False)
 (sysfs/'phy03/index').write_text('bad\n');shell_run(pci,ok=False)
 (sysfs/'phy03/index').write_text('17\n')
 boardname.write_text('other,family\n')
 for path,ok,iw in [(ahb,True,'Usage: mock'),(pci+'+1',False,'Usage: mock'),(pci,True,'phy01')]:
  assert shell_run(path,ok=ok,iwinfo=iw)==shell_run(path,ok=ok,original=True,iwinfo=iw)
 print('PASS: actual Miami shell resolver; platform-normalized AHB and dual PCI ordinals by numeric index; invalid/ambiguous refusal; non-Miami full resolver baseline unchanged')
