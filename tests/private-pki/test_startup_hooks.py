"""Redirected filesystem/stubbed procd tests; never operate an AP/service."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
shell = os.environ.get("PKI_TEST_SHELL", "/bin/sh")


def run_tests():
    assert (repo / "feeds/tip/ucentral-private-pki/files/materialize").read_bytes() == (repo / "tests/private-pki/ap-boot-materialize.sh").read_bytes()
    with tempfile.TemporaryDirectory(prefix="private-pki-startup-") as path:
        root = Path(path)
        for directory in ("etc/ucentral", "etc/config-shadow", "etc/config", "lib", "usr/libexec", "tmp", "bin"):
            (root / directory).mkdir(parents=True, exist_ok=True)
        (root / "tmp/ucentral-network.ready").touch()
        (root / "tmp/ucentral.version").write_text("synthetic-test")
        (root / "etc/ucentral/capabilities.json").write_text('{"wifi":{}}')
        (root / "etc/config-shadow/ucentral").write_text("synthetic")
        (root / "etc/ucentral/cert.pem").write_text("synthetic-demo-placeholder")
        (root / "etc/ucentral/gateway.json").write_text(json.dumps({"server": "gateway.test", "port": 15002, "cert": "candidate.pem", "ca": "trust.pem", "hostname_validate": 1}))
        (root / "lib/functions.sh").write_text('''config_load() { :; }
config_get() {
 case "$3" in serial) value=001122334455;; debug) value=0;; insecure) value=${TEST_INSECURE:-${4:-0}};; *) value=${4:-};; esac
 eval "$1=\\\"$value\\\""
}
''')
        helper = root / "usr/libexec/ucentral-private-pki"
        helper.write_text('''#!/bin/sh
case "$1" in
 mode) [ "$TEST_MODE" != invalid ] || exit 2; echo "$TEST_MODE";;
 restore) echo restore >> "$TEST_RECORD"; [ "${TEST_RESTORE_FAIL:-0}" = 0 ];;
esac
''')
        helper.chmod(0o755)
        for command, content in {
            "openssl": '#!/bin/sh\necho "issuer=OpenLAN Demo Birth CA"\n',
            "est_client": '#!/bin/sh\necho est >> "$TEST_RECORD"\n',
            "logger": '#!/bin/sh\nexit 0\n',
            "jsonfilter": '''#!/usr/bin/env python3
import json,sys
a=sys.argv[1:]; expression=a[a.index('-e')+1]; key=expression.split('"')[1]
data=json.load(open(a[a.index('-i')+1])) if '-i' in a else json.load(sys.stdin)
v=data.get(key, '')
print(str(v).lower() if isinstance(v,bool) else v)
''',
        }.items():
            file = root / "bin" / command
            file.write_text(content)
            file.chmod(0o755)
        stub = '''procd_open_instance() { echo open >> "$TEST_RECORD"; }
procd_set_param() { printf 'set %s\\n' "$*" >> "$TEST_RECORD"; }
procd_append_param() { printf 'append %s\\n' "$*" >> "$TEST_RECORD"; }
procd_close_instance() { echo close >> "$TEST_RECORD"; }
'''
        def execute(source, mode, fail=False, insecure=None):
            text = (repo / source).read_text()
            for prefix in ("/etc/", "/usr/libexec/", "/lib/", "/tmp/"):
                text = text.replace(prefix, str(root) + prefix)
            script = root / "test-init.sh"
            script.write_text(stub + text + '\nstart_service\n')
            record = root / "record"
            record.write_text("")
            env = dict(os.environ, PATH=str(root / "bin") + ":" + os.environ["PATH"], TEST_MODE=mode, TEST_RECORD=str(record), TEST_RESTORE_FAIL=str(int(fail)))
            if insecure is not None:
                env["TEST_INSECURE"] = insecure
            result = subprocess.run([shell, str(script)], env=env, capture_output=True)
            return result.returncode, record.read_text()
        client = "feeds/ucentral/ucentral-client/files/etc/init.d/ucentral"
        cloud = "feeds/tip/cloud_discovery/files/etc/init.d/cloud_discover"
        code, events = execute(client, "stock")
        assert code == 0 and "append command -i" in events and "restore" not in events, events
        code, events = execute(client, "private")
        assert code == 0 and "restore" in events and "append command -i" not in events and "append command -h" in events, events
        for mode, fail, insecure in (("invalid", False, None), ("private", True, None), ("private", False, "1")):
            code, events = execute(client, mode, fail, insecure)
            assert code != 0 and "open" not in events, events
        (root / "etc/ucentral/restrictions.json").write_text('{"allow-self-signed":true}')
        code, events = execute(client, "private")
        assert code != 0 and "open" not in events
        code, events = execute(cloud, "private")
        assert code == 0 and "est" not in events and "open" not in events
        code, events = execute(cloud, "stock")
        assert code == 0 and "est" in events and "open" in events
        code, events = execute(cloud, "invalid")
        assert code != 0 and "est" not in events and "open" not in events
        # Source guard must precede any stock EST/discovery state mutation.
        for name in ("cloud_discovery", "est_client"):
            source = (repo / f"feeds/tip/cloud_discovery/files/usr/bin/{name}").read_text()
            assert source.index("cloud-guard") < source.index("let ")
        print("PASS: stock demo behavior preserved; private restore + hostname validation; bad policy/restore/insecure overrides refuse startup; private cloud/EST guards prevent competing writers")
        print("FIXTURE: procd/config/jsonfilter stubs and redirected filesystem, not live service or gateway acceptance")


if __name__ == "__main__":
    run_tests()
