# Source coverage and honest gaps

The common harness is not an AP flashing tool. `models.json` contains an
explicit fixture for every recognized SKU; a registry addition without a
fixture fails the coverage check. Model, source version, bank size and layout
remain distinct. All records are **synthetic source fixtures**, not production
admission records.

## Coverage layers

| Layer | What is exercised | What it does not establish |
|---|---|---|
| Common forward/reverse harness | Every recognized model's unsupported refusal before prompt/write; positive synthetic adapter contexts; pinned helper refusal; exact source-version rejection; critical/protected data preservation; failure journal and private terminal key input | A production adapter or real flash behavior |
| Protection/backup helpers | Root/kernel/bank/config backup exclusion, bounded critical plans, physical chip/range/alias/parent checks, shared-Sage active-child refusal, unrelated ENV preservation | Missing model geometry is never inferred |
| Existing Sage writer/reset tests | Actual shell writer/readback/stager/boot adapters against disposable MTD/UBI/env backends | Real NAND power loss or OEM management access |
| One-shot tests | Actual rendered commands across six family prefixes, both slots and setenv/save/load/reset checkpoints, with the original unsafe command as a negative control | Actual U-Boot parser, flash atomicity or watchdog behavior |
| Shared settings tests | Actual FORMAT2 validation/staging, file modes, job/image bindings and interruptions | Native production EST issuance |
| Linux private OverlayFS test | Public root traversal/exec with UID81 and no capabilities; private seed denial; 0755 positive and 0700 negative control | A real AP boot |
| Family-specific fixtures | Exact supported/unsupported models and their genuine adapter gaps | Sibling admission or arbitrary OEM releases |

The common phase fault model covers inspection, release/version/protection,
boot contract, recovery, writing, readback, staging, sync, unmount and arming.
Protected ART/MFG/bootcode/ENV/retained bank/vault sentinels must remain unchanged
for every failure. Later failures retain the writing journal and never report
an armed candidate. This models persisted state versus temporary state; it is
not a physical power-cut guarantee.

The rendered-command regression distinguishes native OpenWiFi fallback from
the reviewed OEM counter safeguard. Native trial failures fall back directly
to the previous OpenWiFi slot. OEM entry/return counter or default-save failures
must hold at the boot prompt, without loading either bank or resetting through
an unsafe OEM selector. After a successful save, both paths persist the previous
slot before attempting the candidate. Tests inject the actual named state key
(not its former positional index), bootcount where present, each selector and
save failure. An ungated-save mutation demonstrates the unsafe candidate load.
The single runner also executes the retained Jaguar, Cheetah and Thor counter
regressions; their standalone tests must not be omitted from migration checks.

Network cases must cover failed resolution/connection/header/body, truncated
or wrong data, stalls and reset; valid cached objects are accepted without
contacting a vanished provider. No real external network is used by the
fixtures. The real staging helper requires Linux process identity for its
bounded child cleanup; platform-only checks are identified rather than silently
claimed on macOS.

Unsupported exact models, unavailable source/payload profiles, reverse factory
reset blockers and missing upgrade hooks are **expected refusals**, not positive
migration tests. Gambit currently has no safe hardware-backed migration or
converted restoration adapter. E430 variants do not inherit E410 geometry.

## Running

```sh
python3 tools/oem-migration/unified/tests/run.py
```

The runner prints individual layers and exits nonzero on a failure. Default
source-only runs explicitly report the four Thor actual-data transaction tests
as NOT RUN unless `--thor-inputs /private/path/inputs.json` is supplied. Their
private manifest must contain `runtime_root` and `provider` directories plus
the reviewed `image`, `bdf`, `settings`, `kernel` and `rootfs` files. Relative
paths resolve against the manifest directory. These inputs must describe the
same retained provider/release; do not invent image or calibration bytes to make
the tests pass. A source-only result does not qualify those missing layers or
enable any unsupported model. Keep private manifests and assets out of Git.

Linux OverlayFS requires an isolated mount namespace and suitable privileges; an
unavailable platform is reported explicitly. Sandbox restrictions on terminal
ioctls can prevent the real hidden-prompt test: run that isolated source test
with the host permission needed for a test PTY, never by changing AP settings.

Inspect the actual generated release independently too: all scripts, model
mapping, source version, payload/descriptor pins and helper closure must match
its release receipt. A private generated firmware artifact must not be committed
as a source fixture, and source-test counts never replace operator hardware
onboarding/second-boot/normal-upgrade acceptance.
