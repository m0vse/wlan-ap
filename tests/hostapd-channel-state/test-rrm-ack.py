#!/usr/bin/env python3
"""Compile the actual prepared native ACK/FINISH callbacks against ownership probes."""
import argparse,pathlib,re,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);a=p.parse_args()
s=a.source.read_text()
def fn(name):
 m=re.search(r'static int\n'+name+r'\([^\n]+\)\n\{.*?\n\}',s,re.S);assert m,name
 return m[0]
assert 'nl_cb_set(cb, NL_CB_ACK, NL_CB_CUSTOM, cb_request_ack, &st);'in s
assert 'nl_cb_set(cb, NL_CB_FINISH, NL_CB_CUSTOM, cb_done, &st);'in s
code='''#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
struct nl_msg { int unused; };
struct value { int kind; };
typedef struct { int state; struct value *res; } request_state_t;
#define STATE_REPLIED 2
#define NL_STOP 2
static struct value truth={1}; static int allocations;
static struct value *ucv_boolean_new(int v){assert(v==1);allocations++;return &truth;}
'''+fn('cb_done')+'\n'+fn('cb_request_ack')+'''
int main(void){
 request_state_t st={0};assert(cb_request_ack(NULL,&st)==NL_STOP);assert(st.state==STATE_REPLIED&&st.res==&truth&&allocations==1);
 struct value object={2},array={3};
 st=(request_state_t){0,&object};cb_request_ack(NULL,&st);assert(st.res==&object&&allocations==1);
 st=(request_state_t){0,&array};cb_request_ack(NULL,&st);assert(st.res==&array&&allocations==1);
 st=(request_state_t){0};cb_done(NULL,&st);assert(st.state==STATE_REPLIED&&st.res==NULL&&allocations==1);
 puts("PASS actual ACK callback: empty success, existing object/array ownership, unchanged empty FINISH");
}
'''
with tempfile.TemporaryDirectory()as d:
 c=pathlib.Path(d)/'ack.c';c.write_text(code);binary=pathlib.Path(d)/'ack'
 subprocess.run(['cc','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(c),'-o',str(binary)],check=True);subprocess.run([str(binary)],check=True)
