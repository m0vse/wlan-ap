#!/usr/bin/env python3
"""Inspect the real binding's encoded SET_WIPHY without sending it.

The separately compiled LD_PRELOAD interceptor exits at send time. This needs
Linux nl80211 family discovery but sends no power request. --ssh-target is an
explicit opt-in to run installed target ucode; files must already be staged.
Never substitute a guessed UAPI constant when building the interceptor.
"""
import argparse,json,subprocess,shlex
p=argparse.ArgumentParser()
p.add_argument('--ucode',required=True)
p.add_argument('--old-module',required=True)
p.add_argument('--new-module',required=True)
p.add_argument('--interceptor',required=True)
p.add_argument('--ssh-target')
p.add_argument('--ssh-option',action='append',default=[])
a=p.parse_args()
count=0
for module,link,expected in [(a.old_module,0,0),(a.old_module,1,0),(a.new_module,0,1),(a.new_module,1,1),(a.new_module,7,1),(a.new_module,15,1),(a.new_module,None,0)]:
 attrs={'wiphy':0x7fffffff,'wiphy_tx_power_setting':2,'wiphy_tx_power_level':1200}
 if link is not None:attrs['mlo_link_id']=link
 code='let n=require("nl80211"); let r=n.request(n.const.NL80211_CMD_SET_WIPHY,n.const.NLM_F_ACK,'+json.dumps(attrs)+'); printf("%J\\n",{unexpected_return:r,error:n.error()});'
 cmd=['env','LD_PRELOAD='+a.interceptor,a.ucode,'-L',module,'-L','/usr/lib/ucode','-e',code]
 if a.ssh_target:cmd=['ssh','-T','-o','BatchMode=yes',*[x for o in a.ssh_option for x in ['-o',o]],a.ssh_target,shlex.join(cmd)]
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
 assert result.returncode==0,(result.returncode,result.stderr)
 assert 'RRM_CODEC_INTERCEPT_ACTIVE' in result.stderr,result.stderr
 assert 'cannot be preloaded' not in result.stderr and 'Error loading shared library' not in result.stderr,result.stderr
 row=json.loads(result.stdout)
 assert row.get('transmitted')is False and row['count']==expected and row['ack']is True,row
 if expected:assert row['bytes']==1 and row['value']==link,row
 print(json.dumps({'module':'old'if module==a.old_module else'fixed','requested_link':link,'encoded':row}));count+=1
print(f'PASS {count} real native codec controls; old-field omission negative, explicit 0/1/7/15, legacy absent; no SET transmitted')
