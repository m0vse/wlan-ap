# Thor shared-installer source pieces

The source adapter now defines the shared dispatcher's complete forward phases
and the separate converted-to-OEM test-return phases. The final release schema
and transaction scope are in `family-thor-release-interface.md`. Publication,
actual AP qualification and first-normal-upgrade integration are separate.
No AP writes, builds, ENV changes or reboots were performed.

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
Unknown or resumed OpenWiFi targets are refused rather than erased. A currently
unattached bank is attached only inside the confirmed transaction after backup
and source save, then its entire namespace is inspected before erasure.

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

## Whole-path results

33 complete forward cases passed, including unattached-target inspection and
identity-store refusal: the successful path and failure injection at
all30 persistent/process steps, with no premature arm. Actual published .8
image/parts and the actual shared vendor BDF were used; the source producer,
stager, allocator, source/physical/ENV checks executed. The generated vault also
passed the unchanged shipped .8 consumer, and the actual identity context
command/pending-boot script accepted the writer's staged triplet.

26 complete OEM-return cases passed across both source banks, including
unattached targets, with failure
injection at all11 persistent/process steps per direction. The actual pinned
7.2-r1 meaningful FIT/SquashFS were used. Active firmware and both inactive
identity children remained byte-identical in the fixtures. Six exact .8 guard/
health cases proved native-accepted healthy commit, prior-only rollback, and
handoff back to the standard guard after genuine conversion.

All device/fwtools/mount operations remain isolated file actors. Native identity
acceptance/cleanup and network/physical health are subprocess/health actors;
these cases do not perform a production enrollment or physical power-loss test.

## Integration and readiness boundary

The full transaction now composes preparation, actual payload/vault writes and
readback, private FORMAT2 production/staging, persisted read-only verification,
sync/unmount and final guarded arm. The incoming .8 hook uses the shipped native
health/confirmation mechanism without reporting its OEM bank as converted.
The reverse writer preserves both identity children and implements the actual
rootfs-to-ubi_rootfs transition using pinned vendor7.2-r1 parts.

Release assembly needs the exact authenticated member paths in
`family-thor-release-interface.md`; it must not use a stripped/intermediate
upgrade file. Genuine extra master MTD nodes require genuine profile rows.
The upstream named BOOTCONFIG allowance accepts the actual128KiB records;
use the updated helper and never truncate them.

The standard .8 first sysupgrade still requires actual conversion; no flag is
fabricated here to bypass it. Physical migration/return qualification and OEM
health confirmation/defaults remain separate. No AP readiness claim is made.
The completed boot fix and working reboot-required setting remain untouched.

## Running the focused fixtures

Each test prints its precise fixture boundaries. Pass the current shared helper
location explicitly when testing this source branch against the owner's code.

```sh
python3 tools/oem-migration/unified/tests/family-thor-inspection.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-existing-child.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-profiles.py COMMON_LIB
python3 tools/oem-migration/unified/tests/family-thor-seed.py SETTINGS_LIB
python3 tools/oem-migration/unified/tests/family-thor-layout.py COMMON_LIB PREPARED_RUNTIME_ROOT ACTUAL_PROVIDER
python3 tools/oem-migration/unified/tests/family-thor-forward.py COMMON_LIB PREPARED_RUNTIME_ROOT ACTUAL_PROVIDER IMAGE BDF SETTINGS_LIB
python3 tools/oem-migration/unified/tests/family-thor-restore.py COMMON_LIB PREPARED_RUNTIME_ROOT ACTUAL_PROVIDER OEM_KERNEL OEM_ROOT
python3 tools/oem-migration/unified/tests/family-thor-handoff.py
```
