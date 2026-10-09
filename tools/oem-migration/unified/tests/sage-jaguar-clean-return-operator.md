# Sage/Jaguar clean OEM return: separate identity retirement

`CONFIRM OEM` confirms the healthy OEM candidate and its reviewed boot selector.
It does **not** retire native OpenWiFi enrollment. The working OpenWiFi bank,
configuration, certificates and recovery information remain intact throughout
the unconfirmed trial. Native factory reset is not identity retirement either:
on Sage it does not clear the shared `certificates` UBI volume (ID 7).

The forward fresh-install adapter must continue to refuse an existing native
identity store. Do not bypass that refusal, reuse an old onboarding key, or
describe confirmed OEM return alone as a clean re-enrollment-ready device.

## One separate operator action, after healthy OEM confirmation

The human must explicitly authorize **retirement of this AP's previous
OpenWiFi private identity**, identifying its canonical serial and old leaf
fingerprint. This authorization is separate from OEM boot confirmation and
factory reset. It means losing the old OpenWiFi slot's usable enrollment;
until that action is complete, preserve its recovery path and identity.

The retirement operation must:

1. Verify healthy confirmed OEM boot, exact model/source release, native boot
   selector and actual mounted root. Keep the AP isolated/offline from the
   OpenWiFi gateway while retiring it. No instant gateway revocation is assumed.
2. Resolve the exact old OpenWiFi identity stores from the actual parent MTD,
   UBI parent, volume ID **and** `certificates` name, with mount/mountinfo and
   block-device alias checks. Do not use a guessed `/dev/ubiN` or volume name
   alone. Sage uses the shared `fs` parent / certificate ID 7. Jaguar uses
   bank-local certificate ID 4; examine both banks for retained copies of the
   same old identity. Never erase the bank, source kernel/root, ART, MFG, vault,
   OEM identity, shared nvram or unrelated configuration to clear a certificate.
3. Inventory the exact old identity stores, retained on-AP private-key copies,
   old leaf fingerprint and store/bank/parent bindings. This is the operator's
   cleanup boundary, not a new manufacturing registry. There is **no mandatory
   per-AP backup of replaceable certificates or private keys**. Routine unique
   recovery material remains ART/MFG/ENV/indispensable BOOTCONFIG only.
   If the human separately requests old-key recovery, use a separately approved
   encrypted/private destination under a Root-only 0700 directory with files
   0600. Never send keys or certificates through the ordinary HTTP critical
   relay, and never make optional old-key recovery a routine admission gate.
4. Clear only the proved old native identity and its retained private-key
   copies, then verify absence/readback on every identified store. An automatic
   reset, unmount success or server revocation does not prove AP key removal.
   If the source overlay/backup-file inventory or a mount/alias/parent binding
   is unresolved, stop rather than claiming `identity-cleared`.
5. On the server, use the already delivered `reset_native_enrollment.py` with
   this exact serial and old leaf fingerprint. Obtain a fresh read-only dry-run
   binding, then apply with that exact binding, a new private database-backup destination
   and `--offline-identity-cleared` **only after steps 1–4 are actually proved**.
   That mandatory backup protects the server tool's own database state; it is
   distinct from optional AP old-key recovery. The tool does not access or clear
   the AP. It preserves issued/revoked,
   lifecycle and audit history; it retires only the named current membership,
   grant/cache and lifecycle state. Do not replace this with SQL or Delete-unused.
6. Use the existing approved fresh enrollment-batch flow after authoritative
   inventory/ownership is ready. Run the fresh unified installer with the new
   privately entered batch key; the AP generates a new key/CSR. Verify new
   enrollment, controller configuration and confirmed boot before calling the
   complete return/re-enrollment path accepted.

Server reference: `m0vse/wlan-cloud-ucentral-deploy` commit
`4c7d334f3271a4df4d339b3ac2c4767825bec185`, deployed tool SHA-256
`f2ee04566fc4dbdcdfa263b9eb3d0898467dea92119d34f6c2e1373ce7e7c0df`.
The 2026-10-08 delivery receipt records a successful live **dry-run**, not a
reset apply. No new CA, database schema, manufacturing gate or signing flow is
introduced here.

## Current implementation boundary

The adapter does not yet automate this destructive retirement operation. It
preserves identities and displays the lifecycle boundary. Exact live store and
retained-key-copy discovery and human cleanup authorization must be reviewed
before an executable cleanup command is issued. Optional old-key recovery needs
separate consent and a private encrypted destination, not an extra routine gate.
No AP/server credential operation was run to prepare this note. Fixture writer
or OEM confirmation success is not evidence of a completed identity retirement.
