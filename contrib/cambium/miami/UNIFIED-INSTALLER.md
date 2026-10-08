# Miami provider contract for the unified installer

The unified installer owns detection, operator prompts, downloads, recovery
uploads and the complete migration flow. Miami reuses the generated persistent
provider and the shared FORMAT2 producer. The old `miami-oem-persistent-test.sh`
name is a compatibility backend, not a separate production operator interface.

## Recognized hardware and source

The supported Miami model is X7-35X, SKU `0000002c`, with controller device ID
`cambium_x7-35x` and display model `Cambium Networks X7-35X`. Unknown models,
source releases or layouts must stop before writing anything.

The retained OEM capture is release `7.2-r1`, Linux 5.4.213. Its private
`private/miami/x7-35x/oem-7.2-r1/report.txt` contains the OEM VERSION and the
physical partition bounds; its SHA-256 is
`7deeec60c09d426b5f9920551fdc222b8767612ab1adf1e7d7556516487e98f0`.
The older test value `7.1-r1` is synthetic and does not admit that OEM release.
The U-Boot version is separate from the OEM VERSION.

NAND banks are 96 MiB at offsets `0xc0000` and `0x60c0000`, with 128 KiB
eraseblocks, 2048-byte writes and 126976-byte UBI LEBs. OEM NOR exposes 4096-byte
erase sectors; the environment occupies one complete 64 KiB region. OpenWrt's
NOR erase geometry differs. Resolve real physical partitions by name, type,
parent and range; never reuse captured numeric MTD/UBI indices. Whole-chip
parent nodes, read-only aliases and exported UBI MTD views are not write targets.

## Fully staged local operation

The release manifest authenticates the generated helper and both slots' object
maps. The header contains `KERNEL0`, `ROOTFS0`, `PAIR0` and their `_SHA`/`_SIZE`
fields, plus the equivalent slot-1 fields. Before migration, the common bounded
download helper stages the selected kernel, rootfs and pair descriptor locally.
The helper also stages every other release dependency before any persistent
write or boot arm. Recovery upload must have its required verified receipt.

The provider accepts these non-secret variables:

| Variable | Contract |
| --- | --- |
| `CAMBIUM_INSTALL_CACHE_DIR` | Absolute canonical root-owned directory, mode 0700. |
| `CAMBIUM_INSTALL_LOCAL_ONLY=1` | Requires the cache and forbids HTTP fallback. |
| `CAMBIUM_ENROLMENT_SERVER` | Validated controller hostname, supplied by the common wrapper. |

Every cached member must be a root-owned, single-link regular file, mode 0600,
with exact size and SHA-256. Missing, changed or unsafe members fail. The
provider copies verified local objects into its existing temporary paths and
verifies them again. Install/update validates the pair descriptor before
attaching the target or recording any storage writes. Arm uses the same cache.
The server may disappear after staging; it is not needed for storage writes or
the bootloader fallback. Native enrolment/health still needs its controller;
failure prevents confirmation of the candidate.

The common private prompt passes the enrolment key to a shell function in a
scoped subshell that sources the independently pinned provider. It must not
execute a child shell with the key in its arguments, export the key, enable
shell tracing or print it. No family-specific secret flag is required. Legacy
backend CLI support remains for compatibility, not for the unified flow.

## Storage and recovery boundaries

Preserve the running OEM bank and all unique calibration/factory/boot data.
Backup only indispensable per-device ART/calibration, factory identity,
environment and boot records. A backup never authorizes overwriting them.
Neither a whole-bank image nor a whole-firmware dump is a routine requirement.

Clean OEM targets have kernel volume 0 and `ubi_rootfs` volume 1. The provider
stages and validates the running unit's radio vault before changing the target.
The OpenWiFi bank uses kernel 0, rootfs 1, overlay 2, radio vault 3 (72 LEBs) and
certificates 4 (64 LEBs). Reject unknown/duplicate volumes, corrupt/update
markers, mounts, mappings, open device handles, geometry/range mismatches and
insufficient space. Remove an idle rootfs block mapping only after proving its
exact inactive parent and that it is unused; never remove a guessed mapping.

Payload readback must finish before boot arm. The initial OEM-to-OpenWiFi boot
restores and saves the retained OEM default before loading the candidate. It
is one attempt; confirmation is based on native identity, controller
configuration and services. The qualified pilot has manual reset/power-cycle
fallback. Automatic watchdog recovery and physical interruption inside NOR
environment erase/program are not established by synthetic tests.

## Normal upgrade readiness

`cambium-ab-status` and `cambium-return-oem --check|--arm` are existing shared
commands. `cambium-ab-ready` is the common read-only readiness interface. Status
must distinguish `onboarded` from `ready` and `unsupported`.

The proven OEM-preserving b6d1a26f image is onboarded, not sysupgrade-ready:
the other bank is read-only, the platform rejects Miami upgrades, and the
image has no admitted sysupgrade artifact. A one-shot boot does not prove A/B
readiness. Converted-layout OEM restoration is also not currently admitted.

Future controlled A/B testing needs a reviewed running kernel/profile with
both firmware banks writable and every unique partition protected; complete
pre-RAM certificate/key/policy export and sealed RAM handoff; a target-specific
FIT/sysupgrade image; source-only durable fallback before the first OEM-bank
write; verified identity/vault restore; and one-shot native healthy
confirmation. The first upgrade overwrites the retained OEM bank only when
the human explicitly runs the qualified workflow. Later upgrades must return
to the previous working OpenWiFi bank on failure, never blindly to `bootipq`.

No forced generic NAND path, automatic second upgrade, enrollment reset or
certificate replacement is part of this contract. No A/B production-ready
claim is made until those source paths and the controlled hardware test pass.

## Evidence and test scope

The corrected producer explicitly creates overlay `upper` as 0755; private
root/seed directories remain 0700 and files 0600. Actual generated-provider
tests and real private-namespace OverlayFS checks established public access
for capability-free UID 81 while denying access to the private seed.

`test-local-cache.py` executes the actual provider against regular-file
MTD/UBI/environment fixtures. Its 48 pre-write refusals cover both slots and
missing, truncated, altered, linked, wrongly owned or wrongly permissioned
kernel/root/pair objects and unsafe caches. Both-slot offline install/arm is
tested without HTTP. This specific test arms without an enrolment key;
native producer/cache integration is a separate generated-provider test.
All synchronization and device mutations in these fixtures are mocked.

Hardware evidence covers OEM-preserving first boot, native enrolment,
controller connection/configuration application and a successful repeat boot.
It does not establish every A/B upgrade/restore, physical power-loss point,
renewal or client-traffic behavior. Shared harness results must state those
limits and explicitly test unsupported model/version refusal.
