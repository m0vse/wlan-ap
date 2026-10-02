"""Audit an extracted APK only; never install or run its package hooks."""
import json
from pathlib import Path
import stat
import sys

source, extracted, target_root = map(Path, sys.argv[1:4])
mapping = {
    "files/private-pki.json": ("etc/ucentral/private-pki.json", 0o600),
    "files/private-pki.init": ("etc/init.d/ucentral-private-pki", 0o755),
    "files/private-pki": ("usr/libexec/ucentral-private-pki", 0o755),
    "files/materialize": ("usr/libexec/ucentral-private-pki-materialize", 0o755),
    "files/private-pki-scheduler": ("usr/libexec/ucentral-private-pki-scheduler", 0o755),
}
for src, (dst, mode) in mapping.items():
    file = extracted / dst
    assert file.is_file() and not file.is_symlink(), dst
    assert file.read_bytes() == (source / src).read_bytes(), dst
    assert stat.S_IMODE(file.stat().st_mode) == mode, dst
policy = json.loads((extracted / "etc/ucentral/private-pki.json").read_text())
assert policy["enabled"] is False
assert policy["store"] == "/certificates/private-pki"
assert (extracted / "lib/apk/packages/ucentral-private-pki.conffiles").read_text().strip() == "/etc/ucentral/private-pki.json"
expected = {dst for dst, _ in mapping.values()} | {
    "lib/apk/packages/ucentral-private-pki.list",
    "lib/apk/packages/ucentral-private-pki.conffiles",
    "lib/apk/packages/ucentral-private-pki.conffiles_static",
}
assert {str(file.relative_to(extracted)) for file in extracted.rglob("*") if file.is_file()} == expected
for dependency in ("usr/bin/openssl", "usr/bin/ucode", "usr/lib/ucode/fs.so", "sbin/uci", "bin/busybox"):
    assert (target_root / dependency).exists(), dependency
print("PASS: five source-identical installed files/modes, disabled policy/conffile, no extra key/cert payload, packaged OpenSSL/ucode/fs/UCI/BusyBox dependencies present")
print("AUDIT ONLY: not package installation, full fresh solver transaction, init ordering or hardware runtime proof")
