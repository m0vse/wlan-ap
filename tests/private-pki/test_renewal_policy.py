"""Synthetic validity-window tests; no system clock or fleet cert changes."""
from datetime import timedelta
import importlib.util
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from renewal_policy import renewal_decision

spec = importlib.util.spec_from_file_location("pki", Path(__file__).with_name("private-pki-prototype.py"))
pki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pki)


def run_tests():
    authority = pki.Authority()
    key = ec.generate_private_key(ec.SECP256R1())
    serial = "001122334455"
    csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name(serial)).sign(key, hashes.SHA256())
    cert = authority.issue(serial, csr)
    chain = [authority.device, authority.root]
    assert timedelta(days=364) < cert.not_valid_after_utc - pki.now() <= timedelta(days=365)
    assert renewal_decision(cert, chain)["action"] == "wait"
    assert renewal_decision(cert, chain, cert.not_valid_after_utc - timedelta(days=91))["action"] == "wait"
    assert renewal_decision(cert, chain, cert.not_valid_after_utc - timedelta(days=90))["action"] == "renew"
    assert renewal_decision(cert, chain, cert.not_valid_after_utc - timedelta(days=89), failures=0)["retry_seconds"] == 900
    assert renewal_decision(cert, chain, cert.not_valid_after_utc - timedelta(days=89), failures=99)["retry_seconds"] == 21600
    assert renewal_decision(cert, chain, cert.not_valid_after_utc - timedelta(seconds=8), failures=99)["retry_seconds"] == 2
    assert renewal_decision(cert, chain, cert.not_valid_after_utc)["action"] == "authenticated-recovery-required"
    assert renewal_decision(cert, chain, cert.not_valid_before_utc - timedelta(seconds=1))["action"] == "clock-or-chain-invalid"
    authority.device = pki.certificate(pki.name("ISOLATED SHORT DEVICE ISSUER"), authority.device_key,
                                       authority.root_key, authority.root, 45, ca=True)
    short = authority.issue(serial, csr)
    assert short.not_valid_after_utc <= authority.device.not_valid_after_utc
    assert renewal_decision(short, [authority.device, authority.root])["action"] == "renew"
    assert timedelta(days=3649) < authority.root.not_valid_after_utc - pki.now() <= timedelta(days=3650)
    print("PASS: one-year/issuer-capped leaves, ten-year root, 90-day renewal threshold, bounded outage backoff and authenticated expiry recovery requirement")


if __name__ == "__main__":
    run_tests()
