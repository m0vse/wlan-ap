# Per-device migration job handoff

This is an integration contract, not an executable installer. A root-authorized
portal action creates one resumable, ownership-bound job and private per-device
API key. Protected retrieval delivers the exact approved command/bundle to the
AP; there is no server-side SSH execution service or operator countdown.

The shared job backend and PKI lifecycle remain owned by the provisioning
service. Do not add a second issuer, identity store or activation protocol.

## Admission and delivery

The backend evaluates `qualification.py` using trusted policy, authoritative
inventory and verified runtime evidence. The AP's initial reader verifies exact
source identity/layout without changing flash, environment, configuration or
device identity. Unknown, unsupported, unqualified, cross-model or wrong-source
jobs stop before persistent staging, backup or enrollment. The operations remain
`production-oem-migration` and `production-stock-openwrt-migration`; qualification
for one cannot authorize the other. Routine renewal remains separate.

Retrieve the job over hostname-verified HTTPS using independently provisioned
trust. Do not accept a trust anchor from the same downloaded bundle as proof of
that bundle's authenticity. The reviewed job envelope must bind job ownership,
version, operation, canonical serial, exact model/SKU/revision/region, source
capability digest, installer/image/recovery digests and qualification policy.
The existing backend owns cancellation, current ownership and resumable key/CSR
binding. API field names and routes must be taken from that backend's actual
interface, not inferred from this contract. An API key is job authorization,
not a firmware signing key. Keep it out of URLs, logs, image defaults and
ordinary configuration archives. No generic firmware secret is permitted.

## AP execution sequence

1. Complete read-only source and policy checks and authenticate the exact bundle.
2. Generate the device's unique private key and CSR locally, then use the shared
   backend's atomic first-CSR binding and enrollment protocol. Preserve a
   resumable candidate handoff using the approved private lifecycle store.
3. Invoke only the qualified family/source adapter. Protect the running bank,
   unique calibration/identity and reviewed recovery set. Stock migration clears
   legacy configuration through its existing bridge/sysupgrade route; candidate
   identity handoff must survive independently of the discarded configuration.
4. Boot the candidate and use the shared sole-client activation flow in
   `tests/private-pki/private-activation-nonce.md`. Verify the protected receipt
   binds the expected serial, candidate TLS leaf, fresh nonce and ordinary
   gateway session. Issuance or transmitting a nonce alone is insufficient.
5. Commit the durable candidate identity and then the qualified bank transaction
   only after acceptance evidence is persisted. Any failure must preserve or
   restore the prior identity/client and qualified source-bank recovery.

The source lifecycle store helper is a primitive. Its existence does not prove
this sequence works on a target. The target firmware must contain the agreed
orchestrator, store, native client hook and bank guard before a job is enabled.

## Existing adapter insertion points

Paths below are repository-relative source references, not published bundle URLs.

| Source | Current interface | Integration boundary |
| --- | --- | --- |
| OEM, controller-neutral stock fork | `scripts/cambium-oem-prepare.sh check`, `inspect-capture ROOT`, `backup NEW_PRIVATE_DIRECTORY`; Sage delegate and `cambium-oem-models.tsv` | Read-only identity/layout first; backup is admission-gated. No production OEM writer exists yet and all OEM write qualifications remain disabled. |
| OEM payload verification, stock fork | `scripts/cambium-oem-verify-bundle.py` | Workstation authenticated payload verifier; not an OEM runtime dependency or installer. |
| Converted stock Sage | `tests/installer/sage-stock6-r3/sage-sysinstall.sh --check\|--install` | Sealed IMAGE/SHA256SUMS bundle, prepare-upgrader bridge recovery/install/verification, then stock `sysupgrade -n -T` and `sysupgrade -v -n`. |
| Converted stock Jaguar | `tests/installer/jaguar-stock-r3/jaguar-sysinstall.sh --check\|--install` | Same bridge/preflight boundary with the exact family's hardware-data protection. |
| Stock Thor | `tools/thor-installer/thor-sysinstall.sh --check\|--install --stock` | Reviewed source inputs only; README requires assembly/qualification of the complete bundle. |

Existing Cheetah stock operator bundles are local generated artifacts, not a
canonical source adapter in this directory. Select its reviewed source with the
family owner before publication. Existing wrappers do not yet implement the
per-job identity handoff above. Do not substitute the historical
`e410-oem-install-openwrt.sh` for a production OEM writer, or invoke generic
sysupgrade from OEM. Each OEM writer needs qualified tools, geometry, inactive
capacity, image semantics, boot guard and recovery evidence first.

Extreme OEM recovery uses one authenticated shared kernel/root set per exact
model/variant plus this AP's own unique data. Restore reviewed OEM U-Boot defaults
merged with unique factory fields; never copy a donor environment or rewrite
bootloader executable code as part of this flow.
