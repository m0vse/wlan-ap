import os
from pathlib import Path
import tempfile,subprocess,json
s=(Path(os.environ['NATIVE_CLIENT_SOURCE_DIR'])/'proto.c').read_text();body=s[s.index('static bool\nsend_blob'):s.index('static void\nproto_send_blob')];d=Path(tempfile.mkdtemp(prefix='boot-transport.'));p=d/'test.c';p.write_text('''#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#define LWS_PRE 16
#define LWS_WRITE_TEXT 1
#define ULOG_DBG(...) ((void)0)
#define ULOG_ERR(...) ((void)0)
struct blob_buf{void *head;};static void *websocket=(void*)1;static int response=2;static bool json_failure=false;
static char*blobmsg_format_json(void*p,bool b){(void)p;(void)b;return json_failure?NULL:strdup("{}");}
static int lws_write(void*w,unsigned char*p,int n,int f){(void)w;(void)f;assert(n==2&&!memcmp(p,"{}",2));return response;}
'''+body+'''int main(void){struct blob_buf b={0};assert(send_blob(&b));response=1;assert(!send_blob(&b));response=-1;assert(!send_blob(&b));websocket=NULL;assert(!send_blob(&b));websocket=(void*)1;json_failure=true;assert(!send_blob(&b));return 0;}
''');subprocess.run(['cc','-Wall','-Wextra','-Werror','-o',str(d/'test'),str(p)],check=True);subprocess.run([str(d/'test')],check=True);print(json.dumps({'passed':True,'cases':['complete-write-success','partial-write-failure','write-error','disconnected','JSON-allocation-failure'],'scope':'Actual full patched send_blob with JSON/websocket boundaries isolated; no live connection.'}))
