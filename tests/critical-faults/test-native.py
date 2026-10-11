#!/usr/bin/env python3
"""Exercise native production probe with ioctl/pread device boundaries mocked."""
from pathlib import Path
import subprocess,tempfile,json,sys,os
src=Path(sys.argv[1]).resolve();w=Path(tempfile.mkdtemp(prefix='native-fault-'));root=w/'root'
for name in ('tmp','dev','proc','sys/class/mtd/mtd3'):(root/name).mkdir(parents=True,exist_ok=True)
for k,v in {'type':'nand','name':'rootfs_1','ecc_failures':'0','corrected_bits':'0'}.items():(root/'sys/class/mtd/mtd3'/k).write_text(v)
(root/'proc/mounts').write_text('');(root/'dev/mtd3ro').write_bytes(b'')
h=w/'harness.c';h.write_text(r'''
#define _GNU_SOURCE
#include <sys/types.h>
#include <stdarg.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <mtd/mtd-user.h>
static int mock_ioctl(int fd,unsigned long cmd,...) {
 (void)fd;va_list ap;va_start(ap,cmd);void *p=va_arg(ap,void*);va_end(ap);
 if(cmd==MEMGETINFO) {struct mtd_info_user *i=p;memset(i,0,sizeof(*i));i->type=MTD_NANDFLASH;i->size=getenv("INFO_SIZE")?strtoul(getenv("INFO_SIZE"),NULL,10):100663296;i->erasesize=131072;i->writesize=2048;return 0;}
 if(cmd==MEMGETBADBLOCK) {
  if(getenv("NO_BAD_IOCTL")){errno=ENOTSUP;return -1;}
  return *(loff_t*)p==249*131072LL;
 }
 fprintf(stderr,"FORBIDDEN ioctl %lu\n",cmd);abort();
}
static ssize_t mock_pread(int fd,void *p,size_t n,off_t off) {
 (void)fd;memset(p,0xff,n);
 if(getenv("READ_FAIL")){errno=EIO;return -1;}
 if(!getenv("BROKEN"))memcpy(p,"UBI#",4);
 fprintf(stderr,"read:%lld:%zu\n",(long long)off,n);return n;
}
#define ioctl mock_ioctl
#define pread mock_pread
#define STORAGE_ROOT "__TEST_ROOT__"
#include "__PROD_SOURCE__"
'''.replace('__TEST_ROOT__',str(root)).replace('__PROD_SOURCE__',str(src)))
exe=w/'probe';subprocess.run(['cc','-Wall','-Wextra','-Werror','-O2','-o',str(exe),str(h)],check=True)
checks=0
def run(flags={},size=100663296,pebs="249,250,251"):
 global checks
 env=os.environ.copy();env.update(flags)
 p=subprocess.run([str(exe),'3',str(size),'131072',pebs],env=env,capture_output=True,text=True,check=True)
 return json.loads(p.stdout),p.stderr
r,log=run();assert r['canary'][0]['status']=='checked';assert r['canary'][0]['samples'][0]['bad'];assert 'read:32636928' not in log;checks+=1
r,log=run({'NO_BAD_IOCTL':'1'});assert r['canary'][0]['status']=='checked';checks+=1 # cached MEMGETBADBLOCK list
r,log=run({'BROKEN':'1'});assert r['canary'][0]['status']=='checked' and not r['canary'][0]['samples'][1]['ok'];checks+=1
r,log=run({'READ_FAIL':'1'});assert r['canary'][0]['samples'][1]['error']==5;checks+=1
(root/'tmp/ucentral-storage-probe/mtd3').unlink();r,log=run({'BROKEN':'1'});assert r['canary'][0]['status']=='unavailable';checks+=1
(root/'tmp/ucentral-storage-probe/mtd3').unlink();r,log=run({'NO_BAD_IOCTL':'1'});assert r['canary'][0]['status']=='unavailable';checks+=1
assert 'FORBIDDEN' not in log;checks+=1
(root/'sys/class/mtd/mtd3/name').write_text('rootfs0')
r,log=run({'INFO_SIZE':'46137344'},size=46137344,pebs='0,127,249,255');assert r['canary'][0]['status']=='checked' and r['canary'][0]['samples'][2]['bad'];checks+=1
r,log=run({'INFO_SIZE':'47185920'},size=46137344,pebs='0,127,255');assert r['canary'][0]['status']=='unavailable';checks+=1
print(f'PASS {checks} native read-only/bad-cache/format controls')
