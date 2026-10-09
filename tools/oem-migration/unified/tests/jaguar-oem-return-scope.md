# Jaguar source-preserving OEM return writer

This is a test return from confirmed OpenWiFi into an inactive OEM 7.2-r1
candidate. It is not a factory reset, native-identity retirement or a claim of
healthy OEM boot. The working source boot function, firmware, writable
configuration and native certificate store remain available.

## Provider map (same authenticated bundle mechanism)

Under `profiles/MODEL/restore/`:

- `source-contract`: exact running OpenWiFi version and reviewed source digest,
  two lines; `source-sets/runtime-implementation.set` retains publisher evidence
  with runtime admission limited to release/build, required native commands and
  critical identity/boot/updater hook rows.
- `source-boot0.sha256`, `source-boot1.sha256`: independently rendered qualified
  source boot-function hashes, not hashes accepted from observed ENV text.
- `mtd-slot0.tsv`, `mtd-slot1.tsv`: actual model-specific eight-column physical
  inventories, suffix **SOURCE** as in `jaguar-slot-profile-convention.md`.
- `operator-artifact-pins`: kernel, SquashFS and authenticated shared signed-
  source receipt digests, three lines; `oem-release`: `7.2-r1`, one line.
- `critical-backup.tsv`: the existing routine unique ENV/ART/MFG/indispensable
  BOOTCONFIG selection only. No per-AP firmware bank or replaceable-key backup.

Public payload paths: `payloads/MODEL/oem/kernel.itb`, `rootfs.squashfs`,
`shared.json`. For the independently verified vendor 7.2-r1 container, the
kernel is 4,048,776 bytes / SHA-256
`02a4fd7c84c5da2c1d9a89c332e2f8e13db6387b064dc7a3eb91616fa9d8d83b`,
root 42,709,508 bytes / SHA-256
`34e2e384c8874aa1b5149f82322f1f8bf9da250f02e02c6efc5dbd1d0056ba61`.
Native UBI capacity is kernel 32 / root 337 LEBs; this decoder/writer does not
execute vendor updater instructions or substitute OpenWiFi kernel/root files.
The publisher must bind the actual signed container/extraction receipt; a
synthetic fixture or an arbitrary file called `shared.json` is not such proof.

## Transaction boundaries

All public payloads and profiles are authenticated and checked locally before
ENV or target operations. Existing attached inactive banks must expose the
converted five-volume layout. Source boot function identity is checked before
changing control fields. The source-only default and narrowed source stable
wrapper are persisted/read back before any inactive operation; the latter
prevents the old OpenWiFi rollback guard restoring a dual-fall-through wrapper.

If the target is not attached, only standard target-only `ubiattach` is used
after explicit RESTORE OEM consent and source-only persistence. The exact
target physical identity, absence of an attached alias, direct mount/open-FD
aliases and local public payload hashes are rechecked immediately beforehand.
Attachment can perform UBI metadata writes; it is not described as read-only.
There is no invented read-only-attach utility, no active-bank detach and no
pre-attach claim of target-certificate byte proof. Newly discovered target
volume/parent/health/geometry/vault evidence must pass before erase/resize.

The inactive vault at ID 3 must be a consumer-valid raw format-1 tar bound to
this model, SKU and own ART. Required radio files, sizes, hashes, archive member
counts/types/paths and both zero end markers are checked. Only meaningful
original header/data/end-marker bytes are frozen; MANIFEST and assets are never
regenerated or replaced. Uncertain/foreign/formatted vaults refuse.

For XV2-2 only, when its 392-LEB budget otherwise cannot hold 32+337 OEM LEBs
plus the retained stores, the existing target raw vault is reduced to the ceil
of that verified archive length. Meaningful bytes are checked before/after and
throughout the transaction. The certificate volume at ID 4 is never removed,
resized, rewritten or remounted; its full bytes and name/type/alignment/data/
reserved geometry remain the discovered baseline. Larger banks keep the vault
size unchanged. No formatted filesystem is shrunk.

Only inactive software IDs 0/1 and nonunique overlay 2 are reclaimed. OEM
`kernel`/`ubi_rootfs` are created at IDs 0/1 and written/read back. The existing
shared helper can remove exactly one proven idle target rootfs block map, after
source-only persistence; a mounted/ambiguous map remains a refusal. Source
immutable data are hashed, while mutable source overlays/certificates are
protected by identity/geometry/health and no-source-writer exclusion, not an
accidental whole-UBIFS byte-equality gate.

Both OEM payload readbacks, retained vault/certificate proof, protected source,
unlisted ENV fields and arm-field readbacks are checked before the last selector
write. The one-shot prefix restores and saves the source-only default before
loading `setenv image TARGET; bootipq`; a failed save cannot load the candidate.
No confirmation/default reset/server identity cleanup is executed by this writer.

## Fixture limits

`test-jaguar-restore.py` composes the actual adapter/callbacks with inert media,
ENV, attachment, root-map and UBI tools. It covers three known models/two slots,
source-first ordering, actual incoming format-1 reader acceptance after raw
shrink, untouched source/target certificate proof, write interruptions, attach
failures/uncertainty, alias refusals and late payload/vault/certificate drift.
NOR offsets, source boot functions and payload bodies are deliberately synthetic
and do not qualify a real device or signed OEM image. Do not copy fixture
physical inventories into a production provider.

Real flash/ENV durability, power cuts, U-Boot execution and healthy OEM boot
remain hardware acceptance. Executable OEM confirmation and the separately
consented identity-retirement lifecycle are not claimed complete by writer
fixture success. No AP, build, certificate cleanup or stock-source mutation was
performed to implement these tests.
