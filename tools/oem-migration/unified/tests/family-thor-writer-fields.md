# Thor local writer-piece integration

These are source helpers for the single shared installer, not a second launcher
or a released migration adapter. `adapters/thor.sh` implements actual read-only `oem_adapter_inspect` and the
local existing-child pieces. It does not define all four complete dispatcher
phases until their exact OEM transition mapping is wired.
An incomplete adapter therefore cannot satisfy the dispatcher's phase checks.
The main-reviewed boot increment is separate at
`/private/tmp/thor-one-shot-current-main`, frozen HEAD
`327c42f8b035f6c19bd77df38188c1eef7365c13`.

## Implemented pieces

`oem_thor_local_payload kernel|rootfs` reads only independently authenticated
local bundle members. `profiles/XV3-8/payloads.tsv` has exactly two tab-separated
rows: role, direct role-specific `payloads/XV3-8/ROLE.bin` path, positive byte
count at most 100663296, lowercase SHA256. Every row and payload is a pinned
bundle member, and role-specific descriptor size/hash must match actual bytes.
This does not itself establish FIT/DT/rootfs/model boot semantics; reuse the
existing release image validators before calling the writer.

`oem_thor_update_existing_child kernel|rootfs` requires context derived by the
owner's preflight: exact SKU `00000013`/XV3-8, distinct source/target slots and
physical MTDs, a uniquely attached target UBI and the complete protected-range
inventory. It calls actual shared `oem_write_boundary` and `oem_ubi_child_check`
before updating only existing kernel child 0 or rootfs child 1. It repeats child
health/binding and checks exact pinned payload readback afterward. It retains
a per-role writing/failure/verified journal. No bank erase, child removal,
create/resize, ENV arm, network fetch, service stop or reboot is implemented.

The existing OEM `ubi_rootfs` child is not silently reclassified or removed.
Both-bank conversion and restore need the owner's explicit, validated
name/ID/layout transition and volume inventory. Certificate/vault children are
not accepted writer roles. The current active bank and unique ART/MFG/boot data
are never writable via this helper. A backup does not override those boundaries.
All required release objects must be staged locally by the common network
owner before any earlier erase; these helpers perform no network operation.

## Required mapping, context and remaining source gap

The existing common model record needs exact SKU/family/model/adapter/tested OEM
source version; no Thor OEM version is guessed here. The owner can use the
existing `/etc/version` reader only with its actual tested exact version row,
and derive serial from verified own factory identity, not an operator field.
Source/target bank proof includes cmdline, current UBI parent, ENV image and
captured 96 MiB/0x20000/2048/126976 geometry. The original OEM writer reference
allows OEM on bank 1 and target bank 0; bank-0 OEM requires its actual reviewed
opposite-direction mapping, not an inherited flag.

The release also needs the complete eight-column physical profile, genuine
manufacturing-identity location, minimal critical backup map, destination
kernel/root pins and both FIT/root-bank configurations, shared model/revision
radio/BDF/regdb assets, exact local-only helper inventory, and original OEM
restore payload/container extraction mapping. None requires a new registry,
issuer or signing service. Do not copy unique ART/calibration into generic
release payloads. Reuse existing protected FORMAT2 producer/stager with actual
serial/source slot/target slot/source contract/image hash/job/controller/EST
context. No private input/key/CSR/cert material is included in this commit.

The remaining full adapter phases are exact released source preflight,
critical backup/upload receipt, the explicit OEM volume-layout transition,
vault/FORMAT2 staging and readback, sync/unmount and existing one-shot arm.
Restore must preserve the previous working OpenWiFi slot and identity, and
factory configuration reset needs exact nonunique targets. Those gaps are not
passing stub cases and do not admit Thor installation. No new watchdog gate is
added; the agreed manual-reset/power-cycle one-shot scope remains.

## Fixtures

```sh
python3 tools/oem-migration/unified/tests/family-thor-existing-child.py PATH_TO_UNIFIED_OWNER_LIB
```

23 cases passed with the actual owner `common.sh` and `protection.sh` from
`/private/tmp/unified-oem-wlan-ap/tools/oem-migration/unified/lib`: both banks and
roles, local pin/size/descriptor failures, active aliases, wrong parents,
duplicate UBI attachments/names, unhealthy markers, protected/overlapping
ranges, partial update/retry and readback/metadata failures. Character-device
lookup and ubiupdatevol are temporary-file actors; actual bundle/range/child
logic executes. Synthetic active-bank/ART/MFG/ENV/BOOTCONFIG/certificate/vault
sentinels stay unchanged. No device, network, mounts, firmware build, real key
prompt or ENV/boot action occurs. This is not physical power-loss or complete
forward/restore qualification.

## Retained source fields now implemented

`oem_adapter_inspect` clears stale context and only publishes it after complete
read-only validation. It uses the shared `/etc/version` reader (VERSION token),
unique physical `rootfs`/`rootfs_1` names, sizes/erase/write geometry and exact
physical offsets, cmdline `ubi.mtd`/root, uniquely bound dynamic UBI index and
healthy `kernel`/`ubi_rootfs` children. The explicit named NOR ENV configuration
must agree across /etc and /tmp; `fw_printenv -c ... -n image/bootcmd` must agree
with the actual source slot and original `aq_load_fw&&bootipq` default. Exact
XV3-8 factory base identity is read from own 256 KiB ART at byte offset 0x40,
length six, matching the retained reference; no radio-MAC arithmetic or donor
identity is used. No manufacturing registry or new watchdog gate is introduced.

25 actual inspection/context fixtures pass: both source banks, relocated MTD
indices, synthetic exact-version acceptance and old/new/missing/conflicting
version refusal, physical/root/volume/ENV disagreement, wrong model and invalid
ART identity. Shared context enforces the released exact version; the synthetic
`fixture-supported` token does not admit a real OEM version. Source file bytes
and modes stay unchanged. fw_printenv and character-device lookup are actors,
while actual inspection, shared readers and own-ART byte extraction execute.

The concrete unavailable release inputs are: the exact real OEM version row and
its applicable capabilities; authenticated complete model/source physical and
minimal-critical profiles (including the genuine unique manufacturing record
if it is a separate backup requirement); local destination image/contents/FIT
metadata plus model/revision reusable radio assets; original OEM restoration
payload/container mapping; and the approved kernel/ubi_rootfs-to-rootfs layout
transition and allocation/inventory needed before the child writer can run.
Keep all unknown/outside-target unique regions untouched. Absence of a factory
record format does not justify a new registry or copying full customer config.
Original stock `thor_write` uses ubiformat/factory UBI, which this shared child
plan intentionally does not pretend to authorize. The FORMAT2 seed/native
worker already exists; the owner wires it after the actual transition and
readback, using existing private 0700/0600/public-upper0755 rules.
