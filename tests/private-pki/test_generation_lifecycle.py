"""Synthetic outage/interruption/expiry tests, without host clock changes."""
import importlib.util
import json
from datetime import timedelta
from pathlib import Path
import tempfile
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

spec = importlib.util.spec_from_file_location("pki", Path(__file__).with_name("private-pki-prototype.py"))
pki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pki)


def run_tests():
    authority = pki.Authority()
    serial = "001122334455"
    key = ec.generate_private_key(ec.SECP256R1())
    csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name(serial)).sign(key, hashes.SHA256())
    original = authority.issue(serial, csr)
    candidate = authority.issue(serial, csr)
    with tempfile.TemporaryDirectory(prefix="isolated-generation-lifecycle-") as path:
        store = Path(path)
        store.chmod(0o700)
        initial = pki.activate(store, original, key, serial, authority, lambda _: True)
        previous = (store / "current.json").read_bytes()
        for failure in (lambda _: False, lambda _: (_ for _ in ()).throw(ConnectionError("synthetic outage"))):
            try:
                pki.activate(store, candidate, key, serial, authority, failure)
            except (ValueError, ConnectionError):
                pass
            else:
                raise AssertionError("outage unexpectedly committed")
            assert (store / "current.json").read_bytes() == previous
        with patch.object(pki.os, "replace", side_effect=OSError("synthetic pre-commit interruption")):
            try:
                pki.activate(store, candidate, key, serial, authority, lambda _: True)
            except OSError:
                pass
            else:
                raise AssertionError("interrupted commit unexpectedly succeeded")
        assert (store / "current.json").read_bytes() == previous
        assert (initial / "cert.pem").exists()
        # Expired leaves and expired root chains are never activated or rescued
        # by relaxing verification. Time is injected only into the test module.
        for stamp in (candidate.not_valid_after_utc + timedelta(seconds=1),
                      authority.root.not_valid_after_utc + timedelta(seconds=1)):
            with patch.object(pki, "now", return_value=stamp):
                try:
                    pki.activate(store, candidate, key, serial, authority, lambda _: True)
                except ValueError:
                    pass
                else:
                    raise AssertionError("expired identity/chain accepted")
            assert (store / "current.json").read_bytes() == previous
        final = pki.activate(store, candidate, key, serial, authority, lambda _: True)
        assert json.loads((store / "current.json").read_text())["generation"] == final.name
        assert final != initial and (initial / "cert.pem").exists()
        print("PASS: outage and pre-pointer interruption preserve previous identity; expired leaf/root refuse; successful retry commits and retains previous generation")
        print("TEST ONLY: proof callback is synthetic; no power-loss filesystem or real OWGW acceptance claim")


if __name__ == "__main__":
    run_tests()
