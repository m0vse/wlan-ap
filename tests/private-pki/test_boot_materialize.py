"""Synthetic committed-generation boot restoration with real OpenSSL/ucode.
No AP/network activity. The commit proof here is a fixture stub; authenticated
loopback proof is tested separately, and real OWGW proof is still required.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography import x509

spec = importlib.util.spec_from_file_location("pki", Path(__file__).with_name("private-pki-prototype.py"))
pki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pki)


def run_tests():
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix="isolated-identity-boot-") as directory:
        root = Path(directory)
        store = root / "generations"
        store.mkdir(mode=0o700)
        runtime = root / "runtime"
        authority = pki.Authority()
        serial = "001122334455"
        key = ec.generate_private_key(ec.SECP256R1())
        csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name(serial)).sign(key, hashes.SHA256())
        cert = authority.issue(serial, csr)
        pki.write(root / "trust.pem", pki.pem(authority.root))
        generation = pki.activate(store, cert, key, serial, authority, lambda _: True)
        script = Path(__file__).with_name("ap-boot-materialize.sh")
        command = ["sh", str(script), str(store), str(runtime), str(root / "trust.pem"), serial, "openwifi.shinesystems.co.uk", "15002"]
        def restore(accept=True):
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if (result.returncode == 0) != accept:
                raise AssertionError(result.stdout.decode() + result.stderr.decode())
        validated = subprocess.run(command + ["validate"], capture_output=True)
        assert validated.returncode == 0, validated.stderr.decode()
        assert not runtime.exists(), "validation-only mode mutated runtime"
        restore()
        gateway = json.loads((runtime / "gateway.json").read_text())
        assert gateway["cert"] == str(generation / "cert.pem")
        assert gateway["ca"] == str(root / "trust.pem") and gateway["hostname_validate"] == 1
        assert (runtime / "key.pem").read_bytes() == pki.private(key)
        # Exercise the package dispatcher with real OpenSSL/ucode. Redirect
        # only fixed filesystem paths and root-owner expectation for the
        # unprivileged fixture; no host UCI or services are accessed.
        repo = Path(os.environ.get("PKI_TEST_REPO", str(Path(__file__).resolve().parents[2])))
        helper_source = repo / "feeds/tip/ucentral-private-pki/files/private-pki"
        if helper_source.exists():
            policy_file = root / "policy.json"
            helper = root / "dispatcher"
            dispatcher_materializer = root / "materializer"
            dispatcher_materializer.write_bytes(script.read_bytes())
            dispatcher_materializer.chmod(0o700)
            text = helper_source.read_text()
            replacements = {
                "/etc/ucentral/private-pki.json": str(policy_file),
                "/etc/ucentral/private-trust.pem": str(root / "trust.pem"),
                "/certificates/private-pki": str(store),
                "/usr/libexec/ucentral-private-pki-materialize": str(dispatcher_materializer),
                "/etc/ucentral": str(runtime),
                "$3==0 &&": "$3==" + str(os.getuid()) + " &&",
            }
            for old, new in replacements.items():
                text = text.replace(old, new)
            helper.write_text(text)
            helper.chmod(0o700)
            tools = root / "test-bin"
            tools.mkdir()
            for name, body in {"uci": '#!/bin/sh\nprintf "%s\\n" 001122334455\n', "logger": '#!/bin/sh\nexit 0\n'}.items():
                (tools / name).write_text(body)
                (tools / name).chmod(0o700)
            env = dict(os.environ, PATH=str(tools) + ":" + os.environ["PATH"])
            policy = {"enabled": False, "store": str(store), "trust": str(root / "trust.pem"), "server": "openwifi.shinesystems.co.uk", "port": 15002}
            def dispatch(operation):
                policy_file.write_text(json.dumps(policy))
                policy_file.chmod(0o600)
                return subprocess.run(["sh", str(helper), operation], env=env, capture_output=True)
            assert dispatch("mode").stdout.strip() == b"stock"
            assert dispatch("cloud-guard").returncode == 0
            policy["enabled"] = True
            assert dispatch("mode").stdout.strip() == b"private"
            assert dispatch("cloud-guard").returncode != 0
            assert dispatch("restore").returncode == 0
            assert dispatch("renewal-status").stdout.strip() == b"identity-current"
            saved_chain = (generation / "cert.pem").read_bytes()
            saved_issuer = authority.device
            authority.device = pki.certificate(saved_issuer.subject, authority.device_key,
                                               authority.root_key, authority.root, 45, ca=True)
            short_leaf = authority.issue(serial, csr)
            (generation / "cert.pem").write_bytes(pki.pem(short_leaf) + pki.pem(authority.device))
            pointer_before = (store / "current.json").read_bytes()
            runtime_before = (runtime / "gateway.json").read_bytes()
            assert dispatch("renewal-status").stdout.strip() == b"renewal-due-activation-blocked"
            assert (store / "current.json").read_bytes() == pointer_before
            assert (runtime / "gateway.json").read_bytes() == runtime_before
            authority.device = saved_issuer
            (generation / "cert.pem").write_bytes(saved_chain)
            policy["port"] = 70000
            assert dispatch("restore").returncode != 0
            policy["port"] = 15002
            policy["store"] = "../escape"
            assert dispatch("restore").returncode != 0
            policy["store"] = str(store)
            policy["enabled"] = "true"
            assert dispatch("mode").returncode != 0
            policy["enabled"] = True
            policy_file.write_text(json.dumps(policy))
            policy_file.chmod(0o666)
            refused_policy = subprocess.run(["sh", str(helper), "mode"], env=env, capture_output=True)
            assert refused_policy.returncode != 0
            print("PASS: package dispatcher stock/private gates, validated restore/readiness, bad port/path/type/permissions refusal (fixture paths/owner redirected)")
        before = (runtime / "gateway.json").read_bytes()
        try:
            pki.activate(store, authority.issue(serial, csr), key, serial, authority, lambda _: False)
        except ValueError:
            pass
        else:
            raise AssertionError("failed proof committed")
        restore()
        assert (runtime / "gateway.json").read_bytes() == before
        leaf = (generation / "cert.pem").read_bytes()
        private = (generation / "key.pem").read_bytes()
        (generation / "key.pem").write_bytes(pki.private(ec.generate_private_key(ec.SECP256R1())))
        restore(False)
        (generation / "key.pem").write_bytes(private)
        (generation / "cert.pem").write_bytes(pki.pem(authority.device))
        restore(False)
        other_csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name("001122334456")).sign(key, hashes.SHA256())
        (generation / "cert.pem").write_bytes(pki.pem(authority.issue("001122334456", other_csr)) + pki.pem(authority.device))
        restore(False)
        (generation / "cert.pem").write_bytes(leaf)
        (root / "trust.pem").write_bytes(pki.pem(pki.Authority().root))
        restore(False)
        (root / "trust.pem").write_bytes(pki.pem(authority.root))
        pointer = (store / "current.json").read_bytes()
        (store / "current.json").write_text(json.dumps({"serial": serial, "generation": "../outside"}))
        restore(False)
        (store / "current.json").write_bytes(pointer)
        (store / "current.json").chmod(0o644)
        restore(False)
        (store / "current.json").chmod(0o600)
        saved = store / "saved-generation"
        generation.rename(saved)
        generation.symlink_to(saved, target_is_directory=True)
        restore(False)
        generation.unlink()
        saved.rename(generation)
        # A different already-provisioned AP key must never be replaced.
        (runtime / "key.pem").write_bytes(pki.private(ec.generate_private_key(ec.SECP256R1())))
        protected_key = (runtime / "key.pem").read_bytes()
        restore(False)
        assert (runtime / "key.pem").read_bytes() == protected_key
        assert (runtime / "gateway.json").read_bytes() == before
        print("PASS: real OpenSSL/ucode committed boot restore; failed-proof pending generation ignored; chain/CA/serial/key/traversal/privacy/symlink/existing-key failures leave runtime gateway unchanged")
        print("EXPERIMENTAL: not installed in firmware; no hardware boot, RAM pivot or real OWGW proof")


if __name__ == "__main__":
    run_tests()
