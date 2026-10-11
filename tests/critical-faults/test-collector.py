#!/usr/bin/env python3
"""Execute actual collector and snapshot with module/syscall boundaries mocked."""
from pathlib import Path
import subprocess,sys,tempfile,re,json
root,module,collector,profiles=map(Path,sys.argv[1:5])
m=re.sub(r'^import .*;\n','',module.read_text(),flags=re.M).replace('export function','function').replace('return { evaluate, snapshot, radio_facts, select_banks };','')
s=re.sub(r'^#!.*\n','',collector.read_text());s=re.sub(r'^import .*;\n','',s,flags=re.M).replace('require(', 'mock_require(')
prefix='''let saved,cmds=[],logcalls=[],nl_calls=[],facts={mtd:[{index:2,ecc_failures:0,corrected_bits:4}],mounts:[{path:'/overlay',readonly:false,total_bytes:10000000,available_bytes:5000000}],canary:[{mtd:2,status:'checked',samples:[{peb:0,ok:true}]}]};
let fs={lstat:()=>({type:'directory',mode:0700,uid:0}),mkdir:()=>true,stat:()=>null,
 glob:path=>index(path,'/sys/class/mtd')==0?['/sys/class/mtd/mtd2','/sys/class/mtd/mtd27','/sys/class/mtd/mtd3']:[],
 readfile:path=>{
 if(path=='/tmp/sysinfo/board_name')return 'cambiumnetworks,x7-35x';
 if(path=='/etc/ucentral/storage-canary.json')return PROFILE;
 if(path=='/proc/uptime')return '1000.00';if(path=='/proc/meminfo')return 'MemTotal: 1000000 kB\\nMemAvailable: 500000 kB\\n';
 if(path=='/tmp/ucentral-faults/status.json')return saved;
 let x=match(path,/mtd([0-9]+)\\/(.*)$/);if(!x)return null;
 let rec={'2':{name:'rootfs',type:'nand',offset:'786432',size:'100663296',erasesize:'131072',writesize:'2048'},'3':{name:'rootfs_1',type:'nand',offset:'101449728',size:'100663296',erasesize:'131072',writesize:'2048'},'27':{name:'rootfs',type:'ubi',size:'100663296',erasesize:'126976',writesize:'2048'}};
 return rec[x[1]]?.[x[2]];
 },popen:cmd=>{push(cmds,cmd);return {read:()=>index(cmd,'storage-probe')>=0?sprintf('%J',facts):'[ 10.00] SQUASHFS error: old\\n',close:()=>0};},
 open:()=>({write:text=>{saved=text;return length(text);},close:()=>true}),rename:()=>true};
let libuci={cursor:()=>({load:()=>true,get_all:()=>({})})};let libubus={connect:()=>({call:()=>({})})};
let ulog_open=()=>null,ulog=(...x)=>push(logcalls,x),ULOG_SYSLOG=0,LOG_DAEMON=0,LOG_WARNING=4,LOG_INFO=6;
'''.replace('PROFILE',json.dumps(profiles.read_text()))
text=prefix+m+"function mock_require(x){if(x=='faults')return {evaluate,radio_facts,select_banks};if(x=='nl80211')return {const:{NL80211_CMD_GET_INTERFACE:1,NLM_F_DUMP:2},request:(cmd,flags)=>{push(nl_calls,[cmd,flags]);return [];}};return {collect:()=>({sections:{},radios:{}})};}\n"+s+'''
let checks=0;function check(x,n){assert(x,n);checks++;}
let result=json(saved);check(result.monitoring.radio=='available','read-only kernel metadata capability available');check(length(nl_calls)==1&&nl_calls[0][0]==1&&nl_calls[0][1]==2,'GET_INTERFACE dump only, no scan request');check(result.monitoring.storage=='available'&&!length(result.active),'actual collector serializes idle facts');
check(result.monitoring.adapter.status=='qualified','physical banks qualified with duplicate gluebi excluded');
check(index(cmds[0],'2 100663296 131072')>=0&&index(cmds[0],'3 100663296 131072')>=0,'exact physical probe args');
check(!length(result.active),'stale kernel error ignored');
let fresh=snapshot();check(!length(fresh.active)&&fresh.monitoring.storage=='available','health snapshot actual serialization');
saved=sprintf('%J',{...result,updated:time()-181});check(snapshot().monitoring.reason=='collector_stale','stale reported unavailable');
printf('PASS %d actual collector/health snapshot controls\\n',checks);
'''
p=Path(tempfile.mkdtemp(prefix='fault-collector-'))/'test.uc';p.write_text(text)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],text=True,capture_output=True);print(r.stdout,r.stderr);raise SystemExit(r.returncode)
