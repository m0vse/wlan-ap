#!/usr/bin/env python3
"""Exercise exact connect_send with real native receipts; IO/transport is stubbed."""
from pathlib import Path
import argparse, subprocess, tempfile, hashlib, json

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
source=args.source
args.output.mkdir(parents=True,exist_ok=True)
s=(source/'proto.c').read_text()
start=s.index('void\nconnect_send(void)')
opening=s.index('{',start)
depth,end=1,opening+1
while depth:
    depth+=(s[end]=='{')-(s[end]=='}')
    end+=1
connect=s[start:end]
head=r'''
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <stdint.h>
#include <sys/stat.h>
#include <syslog.h>
#include "session_status.h"
#define UCENTRAL_CONFIG "/nonexistent-test-ucentral"
#define ULOG_DBG(...) ((void)0)
int proto;
char *password;
uint64_t uuid_active=100;
struct {char *serial,*firmware,*boot_cause;int recovery;} client={"test-serial","test-firmware","firmware-upgrade",0};
char emitted[64];bool capabilities_ok=true,drop_transport=true;unsigned writes,delivered;
void *proto_new_blob(const char *method) {(void)method;emitted[0]=0;return NULL;}
void blobmsg_add_string(void *p,const char *name,const char *value) {(void)p;if(!strcmp(name,"reason"))snprintf(emitted,sizeof(emitted),"%s",value);}
void blobmsg_add_u64(void *p,const char *n,uint64_t value) {(void)p;(void)n;(void)value;}
void blobmsg_add_u8(void *p,const char *n,unsigned value) {(void)p;(void)n;(void)value;}
void *blobmsg_open_table(void *p,const char *n) {(void)p;(void)n;return NULL;}
void blobmsg_close_table(void *p,void *c) {(void)p;(void)c;}
bool blobmsg_add_json_from_file(void *p,const char *path) {(void)p;(void)path;return capabilities_ok;}
void log_send(const char *message,int severity) {(void)message;(void)severity;}
void proto_send_blob(void) {writes++;if(!drop_transport)delivered++;}
'''
body=r'''
static void expect(const char *reason,const char *test) {
 connect_send();assert(!strcmp(emitted,reason));printf("PASS %s\n",test);
}
int main(void) {
 session_connected();expect("firmware-upgrade","first hello dropped retains first-process reason");
 assert(writes==1 && delivered==0 && client.boot_cause);
 session_disconnected();session_connected();drop_transport=false;
 expect("firmware-upgrade","retry after lost hello remains first-process reason");
 capabilities_ok=false;expect("firmware-upgrade","failed hello construction cannot consume first-process reason");
 capabilities_ok=true;session_received(101,1);
 struct session_receipt receipt=session_capture(101,1);
 session_applied(receipt,101,1,false);
 session_disconnected();session_connected();
 expect("firmware-upgrade","failed application never becomes socket reconnect");
 session_received(102,2);session_disconnected();session_connected();
 expect("firmware-upgrade","incomplete application never becomes socket reconnect");
 session_received(103,3);receipt=session_capture(103,3);
 session_applied(receipt,103,3,true);assert(session_has_completed_config());
 session_disconnected();session_connected();
 expect("socket","genuine completed application permits ordinary reconnect");
 assert(!client.boot_cause);
 session_disconnected();session_connected();expect("socket","repeated completed reconnect remains socket");
 session_received(104,4);assert(!session_has_completed_config());
 expect("socket","later pending request cannot resurrect consumed boot reason");
 /* A new process starts static-zero and receives the installed service's -b. */
 memset(&native_session,0,sizeof(native_session));client.boot_cause="unexpected-shutdown";
 session_connected();expect("unexpected-shutdown","new process cannot reuse old completed acceptance");
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='native-connect-reason-') as tmp:
    tmp=Path(tmp)
    (tmp/'fixture.c').write_text(head+connect+'\n'+body)
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(source),str(tmp/'fixture.c'),str(source/'session_status.c'),'-o',str(tmp/'fixture')],check=True)
    result=subprocess.check_output([str(tmp/'fixture')],text=True)
    assert len(result.splitlines())==9
    receipt={'cases':9,'output':result.splitlines(),'source_sha256':{n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in ['session_status.c','session_status.h','proto.c']},'limitations':__doc__}
    (args.output/'native-connect-reason-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(result,end='')
