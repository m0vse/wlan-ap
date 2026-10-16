from pathlib import Path
import tempfile,shutil,json,re,subprocess,sys,os
import argparse,copy
parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path);parser.add_argument('--qemu',default='/usr/bin/qemu-aarch64');parser.add_argument('--patch',type=Path);parser.add_argument('--regulatory',type=Path);args=parser.parse_args()
root=args.root.resolve();e=Path(__file__).resolve().parent
work=Path(tempfile.mkdtemp(prefix='shared-band-ssid-'));share=work/'usr/share/ucentral';share.parent.mkdir(parents=True);shutil.copytree(root/'usr/share/ucentral',share)
regulatory=args.regulatory or e.parents[1]/'feeds/ucentral/ucentral-schema/files/usr/share/ucentral/wifi/regulatory.uc'
assert __import__('hashlib').sha256(regulatory.read_bytes()).hexdigest()=='b1dccbacc857fcee948bfefc5624ec7d2f5922e82b08f308820ee7654044fed9'
shutil.copy2(regulatory,share/'wifi/regulatory.uc')
for rel in ['etc/config','etc/ucentral','tmp','bin']:(work/rel).mkdir(parents=True,exist_ok=True)
for p in (root/'etc/config').iterdir():
 if p.is_file():shutil.copy2(p,work/'etc/config'/p.name)
cap=json.loads((e/'capabilities.json').read_text());(work/'etc/ucentral/capabilities.json').write_text(json.dumps(cap));shutil.copy2(e/'board.json',work/'etc/board.json');(work/'etc/ucentral/ucentral.defaults').write_text('{"country":"GB"}')
wireless=[]
for path,phy in cap['wifi'].items():
 name='radio'+str(phy['wiphy_name'].replace('phy',''));wireless += ['config wifi-device '+name," option type 'mac80211'"," option path '"+path+"'"," option band '"+phy['band'][0].lower()+"'"]
(work/'etc/config/wireless').write_text('\n'.join(wireless)+'\n')
for p in share.rglob('*.uc'):
 s=p.read_text()
 s=re.sub(r'/(?:usr/share/ucentral/|etc/|sys/|tmp/)',lambda m:str(work)+m.group(),s)
 s=s.replace('uci.cursor()',"uci.cursor("+repr(str(work/'etc/config'))+","+repr(str(work/'tmp/uci'))+")")
 p.write_text(s)
# Use sanitized model-shape fixtures; hardware reads are outside rendering.
(share/'wifi/phy.uc').write_text('return '+json.dumps(cap['wifi'])+';\n')
fw=work/'bin/fw_printenv';fw.write_text('#!/bin/sh\necho developer=0\n');fw.chmod(0o755)
program=work/'render.uc';program.write_text("modules.ubus={connect:()=>({call:()=>null})}; let fs=require('fs'); import * as schema from 'schemareader'; let renderer=require('renderer');let cfg=json(fs.readfile(ARGV[0]));let errors=[];let state=schema.validate(cfg,errors);assert(state,sprintf('%J',errors));let batch=renderer.render(state,errors);assert(length(batch),sprintf('%J',errors));assert(!length(filter(errors,x=>substr(x,0,3)=='[E]')),sprintf('%J',errors));print(batch);\n")
config={'uuid':12345,'unit':{'hostname':'fixture'},'radios':[{'band':'2G','channel':'auto','channel-width':20,'country':'GB','enable':False},{'band':'5G-lower','channel':36,'channel-width':80,'country':'GB','mimo':'4x4'},{'band':'5G-upper','channel':149,'channel-width':80,'country':'GB','mimo':'4x4'}],'interfaces':[{'name':'LAN','role':'upstream','services':['ssh','lldp'],'ethernet':[{'select-ports':['WAN'],'multicast':True}],'ipv4':{'addressing':'dynamic'},'ssids':[{'name':'Fixture','wifi-bands':['5G'],'encryption':{'proto':'psk2','key':'SyntheticRegression123'},'bss-mode':'ap'}]}]}
(work/'input.json').write_text(json.dumps(config));env={**os.environ,'PATH':str(work/'bin')+':'+os.environ['PATH']}
cmd=[args.qemu,'-L',str(root),str(root/'usr/bin/ucode'),'-L',str(root/'usr/lib/ucode'),'-L',str(share/'*.uc'),str(program),str(work/'input.json')]
old=subprocess.run(cmd,env=env,text=True,capture_output=True);assert old.returncode==0,old.stderr
# Candidate template uses no absolute paths; install it into only the isolated copy.
patch=args.patch or e.parents[1]/'feeds/ucentral/ucentral-schema/patches/109-unique-ssid-sections-for-shared-band-phys.patch'
subprocess.run(['patch','--batch','--fuzz=0','-p2','-i',str(patch)],cwd=share,check=True,capture_output=True)
new=subprocess.run(cmd,env=env,text=True,capture_output=True);assert new.returncode==0,new.stderr
for label,result in [('old',old),('new',new)]:
 matches=re.findall(r"set wireless\.([^\.\s]+)\.device='?([^'\n\s]+)",result.stdout);print(label,matches)
print('work',work)

import copy
cases=[('generic',['5G'],1,2),('two-ssids',['5G'],2,4),('explicit-split',['5G-lower','5G-upper'],1,2),('overlap',['5G','5G-lower','5G-upper'],1,2),('lower-only',['5G-lower'],1,1),('upper-only',['5G-upper'],1,1)]
for label,bands,number,expected in cases:
 cfg=copy.deepcopy(config); ssid=cfg['interfaces'][0]['ssids'][0];ssid['wifi-bands']=bands
 cfg['interfaces'][0]['ssids']=[{**copy.deepcopy(ssid),'name':'Fixture'+str(i)} for i in range(number)]
 (work/'input.json').write_text(json.dumps(cfg));result=subprocess.run(cmd,env=env,text=True,capture_output=True)
 assert result.returncode==0,(label,result.stderr)
 matches=re.findall(r"set wireless\.([^\.\s]+)\.device='?([^'\n\s]+)",result.stdout)
 assert len(matches)==expected,(label,matches)
 assert len(set(n for n,d in matches))==expected,(label,matches)
 assert all('null' not in n for n,d in matches),(label,matches)
 print(label,'PASS',matches)

# Apply generated batches with the actual target UCI library, not a text parser.
query=work/'query.uc'
query.write_text("let u=require('uci').cursor(ARGV[0],ARGV[1]);let a=[];u.foreach('wireless','wifi-iface',s=>push(a,s));print(sprintf('%J',a));")
def apply_batch(batch):
 stage=Path(tempfile.mkdtemp(prefix='uci-',dir=work));cfg=stage/'config';shutil.copytree(work/'etc/config',cfg);saved=stage/'saved';saved.mkdir()
 cli=[args.qemu,'-L',str(root),str(root/'sbin/uci'),'-c',str(cfg),'-t',str(saved)]
 result=subprocess.run(cli+['batch'],input='\n'.join(line for line in batch.splitlines() if re.match(r'^(set|add|add_list|del_list|delete) wireless(?:[ .])',line))+'\ncommit wireless\n',env=env,text=True,capture_output=True)
 assert result.returncode==0,result.stderr
 assert not result.stderr.strip(),result.stderr
 result=subprocess.run(cmd[:cmd.index(str(program))]+[str(query),str(cfg),str(saved)],env=env,text=True,capture_output=True)
 assert result.returncode==0,result.stderr
 return json.loads(result.stdout)
def devices(batch):return {s['.name']:s['device'] for s in apply_batch(batch)}
assert list(devices(old.stdout).values())==['radio3'],'negative control must reproduce lost upper SSID'
assert sorted(devices(new.stdout).values())==['radio1','radio3']
print('actual-UCI old-negative and fixed-dual PASS')
for label,bands,number,expected in cases:
 cfg=copy.deepcopy(config);ssid=cfg['interfaces'][0]['ssids'][0];ssid['wifi-bands']=bands
 cfg['interfaces'][0]['ssids']=[{**copy.deepcopy(ssid),'name':'Fixture'+str(i)} for i in range(number)]
 (work/'input.json').write_text(json.dumps(cfg));result=subprocess.run(cmd,env=env,text=True,capture_output=True);assert result.returncode==0,result.stderr
 assert len(devices(result.stdout))==expected,(label,devices(result.stdout))
 print('actual-UCI',label,'PASS')

cfg=copy.deepcopy(config);cfg['interfaces'][0]['ssids'][0]['encryption']={'proto':'owe-transition'}
(work/'input.json').write_text(json.dumps(cfg));result=subprocess.run(cmd,env=env,text=True,capture_output=True);assert result.returncode==0,result.stderr
entries=apply_batch(result.stdout);assert len(entries)==4
byname={s['.name']:s for s in entries}
for s in entries:
 peer=byname[s['owe_transition_ifname']];assert peer['device']==s['device'];assert peer['owe_transition_ifname']==s['.name']
assert sorted(s['device'] for s in entries)==['radio1','radio1','radio3','radio3']
print('actual-UCI split OWE reciprocal pairs PASS')

before=(share/'templates/interface/ssid.uc').read_text()
# Undo the candidate only in this disposable test tree for legacy comparisons.
subprocess.run(['patch','--batch','--fuzz=0','-R','-p2','-i',str(patch)],cwd=share,check=True,capture_output=True)
legacy=(share/'templates/interface/ssid.uc').read_text()
(share/'templates/interface/ssid.uc').write_text(before)

def hardware(wifi):
 (share/'wifi/phy.uc').write_text('return '+json.dumps(wifi)+';\n')
 active=copy.deepcopy(cap);active['wifi']=wifi;(work/'etc/ucentral/capabilities.json').write_text(json.dumps(active))
 lines=[]
 for path,phy in wifi.items():
  name=phy.get('fixture_section','radio'+phy['wiphy_name'].replace('phy',''))
  lines+=['config wifi-device '+name," option type 'mac80211'"," option path '"+path+"'"," option band '"+phy['band'][0].lower()+"'"]
  if 'radio_index' in phy:lines.append(" option radio '"+str(phy['radio_index'])+"'")
 (work/'etc/config/wireless').write_text('\n'.join(lines)+'\n')

def compare_legacy(label,cfg,expected):
 (work/'input.json').write_text(json.dumps(cfg));batches=[]
 for template in [legacy,before]:
  (share/'templates/interface/ssid.uc').write_text(template)
  result=subprocess.run(cmd,env=env,text=True,capture_output=True);assert result.returncode==0,(label,result.stderr);batches.append(result.stdout)
 assert [x for x in batches[0].splitlines() if x.strip()]==[x for x in batches[1].splitlines() if x.strip()],label+' legacy commands changed'
 assert len(devices(batches[1]))==expected,(label,devices(batches[1]))
 print(label,'identical legacy commands + actual-UCI PASS')

upper_path=next(p for p,v in cap['wifi'].items() if v['wiphy_name']=='phy1')
two_path=next(p for p,v in cap['wifi'].items() if v['wiphy_name']=='phy2')
upper=copy.deepcopy(cap['wifi'][upper_path]);two=copy.deepcopy(cap['wifi'][two_path])
hardware({upper_path:upper})
cfg=copy.deepcopy(config);cfg['radios']=[cfg['radios'][2]];cfg['radios'][0]['band']='5G'
compare_legacy('single-5G',cfg,1)
# Independent tri-band fixture, with MLO explicitly disabled.
six=copy.deepcopy(upper);six.update(wiphy_name='phy4',band=['6G'],channels=[1,5,9,13],frequencies=[5955,5975,5995,6015],dfs_channels=[],htmode=['HE20','HE40','HE80'])
hardware({upper_path:upper,two_path:two,'platform/fixture-six.wifi':six})
cfg=copy.deepcopy(config);cfg['radios']=[{'band':'2G','channel':1,'channel-width':20,'country':'GB'},{'band':'5G','channel':149,'channel-width':80,'country':'GB'},{'band':'6G','channel':1,'channel-width':80,'country':'GB'}]
cfg['interfaces'][0]['ssids'][0].update({'wifi-bands':['2G','5G','6G'],'mlo':False,'encryption':{'proto':'sae','key':'SyntheticRegression123','ieee80211w':'required'}})
compare_legacy('independent-tri-band-MLO-disabled',cfg,3)
# Explicit MLO remains rejected on Thor before any output.
cfg['interfaces'][0]['ssids'][0]['mlo']=True;cfg['interfaces'][0]['ssids'][0]['wifi-bands']=['5G','6G'];(work/'input.json').write_text(json.dumps(cfg))
for template in [legacy,before]:
 (share/'templates/interface/ssid.uc').write_text(template);result=subprocess.run(cmd,env=env,text=True,capture_output=True)
 assert result.returncode!=0 or not result.stdout.strip(),'Thor must not accept enabled MLO'
 assert 'MLO is not qualified on this model' in result.stderr,result.stderr
print('Thor enabled-MLO rejection unchanged PASS')
(share/'templates/interface/ssid.uc').write_text(before)
# Qualified synthetic Miami MLO fixture: driver-indexed links on one WIPHY.
cap['compatible']='cambium_x7-35x'
mfive=copy.deepcopy(upper);msix=copy.deepcopy(six)
for index,phy in enumerate([mfive,msix]):
 phy.update(mlo_support=True,radio_index=index,radio_index_source='driver',wiphy_name='phy1',fixture_section='radio'+str(index+1),htmode=['EHT20','EHT40','EHT80'])
hardware({'platform/fixture-mlo.wifi+0':mfive,'platform/fixture-mlo.wifi+1':msix})
cfg=copy.deepcopy(config);cfg['radios']=[{'band':'5G','channel':149,'channel-width':80,'channel-mode':'EHT','country':'GB'},{'band':'6G','channel':1,'channel-width':80,'channel-mode':'EHT','country':'GB'}]
cfg['interfaces'][0]['ssids'][0].update({'wifi-bands':['5G','6G'],'mlo':True,'encryption':{'proto':'sae','key':'SyntheticRegression123','ieee80211w':'required'}})
compare_legacy('qualified-MLO',cfg,2)
(work/'input.json').write_text(json.dumps(cfg));result=subprocess.run(cmd,env=env,text=True,capture_output=True);entries=apply_batch(result.stdout)
assert {s.get('mld') for s in entries}=={'ml0_0'}
print('qualified-MLO group/link identities retained PASS')
print('All shared-band renderer/UCI/MLO regressions PASS')
