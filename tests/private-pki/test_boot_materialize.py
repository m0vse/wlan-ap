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
        restore()
        gateway = json.loads((runtime / "gateway.json").read_text())
        assert gateway["cert"] == str(generation / "cert.pem")
        assert gateway["ca"] == str(root / "trust.pem") and gateway["hostname_validate"] == 1
        assert (runtime / "key.pem").read_bytes() == pki.private(key)
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
