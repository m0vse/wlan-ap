# Per-device migration job handoff

This is an integration contract, not an executable installer. A root-authorized
portal action creates one resumable, ownership-bound job and private per-device
API key. The operator runs the qualified local migration installer and securely
supplies that job's enrollment material. Initial migration is operator-assisted;
post-install onboarding is automatic. There is no controller-to-private-LAN
execution agent, server-side SSH service or operator countdown.

The shared job backend remains owned by the provisioning service. Certificate
enrollment and lifecycle use native OpenWiFi EST. Do not add a bespoke issuer,
identity store or activation protocol.

## Admission and delivery

The backend evaluates `qualification.py` using trusted policy, authoritative
inventory and verified runtime evidence. The AP's initial reader verifies exact
source identity/layout without changing flash, environment, configuration or
device identity. Unknown, unsupported, unqualified, cross-model or wrong-source
jobs stop before persistent staging, backup or enrollment. The operations remain
`production-oem-migration` and `production-stock-openwrt-migration`; qualification
for one cannot authorize the other. Routine renewal remains separate.

Supply the approved job and authenticated bundle to the local installer through
the protected operator channel. Any HTTPS retrieval must verify the hostname
using independently provisioned trust. Do not accept a trust anchor from the
same downloaded bundle as proof of its authenticity. The reviewed job envelope
must bind job ownership,
version, operation, canonical serial, exact model/SKU/revision/region, source
capability digest, installer/image/recovery digests and qualification policy.
The existing backend owns cancellation, current ownership and resumable key/CSR
binding. API field names and routes must be taken from that backend's actual
interface, not inferred from this contract. An API key is job authorization,
not a firmware signing key. Keep it out of URLs, logs, image defaults and
ordinary configuration archives. No generic firmware secret is permitted.

### Exact job admission metadata

Use the frozen `openwifi.oem-migration-qualification.v1` evaluator schema rather
than a second model allowlist. The download envelope carries these normalized
objects alongside the backend's job ID, envelope schema, current job version,
owner binding, current cancellation/completion state and authenticated manifest
identity/signing-key reference. Backend wire names remain its API contract;
extract exactly the following evaluator fields without passing wrapper metadata
as extra evaluator keys.

| Object | Required evaluator fields |
| --- | --- |
| Authoritative inventory | `serial`, `exact_model`, `sku_hex`, `hardware_revision`, `region` |
| Verified runtime | All five inventory fields, `operation`, and all five digests below |
| Trusted qualification | `schema`, `operation`, `status`, `exact_model`, `sku_hex`, `hardware_revision`, `region_compatibility`, and all five digests below |

The five digests are `source_capability_contract_digest`, `installer_sha256`,
`target_image_sha256`, `shared_recovery_manifest_sha256` and
`qualification_evidence_digest`. Each is lowercase 64-hex SHA256; serial is
lowercase 12-hex and SKU lowercase 8-hex. Only `status: qualified` admits a job.
Resolve exact hardware fields by joining existing inventory serial to privately
approved manufacturing evidence. Portal `deviceType` alone cannot establish
factory SKU/revision/region. Missing evidence denies; requester-supplied values
cannot populate that authoritative registry.

For OEM, the source capability digest binds the exact reviewed OEM release,
tools, layout, inactive geometry and boot guard, and the recovery digest binds
the exact shared OEM recovery set. For stock OpenWrt, those digests bind its
independently qualified stock release/updater bridge/runtime and stock rollback
set. A stock job must not require OEM qualification. Verify the AP manufacturing
identity and source/layout read-only against those contracts before enrollment
or writing. The issuer also reevaluates current qualification before enrollment
side effects; a prior downloaded approval cannot bypass later revocation.

## Secure local input boundary

The local installer takes a public approved job-envelope path and a separate
private enrollment-input path, not an API key in its command line. These are
integration inputs, not new executable flags on the existing family wrappers.
The secret input must be a regular file owned by root, mode 0600, within a
root-owned 0700 directory. Reject symlinks, shared/writable parent directories,
wrong owner/mode and unapproved job/serial/operation before copying the material
to persistent AP storage or invoking enrollment. Never source or evaluate the
input as shell code. Do not print its contents, enable shell tracing, include it
in receipts, or place it in public artifact hosting or ordinary backup archives.

After successful admission, the reviewed transport stages the approved input
into a private AP path without exposing credentials in arguments, URLs or logs.
The AP generates its own key and CSR; no private device key is generated in the
portal or copied from another AP. Native EST uses `/certificates/est.json` with
`server` and `tls_ca`, and the root-only curl configuration
`/certificates/est-bootstrap.conf` with the canonical serial/per-job credential.
Both files are root-owned mode 0600; the credential is not a gateway discovery
secret. Exact serialization/transport and executable bootstrap adapter remain
owned by the CA integration and must be tested before use.

Native output is `operational.pem` and `operational.ca`, using the AP-local
`/etc/ucentral/key.pem` and CSR. Full resolved output paths, atomic persistence,
reload and rollback behavior require the lifecycle owner's final tested handoff.
Preserve bootstrap credentials for interrupted retries. Remove them only after
server-confirmed job completion and verified normal native connection; enroll
success alone is not completion. Unlinking is cleanup, not a claim of physical
secure erasure on flash. No new retrieval API is required merely to supply this
local input. Existing job cancellation/ownership checks still apply.

After installation, approved inventory/configuration and provisioned identity
drive automatic onboarding. DHCP option 224 overrides the private gateway
default; EST trust/configuration remains separate from gateway discovery.

## AP execution sequence

1. Complete read-only source and policy checks and authenticate the exact bundle.
2. Generate the device's unique private key and CSR locally, then enroll through
   native OpenWiFi EST using the reviewed bootstrap trust/authentication. Bind
   the job to the actual device/CSR through the approved backend interface.
   Preserve a resumable candidate handoff using native certificate persistence.
3. Invoke only the qualified family/source adapter. Protect the running bank,
   unique calibration/identity and reviewed recovery set. Stock migration clears
   legacy configuration through its existing bridge/sysupgrade route; candidate
   identity handoff must survive independently of the discarded configuration.
4. Boot the candidate and reload the sole native client using the reviewed native
   identity interface. Verify ordinary gateway acceptance binds the expected
   serial and candidate TLS leaf to the current session, with evidence that
   distinguishes it from a stale connection. Issuance alone is insufficient.
5. Commit the durable candidate identity and then the qualified bank transaction
   only after acceptance evidence is persisted. Any failure must preserve or
   restore the prior identity/client and qualified source-bank recovery.

Native EST bootstrap/authentication, certificate paths, persistence, reload and
acceptance interfaces remain pending confirmation with the lifecycle owner.
Do not guess endpoints or retain bespoke nonce/store hooks as prerequisites.
The target firmware must contain and validate the agreed native EST integration
and bank guard before a job is enabled. Source tests alone do not enable a job.

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
