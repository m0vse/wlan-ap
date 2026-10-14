#!/usr/bin/env python3
"""Compile real session/config/apply source; only external IO/task scheduling is stubbed."""
from pathlib import Path
import subprocess, json, tempfile, hashlib, argparse

parser=argparse.ArgumentParser()
parser.add_argument("--source",type=Path,required=True)
parser.add_argument("--output",type=Path,required=True)
args=parser.parse_args()
here=args.source
output=args.output
output.mkdir(parents=True,exist_ok=True)

def function(name, filename):
    source = (here / filename).read_text()
    start = source.index('static void\n' + name)
    opening = source.index('{', start)
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

assert 'session_applied(t->session, t->uuid, t->id, !t->ret && !task->cancelled);' in (here/'task.c').read_text()

head = r'''
#include <assert.h>
#include <stdio.h>
#include <inttypes.h>
#include <string.h>
#include <time.h>
#include "session_status.h"
uint64_t uuid_latest, uuid_applied, uuid_active;
unsigned apply_calls, replies; int apply_pending;
bool apply_success = true;
struct task { int unused; };
#define ULOG_INFO(...) ((void)0)
#define ULOG_ERR(...) ((void)0)
static bool installer_reapply_allowed(uint32_t id) { (void)id; return false; }
static void configure_reply(int code, const char *msg, uint64_t uuid, uint32_t id) { (void)code;(void)msg;(void)uuid;(void)id; replies++; }
static void config_init(int apply, uint32_t id) { (void)apply;(void)id; }
static void apply_run(uint32_t id);
'''
body = r'''
static void apply_run(uint32_t id) {
 apply_calls++;
 struct session_receipt receipt=session_capture(uuid_latest,id);
 /* Same receipt call as task_complete; IO and asynchronous scheduler are controlled. */
 session_applied(receipt,uuid_latest,id,apply_success);
 apply_complete_cb(NULL,uuid_latest,id,apply_success ? 0 : 1);
}
static void status(const char *name) {
 printf("{\"case\":\"%s\",\"connected\":%u,\"connection_generation\":%u,"
 "\"config_received_sequence\":%u,\"config_applied_sequence\":%u,"
 "\"config_received_uuid\":%" PRIu64 ",\"config_applied_uuid\":%" PRIu64 ","
 "\"boot_report_transport\":1}\n",name,native_session.connected,native_session.generation,
 native_session.received.sequence,native_session.applied.sequence,
 native_session.received.uuid,native_session.applied.uuid);
}
static bool accepted(void) {
 return native_session.connected && native_session.received.sequence>0 &&
 native_session.received.sequence==native_session.applied.sequence &&
 native_session.received.uuid>0 && native_session.received.uuid==native_session.applied.uuid;
}
int main(void) {
 uuid_latest=100; config_apply(0); assert(uuid_applied==100 && !accepted());
 session_connected(); assert(!accepted()); status("boot-cached-no-receipt");
 unsigned before=apply_calls; session_received(100,1); config_apply(1);
 assert(apply_calls==before && replies==1 && !accepted()); status("already-applied-received-only");
 session_disconnected(); session_connected(); assert(!accepted());
 assert(!native_session.received.sequence && !native_session.applied.sequence); status("incomplete-reconnect-cleared");
 uuid_latest=101; session_received(101,2); config_apply(2);
 assert(apply_calls==before+1 && accepted() && uuid_applied==101); status("fresh-uuid-accepted");
 struct session_receipt stale=native_session.applied;
 session_disconnected(); assert(!accepted()); status("disconnected-not-accepted");
 session_connected(); assert(accepted());
 assert(!session_capture(101,2).sequence); status("completed-reconnect-preserved");
 session_applied(stale,101,2,true); assert(accepted());
 assert(native_session.applied.generation==stale.generation);
 for (int i=0;i<3;i++) {session_disconnected();session_connected();assert(accepted());}
 assert(apply_calls==before+1);status("repeated-reconnect-no-reapply");
 uuid_latest=102; session_received(102,3);
 assert(!accepted()); status("new-request-pending-not-accepted");
 session_applied(stale,101,2,true);assert(!accepted());status("stale-completion-rejected");
 apply_success=false;config_apply(3);assert(!accepted());status("failed-apply-not-accepted");
 session_disconnected();session_connected();assert(!accepted());status("failed-reconnect-cleared");
 uuid_latest=103;session_received(103,4);apply_success=true;config_apply(4);
 assert(accepted());status("subsequent-success-accepted");
 /* Emulate C static zero initialization of a NEW process; no persistence is imported. */
 memset(&native_session,0,sizeof(native_session));uuid_latest=103;uuid_applied=0;
 config_apply(0);session_connected();assert(!accepted());status("new-process-no-old-receipts");
 uuid_latest=104;session_received(104,5);config_apply(5);assert(accepted());status("new-process-new-uuid-accepted");
 native_session.generation=UINT32_MAX;session_connected();assert(!accepted());status("generation-overflow-not-connected");
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='miami-native-receipts-') as tmp:
    tmp = Path(tmp)
    fixture = tmp/'fixture.c'
    fixture.write_text(head+function('apply_complete_cb','apply.c')+'\n'+function('config_apply','config.c')+'\n'+body)
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-I',str(here),str(fixture),str(here/'session_status.c'),'-o',str(tmp/'fixture')],check=True)
    result=subprocess.check_output([str(tmp/'fixture')],text=True)
    rows=[json.loads(line) for line in result.splitlines()]
    assert len(rows)==15
    (output/'native-status-cases.json').write_text(json.dumps(rows,indent=2)+'\n')
    receipt={'cases':len(rows),'real_source_sha256':{name:hashlib.sha256((here/name).read_bytes()).hexdigest() for name in ['session_status.c','session_status.h','config.c','apply.c','task.c']},'limitations':'External IO, installer reapply and async task scheduler stubbed; actual native counters, config shortcut and apply completion used. New process simulated by C static-zero state. No AP test.'}
    (output/'native-test-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(f'PASS {len(rows)} real native receipt lifecycle cases')
