#!/usr/bin/env python3
"""Exercise actual native callbacks/session code; compile a test, not firmware."""
from pathlib import Path
import argparse,json,re,subprocess,tempfile,shutil,hashlib

def function(source,name):
    start=re.search(r'^'+re.escape(name)+r'\(',source,re.M).start()
    opening=source.index('{',start);depth=1;i=opening+1
    while depth:
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    return source[start:i]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('native_source',type=Path);ap.add_argument('repo',type=Path);args=ap.parse_args()
    work=Path(tempfile.mkdtemp(prefix='native-deferred-'))
    try:
        for n in ('apply.c','task.c','session_status.c','session_status.h','proto.c'):
            shutil.copyfile(args.native_source/n,work/n)
        subprocess.run(['patch','--fuzz=0','-p1','-d',str(work),'-i',str((args.repo/'feeds/ucentral/ucentral-client/patches/005-deferred-configuration-outcome.patch').resolve())],check=True,capture_output=True)
        apply=(work/'apply.c').read_text();task=(work/'task.c').read_text();proto=(work/'proto.c').read_text()
        struct=task[task.index('struct ucentral_task {'):task.index('};',task.index('struct ucentral_task {'))+2]
        c=r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include "session_status.h"
#include "apply-status.h"
struct task;
struct runqueue {int unused;};
struct uloop_process {int unused;};
struct runqueue_task {int cancelled;};
struct runqueue_process {struct runqueue_task task;struct uloop_process proc;};
struct uloop_timeout {void(*cb)(struct uloop_timeout*);};
struct task {int cancelled,periodic;void*t;void(*complete)(struct task*,time_t,uint32_t,int);};
static struct runqueue queue;
static int reloads, timers, errors, infos;
static int apply_pending;
static time_t uuid_active=100,uuid_applied=100;
struct blob_attr {const char*name;const char*value;struct blob_attr*children,*next;};
struct blob_buf {int unused;};
static struct blob_buf result;
static uint32_t wire_id;static time_t wire_uuid;static int wire_count,wire_attributes;
static struct blob_attr wire[8];
#define blobmsg_for_each_attr(b,a,rem) for(b=(a)->children;b;b=b->next)
static void*result_new_blob(uint32_t id,time_t uuid){wire_id=id;wire_uuid=uuid;return NULL;}
static void*blobmsg_open_table(struct blob_buf*b,const char*n){return NULL;}
static void blobmsg_close_table(struct blob_buf*b,void*t){}
static void blobmsg_add_blob(struct blob_buf*b,struct blob_attr*a){wire[wire_attributes++]=*a;}
static void result_send_blob(void){wire_count++;}
#define container_of(p,t,m) ((t*)((char*)(p)-offsetof(t,m)))
#define ULOG_INFO(...) (++infos)
#define ULOG_ERR(...) (++errors)
static void config_init(int a,uint32_t id){reloads++;}
static void task_delay(struct uloop_timeout*d){}
static void uloop_timeout_set(struct uloop_timeout*d,int ms){timers++;}
static void task_complete(struct runqueue*,struct runqueue_task*);
static void runqueue_task_complete(struct runqueue_task*t){task_complete(&queue,t);}
'''+struct+'\nvoid\n'+function(proto,'result_send')+'\nstatic void\n'+function(apply,'apply_complete_cb')+'\nstatic struct task apply_task={.complete=apply_complete_cb};\nstatic void\n'+function(task,'task_complete')+'\nstatic void\n'+function(task,'runqueue_proc_cb')+r'''
static void check(int code,bool cancelled,bool success,bool deferred) {
    session_connected();session_received(200,99);
    struct ucentral_task*t=calloc(1,sizeof(*t));
    t->uuid=200;t->id=99;t->task=&apply_task;t->session=session_capture(200,99);
    t->proc.task.cancelled=cancelled;
    apply_task.t=t;apply_task.periodic=0;apply_pending=1;
    reloads=timers=errors=infos=0;uuid_active=uuid_applied=100;wire_count=wire_attributes=0;
    if(deferred){
        struct blob_attr reboot={.name="reboot_required",.value="true"};
        struct blob_attr text={.name="text",.value="Reboot required",.next=&reboot};
        struct blob_attr error={.name="error",.value="0",.next=&text};
        struct blob_attr status={.children=&error};
        result_send(99,&status,200);
    }
    pid_t pid=fork();if(!pid){if(code<0)raise(-code);_exit(code);}
    int raw;waitpid(pid,&raw,0);
    runqueue_proc_cb(&t->proc.proc,raw);
    if(success) {
        if(uuid_active!=200||uuid_applied!=200||native_session.applied.uuid!=200||!native_session.applied.sequence)abort();
    }else if(uuid_active!=100||uuid_applied!=100||native_session.applied.sequence)abort();
    if(apply_pending||timers||apply_task.t)abort();
    if(deferred&&(errors||reloads))abort();
    if(deferred&&(wire_count!=1||wire_id!=99||wire_uuid!=200||wire_attributes!=3||
       strcmp(wire[0].name,"error")||strcmp(wire[1].name,"text")||strcmp(wire[2].name,"reboot_required")||
       strcmp(wire[0].value,"0")||strcmp(wire[1].value,"Reboot required")||strcmp(wire[2].value,"true")))abort();
    if(!deferred&&wire_count)abort();
    if(!success&&!deferred&&reloads!=1)abort();
    if(!native_session.connected)abort();
    printf("PASS exit=%d cancelled=%d deferred=%d applied=%d raw_wait=%d\n",code,cancelled,deferred,success,raw);
}
int main(void){
    check(75,false,false,true);
    check(75,true,false,false);
    check(0,false,true,false);
    check(0,true,false,false);
    check(1,false,false,false);
    check(255,false,false,false);
    check(-9,true,false,false);
    check(75,false,false,true);
    return 0;
}
'''
        (work/'test.c').write_text(c)
        subprocess.run(['cc','-std=gnu11','-Werror=implicit-function-declaration','-I',str(work),str(work/'test.c'),str(work/'session_status.c'),'-o',str(work/'test')],check=True)
        r=subprocess.run([str(work/'test')],check=True,text=True,capture_output=True)
        print(json.dumps({'passed':True,'count':8,'output':r.stdout,'scope':'Actual patched runqueue_proc_cb/task_complete/apply_complete_cb, unmodified session_status.c and proto.c result_send; real fork/waitpid exit/signal encoding. Queue/timer/log/config reload/blob serialization/socket boundaries stubbed; wire forwarding count/id/uuid/status retained, no second reply. No firmware build, network or AP actions.','source_sha256':{n:hashlib.sha256((args.native_source/n).read_bytes()).hexdigest() for n in ('apply.c','task.c','session_status.c','session_status.h','proto.c')}},indent=2))
    finally:shutil.rmtree(work)

if __name__=='__main__':main()
