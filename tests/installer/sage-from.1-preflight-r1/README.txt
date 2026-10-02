Sage .1 normal-UI upgrade prerequisite checker, revision 1.
This bundle has no installer mode, bridge transaction or firmware payload.
Run only after checking the published archive checksum and unpacking privately:
  env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin sh ./check.sh

Authenticates reviewed source/runtime/release before sourcing AP helpers.
Checks confirmed qualified pair, compatibility1.0, same-UBI shared store,
mounted UBIFS geometry/privacy, current durable key/certificate matching,
cryptographic pairing, other runtime PEM/CA files matching durable copies,
and target volume reserved capacities. Cryptographic comparison uses only
private tmpfs public-key files, removed afterwards. No private key is printed.
Refusal means stop for diagnosis; no manual mount, repair or forced upgrade.

Offline scope: exact authentication gates passed against frozen Sage .1;
actual frozen ARM ash parses check.sh; unchanged shared-store checker passed
22 isolated cases (crypto real, identity/UBI/mount tables private fixtures).
Full driver has not been executed on an AP or simulated end to end.
Coordinator must review driver before publication/operator use.

PASS establishes prerequisites only, not an upgrade result or image approval.
Use the separately published .3 image pinned in SAGE-FROM1-NORMAL-UI-AUDIT.txt;
normal controller upgrade still performs its firmware validation. Human
trial/reconnect/configuration and identity retention/new-slot confirmation
remain required. Unknown/unmounted/absent/stale stores refuse conservatively.
