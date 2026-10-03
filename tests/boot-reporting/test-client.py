#!/usr/bin/env python3
"""Offline controls for exact patched client functions. No firmware build."""
import pathlib
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1])

def function(text, name):
    start = text.index('\n' + name + '(')
    brace = text.index('{', start)
    level = 1
    end = brace + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start + 1:end]

proto = (source / 'proto.c').read_text()
main = (source / 'main.c').read_text()
ubus = (source / 'ubus.c').read_text()
legacy = (source / 'rebootlog.c').read_text()
established = main.split('case LWS_CALLBACK_CLIENT_ESTABLISHED:', 1)[1].split('case LWS_CALLBACK_CLIENT_RECEIVE:', 1)[0]
assert established.count('ubus_set_client_status("online")') == 1
assert established.index('return -1;') < established.index('websocket = wsi;') < established.index('ubus_set_client_status("online")')
assert 'match_hostname(ci.ns.name) && validate_SAN(wsi)' in established
assert 'if (!client.selfsigned && client.hostname_validate)' in established
assert 'return send_blob(&proto);' in function(proto, 'raw_send')
assert '"serial", client.serial' in function(proto, 'raw_send') and '"uuid", uuid_active' in function(proto, 'raw_send')
assert 'if (!raw_send(msg))' in ubus and '"transmitted", true' in ubus and '"boot_report_transport", 1' in ubus
assert 'if (transmitted)\n\t\tunlink(file);' in legacy

header = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#define LWS_PRE 16
#define LWS_WRITE_TEXT 1
#define ULOG_DBG(...) ((void)0)
#define ULOG_ERR(...) ((void)0)
struct blob_attr { int placeholder; };
struct blob_buf { struct blob_attr *head; };
static struct blob_buf proto;
static struct { char *serial; } client = { "TEST-serial" };
static unsigned long uuid_active = 1;
static void *websocket;
static int writes, response, allocation_failure, format_failure;
static const char *method, *array;
static char *blobmsg_format_json(void *head, bool pretty) {
  return format_failure ? NULL : strdup("{\"TEST\":true}");
}
static void *test_realloc(void *ptr, size_t size) {
  return allocation_failure ? NULL : realloc(ptr, size);
}
#define realloc test_realloc
static int lws_write(void *ws, unsigned char *data, int len, int mode) {
  assert(ws && mode == LWS_WRITE_TEXT);
  assert(len == strlen("{\"TEST\":true}"));
  assert(!memcmp(data, "{\"TEST\":true}", len));
  for (int i=1;i<=LWS_PRE;i++) assert(data[-i] == 0);
  writes++;
  return response == 99 ? len : response;
}
static void *proto_new_blob(const char *name) { method=name; return NULL; }
#define blobmsg_add_string(...) ((void)0)
#define blobmsg_add_u64(...) ((void)0)
#define blobmsg_add_blob(...) ((void)0)
static void *blobmsg_open_array(void *b, const char *name) { array=name; return NULL; }
#define blobmsg_close_array(...) ((void)0)
#define blobmsg_close_table(...) ((void)0)
#define blobmsg_for_each_attr(b,a,rem) for ((rem)=0; (rem)<0; (rem)++)
'''
footer = r'''
int main(void) {
  struct blob_buf blob={0};
  assert(!send_blob(&blob) && writes==0);
  websocket=(void *)1;
  response=-1; assert(!send_blob(&blob) && writes==1);
  response=0; assert(!send_blob(&blob));
  response=12; assert(!send_blob(&blob));
  response=99; assert(send_blob(&blob));
  int before=writes;
  format_failure=1; assert(!send_blob(&blob) && writes==before); format_failure=0;
  allocation_failure=1; assert(!send_blob(&blob) && writes==before); allocation_failure=0;
  assert(rebootlog_send("crashlog", NULL)); assert(!strcmp(method,"crashlog") && !strcmp(array,"loglines"));
  assert(rebootlog_send("firmware-upgrade", NULL)); assert(!strcmp(method,"rebootLog") && !strcmp(array,"info"));
  response=-1; assert(!rebootlog_send("crashlog", NULL));
  puts("TEST exact C write/short/error/allocation/protocol controls: 10 PASS");
  return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='report-C-fixture-') as temporary:
    test = pathlib.Path(temporary) / 'fixture.c'
    binary = pathlib.Path(temporary) / 'fixture'
    test.write_text(header + '\nstatic bool\n' + function(proto, 'send_blob') + '\nbool\n' + function(proto, 'rebootlog_send') + footer)
    subprocess.run(['cc', '-std=gnu11', str(test), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('TEST validated peer notification, serial/uuid injection, capability and legacy retention controls: PASS')
