#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real target BusyBox + procd preload; configfs consumes each write."""
import argparse,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--helper',type=Path);p.add_argument('--qemu',default='qemu-aarch64');p.add_argument('--output',type=Path);a=p.parse_args()
repo=Path(__file__).resolve().parents[2]
helper=a.helper or repo/'feeds/tip/cambium-miami-capture/files/miami-netconsole-setup'
source=helper.read_text();match=re.search(r'if ! (.+) > "\$base/\$1"; then',source);assert match,'setting writer not found'
writer=match[1];root=a.root.resolve();assert(root/'lib/libsetlbf.so').is_file()
rows=[]
def run(label,command,value,preload):
 argv=[a.qemu,'-strace','-L',str(root)]
 if preload:argv+=['-E','LD_PRELOAD='+str(root/'lib/libsetlbf.so')]
 else:argv+=['-U','LD_PRELOAD']
 argv += [str(root/'bin/busybox'),'ash','-c','set -- setting "$1"; '+command,'capture-writer-test',value]
 r=subprocess.run(argv,capture_output=True,text=True);assert r.returncode==0,(label,r.stderr)
 assert r.stdout==value+'\n',(label,r.stdout)
 sizes=[int(m.group(1))for line in r.stderr.splitlines()if(m:=re.search(r'write(?:v)?\(1,.*\) = ([0-9]+)$',line))]
 assert sum(sizes)==len(r.stdout.encode()),(label,sizes)
 at=0;chunks=[]
 for size in sizes:chunks.append(r.stdout[at:at+size]);at+=size
 rows.append({'case':label,'procd_preload':preload,'write_sizes':sizes,'chunks':chunks})
 return chunks
legacy='printf \'%s\\n\' "$2"'
assert run('legacy-manual-shell',legacy,'up0v0',False)==['up0v0\n']
assert run('legacy-procd-negative',legacy,'up0v0',True)==['up0v0','\n']
assert run('legacy-MAC-negative',legacy,'02:00:00:00:00:01',True)==['02:00:00:00:00:01','\n']
# These are protocol requirements, independently of the selected implementation.
for attr,value in [('dev_name','up0v0'),('local_ip','192.0.2.10'),('remote_ip','192.0.2.20'),('remote_mac','02:00:00:00:00:01'),('remote_port','6666'),('local_port','6665'),('enabled','1')]:
 assert run('fixed-'+attr,writer,value,True)==[value+'\n'],attr
 assert 'write_setting '+attr+' 'in source,attr
assert 'read-back mismatch'in source
receipt={'status':'PASS','cases':rows,'negative_control':'Released printf succeeds in manual shell, splits value/newline under real procd preload; configfs treats newline as a separate replacement','fixed_writer':writer,'root':str(root),'helper':str(helper)}
if a.output:a.output.write_text(json.dumps(receipt,indent=2)+'\n')
print('PASS: 10 target BusyBox/procd write cases; legacy negative and all seven complete setting writes')
