"""Isolated TLS operator authorization + durable issuance/recovery tests.

No host ports or production credentials. Inventory and operator pins are
trusted local test inputs, not supplied by the enrollment requester.
"""
import base64
import importlib.util
import json
from pathlib import Path
import ssl
import tempfile
import threading
from datetime import timedelta
from unittest.mock import patch
import urllib.error
import urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7
from enrollment_store import EnrollmentStore

spec = importlib.util.spec_from_file_location("pki", Path(__file__).with_name("private-pki-prototype.py"))
pki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pki)


def refused(fn):
    try:
        fn()
    except (urllib.error.URLError, ssl.SSLError, ValueError):
        return
    raise AssertionError("unexpected authorization")


def run_tests():
    with tempfile.TemporaryDirectory(prefix="isolated-operator-est-") as directory:
        root = Path(directory)
        store = EnrollmentStore(root / "state" / "grants.sqlite")
        serial = "001122334455"
        store.approve(serial)
        authority = pki.Authority(store)
        key = ec.generate_private_key(ec.SECP256R1())
        csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name(serial)).sign(key, hashes.SHA256())
        operator_issuer_key = ec.generate_private_key(ec.SECP256R1())
        operator_issuer = pki.certificate(pki.name("ISOLATED OPERATOR ISSUER"), operator_issuer_key,
                                         authority.root_key, authority.root, 365, ca=True)
        operator_key = ec.generate_private_key(ec.SECP256R1())
        operator_cert = pki.certificate(pki.name("ISOLATED APPROVED OPERATOR"), operator_key,
                                       operator_issuer_key, operator_issuer, 30)
        authority.operator_fingerprints.add(operator_cert.fingerprint(hashes.SHA256()).hex())
        tls_key = ec.generate_private_key(ec.SECP256R1())
        tls_cert = pki.certificate(pki.name("localhost"), tls_key, authority.server_key, authority.server, 365, server=True)
        for filename, data in {
            "root.pem": pki.pem(authority.root), "server.pem": pki.pem(tls_cert) + pki.pem(authority.server),
            "server.key": pki.private(tls_key), "operator.pem": pki.pem(operator_cert) + pki.pem(operator_issuer),
            "operator.key": pki.private(operator_key), "device.key": pki.private(key),
        }.items():
            pki.write(root / filename, data)
        server = pki.http.server.HTTPServer(("127.0.0.1", 0), pki.handler(authority))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(root / "server.pem", root / "server.key")
        context.load_verify_locations(root / "root.pem")
        context.verify_mode = ssl.CERT_OPTIONAL
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"https://localhost:{server.server_port}"
        anonymous = ssl.create_default_context(cafile=str(root / "root.pem"))
        operator = ssl.create_default_context(cafile=str(root / "root.pem"))
        operator.load_cert_chain(root / "operator.pem", root / "operator.key")

        def authorization(tls=operator, requested_serial=serial, requested_csr=csr):
            request = urllib.request.Request(url + "/operator/enrollment-authorizations",
                json.dumps({"serial": requested_serial,
                            "csr": base64.b64encode(requested_csr.public_bytes(serialization.Encoding.DER)).decode()}).encode(),
                {"Content-Type": "application/json"})
            with urllib.request.urlopen(request, context=tls, timeout=5) as result:
                return json.load(result)["authorization"]

        def bootstrap(token, requested_csr=csr, tls=anonymous):
            headers = {"Content-Type": "application/pkcs10", "Authorization": "Basic " +
                       base64.b64encode((serial + ":" + token).encode()).decode()}
            request = urllib.request.Request(url + "/bootstrap",
                base64.b64encode(requested_csr.public_bytes(serialization.Encoding.DER)), headers)
            with urllib.request.urlopen(request, context=tls, timeout=5) as result:
                return next(cert for cert in pkcs7.load_der_pkcs7_certificates(base64.b64decode(result.read()))
                            if cert.subject == pki.name(serial))

        try:
            refused(lambda: authorization(anonymous))
            unapproved_csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name("001122334456")).sign(key, hashes.SHA256())
            refused(lambda: authorization(requested_serial="001122334456", requested_csr=unapproved_csr))
            refused(lambda: authorization(requested_serial="001122334456"))
            token = authorization()
            issued = bootstrap(token)
            pki.validate(issued, key, serial, authority)
            authority.store = EnrollmentStore(root / "state" / "grants.sqlite")
            assert bootstrap(token).serial_number == issued.serial_number
            other_key = ec.generate_private_key(ec.SECP256R1())
            other_csr = x509.CertificateSigningRequestBuilder().subject_name(pki.name(serial)).sign(other_key, hashes.SHA256())
            refused(lambda: bootstrap(token, other_csr))
            pki.write(root / "device.pem", pki.pem(issued) + pki.pem(authority.device))
            device = ssl.create_default_context(cafile=str(root / "root.pem"))
            device.load_cert_chain(root / "device.pem", root / "device.key")
            refused(lambda: authorization(device))  # AP identity is not an operator.
            # Expired AP credentials cannot perform ordinary mTLS renewal.
            # Recovery is a new explicit operator authorization, bound to this
            # AP's same-key CSR, over independently verified server TLS.
            with patch.object(pki, "now", return_value=pki.now() - timedelta(days=367)):
                expired = authority.issue(serial, csr)
            pki.write(root / "expired.pem", pki.pem(expired) + pki.pem(authority.device))
            expired_client = ssl.create_default_context(cafile=str(root / "root.pem"))
            expired_client.load_cert_chain(root / "expired.pem", root / "device.key")
            refused(lambda: bootstrap(token, tls=expired_client))
            recovery_token = authorization()
            recovered = bootstrap(recovery_token)
            pki.validate(recovered, key, serial, authority)
            assert recovered.serial_number != issued.serial_number
            assert bootstrap(recovery_token).serial_number == recovered.serial_number
            expiring_token = authorization()
            authority.store = EnrollmentStore(root / "state" / "grants.sqlite", lambda: pki.now().timestamp() + 601)
            refused(lambda: bootstrap(expiring_token))
            authority.store = EnrollmentStore(root / "state" / "grants.sqlite")
            authority.store.revoke(operator_cert.serial_number)
            refused(lambda: authorization())
            # Forged same-name issuer is not enough to authenticate renewal.
            impostor_key = ec.generate_private_key(ec.SECP256R1())
            forged = pki.certificate(pki.name(serial), key, impostor_key, authority.device, 1)
            refused(lambda: authority.enroll(forged, csr))
            with authority.store.connect() as db:
                assert db.execute("SELECT count(*) FROM audit WHERE event='grant-issued'").fetchone()[0] == 2
            print("PASS: pinned operator mTLS + inventory authorization, durable wire retry, CSR substitution/expiry/revoked operator/AP-as-operator/issuer-spoof refusal")
            print("PASS: expired AP TLS refuses; explicit pinned-operator same-CSR recovery over verified server TLS issues one new leaf with idempotent retry")
            print("TEST ONLY: no production issuer/service, rate limit, AP installer or real controller activation")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    run_tests()
