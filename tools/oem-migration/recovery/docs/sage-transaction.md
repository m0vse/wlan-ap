# Sage OEM transaction integration

The source runner loads three sibling libraries: `cambium-sage-pair-write.sh`,
`cambium-installer-settings.sh` and `cambium-oem-sage-transaction.sh`. The reviewed
native boot adapter is `cambium-oem-sage-boot.sh`. These are OpenWiFi sources;
no migration code belongs in the stock OpenWrt enhancement repository.

`cos_install IMAGE KERNEL ROOT SETTINGS_DIRECTORY` performs exact qualification,
authentication, live source and pending-job checks, FORMAT2 input validation,
inactive geometry/capacity and boot preflight before recovery or modification.
The authenticated source runner supplies `cos_admit`, `cos_authenticate` and
`cos_recovery`; `cambium-oem-sage-source.sh` implements the concrete read-only
`cos_source_check` and complete-environment `cos_refuse_pending` callbacks; these functions are
never loaded from operator settings. It must hold exclusive execution, freeze
private payloads, verify the actual FIT and SquashFS semantics, validate the
named 64 KiB OEM environment mapping and preserve device-specific recovery.
The existing qualification evaluator remains the authority; this library does
not enable an unqualified model or provide a trial-mode exemption.

The actual pair writer uses the reviewed OEM remove/create mechanism for the
inactive root, verifies both writes, and preserves the source and shared data.
The caller independently rereads both payloads, mounts the exact target
`rootfs_data`, invokes the shared FORMAT2 stager, syncs and unmounts it. Only then
can `cos_arm` publish native A/B metadata and finally the boot selector. It never
reboots. Existing pending migrations are refused before destructive staging;
there is no automatic formatting of a same-job candidate holding its identity.

The native adapter publishes `sage_ab_version=1` so the incoming pair guard runs,
plus confirmed source, candidate target, armed state and installer target/job/image.
It writes and reads back all metadata before writing `bootcmd` last. The one-shot
first saves the stable source fallback and `trial-started` state, then tries the
candidate and source commands. The source command remains the qualified OEM
`setenv image SOURCE; bootipq`, not a generated OpenWiFi command. The candidate
uses its authenticated E410 `config@5` or E410B `config@17` FIT with its exact
SquashFS root, overlay and slot arguments. Incoming native guard confirmation
uses `run sage_stableTARGET` and clears pending settings only after native
connection and successfully applied fresh configuration.

## Durable native identity store

A fresh OEM transaction requires an absent shared `certificates` volume. An
existing identity store is never cleared or mounted on the source as a key-cache
prerequisite. Before writing, inactive root plus reclaimed inactive overlay and
free capacity must cover 285 root LEBs, 67 overlay LEBs and 20 certificate LEBs.
After writing, actual remaining free capacity must still be at least 20 LEBs.

The existing incoming producer is
`feeds/tip/certificates/files/lib/preinit/75_certificates`, function
`generate_cambium_sage_certificate_volume`, registered through `preinit_main`.
It validates qualified Sage pair identity, MTD and LEB geometry, then allocates
an absent shared store with `ubimkvol -N certificates -S 20`. It never deletes,
shrinks or changes an existing store. The authenticated candidate's package
closure must include this producer and the native empty-store mount validator;
reserved space alone is not proof of that package closure. Key/CSR generation
and native EST remain incoming-only after networking and time are ready.

## Validation and remaining qualification

Actual boot callback tests cover both banks and E410/E410B commands, native guard
activation, metadata write/readback faults and final selector failure. Caller
fault tests cover authentication, admission, pending state, recovery, writer,
payload readback, mount, settings publication, sync and unmount; no earlier fault
reaches activation. Capacity shortage and existing-store cases reject before
backup or writing. Separate pair and settings tests exercise those actual
primitives. These are source tests, not physical power-loss or AP boot evidence.

Production remains disabled until the sealed authenticated runner supplies and
qualifies all callbacks on the actual outgoing OEM runtime, including complete
tool closure and environment geometry. Exact OEM recovery still requires the
bounded shared/NOR reset, reviewed defaults, fallback and recovery-access trial.
No source test grants permission to flash or reboot a device.

The shared settings library uses `ow_settings_metadata PATH`, returning numeric
`uid:mode:linkcount` from one successful `LC_ALL=C ls -ldn` output row. It accepts
only exact private regular-file 0600 or directory 0700 modes, numeric owner/group
and link counts, and absolute paths. Callers independently reject symlinks and
require ordinary single-link files. There is no stock `stat` dependency; wrong
modes, special mode bits, annotated/ambiguous output and multiple rows deny.

Post-write read-only source validation permits a 285-LEB root only for the
inactive candidate. The active OEM root still requires its reviewed 305/372-LEB
layout. A failed complete environment read always denies fresh installation;
missing per-key output never turns an ENV error into approval.
