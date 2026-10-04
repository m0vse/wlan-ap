# Shared enrollment migration handoff

This is an integration contract, not an executable installer. One root-authorized
portal bulk action approves a migration batch with one shared enrollment key.
The operator reuses that private key through the same protected input file or
non-echoing prompt across installer runs. No per-AP operator key generation or
individual portal approval is required. The backend authorizes approved batch
members and binds each device's first CSR independently.
Initial migration is operator-assisted;
post-install onboarding is automatic. There is no controller-to-private-LAN
execution agent, server-side SSH service or operator countdown.

The shared enrollment backend remains owned by the provisioning service. Certificate
enrollment and lifecycle use native OpenWiFi EST. Do not add a bespoke issuer,
identity store or activation protocol.

## Admission and delivery

The backend evaluates `qualification.py` using trusted policy, authoritative
inventory and verified runtime evidence. The AP's initial reader verifies exact
source identity/layout without changing flash, environment, configuration or
device identity. Unknown, unsupported, unqualified, cross-model or wrong-source
jobs stop before persistent staging, backup or writes. The operations remain
`production-oem-migration` and `production-stock-openwrt-migration`; qualification
for one cannot authorize the other. Routine renewal remains separate.

Supply the approved batch material and authenticated bundle to the local installer through
the protected operator channel. Any HTTPS retrieval must verify the hostname
using independently provisioned trust. Do not accept a trust anchor from the
same downloaded bundle as proof of its authenticity. Firmware admission binds
the actual source operation, serial, exact hardware, capability and artifact
digests to approved qualification, separately from enrollment authorization.
No job-download, job-version or remote execution protocol is required.
The shared enrollment key authorizes
only the approved migration batch, not arbitrary devices or Root operations.
It is enrollment authorization,
not a firmware signing key. Keep it out of URLs, logs, image defaults and
ordinary configuration archives. No generic firmware secret is permitted.
The shared batch key must not be compiled into firmware or treated as a global
Root API credential. Each AP still generates its own private key and CSR;
first-CSR binding and native renewal remain per-device.

The protected Root API is `POST /api/v1/pki/create-enrollment-key` with
`{serials: [canonical serials], operation: "migration"}`. Its response contains
`id`, `enrollmentKey`, `devices`, `operation` and `server`. Download that material
privately, never to chat or public firmware hosting. The wire operation
`migration` does not collapse the two source-specific qualification operations.
Native EST enrollment uses Basic canonical serial/shared key with a locally
signed CSR whose CN is that serial, standard base64 DER PKCS10 input and base64
PKCS7 output. Subsequent renewal uses native certificate authentication.

### Exact firmware admission metadata

Use the frozen `openwifi.oem-migration-qualification.v1` evaluator schema rather
than a second model allowlist. The trusted qualification registry and verified
local source/bundle evidence provide these normalized objects. They are not
additional fields required from the shared-key API response. Extract exactly
these fields for the evaluator; batch response metadata is not evaluator input.

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

Sage E410 revision A and E410B revision B are distinct hardware revisions.
Early B units shared the A-style enclosure; later B enclosures changed without
another hardware revision. Identify A/B from verified manufacturing product and
revision evidence, never case appearance or assumed storage capacity. Retain
separate A/B qualification and hardware support checks.

For OEM, the source capability digest binds the exact reviewed OEM release,
tools, layout, inactive geometry and boot guard, and the recovery digest binds
the exact shared OEM recovery set. For stock OpenWrt, those digests bind its
independently qualified stock release/updater bridge/runtime and stock rollback
set. A stock job must not require OEM qualification. Verify the AP manufacturing
identity and source/layout read-only against those contracts before staging
or writing. The issuer also reevaluates current qualification before enrollment
side effects; possessing a batch key cannot bypass current registry refusal.

## Secure local input boundary

The local installer takes an authenticated firmware bundle and a separate
private enrollment-input path, not an API key in its command line. These are
integration inputs, not new executable flags on the existing family wrappers.
The secret input must be a regular file owned by root, mode 0600, within a
root-owned 0700 directory. Reject symlinks, shared/writable parent directories,
wrong owner/mode and unapproved serial/source operation before copying the material
to persistent AP storage. Outgoing OEM and stock firmware never invoke
enrollment or generate a device key/CSR. Never source or evaluate the
input as shell code. Do not print its contents, enable shell tracing, include it
in receipts, or place it in public artifact hosting or ordinary backup archives.

After successful admission, the reviewed transport stages the approved input
into a private AP path without exposing credentials in arguments, URLs or logs.
On OpenWiFi first boot, the AP generates its own key and CSR; no private device
key is generated in the portal or copied from another AP. Native EST uses `/certificates/est.json` with
`server` and `tls_ca`, and the root-only curl configuration
`/certificates/est-bootstrap.conf` with Basic username equal to the canonical
serial and password equal to the shared approved batch enrollment key.
Both files are root-owned mode 0600; the credential is not a gateway discovery
secret. Exact serialization/transport and executable bootstrap adapter remain
owned by the CA integration and must be tested before use.

Native output is `/etc/ucentral/operational.pem` and
`/etc/ucentral/operational.ca`, persisted under `/certificates/` with the same
basenames, using the AP-local `/etc/ucentral/key.pem` and CSR. Atomic persistence,
key handoff, reload and rollback require the lifecycle owner's tested interface.
Preserve bootstrap credentials for interrupted retries. Remove them only after
confirmed per-device completion and verified normal native connection; enroll
success alone is not completion. The exact completion/cleanup interface remains
pending, not an assumed server job API. Completion of one AP removes only that AP's
bootstrap copy; it must not revoke the shared batch key while other approved
devices still need enrollment or retries. Batch cancellation/revocation stops
new enrollment without substituting the batch key for native mTLS renewal.
Unlinking is cleanup, not a claim of physical
secure erasure on flash. No new retrieval API is required merely to supply this
local input. Existing batch authorization/revocation checks still apply.

After installation, approved inventory/configuration and provisioned identity
drive automatic onboarding. DHCP option 224 overrides the private gateway
default; EST trust/configuration remains separate from gateway discovery.

### First-boot key and retry boundary

Outgoing OEM and stock installers only validate exact model/source and policy,
preserve critical recovery, stage protected enrollment authorization/settings,
write the verified inactive bank and arm the qualified recoverable candidate.
They must not request a certificate or require EST, OpenSSL, curl, ucode or a
certificate issuer runtime on the outgoing firmware. Source capability contracts
cover the actual reader, writer, authenticated delivery and recovery tools only.
No enrollment runtime is packaged for old firmware.

Authorization staging must be bound to canonical factory serial, exact model,
actual source operation/bank, candidate bank, transaction ID and verified image
digest. It must survive the clean migration without overwriting the source or
its recovery identity. Require atomic protected publication, durable flush and
readback before arming the candidate. Preserve authenticated bridge closure,
inactive-only geometry and the source's existing empty-store/rollback guards.
The native lifecycle owner defines the fixed staged file schema and first-boot
consume interface; wrappers must not introduce a parallel secret reader or
certificate implementation. Nothing in this document enables an old seed that
requires an already issued identity or source-generated private key.

Once OpenWiFi boots and networking is ready, DHCP option 224 overrides the
private gateway default. The minimal first-boot coordinator validates staged
provenance against the running bank and actual factory identity, then invokes
the native EST client. Before first contact it generates the unique AP-local key
once, atomically persists that key and CSR intent in qualified private candidate
storage, flushes them and rereads/validates them. Interrupted or uncertain
issuance retries retain the same durable key and CSR identity. RAM alone is
insufficient. Do not copy a donor key or generate the AP key in the portal.

Native EST must validate bootstrap trust, issued serial/key/issuer and secure
durable certificate persistence. It then reconnects the native controller client.
Only a fresh authenticated connection and configuration actually received and
successfully applied in that session permit bank confirmation. Reject stale
connection flags and old configuration files. Bounded retry and rollback retain
the working source and do not erase an unrelated prior identity or interrupt
normal native renewal. Cleanup follows durable confirmation, never issuance
alone; remove only this AP's bootstrap copy, leaving the shared batch key usable
by other approved members.

## AP execution sequence

1. Finish read-only source/model/policy checks and authenticate the exact bundle.
2. Preserve minimal unique recovery and stage protected authorization/settings
   with exact serial/model/source/job/candidate/image provenance. Generate no
   key/CSR and make no enrollment request on outgoing OEM or stock firmware.
3. Use the qualified family/source adapter to write and verify only the inactive
   bank, preserving the source, calibration, factory identity and shared recovery
   set. Complete durable staging/readback before arming the recoverable candidate.
4. On OpenWiFi first boot after networking, validate staging provenance, resolve
   DHCP224 over the private default, persist the unique local key/CSR intent and
   enroll through the native EST client with interruption-safe same-key retries.
5. Validate and persist the intended identity/trust, reconnect the sole native
   controller client and require fresh authenticated connection plus successful
   configuration apply from that session. Issuance alone is insufficient.
6. Persist acceptance, confirm the bank transaction and clean this AP's bootstrap
   authorization. Failures use bounded retries/qualified rollback; background
   native renewal remains mandatory after acceptance.

Gateway VERIFIED/serial/issuer/expiry may corroborate acceptance later. No Root
API credential or new synchronous acceptance API belongs on the AP. Native
first-boot and staging adapters must be reviewed against this sequence before
family integration. Earlier source-side enrollment/key-seed helpers are
superseded and must not be included by a new migration wrapper. Retain useful
incoming identity persistence, controller configuration acceptance and native
renewal work; do not blindly deploy obsolete source-enrollment coupling. Source
fixtures alone do not enable production migration or lift the family build hold.

## Existing adapter insertion points

Paths below are repository-relative source references, not published bundle URLs.

| Source | Current interface | Integration boundary |
| --- | --- | --- |
| OEM, OpenWiFi recovery tools | `tools/oem-migration/recovery/scripts/cambium-oem-prepare.sh check`, `inspect-capture ROOT`, `backup NEW_PRIVATE_DIRECTORY`; Sage delegate and `cambium-oem-models.tsv` | Read-only identity/layout first; backup is admission-gated. No production OEM writer exists yet and all OEM write qualifications remain disabled. |
| OEM payload verification, OpenWiFi recovery tools | `tools/oem-migration/recovery/scripts/cambium-oem-verify-bundle.py` | Workstation authenticated payload verifier; not an OEM runtime dependency or installer. |
| Converted stock Sage | `tests/installer/sage-stock6-r3/sage-sysinstall.sh --check\|--install` | Sealed IMAGE/SHA256SUMS bundle, prepare-upgrader bridge recovery/install/verification, then stock `sysupgrade -n -T` and `sysupgrade -v -n`. |
| Converted stock Jaguar | `tests/installer/jaguar-stock-r3/jaguar-sysinstall.sh --check\|--install` | Same bridge/preflight boundary with the exact family's hardware-data protection. |
| Stock Thor | `tools/thor-installer/thor-sysinstall.sh --check\|--install --stock` | Reviewed source inputs only; README requires assembly/qualification of the complete bundle. |

Existing Cheetah stock operator bundles are local generated artifacts, not a
canonical source adapter in this directory. Select its reviewed source with the
family owner before publication. Existing wrappers do not yet implement the
protected authorization staging and first-boot enrollment above. Do not substitute the historical
`e410-oem-install-openwrt.sh` for a production OEM writer, or invoke generic
sysupgrade from OEM. Each OEM writer needs qualified tools, geometry, inactive
capacity, image semantics, boot guard and recovery evidence first.

Extreme OEM recovery uses one authenticated shared kernel/root set per exact
model/variant plus this AP's own unique data. Restore reviewed OEM U-Boot defaults
merged with unique factory fields; never copy a donor environment or rewrite
bootloader executable code as part of this flow.
