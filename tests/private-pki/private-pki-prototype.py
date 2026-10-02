"""ISOLATED TEST ONLY: constrained issuance + RFC7030 wire subset.

Not a production CA/EST service. Durable grants and an isolated pinned-mTLS
operator endpoint are tested; no revocation distribution, rate limiting,
production issuer loading or real OWGW activation is provided.
All keys/identities are created inside temporary private test directories.
"""
import base64
import hashlib
import http.server
import json
import os
import re
from pathlib import Path
import secrets
import ssl
import tempfile
import threading
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from enrollment_store import EnrollmentStore

ROOT_DAYS = 3650
LEAF_DAYS = 365
RENEW_DAYS = 90


def now():
    return datetime.now(timezone.utc)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def public(key):
    return key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def pem(cert):
    return cert.public_bytes(serialization.Encoding.PEM)


def private(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def write(path, data):
    with open(path, "xb") as handle:
        os.chmod(path, 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def certificate(subject, key, signer_key, issuer, days, ca=False, server=False):
    stamp = now()
    expiry = stamp + timedelta(days=days)
    if issuer:
        expiry = min(expiry, issuer.not_valid_after_utc)
    builder = (x509.CertificateBuilder().subject_name(subject)
               .issuer_name(issuer.subject if issuer else subject)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(stamp - timedelta(minutes=1)).not_valid_after(expiry)
               .add_extension(x509.BasicConstraints(ca=ca, path_length=1 if issuer is None and ca else (0 if ca else None)), True)
               .add_extension(x509.KeyUsage(True, False, False, False, False, ca, ca, False, False), True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
               .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signer_key.public_key()), False))
    if not ca:
        purpose = ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH
        builder = builder.add_extension(x509.ExtendedKeyUsage([purpose]), False)
        if server:
            builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), False)
    return builder.sign(signer_key, hashes.SHA256())


class Authority:
    def __init__(self, store=None):
        self.root_key = ec.generate_private_key(ec.SECP384R1())
        self.root = certificate(name("ISOLATED TEST ROOT - NOT FLEET TRUST"), self.root_key, self.root_key, None, ROOT_DAYS, True)
        self.device_key = ec.generate_private_key(ec.SECP256R1())
        self.device = certificate(name("ISOLATED TEST DEVICE ISSUER"), self.device_key, self.root_key, self.root, 1825, True)
        self.server_key = ec.generate_private_key(ec.SECP256R1())
        self.server = certificate(name("ISOLATED TEST SERVER ISSUER"), self.server_key, self.root_key, self.root, 1825, True)
        self.authorizations = {}
        self.revoked = set()
        self.store = store
        self.operator_fingerprints = set()
        self.trusted_device_issuers = [self.device]

    def peer_revoked(self, serial):
        return serial in self.revoked or (self.store is not None and self.store.is_revoked(serial))

    def authorize(self, serial, csr):
        # Trusted local operator method, NOT an unauthenticated HTTP API.
        self.check_csr(serial, csr)
        if self.store is not None:
            return self.store.authorize(serial,
                hashlib.sha256(csr.public_bytes(serialization.Encoding.DER)).digest(),
                self.device.fingerprint(hashes.SHA256()).hex())
        token = secrets.token_urlsafe(32)
        self.authorizations[hashlib.sha256(token.encode()).digest()] = {
            "serial": serial, "digest": hashlib.sha256(csr.public_bytes(serialization.Encoding.DER)).digest(),
            "expires": now() + timedelta(minutes=10), "response": None,
        }
        return token

    def check_csr(self, serial, csr):
        if not csr.is_signature_valid or csr.subject != name(serial):
            raise ValueError("CSR proof/subject rejected")
        if not re.fullmatch(r"[0-9a-f]{12}", serial):
            raise ValueError("serial rejected")
        if not isinstance(csr.public_key(), ec.EllipticCurvePublicKey) or csr.public_key().curve.name != "secp256r1":
            raise ValueError("unsupported key")

    def issue(self, serial, csr):
        self.check_csr(serial, csr)
        # Ignore all requested extensions: issuer controls CA and EKU policy.
        key_proxy = type("PublicOnly", (), {"public_key": lambda _: csr.public_key()})()
        return certificate(name(serial), key_proxy, self.device_key, self.device, LEAF_DAYS)

    def bootstrap(self, serial, token, csr):
        self.check_csr(serial, csr)
        if self.store is not None:
            result = self.store.redeem(serial, token,
                hashlib.sha256(csr.public_bytes(serialization.Encoding.DER)).digest(),
                self.device.fingerprint(hashes.SHA256()).hex(), lambda: pem(self.issue(serial, csr)))
            return x509.load_pem_x509_certificate(result)
        grant = self.authorizations.get(hashlib.sha256(token.encode()).digest())
        digest = hashlib.sha256(csr.public_bytes(serialization.Encoding.DER)).digest()
        if not grant or grant["serial"] != serial or not secrets.compare_digest(grant["digest"], digest) or grant["expires"] <= now():
            raise ValueError("enrollment authorization rejected")
        if grant["response"] is None:
            grant["response"] = self.issue(serial, csr)
        # Same authorized CSR retry is idempotent, never a second issuance.
        return grant["response"]

    def check_peer(self, peer):
        if self.peer_revoked(peer.serial_number) or not peer.not_valid_before_utc <= now() < peer.not_valid_after_utc:
            raise ValueError("client identity rejected")
        for issuer in self.trusted_device_issuers:
            try:
                peer.verify_directly_issued_by(issuer)
                break
            except (ValueError, InvalidSignature):
                continue
        else:
            raise ValueError("client issuer rejected")
        if ExtendedKeyUsageOID.CLIENT_AUTH not in peer.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
            raise ValueError("client purpose rejected")

    def enroll(self, peer, csr):
        self.check_peer(peer)
        serial = peer.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        self.check_csr(serial, csr)
        if public(peer.public_key()) != public(csr.public_key()):
            raise ValueError("CSR is not bound to authenticated client key")
        return self.issue(serial, csr)


def response(certs):
    return base64.b64encode(pkcs7.serialize_certificates(certs, serialization.Encoding.DER))


def handler(authority):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Never log enrollment authorization or request bodies.

        def reply(self, status, body, kind="application/pkcs7-mime; smime-type=certs-only"):
            self.send_response(status)
            self.send_header("Content-Type", kind)
            if kind.startswith("application/pkcs7-mime"):
                self.send_header("Content-Transfer-Encoding", "base64")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/.well-known/est/cacerts":
                self.reply(200, response([authority.root, authority.device, authority.server]))
            elif self.path == "/identity":
                der = self.connection.getpeercert(binary_form=True)
                if not der:
                    self.reply(403, b"")
                    return
                peer = x509.load_der_x509_certificate(der)
                try:
                    authority.check_peer(peer)
                except (ValueError, x509.ExtensionNotFound):
                    self.reply(403, b"")
                    return
                serial = peer.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                self.reply(200, json.dumps({"serial": serial}).encode(), "application/json")
            else:
                self.reply(404, b"")

        def do_POST(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size < 1 or size > 65536:
                    raise ValueError("request format rejected")
                body = self.rfile.read(size)
                if self.path == "/operator/enrollment-authorizations":
                    if authority.store is None or self.headers.get("Content-Type") != "application/json":
                        raise ValueError("operator request rejected")
                    der = self.connection.getpeercert(binary_form=True)
                    if not der:
                        raise ValueError("operator mTLS required")
                    peer = x509.load_der_x509_certificate(der)
                    if peer.fingerprint(hashes.SHA256()).hex() not in authority.operator_fingerprints or \
                            authority.peer_revoked(peer.serial_number) or \
                            ExtendedKeyUsageOID.CLIENT_AUTH not in peer.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
                        raise ValueError("operator identity rejected")
                    request = json.loads(body)
                    csr = x509.load_der_x509_csr(base64.b64decode(request["csr"], validate=True))
                    token = authority.authorize(request["serial"], csr)
                    self.reply(200, json.dumps({"authorization": token, "expires_in": 600}).encode(), "application/json")
                    return
                if self.headers.get("Content-Type") != "application/pkcs10":
                    raise ValueError("request format rejected")
                csr = x509.load_der_x509_csr(base64.b64decode(b"".join(body.split()), validate=True))
                if self.path == "/bootstrap":
                    auth = self.headers.get("Authorization", "")
                    if not auth.startswith("Basic "):
                        raise ValueError("authorization required")
                    serial, token = base64.b64decode(auth[6:], validate=True).decode().split(":", 1)
                    cert = authority.bootstrap(serial, token, csr)
                elif self.path in ("/.well-known/est/simpleenroll", "/.well-known/est/simplereenroll"):
                    der = self.connection.getpeercert(binary_form=True)
                    if not der:
                        raise ValueError("mTLS identity required")
                    cert = authority.enroll(x509.load_der_x509_certificate(der), csr)
                else:
                    self.reply(404, b"")
                    return
                self.reply(200, response([cert, authority.device]))
            except (ValueError, TypeError, IndexError, KeyError, x509.ExtensionNotFound):
                self.reply(403, b"")
    return Handler


def validate(cert, key, serial, authority):
    if authority.peer_revoked(cert.serial_number):
        raise ValueError("candidate is revoked")
    cert.verify_directly_issued_by(authority.device)
    authority.device.verify_directly_issued_by(authority.root)
    authority.root.verify_directly_issued_by(authority.root)
    if cert.subject != name(serial) or public(cert.public_key()) != public(key.public_key()):
        raise ValueError("candidate identity mismatch")
    if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca:
        raise ValueError("candidate is a CA")
    if ExtendedKeyUsageOID.CLIENT_AUTH not in cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value:
        raise ValueError("candidate is not a client identity")
    for item in (cert, authority.device, authority.root):
        if not item.not_valid_before_utc <= now() < item.not_valid_after_utc:
            raise ValueError("candidate chain dates rejected")
    if cert.not_valid_after_utc > authority.device.not_valid_after_utc:
        raise ValueError("candidate outlives issuer")


def activate(store, cert, key, serial, authority, proof):
    validate(cert, key, serial, authority)
    generation = store / ("generation-" + secrets.token_hex(8))
    generation.mkdir(mode=0o700)
    write(generation / "cert.pem", pem(cert) + pem(authority.device))
    write(generation / "key.pem", private(key))
    # Persist both directory entries before publishing a pointer to them.
    for directory in (generation, store):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    if not proof(generation):
        raise ValueError("candidate authentication proof failed; previous generation unchanged")
    pointer = store / ("pointer-" + secrets.token_hex(8))
    write(pointer, json.dumps({"generation": generation.name, "serial": serial}).encode())
    os.replace(pointer, store / "current.json")
    fd = os.open(store, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return generation


def run_tests():
    os.umask(0o077)
    authority = Authority()
    serial = "001122334455"  # Synthetic test device, never a fleet AP.
    key = ec.generate_private_key(ec.SECP256R1())
    csr = x509.CertificateSigningRequestBuilder().subject_name(name(serial)).sign(key, hashes.SHA256())
    token = authority.authorize(serial, csr)
    with tempfile.TemporaryDirectory(prefix="isolated-est-") as directory:
        root = Path(directory)
        write(root / "root.pem", pem(authority.root))
        tls_key = ec.generate_private_key(ec.SECP256R1())
        tls_cert = certificate(name("localhost"), tls_key, authority.server_key, authority.server, LEAF_DAYS, server=True)
        write(root / "server.pem", pem(tls_cert) + pem(authority.server))
        write(root / "server.key", private(tls_key))
        server = http.server.HTTPServer(("127.0.0.1", 0), handler(authority))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(root / "server.pem", root / "server.key")
        context.load_verify_locations(root / "root.pem")
        context.verify_mode = ssl.CERT_OPTIONAL
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"https://localhost:{server.server_port}"
        client = ssl.create_default_context(cafile=str(root / "root.pem"))

        def post(path, body_csr=csr, credentials=None, tls=client):
            headers = {"Content-Type": "application/pkcs10", "Content-Transfer-Encoding": "base64"}
            if credentials:
                headers["Authorization"] = "Basic " + base64.b64encode(credentials.encode()).decode()
            request = urllib.request.Request(url + path, base64.b64encode(body_csr.public_bytes(serialization.Encoding.DER)), headers)
            with urllib.request.urlopen(request, context=tls, timeout=5) as result:
                assert result.headers["Content-Type"].startswith("application/pkcs7-mime")
                return pkcs7.load_der_pkcs7_certificates(base64.b64decode(result.read()))

        def refused(fn):
            try:
                fn()
            except (urllib.error.URLError, ValueError, ssl.SSLError):
                return
            raise AssertionError("unexpected acceptance")

        try:
            refused(lambda: post("/bootstrap"))
            refused(lambda: post("/bootstrap", credentials=serial + ":wrong"))
            other_key = ec.generate_private_key(ec.SECP256R1())
            other_csr = x509.CertificateSigningRequestBuilder().subject_name(name(serial)).sign(other_key, hashes.SHA256())
            refused(lambda: post("/bootstrap", other_csr, serial + ":" + token))
            birth_chain = post("/bootstrap", credentials=serial + ":" + token)
            birth = next(c for c in birth_chain if c.subject == name(serial))
            retried = next(c for c in post("/bootstrap", credentials=serial + ":" + token) if c.subject == name(serial))
            assert birth.serial_number == retried.serial_number
            validate(birth, key, serial, authority)
            write(root / "birth.pem", pem(birth) + pem(authority.device))
            write(root / "device.key", private(key))
            client.load_cert_chain(root / "birth.pem", root / "device.key")
            operational = next(c for c in post("/.well-known/est/simpleenroll") if c.subject == name(serial))
            validate(operational, key, serial, authority)
            write(root / "operational.pem", pem(operational) + pem(authority.device))
            renewal = ssl.create_default_context(cafile=str(root / "root.pem"))
            renewal.load_cert_chain(root / "operational.pem", root / "device.key")
            renewed = next(c for c in post("/.well-known/est/simplereenroll", tls=renewal) if c.subject == name(serial))
            validate(renewed, key, serial, authority)
            assert renewed.serial_number != operational.serial_number
            refused(lambda: post("/.well-known/est/simplereenroll", other_csr, tls=renewal))
            refused(lambda: post("/.well-known/est/simpleenroll", tls=ssl.create_default_context()))
            store = root / "generations"
            store.mkdir(mode=0o700)

            def identity_proof(generation):
                ctx = ssl.create_default_context(cafile=str(root / "root.pem"))
                ctx.load_cert_chain(generation / "cert.pem", generation / "key.pem")
                with urllib.request.urlopen(url + "/identity", context=ctx, timeout=5) as result:
                    return json.load(result)["serial"] == serial

            activate(store, operational, key, serial, authority, identity_proof)
            before = (store / "current.json").read_bytes()
            refused(lambda: activate(store, renewed, key, serial, authority, lambda _: False))
            assert (store / "current.json").read_bytes() == before
            generation = activate(store, renewed, key, serial, authority, identity_proof)
            assert json.loads((store / "current.json").read_text())["generation"] == generation.name
            assert (generation / "key.pem").stat().st_mode & 0o777 == 0o600
            authority.revoked.add(operational.serial_number)
            refused(lambda: post("/.well-known/est/simplereenroll", tls=renewal))
            refused(lambda: activate(store, operational, key, serial, authority, identity_proof))
            # Root replacement is a separate trust transition, never a clock
            # manipulation or replacement of any production listener.
            replacement = Authority()
            # Explicit issuer overlap, not an issuer-CN comparison or implicit
            # permission granted merely by loading another root into TLS.
            replacement.trusted_device_issuers.append(authority.device)
            replacement_tls_key = ec.generate_private_key(ec.SECP256R1())
            replacement_tls_cert = certificate(name("localhost"), replacement_tls_key, replacement.server_key,
                                               replacement.server, LEAF_DAYS, server=True)
            write(root / "replacement-server.pem", pem(replacement_tls_cert) + pem(replacement.server))
            write(root / "replacement-server.key", private(replacement_tls_key))
            write(root / "overlap-roots.pem", pem(authority.root) + pem(replacement.root))
            rotation = http.server.HTTPServer(("127.0.0.1", 0), handler(replacement))
            rotation_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            rotation_context.minimum_version = ssl.TLSVersion.TLSv1_2
            rotation_context.load_cert_chain(root / "replacement-server.pem", root / "replacement-server.key")
            rotation_context.load_verify_locations(root / "overlap-roots.pem")
            rotation_context.verify_mode = ssl.CERT_OPTIONAL
            rotation.socket = rotation_context.wrap_socket(rotation.socket, server_side=True)
            rotation_thread = threading.Thread(target=rotation.serve_forever, daemon=True)
            rotation_thread.start()
            url = f"https://localhost:{rotation.server_port}"
            try:
                refused(lambda: post("/.well-known/est/simplereenroll", tls=client))
                overlap_client = ssl.create_default_context(cafile=str(root / "overlap-roots.pem"))
                overlap_client.load_cert_chain(generation / "cert.pem", generation / "key.pem")
                migrated = next(c for c in post("/.well-known/est/simplereenroll", tls=overlap_client) if c.subject == name(serial))
                validate(migrated, key, serial, replacement)
                write(root / "migrated.pem", pem(migrated) + pem(replacement.device))
                overlap_client.load_cert_chain(root / "migrated.pem", root / "device.key")
                with urllib.request.urlopen(url + "/identity", context=overlap_client, timeout=5) as result:
                    assert json.load(result)["serial"] == serial
                assert migrated.not_valid_after_utc <= replacement.device.not_valid_after_utc
            finally:
                rotation.shutdown()
                rotation.server_close()
                rotation_thread.join(timeout=5)
            assert operational.not_valid_after_utc - now() > timedelta(days=RENEW_DAYS)
            print("PASS: loopback TLS, CSR-bound bootstrap/idempotent retry, mTLS EST enroll/reenroll, wrong-key/trust/revocation refusal, validated generation commit/failed-proof rollback")
            print("PASS: isolated root/server transition refuses old-only trust; explicit dual-root overlap permits authenticated AP reissuance and new identity")
            print("TEST ONLY: no production issuer/service, AP enrollment, real OWGW proof or complete EST conformance")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    run_tests()
