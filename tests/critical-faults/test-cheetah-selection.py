#!/usr/bin/env python3
"""Actual common ucode bank selection and reporting with Cheetah adapter data."""
from pathlib import Path
import os,json,tempfile,subprocess,shlex,hashlib
here=Path(__file__).resolve().parent;source=Path(os.environ.get('CHEETAH_FAULT_SOURCE',str(here.parents[1]/'feeds/ucentral/ucentral-state/files/faults.uc')));profile=json.loads(Path(os.environ.get('CHEETAH_PROFILE_SOURCE',str(here.parents[1]/'feeds/ucentral/ucentral-state/files/storage-canary.json'))).read_text());s='let common=(function(){\n'+source.read_text().replace("let fs = require('fs');",'let fs={readfile:()=>null};').replace("import * as fs from 'fs';",'let fs={readfile:()=>null};')+'\n})();let evaluate=common.evaluate,select_banks=common.select_banks;\n' if 'return { evaluate, snapshot, radio_facts, select_banks };' in source.read_text() else source.read_text().replace("import * as fs from 'fs';",'let fs={readfile:()=>null};').replace('export function','function')
t=r'''
let count=0;function check(ok,name){assert(ok,name);count++;}
let profiles=PROFILE;
let records=[{index:18,name:'rootfs',type:'nand',size:100663296,erase:131072,write:2048,offset:524288},{index:19,name:'rootfs_1',type:'nand',size:100663296,erase:131072,write:2048,offset:101187584},{index:20,name:'0:NVRAM',type:'nand',size:49807360,erase:131072,write:2048,offset:201850880}];
let board='cambiumnetworks,xv2-21x';let a=select_banks(profiles,board,records);
check(a.status=='qualified'&&length(a.banks)==2&&a.banks[0].index==18&&a.banks[1].index==19,'Cheetah exact bank selection, excludes NVRAM');
records[0].index=2;records[1].index=3;a=select_banks(profiles,board,records);check(a.banks[0].index==2&&a.banks[1].index==3,'runtime MTD indexes resolved, not pinned');
records[1].offset=0;a=select_banks(profiles,board,records);check(a.status=='unavailable'&&!length(a.banks),'wrong offset unavailable');records[1].offset=101187584;
records[1].write=4096;a=select_banks(profiles,board,records);check(a.status=='unavailable'&&!length(a.banks),'wrong page geometry unavailable');records[1].write=2048;
push(records,{...records[1],index:33});a=select_banks(profiles,board,records);check(a.status=='unavailable'&&!length(a.banks),'ambiguous bank unavailable');pop(records);
a=select_banks(profiles,'cambiumnetworks,xv2-22h',records);check(a.status=='unsupported'&&!length(a.banks),'unqualified sibling unsupported');
let base={mtd:[{index:2,ecc_failures:0,corrected_bits:0}],mounts:[],canary:[{mtd:3,status:'checked',samples:[{peb:249,bad:true},{peb:250,ok:true}]}],adapter:{status:'qualified'}};
a=evaluate(base,null,100);check(!length(a.active),'baseline good/free EC and bad block skip');
base.mtd[0].corrected_bits=100;a=evaluate(base,a,160);check(!length(a.active),'corrected ECC alone not critical');
base.mtd[0].ecc_failures=1;a=evaluate(base,a,220);check(a.active[0].code=='storage_uncorrectable_ecc','Cheetah uncorrectable delta current');
a=evaluate(base,a,900);check(!length(a.active),'quiet period recovery');
base.canary[0].samples[1].ok=false;a=evaluate(base,a,960);check(!length(a.active),'canary debounce');a=evaluate(base,a,1020);check(a.active[0].code=='storage_canary'&&a.active[0].resource=='mtd3/PEB250','current Cheetah canary fault serialized');
let lost=evaluate(null,a,1080);check(lost.monitoring.storage=='unavailable'&&length(lost.active)==1,'probe missing unavailable preserves current fault');
base.canary[0].samples[1].ok=true;a=evaluate(base,a,1140);check(!length(a.active),'current fault clears on actual recovery');
base.canary=[{mtd:3,status:'unavailable'}];base.adapter={status:'unavailable',reason:'bank_geometry'};a=evaluate(base,a,1200);check(a.monitoring.adapter.status=='unavailable'&&a.monitoring.canary[0].status=='unavailable','unsupported monitoring explicit not healthy');
printf('{"passed":true,"count":%d}\n',count);
'''.replace('PROFILE',json.dumps(profile))
with tempfile.TemporaryDirectory(prefix='cheetah-fault-select.') as td:
 p=Path(td)/'test.uc';p.write_text(s+t);cmd=shlex.split(os.environ['OEM_TEST_UCODE']);r=subprocess.run(cmd+[str(p)],text=True,capture_output=True);assert r.returncode==0,r.stderr;d=json.loads(r.stdout);d.update(tested_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Actual shared source selection/evaluator on Cheetah geometry and fault facts. Synthetic records; no AP, raw MTD reads, firmware build or competing core.');print(json.dumps(d,indent=2))
