# Thor incremental boot fix on current main

Based on OpenWiFi main `3f2a130e5804a1ea6f904363ba871dce72b393d7`, including common prior-only trial patch 0179
and Jaguar patch 0180. This candidate reserves 0183; the unified owner's 0182
readiness patch is separate. Main owns final patch numbering/integration.

The obsolete Thor-specific 0179 override is excluded. There is no change to
the common `ab_trial_command`: its durable reset default remains exclusively
`run thor_bootPRIOR`, never a stable command that can retry the failed candidate.

The Thor module gates OEM candidate loading on successful fallback setenv and
saveenv, requires successful Aquantia loading, and refuses to use the OEM hook
when the actual predecessor is an already-converted OpenWiFi bank. Upgrade
preflight accepts both `run thor_stablePRIOR` and the legitimate source-only
rollback default `run thor_bootPRIOR`. Both bank boot/stable variable expansions
must match the supported routing, confirmed slot and saved marker; only the
exact old/current PHY prefix difference is admitted. No first-OEM conversion
bypass or firmware/persistence contract change is introduced.

Actual prepared package releases are `cambium-ab` 18 → 19 and
`cambium-thor-support` 12 → 13. Both packages are bumped because both installed
source files change. This is not a firmware build or release.

## Validation

Run the Thor fixture against a prepared current OpenWrt source tree containing
the actual `package/cambium` sources and common 0179:

```sh
python3 tools/oem-migration/unified/tests/family-thor-boot.py PREPARED_OPENWRT_ROOT
python3 tests/ab-one-shot/test-trial.py --core PREPARED_OPENWRT_ROOT/package/cambium/cambium-ab/files/cambium-ab.sh
```

On 9 October 2026, 56 Thor cases passed: patch application without fuzz,
unchanged current common core, both slot directions, stable and prior-only
defaults, failed fields/save/load, PHY failure, exact routing refusals and no
OEM fallback for an OpenWiFi predecessor. Two negative controls reproduce the
old Thor OEM failed-save defect. The common test passed 180 rendered-script
cases, including next-reset execution selecting only the prior slot.
Synthetic prior-bank/ART/MFG/PHY/BOOTCONFIG/cert/vault byte sentinels remained
unchanged. The fixture uses real source functions with modeled bootloader I/O;
it is not physical ENV durability, kernel power-loss or watchdog proof.

No new watchdog/hardware admission gate is added. The agreed manual reset or
power-cycle one-shot contract remains; automatic hang recovery must not be
claimed without existing watchdog evidence. No AP, network, firmware-build,
trust or credential actions were performed. Generated receipts remain outside
Git.

## Unified installer handoff

Normal converted Thor sysupgrade retains the existing platform pre-RAM private
certificate export (0163), vault/certificate restore, exact inactive-bank image
validation and native healthy-commit guard. This change does not qualify a new
OEM forward/restore adapter or bypass the existing refusal of first-OEM
conversion through normal sysupgrade.

Concrete remaining Thor inputs are the actual release's exact OEM source
version mapping, complete physical profile/manufacturing location, authenticated
locally staged OpenWiFi/OEM payload and reusable radio-asset mapping, and the
shared owner's target-write/FORMAT2/readback/boot-arm integration. Stock
`thor-sysinstall` requires converted sources; stock `cmd_stock` explicitly
refuses two OpenWiFi banks. They cannot be relabeled as OEM writers. No new
manufacturing registry, issuer, signing service, CLI tree or approval service
is needed. The unified owner retains launcher, common network/protection/CLI
and backup ownership; this commit changes only existing Thor boot behavior,
its generic preflight call and focused fixtures.
