#!/usr/bin/env python3
"""Execute full production health sender plus actual snapshot; mock transport/fs."""
from pathlib import Path
import re,sys,tempfile,subprocess
root,module,health=map(Path,sys.argv[1:4])
def pure(path):return re.sub(r'^import .*;\n','',re.sub(r'^#!.*\n','',path.read_text()),flags=re.M).replace('export function','function').replace('return { evaluate, snapshot, radio_facts, select_banks };','').replace('require(', 'mock_require(')
h='''let packets=[],written,stored={updated:time(),active:[{code:'radio_failure',resource:'radio2',severity:'critical',reason:'configured_radio_down',band:'6G'}],monitoring:{storage:'available'}};
let fs={readfile:()=>sprintf('%J',stored),glob:()=>[],stat:()=>null,open:()=>({write:x=>{written=x;return true;},close:()=>true})};
let libuci={cursor:()=>({load:()=>true,get_all:()=>({})})};
let libubus={connect:()=>({call:(object,method,payload)=>{if(object=='system')return {memory:{total:100,available:50}};if(object=='network.interface')return {interface:[]};if(object=='ucentral'&&method=='health'){push(packets,payload);return {};};return {};}})};
'''
t='''assert(length(packets)==1&&packets[0].data.faults.active[0].band=='6G','actual health carries structured radio fault');assert(packets[0].sanity==100,'critical monitor must not trigger existing WiFi healing');assert(written.data.faults.active[0].reason=='configured_radio_down','persisted existing health snapshot carries cause');stored={updated:time(),active:[],monitoring:{storage:'available'}};main();assert(!length(packets[1].data.faults.active),'health reports recovered current state');printf('PASS 4 actual full health sender controls\\n');'''
p=Path(tempfile.mkdtemp(prefix='fault-health-packet-'))/'test.uc';p.write_text(h+pure(module)+"function mock_require(name){if(name=='faults')return {snapshot};if(name=='dfs_cac')return {collect:()=>({sections:{},radios:{}})};return {};}\n"+pure(health)+t)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],text=True,capture_output=True);print(r.stdout,r.stderr);raise SystemExit(r.returncode)
