# DFS CAC-aware health checking

## Cause and scope

Relayed human runtime evidence from Jaguar XV2-2 (`30cbc75d92f3`) showed
600-second DFS CAC interrupted by the stock whole-network self-healer at
360 seconds (120-second health samples, greater-than-300-second restart gate).
The radio was correctly silent during CAC, but was classified as missing.

This change uses fresh, read-only hostapd global-control `STATUS`, matched to
current netifd interfaces, UCI AP sections, sysfs PHY and encoded SSID. It does
not infer CAC from a channel number or grant a cached grace period. Initial
CAC precedes BSS ubus registration, so a BSS-only ubus detector is insufficient.
The existing hostapd CLI supports `-p ... -i global raw IFNAME=... STATUS`;
it does not support the daemon's `-g` option.

Only failures positively attributable to an active CAC are suppressed. An
independent radio/SSID fault still allows the stock whole-network restart,
which may interrupt the other radio's CAC. RADIUS, DHCP, DNS and RRM policy
are unchanged. Unavailable, malformed, expired or aborted CAC evidence retains
ordinary fault detection/recovery. Automatic and manually selected DFS
channels use the same detector.

## Packaging

`ucentral-schema` release 14 installs `dfs_cac.uc` and depends on standard
`hostapd-utils` and `coreutils-timeout`. The helper uses the exact installed
`/usr/libexec/timeout-coreutils` binary with a two-second kill deadline, not
BusyBox or an alternatives-selected command. `ucentral-state` release 2
depends on the schema package. No kernel, bridge, VLAN or certificate changes.

## Offline verification

The checked-in receipts distinguish fixtures from runtime acceptance:

- 42 classifier/mapping/filter tests: long CAC, mixed radios, multiple SSIDs,
  encoded SSIDs, malformed/missing/expired/aborted status and exact matching.
- 5 subprocess tests: native GNU timeout, real child-process termination,
  failed/oversized output and unsafe interface-name refusal.
- 23 tests of the actual health and self-healing functions with filesystem,
  ubus, clock and process boundaries replaced by isolated fixtures.
- 2 archived target hostapd CLI tests each for Jaguar ARM64 and Sage ARM,
  through QEMU against private STATUS-only Unix sockets.
- Patch dry-run against the pinned prepared Jaguar schema source succeeds.

These are not physical AP acceptance. The positive `state=DFS`, PHY,
600-second duration and numeric remaining fields were separately observed
by the human on the Jaguar AP. New-image package/ELF/dependency closure and
physical post-upgrade behavior still require verification.

## Acceptance after an operator-authorized upgrade

Observe a real DFS CAC lasting longer than the healing threshold. Confirm
`dfs_cac` identifies only the relevant radio/SSID, that it remains silent
without missing-SSID healing/restart throughout CAC, and that AP-ENABLED and
normal health follow completion. Confirm failed/aborted CAC and independent
faults remain detectable. Do not call the issue fixed solely from unit tests.

## Running isolated tests on cnbeacon

Set `OW_TEST_UCODE` to the native built host ucode binary. Run
`test-dfs-cac.uc` with the directory's `source/system/dfs_cac.uc` argument.
For Python tests, set `OW_DFS_MODULE` (subprocess), `OW_DFS_SOURCE`
(health/healing), or `OW_DFS_TARGET_ROOT` and `OW_DFS_QEMU` (target CLI).
Fixtures are private temporary directories; no AP is accessed or changed.
