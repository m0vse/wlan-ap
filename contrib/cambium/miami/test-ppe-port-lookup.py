#!/usr/bin/env python3
"""Check the actual plugin lookup's missing/invalid/valid port behavior."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

source = Path(sys.argv[1]).read_text()
function = re.search(r"^int16_t qca_nss_wifi_plugin_get_vp_num\(.*?^}", source, re.M | re.S)
assert function, "prepared plugin lookup missing"
program = r'''
#include <assert.h>
#include <stdint.h>
#define PPE_DRV_PORT_ID_INVALID (-1)
#define PPE_DRV_VIRTUAL_START 64
#define PPE_DRV_VIRTUAL_END 256
#define unlikely(x) (x)
#define pr_debug(...) ((void)0)
#define pr_err(...) (++errors)
struct net_device { const char *name; };
static int port, errors;
static int ppe_drv_port_num_from_dev(struct net_device *dev) { return port; }
FUNCTION
int main(void) {
    struct net_device dev = {"test-ap"};
    const int ports[] = {-1, -2, 0, 63, 64, 255, 256};
    const int values[] = {-1, -1, -1, -1, 64, 255, -1};
    const int expected_errors[] = {0, 1, 1, 1, 0, 0, 1};
    for (unsigned i = 0; i < sizeof(ports)/sizeof(ports[0]); i++) {
        port = ports[i]; errors = 0;
        assert(qca_nss_wifi_plugin_get_vp_num(&dev) == values[i]);
        assert(errors == expected_errors[i]);
    }
    return 0;
}
'''.replace("FUNCTION", function[0])
with tempfile.TemporaryDirectory(prefix="miami-ppe-lookup-") as tmp:
    path = Path(tmp)
    (path / "test.c").write_text(program)
    subprocess.run(["cc", "-Wall", "-Werror", str(path / "test.c"), "-o", str(path / "test")], check=True)
    subprocess.run([str(path / "test")], check=True)
print("7 actual PPE port lookup cases passed; real invalid ports remain errors")
