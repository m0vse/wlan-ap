# Frozen Thor shared-release interface

Forward source is exact XV3-8/SKU00000013 OEM7.2-r1, with the retained build
tuple in `profiles/XV3-8/source.tsv`. Both source0→target1 and source1→target0
use the same actual .8 parts and the corresponding physical profile/FIT bank
configuration. Source-only ENV persistence/readback precedes target operations;
all unlisted ENV fields and unique regions stay protected.

## Authenticated local release members

The shared SHA256SUMS ledger must cover every member below before preflight.
The operator launcher/framework files retain their existing shared assembly.
No helper fetches lazily or streams HTTP to flash.

- `adapters/thor.sh`, `adapters/restore-thor.sh`, `adapters/thor-handoff.sh`,
  `adapters/upgrade-thor.sh`
- `lib/cambium-installer-settings.sh` (existing FORMAT2 producer/stager)
- `runtime/cambium-ab.sh`, `runtime/cambium-ab-upgrade.sh`,
  `runtime/cambium-ab-thor.sh` (existing prepared allocator/boot source)
- `profiles/XV3-8/source.tsv`, `critical.tsv`, `payloads.tsv`, `vault-assets.tsv`,
  `mtd-slot0.tsv`/`mtd-slot1.tsv` for forward; `mtd-openwifi-slot0.tsv` and
  `mtd-openwifi-slot1.tsv` for reverse
- `payloads/XV3-8/image.bin`, `kernel.bin`, `rootfs.bin`
- `payloads/shared-radio/thor-bdwlan.b215.accton`
- `payloads/XV3-8/oem/kernel.bin`, `payloads/XV3-8/oem/rootfs.bin` for return

For metadata-first assembly, the existing six-column `payload-map.tsv` must
select four install objects (complete image, kernel, root, shared BDF) and two
restore objects (OEM kernel/root). Its remote-object column is publisher-owned;
use the actual uploaded object keys, not guessed URLs. The family-specific
`payloads.tsv` remains exactly the two kernel/root descriptor rows. The common
owner's0b8933fa already accepts the exact Thor shared-radio member spelling.

Raw runtime files must be placed exactly at those three member names. The
source loader explicitly disables directory autoload when using this cache,
then loads the named Thor module: the upgrade library is not a family module.
No whole ELF/libc checksum is used as an AP admission gate. Full source ledgers
remain publisher evidence; the actual commands, source tuple and physical
inventory are checked through existing framework interfaces.

## Exact released objects

| Member | Bytes | SHA256 |
| --- | ---: | --- |
| image.bin (.8 published upgrade) | 29327664 | ef1bbf0fcdc72252df64b3b6944462c7b01eca2d1973a0e1ef8daed00035aae9 |
| kernel.bin | 14125888 | c04f44290a710c169c47886f3a870f630a74a8c3b6e0c203a0e93ccc7411b2c1 |
| rootfs.bin | 15195136 | 670029e07e61e956c9b5788ca8fae36f7e05511fbf1f55183d32ecad528e17a3 |
| shared Thor BDF | 131072 | 831633e2451a456f3f71d4ad49429f519c0148ba1a37312e74e30533ce8adfab |
| OEM meaningful FIT | 3905000 | 9650712dc69a82342ebe2dee753110805dd6154024f305db80ae91d1165a93aa |
| OEM meaningful SquashFS | 40233806 | 75bc545a6cad4fb66642798194318be02a32cf21cd4cd07caf08a75da48a3214 |

Use the complete published upgrade file, including its release metadata. The
29307184-byte intermediate `unified-thor-provider-inputs-20261009/image.bin`
with digest95fb28fe447564fee481019058b811ddf76adc0818f32e0ca52a2f9f68809db7
is refused; it is not the complete published image pin. The complete tested
copy is `/private/tmp/thor-unified-actual-20261005-8.bin`.

The shared BDF was read from the independently verified vendor7.2-r1 SquashFS,
using its exact OEM path. It is reusable model data, not unit calibration. Own
ART remains untouched; the vault manifest binds to its live whole-partition
hash and the exact .8 board/SKU ABI. Meaningful OEM parts come from the verified
shared vendor image, not a unit's raw bank capture. Their retained source paths
are recorded in the existing vendor-source evidence.

## Transaction and native handoff

Read-only preflight accepts an unattached inactive bank after source/physical
proof. It does not attach during check or before operator confirmation. After
all inputs are local, verified critical backup and the durable source save,
the transaction may attach that exact target to inspect its namespace. Forward
requires only the two original healthy OEM children before formatting; any
identity/unknown child stops it. Reverse requires the five healthy native
children and captures only private hashes of its two protected identity
children before firmware updates. No blank/corrupt/resumed target is guessed.
The bank-offset reader uses the existing unique live kernel-range fallback if
older OEM sysfs omits offsets; absence is never inferred from partition order.

Forward prepares private FORMAT2 inputs before any bank write, saves/reads the
working OEM default, calls the existing allocator, writes both actual .8 parts
with exact readback, writes/verifies the AP-bound vault, and mounts the overlay.
It invokes the existing settings stager, installs the authenticated handoff
module under `upper/lib/functions/cambium-ab-thor-handoff.sh`, syncs/unmounts,
reopens read-only to verify persistence, unmounts again, then arms last.

The armer calls the existing reviewed trial generator and verifies its exact
prior-only result. The trial persists only the prior bank before candidate load. Exact .8's guard
module glob loads the handoff hook. The hook delegates to its existing ab_guard
and native installer health/acceptance path, allowing confirmed cleanup while
keeping the retained OEM bank distinguishable through thor_migration_oem_slot.
It never fabricates thor_ab_version=1. Once a genuine later conversion sets
that flag, the hook declines takeover so the original normal A/B guard runs. The stable candidate command can fall
back to the retained OEM command if the candidate boot returns. A failed reset
returns only to the previous working bank; automatic hang recovery is not
claimed beyond the agreed manual-reset/power-cycle contract.

The incoming-source receipt contains exact public .8 guard/core/Thor/board-data,
health, identity, worker, pending-boot, mount and preinit file bytes. The focused
handoff replay executes the shipped guard/health, identity context command,
pending-boot and vault consumer. Native acceptance/cleanup subprocesses and
physical/network/TLS boundaries remain actors; no fresh production enrollment
or full Ucode crypto protocol execution is claimed by these tests.

Return admits confirmed converted .8, uses its genuine DT config-tail mapping,
retains the active bank and both inactive identity children, removes only the
inactive firmware overlay, renames child1 from rootfs to ubi_rootfs, resizes that dynamic
SquashFS child and writes/readbacks the pinned OEM FIT/root. It saves the running
native command before these changes and arms an OEM trial last. The durable
fallback remains the previous native bank. No full-bank format, identity copy
or configuration reset occurs in return. OEM health confirmation and an
explicit defaults/reset operation are distinct later actions.

## Scope

All changes are source-only in the isolated Thor branch. No AP access/write,
firmware build, publication, trust change or reboot occurred. These full phase
implementations supersede the earlier missing-phase notes in writer-fields.
Publisher assembly must include the exact members above. Actual extra exposed
master MTDs remain refused unless genuine profiles account for them.

The .8 standard sysupgrade still requires actual two-native-bank conversion;
this migration does not fake that flag. Shared first-normal-upgrade integration
and physical migration/restore qualification remain separate work. Both paths
print readiness as unverified; source fixture success does not assert those
hardware outcomes.

## Targeted safety correction receipt

Reverse source save narrows `thor_stableSOURCE` to exactly `run thor_bootSOURCE`
in the same verified batch as source-only bootcmd/image. The shipped .8 guard's
rollback recording and stable-default commit body were replayed on that actual
wrapper: any later `run thor_stableSOURCE` selects only the working source.

Before the last selector, the reverse path repeats the pinned local object
checks and both staged kernel/root readbacks, UBI health, full physical/ENV
preservation and private identity hash comparison, then reads every prepared
arm field again. Late kernel/root, identity, unrelated ENV and four arm-field
drifts refuse the selector. Forty-two full return cases passed across both
banks, including the original eleven operation failures per direction.

Before target attachment, direct mounted/open raw MTD, read-only MTD and block
aliases are refused by canonical path and device number. Nine targeted cases
proved busy sources cause no attachment. No real device/ENV action was taken.

`../profiles/XV3-8/installer-runtime-inputs.json` records the exact c604 runtime
root/file hashes and both already-decoded signed OEM object paths on cnbeacon.
These are publisher input receipts, not new AP ELF/libc admission checks.
Publication remains on hold pending review of these targeted corrections.

## Clean return and reuse composition

The confirmation phase observes the actually running OEM bank, healthy mounted
SquashFS, exact signed7.2 kernel/root readbacks, the vendor kernel-build check,
physical geometry and pending/prior selectors. It repeats those checks after
critical backup, then commits only native bootcmd/image and confirmation fields.
It does not reboot, run a factory reset or retire an identity. The known OEM
startup resets ENV on nonempty mtdids/fsbootargs; reverse preflight refuses
that incompatible handoff before writing rather than permitting an implicit
OEM repair to discard the saved source.

After separately authorized defaults reset and unused-store retirement, forward
admits the exact confirmed-return marker tuple only when both unused certificate
stores are absent. The held native target must have kernel0/rootfs1/overlay2 and
its own raw vault3; unknown children, residual identity, foreign/corrupt vault
or busy aliases refuse. The raw-vault parser is the reviewed Jaguar parser with
the Thor file/model/ART bindings, not a new archive format or issuer gate.
Only inactive software and old overlay are reclaimed. Vault3 is neither resized
nor written; cert4 is created only from proven absence. The original fresh-OEM
format path remains separate. Entire raw-vault bytes are compared throughout.

Both complete source-only round-trip directions passed on actual pinned input
bytes: return→running OEM confirmation→explicit config-reset actor→explicit
unused-store-retirement actor→fresh forward reuse. Six residual-cert/vault/
namespace refusal cases and eight RAM-root/kernel/root/pending-selector
confirmation refusals passed. Device, boot, backup transport, reset and
retirement are declared fixture boundaries; no real identity action occurred.

Installed readiness is a separate read-only phase. It loads actual installed
helpers, never the publisher's corrected runtime cache. Confirmed single-native
state reports conversion required; actual bare .8's unsafe older trial command
reports unsupported. Ready also requires actual installed source-persistence
support, correct source routing, existing native upgrade preflight and own-vault
validation. Four exact .8 cases passed without ENV mutation. No installed .8
first-normal-upgrade support is inferred from these source changes.
