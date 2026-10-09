# Thor shared-installer source pieces

These helpers belong to the single shared installer. They are not a complete
migration adapter: only inspection and individual preparation/write/staging
pieces are implemented, so the dispatcher's full phase checks still refuse
installation. No AP writes, builds, ENV changes or reboots were performed.

## Implemented and verified

`oem_adapter_inspect` publishes context only after checking the exact model,
source release, own ART identity, physical bank geometry and offsets, current
cmdline/UBI binding, healthy original OEM volumes, explicit ENV configuration
and the complete warning-free fw_printenv response. The retained vendor source
is genuinely Thor 7.2-r1; source metadata and the complete 26-partition profiles
are in `profiles/XV3-8`. Thirty inspection cases passed.

`oem_thor_local_payload` authenticates both local kernel/root members against
bundle and descriptor pins. `oem_thor_update_existing_child` constrains writes
to the inactive bank's existing kernel0/rootfs1 children, checks shared physical
boundaries and UBI health, then verifies exact readback. Twenty-three cases
passed. Original OEM `ubi_rootfs` is not silently renamed by this helper.

`oem_thor_prepare_native_layout` requires the published 2026.10.05.8 image and
its actual kernel/root pins, local authenticated runtime and reusable radio
assets, the complete physical inventory, verified off-device minimal backup,
and an idle target containing only the two original OEM volumes. It supports
the original reviewed source-bank1/target-bank0 direction. It calls the existing
`ab_prepare_bank` allocator unchanged, constraining each operation to the same
physical target. It reserves eight vault and twenty certificate LEBs before
allocating the remaining overlay. It performs no ENV arm or payload/seed write.
Unknown, unattached or resumed OpenWiFi targets are refused rather than erased.

Seventeen allocator/wrapper cases passed using the actual allocator, current
shared helpers and actual .8 kernel/root bytes. Failures were injected at all
11 operation points. Synthetic active-bank, ART, manufacturing, ENV and boot
bytes remained unchanged. Device operations and character-node lookup are
fixture actors; this is not physical power-loss qualification.

`oem_thor_stage_native_overlay` binds the existing FORMAT2 stager to the exact
inspected Thor serial, release, slots, target MTD/overlay and published image.
Nine actual producer/stager cases passed, including fresh umask077, public
upper0755, private directories700/files600, context and failure checks. Image
policy and mount records are fixture boundaries; no real OverlayFS/UID81
execution, enrollment, device or boot operation occurred.

Character nodes must be nonsymlinks with major/minor matching their sysfs
identity. All release objects must be fully authenticated locally before
preparation. No streaming download, unique identity in generic assets, new
registry, issuer or watchdog admission gate is introduced. Existing manual
reset/power-cycle one-shot scope remains unchanged.

## Remaining integration work

The owner still needs the real reusable radio/vault contents map and own-device
vault construction/readback; safe attachment/resume handling; composition of
payload writes, FORMAT2 staging/readback, sync/unmount and the reviewed armer;
and native mixed-bank confirmation plus the first normal sysupgrade while the
OEM bank remains intact. Converted-to-OEM restoration needs its own validated
volume transition and exact nonunique configuration reset operation.

Profiles must account for genuine exposed master MTD nodes if present; their
names cannot be invented or omitted. The shared backup helper's named
BOOTCONFIG allowance was fixed upstream to accept the actual 128 KiB records.
Use the updated shared helper; never truncate those protected records.

The .8 artifact does not by itself establish that later source boot fixes are
packaged. The completed boot fix remains separate and is not reopened here.
No full migration, restore or first-sysupgrade readiness is claimed.

## Running the focused fixtures

Each test prints its precise fixture boundaries. Pass the current shared helper
location explicitly when testing this source branch against the owner's code.

```sh
python3 tools/oem-migration/unified/tests/family-thor-inspection.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-existing-child.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-profiles.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-seed.py SETTINGS_LIB
python3 tools/oem-migration/unified/tests/family-thor-layout.py COMMON_LIB PREPARED_RUNTIME_ROOT ACTUAL_PROVIDER
```
