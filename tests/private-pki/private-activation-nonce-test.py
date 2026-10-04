"""Compile and run the actual optional nonce helper from patched proto.c.
Usage: python3 private-activation-nonce-test.py /path/to/patched/client/source
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

proto = (Path(sys.argv[1]) / 'proto.c').read_text()
start = proto.index('/* Optional private lifecycle challenge; consumed once and never logged. */')
end = proto.index('void\nconnect_send(void)', start)
helper = proto[start:end]
harness = ' {\n char out[65];\n unsetenv("UCENTRAL_PRIVATE_ACTIVATION_NONCE"); assert(!private_activation_nonce(out));\n const char *invalid[] = {"", "short", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};\n for (size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) { setenv("UCENTRAL_PRIVATE_ACTIVATION_NONCE",invalid[i],1); assert(!private_activation_nonce(out)); assert(!getenv("UCENTRAL_PRIVATE_ACTIVATION_NONCE")); assert(out[0]==0); }\n const char *good="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";\n setenv("UCENTRAL_PRIVATE_ACTIVATION_NONCE",good,1); assert(private_activation_nonce(out)); assert(!strcmp(out,good)); assert(!getenv("UCENTRAL_PRIVATE_ACTIVATION_NONCE")); assert(!private_activation_nonce(out));\n return 0;\n}\n'
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'nonce.c'
    binary = Path(directory) / 'nonce-test'
    source.write_text('#include <stdbool.h>\n#include <stdlib.h>\n#include <string.h>\n#include <assert.h>\n' + helper + 'int main(void)' + harness)
    subprocess.run([os.environ.get('CC', 'cc'), '-std=gnu11', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: absent, malformed and valid one-use nonce; environment cleared')
