# Production migration qualification contract

`tools/oem-migration/qualification.py` exposes
`evaluate(trusted_record, authoritative_inventory, verified_runtime)` and returns
`{"allowed": boolean, "reason": string}`. It performs no I/O or side effects.
All three inputs must come from the caller's approved trust boundaries:
privately approved qualification policy, authoritative existing inventory and
verified source/runtime evidence. Requester-provided identity/model fields must
never create or substitute for inventory. Authenticate the operator and validate
CSR ownership separately before issuing a single-use grant.

The exact schema name is `openwifi.oem-migration-qualification.v1`. The record
requires exactly these fields, with no extra or absent fields:

```json
{
  "schema": "openwifi.oem-migration-qualification.v1",
  "operation": "production-oem-migration",
  "status": "unqualified",
  "exact_model": "EXACT-MODEL",
  "sku_hex": "00000000",
  "hardware_revision": "CAPTURED-REVISION",
  "region_compatibility": ["EU"],
  "source_capability_contract_digest": null,
  "installer_sha256": null,
  "target_image_sha256": null,
  "shared_recovery_manifest_sha256": null,
  "qualification_evidence_digest": null
}
```

This example denies admission. Do not install it as an approved record. Current
model/source manifests and fixture successes approve zero production OEM
models. `unsupported` reports a known unsupported model; every status except
`qualified` denies before staging, backup, inventory/config creation, issuer
approval, grant allocation or operator audit mutation. There is no force or
experimental trial operation. Named hardware qualification testing is managed
separately and never silently approves a model for production.

The two operations are `production-oem-migration` and
`production-stock-openwrt-migration`. A record for one cannot approve the other.
`source_capability_contract_digest` deliberately names the source generally,
so an OEM release/capability record is not required for an independently
qualified stock OpenWrt migration. Likewise, `shared_recovery_manifest_sha256`
binds that operation's reviewed recovery/rollback set; the stock route can use
its existing qualified stock recovery set. Extreme OEM recovery is an additional
shared model/variant capability, not an implicit prerequisite from the OEM
migration gate. Both migration routes use the same device key/CSR/grant and
durable identity/controller acceptance flow.

After admission, both adapters must use native OpenWiFi EST for enrollment and
certificate lifecycle. Bootstrap trust/authentication, local key/CSR creation,
certificate paths, persistence and client reload must follow the reviewed native
integration contract. Those target interfaces remain pending confirmation; do
not substitute a bespoke lifecycle service, nonce hook or certificate store.

Commit the candidate identity and bank transaction only after verified ordinary
gateway acceptance binds the expected canonical serial and candidate TLS leaf
to the current session. Persist sufficient acceptance evidence to distinguish
that session from a stale connection. Issuance alone does not complete migration.
Preserve prior identity and source-bank recovery until acceptance and restore the
prior identity/client on failure through the qualified rollback path. Native EST
integration, durable certificate persistence, renewal and physical AP acceptance
remain qualification gates; source tests do not enable a hardware migration.

Inventory requires exactly `serial`, `exact_model`, `sku_hex`,
`hardware_revision` and `region`. Serial is the canonical lowercase 12-hex AP
identity used by the existing provisioning contract. Do not assume a label's
manufacturing serial uses that format or derive a replacement identity.
Resolve the actual inventory schema in the service adapter instead of guessing
its model fields. Model and revision must be exact, trimmed nonempty strings;
SKU is eight lowercase hexadecimal digits.

Runtime requires exactly those five inventory fields, `operation`, and all
five digest fields above. Digests are lowercase SHA256 strings. Every identity
field must match authoritative inventory, model/SKU/revision must match the
qualified record, region must occur once in its approved region list, and the
operation and all digests must match. The caller must establish the runtime
evidence as verified; equality comparison is not remote attestation.

The issuer integration must evaluate this function against current private
policy before making any changes. Missing policy denies. Revoked qualification
must not remain allowed through a stale cached record. Actual API integration,
durable certificate-store activation and ordinary gateway-session acceptance
remain separate gates. Normal renewal on an already managed AP does not invoke
a new OEM migration qualification.

The tests use only a synthetic model and temporary in-memory records:

```sh
python3 tests/migration/test_oem_qualification.py
```

They check exact bindings, separate source operations, schema/type/unknown-field
refusals, each digest, serial/model/revision/region substitutions and absence of
input mutation. They do not establish model hardware acceptance, deploy a PKI
service or authorize an AP action. Private records, keys, grants, certificate
material and deployment hostname must never be committed here.
