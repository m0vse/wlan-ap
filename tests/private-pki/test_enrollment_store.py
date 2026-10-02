"""Isolated restart/replay/concurrent issuance tests. No network or CA assets."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import tempfile
from enrollment_store import EnrollmentStore


def refused(fn):
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("unexpected acceptance")


def run_tests():
    serial = "001122334455"
    digest = hashlib.sha256(b"synthetic CSR").digest()
    clock = [1000]
    with tempfile.TemporaryDirectory(prefix="isolated-enrollment-db-") as work:
        path = Path(work) / "state" / "grants.sqlite"
        store = EnrollmentStore(path, lambda: clock[0])
        refused(lambda: store.authorize(serial, digest, "issuer-A"))
        store.approve(serial)
        token = store.authorize(serial, digest, "issuer-A")
        calls = []
        def issue():
            calls.append(1)
            return b"one synthetic certificate response"
        def redeem():
            return EnrollmentStore(path, lambda: clock[0]).redeem(serial, token, digest, "issuer-A", issue)
        with ThreadPoolExecutor(max_workers=4) as executor:
            responses = list(executor.map(lambda _: redeem(), range(8)))
        assert len(calls) == 1 and len(set(responses)) == 1
        restarted = EnrollmentStore(path, lambda: clock[0])
        assert restarted.redeem(serial, token, digest, "issuer-A", issue) == responses[0]
        assert len(calls) == 1
        refused(lambda: restarted.redeem(serial, token, hashlib.sha256(b"different").digest(), "issuer-A", issue))
        refused(lambda: restarted.redeem(serial, token, digest, "issuer-B", issue))
        refused(lambda: restarted.redeem("001122334456", token, digest, "issuer-A", issue))
        clock[0] = 1600
        refused(lambda: restarted.redeem(serial, token, digest, "issuer-A", issue))
        clock[0] = 1000
        interrupted = store.authorize(serial, digest, "issuer-A")
        def failed_issue():
            raise ValueError("synthetic pre-commit issuer failure")
        refused(lambda: store.redeem(serial, interrupted, digest, "issuer-A", failed_issue))
        assert store.redeem(serial, interrupted, digest, "issuer-A", issue) == responses[0]
        store.revoke(2**120 + 123)
        assert restarted.is_revoked(2**120 + 123)
        assert path.stat().st_mode & 0o777 == 0o600
        assert path.parent.stat().st_mode & 0o777 == 0o700
        with store.connect() as db:
            assert db.execute("SELECT count(*) FROM audit WHERE event='grant-issued'").fetchone()[0] == 2
        print("PASS: durable CSR/issuer/inventory-bound single issuance, concurrent/idempotent restart retry, expiry/mismatch refusal, pre-commit rollback and persistent revocation")


if __name__ == "__main__":
    run_tests()
