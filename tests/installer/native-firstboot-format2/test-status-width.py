import os
from pathlib import Path
import subprocess,tempfile,json
source=(Path(os.environ['NATIVE_CLIENT_SOURCE_DIR'])/'ubus.c').read_text();callback=source[source.index('static int ubus_status_cb'):source.index('static int ubus_send_cb')]
p=Path(tempfile.mkdtemp(prefix='native-status-width.'));c=p/'test.c';c.write_text('''#include <stdint.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
#include <assert.h>
struct ubus_context{};struct ubus_object{};struct ubus_request_data{};struct blob_attr{};struct blob_buf{void *head;};static struct blob_buf u;
static uint64_t uuid_latest,uuid_active;static time_t conn_time,reconnect_time;static int websocket=1;
static struct{uint32_t generation;struct{uint32_t sequence;uint64_t uuid;}received,applied;}native_session;
#define UBUS_STATUS_OK 0
static uint64_t latest,active,received,applied;
static void blob_buf_init(struct blob_buf*b,int n){(void)b;(void)n;}
static void blobmsg_add_u32(struct blob_buf*b,const char*n,uint32_t v){(void)b;assert(strcmp(n,"latest")&&strcmp(n,"active"));(void)v;}
static void blobmsg_add_u64(struct blob_buf*b,const char*n,uint64_t v){(void)b;if(!strcmp(n,"latest"))latest=v;if(!strcmp(n,"active"))active=v;if(!strcmp(n,"config_received_uuid"))received=v;if(!strcmp(n,"config_applied_uuid"))applied=v;}
static void ubus_send_reply(struct ubus_context*c,struct ubus_request_data*r,void*h){(void)c;(void)r;(void)h;}
'''+callback+'''int main(void){uint64_t cases[]={1,4294967296ULL,9007199254740993ULL,9223372036854775808ULL,UINT64_MAX};for(unsigned i=0;i<5;i++){uuid_latest=uuid_active=native_session.received.uuid=native_session.applied.uuid=cases[i];assert(!ubus_status_cb(0,0,0,0,0));assert(latest==cases[i]&&active==cases[i]&&received==cases[i]&&applied==cases[i]);}return 0;}
''');subprocess.run(['cc','-o',str(p/'test'),str(c)],check=True);subprocess.run([str(p/'test')],check=True);print(json.dumps({'passed':True,'scope':'Actual native ubus callback with captured blob add boundaries, five uint64 values including UINT64_MAX; no live ubus or deployment.'}))
