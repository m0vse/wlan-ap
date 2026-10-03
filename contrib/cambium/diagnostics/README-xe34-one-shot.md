# XE3-4 one-shot clean-boot diagnostic — reviewed 2026-10-04

This is an operator-approved diagnostic, not a production init script or
firmware patch. Nothing in this directory is installed by regular builds.
The candidate remains unqualified until runtime acceptance succeeds.

## Evidence motivating this test

The original driver recovered to 14 dBm after a power cycle under explicit
LPI/GB policy, then firmware pdev power returned to zero after configuration
and a 6 GHz scan. Causation is not established. Existing power-limit changes
13→14 dBm did not restore it; mac80211 tracked the request but firmware and
iw stayed at zero. These checks did not change saved configuration.

The first live-module trial was inconclusive. Its helper failed to wait for
asynchronous wireless shutdown, and treated hostapd ENABLED as ready while
iw reported no wlan2. This triggered restoration, during which SSH became
unreachable. Volatile kernel evidence was lost after the operator power
cycle, so neither a driver fault nor its absence can be established.
Do not repeat that live-unload sequence or mark the candidate accepted.

## Frozen helper and narrow verification

    xe34-ath11k-tpc-once.init
    SHA256 209297b30d8e546a0bfebac7de62c15031d0feecb977cdf0f031d904fc82ca97

    test-xe34-tpc-once.py
    SHA256 a8d5a56a4144583e9c9179862316b0c4e83fa75fedab149a98daaeacdc140f80

Five mocked control-flow checks pass: success, wrong board, dependency-time
autoload race, candidate load failure and invalid parameter. Every case
verifies consumed marker/link removal/sync before any loader and no loader
on a second boot. Hashes and loaders are mocks in these tests; they do not
prove hardware behaviour or replace the independent module ABI checks.
The shipped Jaguar BusyBox shell also passes the syntax check.

Run locally without any AP access:

    python3 test-xe34-tpc-once.py xe34-ath11k-tpc-once.init
    sh -n xe34-ath11k-tpc-once.init

## Exact shipped startup ordering

The selected Jaguar .2 root filesystem has:

    S09cambium-board-data    prepares the AP's own board data
    S09early_boot            restores certificate/config bootstrap if needed
    S09zz_ath11k_tpc_once    diagnostic, manually staged only after review
    S10boot                 /sbin/kmodloader, normal Wi-Fi wrapper loading

There are no ath11k modules in modules-boot.d. /sbin/modprobe is kmodloader.
The helper requests only mac80211 (normal cfg80211/compat dependencies)
and qmi_helpers, then loads the candidate core. It does not load bus wrappers:
the unchanged S10 loader does that normally. These statements require fresh
verification on the actual AP before staging; another image may differ.

The helper never edits Ethernet/network/wireless config, firmware environment,
installed modules, board data, country or power settings. It never unloads
drivers, reloads network or initiates a reboot. It requires the exact XE3-4
identity, kernel, installed module hashes, own API2 board-data hash and
explicit saved LPI0/GB/14 dBm configuration.

## Coordinator staging contract — not performed by this document

Require the operator's physical power-cycle recovery availability and reboot
approval. Check no existing files collide with the following exact paths.
Use root-only storage, preserve original network/wireless/module hashes and
capture this AP's current ath11k parameters, one key=value per line. Store
the parameters SHA256 separately. The helper validates and whitelists these
parameters without eval or sourcing; a null xv3_8_hw_mode is omitted.

Stage the verified candidate module:

    /root/xe34-ath11k-tpc-once/ath11k-ap-tpc.ko
    SHA256 4d706f5518ce5ffa960a50577ee9d0d4876ab39c131b6ca2d027aded1a782b45

Then stage the exact frozen helper as:

    /etc/init.d/zz_ath11k_tpc_once

Verify both copied hashes and syntax before creating the armed marker and
only this link:

    /etc/rc.d/S09zz_ath11k_tpc_once -> ../init.d/zz_ath11k_tpc_once

Do not call the helper's boot function manually. Do not replace or bind-mount
/lib/modules/6.12.85/ath11k.ko. The original installed core stays at:

    bc51dc38ba8bd5884bcc24cbf6f0a750d7be22d67b11dba33c1b0fe20410fa0e

## Disarm, loading and recovery

At boot, before any loader invocation, the helper renames armed to consumed,
removes only its own exact rc.d link and calls sync. If a guard fails, it
returns and leaves the normal loader in charge. It requires the core and
both bus modules absent before and after dependency loading. An autoload
race skips the candidate; there is no unloading or retry.

Module loads are synchronous: a timeout cannot cancel an uninterruptible
kernel initialization and could race S10. A hang therefore requires the
operator's physical power cycle, not a pretend userspace timeout recovery.

After successful durable disarm, a subsequent power cycle loads the unchanged
original module. This is a recovery design, not a hardware/storage guarantee.
Loss of power before disarm reaches storage, unrelated boot faults or failing
hardware can still prevent recovery. If the AP is reachable, cancelling an
armed test means renaming only its armed marker to cancelled, removing only
its own rc.d symlink and syncing; no broad deletion or configuration restore.

Once the candidate is loaded, disarming does not replace the running module.
Returning to the original requires a separately approved reboot/power cycle.
Do not attempt another live unload to restore it.

## Required runtime acceptance — pending

The stages.log must identify the current kernel boot_id, consumed marker,
absent rc.d link, prior core-absence guards and successful candidate insmod.
This provides load provenance; the installed module hash alone cannot identify
the running diagnostic module, whose vermagic/exports match the original.
The core-loaded marker explicitly says it is not hardware acceptance.

Root must obtain fresh evidence: actual wlan2 exists and maps to the PCI radio,
matching BSSID/SSID, fresh hostapd ENABLED, LPI0/GB/14 policy, mac80211 request,
iw power and firmware pdev power (half-dBm units). Verify Ethernet and other
radios/settings unchanged and collect kernel evidence remotely, not only in
volatile /tmp. Existing 5 GHz DFS wait is separate from 6 GHz firmware power.

Observe the existing scan/reconfiguration behaviour before calling the issue
fixed. Do not initiate scans, further policy changes, builds or driver tests
without coordinator release. A positive readback is not a calibrated RF
measurement, and a clean boot alone is not evidence of lasting recovery.
