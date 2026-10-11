# QCN9074 6 GHz LPI AP TPC diagnostic history

Production integration (2026-10-05): patch `0162` now installs this same
driver change as regular ath11k patch `960`, with mac80211 release 3.
Jaguar `.8` image and normal-boot hardware acceptance are pending. `.7`
retained the original driver and therefore did not retain the successful
temporary diagnostic's power behavior. Do not call this fixed in a released
image until its actual packaged module and runtime checks are verified.

This directory records the original diagnostic adaptation of Sebastian Gottschall's
unmerged May 2026 v3 proposal, with the July review's alignment and bss_conf
changes. These diagnostic assets remain outside patches-25.12; patch `0162`
is the separately enabled production integration. The driver proposal uses
LPI for AP TPC, not VLP/SP support.
Do not use it to silently replace an operator's VLP/SP policy.

UK VLP legality and support in this particular driver are different questions.
The selected ath11k AP regulatory path uses indoor/LPI rules. This test is
explicitly operator-approved LPI, country GB, original regulatory limits.

## Offline verification (2026-10-03)

- Zero-fuzz application to selected backports 6.18.7 and stock prepared 7.2.
- Actual predicate executed against 192 combinations of firmware service,
  device mode/subtype, channel presence and band; STA path preserved, no
  extension to 2/5 GHz, unsupported services or subtypes.
- Actual canonical Jaguar gcc/ld commands replayed for mac.o, ath11k.o and
  ath11k.ko only. Compiler uses kernel -nostdinc and unchanged toolchain/config.
- All canonical source/object files restored and original hashes verified.
- Diagnostic .modinfo, dependencies, parameters, undefined symbols and export
  names match the AP module. Kernel CONFIG_MODVERSIONS is disabled.
- Canonical baseline and live AP have identical .text/.rodata/.data/.modinfo
  and export-name bytes. Whole-file hashes differ due to ELF symbol/packaging
  details, so compare load-relevant content rather than assuming a new driver.
- No radio/module activation, firmware build, reboot or power change performed
  by the builder. Compilation and predicate checks are not hardware acceptance.

Final diagnostic on cnbeacon:

    /home/phil/task-artifacts/sage-jaguar-2026-10-06/driver-evidence/ath11k-ap-tpc.ko
    SHA256 4d706f5518ce5ffa960a50577ee9d0d4876ab39c131b6ca2d027aded1a782b45
    vermagic 6.12.85 SMP mod_unload aarch64
    depends mac80211,cfg80211,qmi_helpers

The diagnostic and compact original/patched-source evidence moved to this
Root-only persistent audit location on 2026-10-06 after verified copies and
dependency clearance. The old `/tmp/xe34-ap-tpc-diagnostic.6bpBXv` path and
redundant intermediate objects were removed; no driver/AP/build changes.

Live AP module baseline (XE3-4, serial b4a25c05c018):

    SHA256 bc51dc38ba8bd5884bcc24cbf6f0a750d7be22d67b11dba33c1b0fe20410fa0e

The initial candidate 077ffc22... used debug-only stripping. Use only the
final hash above, processed by the regular OpenWrt strip-kmod.sh.

## Building again (offline only)

The instructions below describe the original unpatched baseline. Once
production patch `960` is applied, do not run the diagnostic builder against
that already-patched source. Use the normal package build instead.

On cnbeacon, with no concurrent Jaguar compiler:

    bash build-ath11k-ap6-tpc.sh /absolute/path/ath11k-ap6-lpi-tpc.patch
    python3 test-ath11k-ap6-tpc.py /diagnostic/output/mac.patched.c

The builder temporarily patches the canonical selected source, saves only
four original files, and restores them on exit; it does not clone the build.
Generated module metadata is retained because no exports/imports or ABI change.
This is a diagnostic module, not a production package/provenance receipt.

## Live acceptance and recovery plan — requires coordinator release

Core ath11k.ko is shared by PCI 6 GHz and AHB 5 GHz. Replacing it requires
both Wi-Fi paths stopped and dependent bus modules unloaded before the core,
or a reboot. PCI-only unbind does not replace the shared loaded core.

Do not reboot or unload drivers without an approved recovery path. A userspace
watchdog cannot recover a kernel panic. Prefer a transient /tmp candidate
without replacing the boot-time module: an independently available physical
power cycle then boots the original driver if a live reload hangs. Confirm
that physical recovery is actually available before attempting it.

Coordinator should guard exact serial/board/kernel and module hashes, save
module parameters, original wrapper/core binaries and relevant config, and
verify wired management/default route immediately before testing.

First ensure BOTH configured power-mode keys and generated hostapd state
indicate explicit LPI (0), country GB, requested 17 dBm. Do not simply edit
UCI and assume netifd cached configuration changed. Avoid global network
reload/early uCentral rerender unless separately authorised and guarded.

Capture before/after: generated hostapd policy, ENABLED/channel/width, iw
power, mac80211 user_power and netdev txpower, firmware pdev Channel TX power,
regulatory domain and limits, kernel errors and client association/traffic.
Firmware pdev power is in half-dBm units. A desired17 readback alone is not
a calibrated RF measurement.

Only after baseline success run a bounded operator-approved scan on the
6 GHz PHY and recheck power, policy and errors. Do not use scans on the
5 GHz DFS PHY or bypass regulatory checks. Power must remain bounded by
the operator request and applicable regulatory/calibration limits.

Restore original loaded modules/parameters/config on failure, verify wired
reachability and both radios. Do not mark the radio fault fixed until these
runtime checks pass; do not merge this into production merely on compile.
