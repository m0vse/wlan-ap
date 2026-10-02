"""Isolated policy component, not an installed AP renewal daemon.

One-year leaves renew with 90 days remaining or earlier for issuer expiry.
Failure retries never disable authentication or treat an expired leaf as valid.
"""
from datetime import datetime, timedelta, timezone

RENEWAL_WINDOW = timedelta(days=90)


def renewal_decision(certificate, issuing_chain, stamp=None, failures=0):
    stamp = stamp or datetime.now(timezone.utc)
    chain = [certificate, *issuing_chain]
    if not chain or any(item.not_valid_before_utc > stamp for item in chain):
        return {"action": "clock-or-chain-invalid", "retry_seconds": 900}
    expiry = min(item.not_valid_after_utc for item in chain)
    remaining = (expiry - stamp).total_seconds()
    if remaining <= 0:
        return {"action": "authenticated-recovery-required", "retry_seconds": 0}
    due = expiry - RENEWAL_WINDOW
    if stamp < due:
        return {"action": "wait", "retry_seconds": min(3600, max(1, int((due - stamp).total_seconds())))}
    # Avoid hot loops during outages; bound retries before the credential ends.
    backoff = min(21600, 900 * 2 ** min(max(int(failures), 0), 7))
    return {"action": "renew", "retry_seconds": min(backoff, max(1, int(remaining / 4)))}
