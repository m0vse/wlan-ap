# One Cambium OEM migration interface

These sources belong to OpenWiFi. **Use a release only when its exact model,
OEM version and adapter are supported.** Source simulations are not hardware
qualification. There is no force or trial bypass.

## Quick start: OEM to OpenWiFi

Obtain the reviewed installer release from your deployment operator and verify
its published launcher hash. The release already contains the correct image
mapping and operator controller/download/critical-backup URLs. Public source
contains no site defaults or enrollment key.

A metadata-first release contains the authenticated common launcher, helpers
and exact-model data map. The same command detects the model and stages only
its selected operation's pinned objects before key input or backup. You do not
choose a family bundle or copy every family's firmware onto the AP. Verified
local objects are rechecked before writes; a self-contained offline release
continues to work without the data map.

From an OEM root console, inside that verified release directory:

```sh
./cambium-oem-install check
./cambium-oem-install
```

The second command detects the model, verifies its OEM version and storage,
checks the image and protected write boundaries, and displays the retained OEM
and target slots. Enter the approved onboarding key at the **hidden prompt**;
it does not belong in a command, environment variable or log. Type `INSTALL`
only after reviewing the summary. The installer verifies critical backup
uploads before changing firmware, stages the image and protected enrollment
settings, reads them back and arms one candidate attempt. It then asks whether
you want to reboot. A refusal or failed check never requests automatic reboot.

OpenWiFi performs its own key/CSR creation and native EST enrollment after
networking and time are ready. A configured controller is a default; normal
DHCP224 discovery retains priority. Enrollment and a freshly applied controller
configuration are required before healthy boot confirmation. There is no
source-side certificate request, imported AP key or new issuer workflow.

After onboarding, use the installed read-only command:

```sh
cambium-ab-status
cambium-ab-ready
```

`onboarded` is not `ready`. `cambium-ab-ready` returns success only when the
installed model's normal A/B backend proves its upgrade prerequisites. A
missing hook, unsupported version or unconverted layout returns nonzero. Only
then may an operator choose a normal OpenWiFi `sysupgrade` using the reviewed
image. The installer **never automatically overwrites the retained OEM slot**.
New readiness/backend hooks require installation through a reviewed firmware
release; this source change does not install them on existing APs.

## Quick start: restore OEM for a clean test

This is a separate operation for APs already running OpenWiFi on both slots.
`cambium-return-oem` checks a retained OEM bank. Arming requires a reviewed
one-shot return handler; releases with unsafe permanent-switch semantics must
refuse before changing the device. It is not a full restoration alias.

Inside an independently verified restoration release:

```sh
./cambium-oem-restore-test --check
./cambium-oem-restore-test --restore
```

The dry run must identify the current OpenWiFi slot, inactive target, verified
OEM assets and model-specific nonunique factory-reset plan. The restore command
requires the separate `RESTORE OEM` confirmation. It preserves the working
OpenWiFi slot and critical identity, reads back the inactive OEM image and arms
one attempt, then offers an explicit reboot choice. It does not reset server
inventory, revoke certificates or wipe the source identity store implicitly.
An unsupported converted layout refuses; do not delete A/B flags manually.
After booting OEM, verify management access and the model's reported kernel,
root and protected-data checks. Where that release provides a reviewed
confirmation handler, use:

```sh
./cambium-oem-restore-test --confirm
```

This requires `CONFIRM OEM` and refuses on OpenWiFi or without that exact-model
handler. It does not infer success merely because the kernel started. Only
then follow the model's reviewed OEM-side factory-reset procedure. Shared
configuration or identity needed by the previous OpenWiFi slot must not be
cleared while the OEM attempt is still unconfirmed. A one-shot OEM boot whose
saved selector still names the prior OpenWiFi slot is not a normal OEM source
for the forward installer; do not change that selector manually.

The E410 pilot's nonempty NOR factory-config partition is read-only from
OpenWiFi. Complete reset therefore needs a reviewed OEM-side procedure after
healthy OEM confirmation, including refreshing the NOR config backup so stale
settings cannot return. The existing OEM reset script alone does not prove
that backup was refreshed. Until the exact-model handler and procedure are
available, the clean-test reset remains unsupported.

## Backups and shared radio data

Routine per-AP backups contain only own ART/calibration, manufacturing identity,
boot environment and indispensable boot-selection records such as Thor's
BOOTCONFIG. A bounded, documented unique-data exception is explicit in the
model plan. No kernel, rootfs, full bank/NAND, firmware dump, customer settings,
logs, enrollment seed or certificate store is exported by this backup helper.

Capture files and checksum receipts are root-private. The existing upload
relay must confirm each chunk and complete file hash; missing confirmation
stops before firmware writes. Files use a per-run identifier to avoid replacing
an older device backup. The local receipt directory is retained on failure.
Backups never authorize overwriting ART, manufacturing data or boot code.

Existing exact-model/release BDF, firmware and regdb assets come from the
reviewed image/provider. Shared assets are reusable per model/release; do not
capture an OEM filesystem for every AP. An otherwise missing required unique
calibration asset is treated separately, never replaced by another AP's data.

## Failure and fallback

All required network objects are authenticated in private local staging before
any target write. Transfers have bounded attempts, budgets and maximum sizes.
A missing or interrupted download/backup upload stops with the previous slot
untouched. After staging, flash operations use local objects; losing the HTTP
provider must not introduce a new post-erase fetch.

The bootloader restores and saves the exact previous working slot **before**
loading the candidate. Save failure cannot authorize candidate loading. On a
reset or powercycle an unconfirmed candidate returns to that previous slot.
Where no automatic early-hang watchdog has been proven, an early hang requires
an operator powercycle; the script does not claim automatic hang recovery.
Power loss or faulty flash can defeat hardware persistence and is not simulated
hardware proof.

After a destructive-phase failure, keep the journal and source slot. Do not
clear pending flags, repeat a clean install, transplant calibration or reboot
because an old command suggested it. Inspect the reported phase and use the
reviewed recovery procedure. Wrong model/version, ambiguous aliases, overlapping
protected ranges, busy targets, low space, corrupt volumes, failed checksums,
unsafe seed modes and failed environment readbacks all refuse.

## Commands and exit status

| Operation | Common command | Existing compatibility |
|---|---|---|
| OEM migration inspection/install | `cambium-oem-install check` / `cambium-oem-install` | `installer.sh` in generated releases |
| Full OEM restoration test | `cambium-oem-restore-test --check` / `--restore` | `oem-restore-test.sh` |
| Normal A/B state | `cambium-ab-status`; new releases also accept `--format tsv` | Legacy no-argument output unchanged |
| Normal-upgrade readiness | `cambium-ab-ready` | Release `check-sysupgrade-ready.sh`; installed backend hook required |
| Retained OEM boot only | `cambium-return-oem --check` / `--arm` | Arming requires safe one-shot support; otherwise refuses |
| Normal firmware upgrade | `sysupgrade` | Existing family platform backend; never implicit |

The new commands use exit 0 for successful checks/actions and exit 1 for refusal/failure,
with exit 2 for invalid usage. Legacy no-argument `cambium-ab-status` keeps its existing `mode=none`, exit-0 query behavior; the new versioned TSV form reports unsupported with exit 1. A preflight pass is not a completed installation or
hardware upgrade acceptance. The new scripts do not rename existing boot
markers, certificate paths or image formats.

## Models, releases and tests

[models.tsv](models.tsv) lists all recognized exact SKUs. A generated release's
`models.tsv`, `restore-models.tsv` and `upgrade-models.tsv` separately bind exact
model, adapter and supported source version. Models absent from the relevant
release, or explicitly disabled, refuse before key input and device backup.
Gambit and unknown sibling models remain recognized but unsupported until an
actual safe adapter exists. Do not infer a family's support from one sibling.

Sage E410/E410B has existing bounded writer/boot/reset source; Jaguar, Cheetah
and Thor adapters reuse their exact model profiles. Miami X7-35X reuses its
reviewed generated storage/FORMAT2 backend. Release readiness additionally
requires the actual model/source profile, payload pins and safe one-shot
contract; these are not fabricated by `prepare-release.py`. Current adapters
and limitations are recorded in [the test coverage guide](tests/COVERAGE.md).
The [release assembly guide](RELEASE-ASSEMBLY.md) records exact-model gaps and
how to package existing assets without a firmware build.

Run the source harness with:

```sh
python3 tools/oem-migration/unified/tests/run.py
```

The harness uses temporary regular files and explicit fake devices, synthetic
credentials and isolated service/network boundaries. Exact-model recognition
coverage is checked against the registry. Actual existing family writer and
one-shot regressions are included where implemented. Linux-only private
OverlayFS/UID81 tests are reported separately when unavailable; no hardware
power-loss, first upgrade or actual radio/controller acceptance is inferred.
