#!/usr/bin/env python3
"""Run actual production fault evaluator under target ucode; mock external fs only."""
from pathlib import Path
import subprocess,sys,tempfile
root,source=map(Path,sys.argv[1:3])
s=source.read_text().replace("import * as fs from 'fs';",'let fs={readfile:()=>null};').replace('export function','function').replace('return { evaluate, snapshot, radio_facts, select_banks };','')
t=r'''
let checks=0;function check(x,n){assert(x,n);checks++;}
let base={mtd:[{index:2,ecc_failures:0,corrected_bits:0}],mounts:[{path:'/overlay',readonly:false,total_bytes:10000000,available_bytes:5000000}],canary:[],radios:[],radio_monitoring:'available'};
let a=evaluate(base,null,100);check(!length(a.active),'healthy baseline');
base.mtd[0].corrected_bits=100;a=evaluate(base,a,160);check(!length(a.active),'corrected ECC not critical');
base.mtd[0].ecc_failures=1;a=evaluate(base,a,220);check(a.active[0].code=='storage_uncorrectable_ecc','uncorrectable delta');
a=evaluate(base,a,900);check(!length(a.active),'ECC quiet period recovers');
base.mounts[0].readonly=true;a=evaluate(base,a,960);check(!length(a.active),'readonly debounced');a=evaluate(base,a,1020);check(a.active[0].code=='storage_readonly','readonly critical');
base.mounts[0].readonly=false;a=evaluate(base,a,1080);check(!length(a.active),'readonly recovers');
base.canary=[{mtd:3,status:'checked',samples:[{peb:249,bad:true},{peb:250,ok:false,error:0}]}];a=evaluate(base,a,1140);check(!length(a.active),'EC debounce');a=evaluate(base,a,1200);check(length(a.active)==1&&a.active[0].reason=='invalid_ec_header','bad PEB skipped; invalid EC alerts');
let lost=evaluate(null,a,1260);check(length(lost.active)==1&&lost.monitoring.storage=='unavailable','unavailable collector does not falsely clear');
base.canary[0].samples[1].ok=true;a=evaluate(base,a,1320);check(!length(a.active),'EC recovery');
base.mounts[0].available_bytes=0;a=evaluate(base,a,1380);a=evaluate(base,a,1440);check(a.active[0].code=='storage_exhausted','space exhaustion');base.mounts[0].available_bytes=5000000;
base.mounts[0].total_inodes=0;base.mounts[0].available_inodes=0;a=evaluate(base,a,1500);a=evaluate(base,a,1560);check(!length(a.active),'unsupported inode accounting ignored');
base.mounts[0].total_inodes=100;base.mounts[0].available_inodes=1;a=evaluate(base,a,1620);a=evaluate(base,a,1680);check(a.active[0].code=='storage_inode_exhausted','inodes critical');
let cfg={r:{'.type':'wifi-device',band:'6G'},s:{'.type':'wifi-iface',device:'r',ssid:'test',mode:'ap'}};
check(length(radio_facts(cfg,{r:{up:true,interfaces:[{section:'s'}]}},{}))==0,'radio healthy');
check(length(radio_facts(cfg,{r:{up:false,pending:true}},{}))==0,'pending not fault');
check(length(radio_facts(cfg,{r:{up:false}}, {radios:{r:true}}))==0,'CAC not fault');
cfg.s.disabled='1';check(!length(radio_facts(cfg,{},{})),'disabled BSS not fault');delete cfg.s.disabled;
let r=radio_facts(cfg,{r:{up:true,interfaces:[]}},{});check(r[0].reason=='configured_bss_unavailable'&&r[0].band=='6G','BSS reason');
check(radio_facts(cfg,{}, {})[0].reason=='configured_radio_absent','missing configured radio reason');
check(radio_facts(cfg,{r:{up:false}}, {})[0].reason=='configured_radio_down','failed start reason');
let serving={r:{up:true,interfaces:[{section:'s',ifname:'ap-test'}]}};
let observed={'ap-test':{mode:'ap',ssid:'test',phy:3,has_channel:false}};
let no_channel=radio_facts(cfg,serving,{},observed);
check(no_channel[0].reason=='configured_bss_no_channel'&&no_channel[0].phy==3,'actual interface no-channel cause and PHY');
observed['ap-test'].has_channel=true;check(!length(radio_facts(cfg,serving,{},observed)),'actual channel recovery');
check(radio_facts(cfg,serving,{}, {})[0].reason=='configured_bss_unavailable','kernel interface absent despite framework up');
observed['ap-test'].has_channel=false;check(!length(radio_facts(cfg,serving,{sections:{s:true},radios:{}},observed)),'fresh exact BSS CAC excludes no-channel');

base.mounts=[];base.mtd[0].ecc_failures=0;base.radios=r;a=evaluate(base,null,1800);a=evaluate(base,a,1860);check(a.active[0].code=='radio_failure','radio debounce');base.radios=[];a=evaluate(base,a,1920);check(!length(a.active),'radio recovery');
printf('PASS %d actual evaluator controls\n',checks);
'''
p=Path(tempfile.mkdtemp(prefix='critical-fault-eval-'))/'test.uc';p.write_text(s+t)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],text=True,capture_output=True)
print(r.stdout,r.stderr);raise SystemExit(r.returncode)
