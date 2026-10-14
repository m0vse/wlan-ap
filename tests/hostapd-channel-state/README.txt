Shared and QSDK channel/width/power verification

No AP is used or modified. Run with the actual prepared hostapd source and
the same SDK hostpkg ucode runtime. Example from the wlan-ap repository:

  python3 tests/hostapd-channel-state/test-start.py --source PREPARED_HOSTAPD --ucode-prefix openwrt/staging_dir/hostpkg
  python3 tests/hostapd-channel-state/test-start.py --source PREPARED_REGULAR_HOSTAPD --ucode-prefix openwrt/staging_dir/hostpkg --without-eht
  python3 tests/hostapd-channel-state/test-event.py --source PREPARED_HOSTAPD/src/ap/drv_callbacks.c
  python3 tests/hostapd-channel-state/test-caller.py --source feeds/qca-wifi-7/hostapd/files/hostapd.uc --ucode openwrt/staging_dir/hostpkg/bin/ucode

test-start compiles the actual prepared startup function and scalar rollback
helper, using real libucode value conversion and the actual hostapd frequency
conversion function. Driver, interface lifecycle and beacon calls are mocked;
the harness structure layout is synthetic. Full package compilation separately
checks the real headers and target layout. Its 20 cases include stale 36/5955,
missing/invalid tuples, unchanged state, same channel number on another band,
width/center/operating-class/puncture-only changes, first/second driver failure,
beacon failure, failed enable, zero-valued legacy enum and null-info initialization.
The regular variant also runs19 controls with EHT disabled and the puncturing
member absent from the structure. Full target builds must retain that layout;
an always-EHT synthetic structure is not evidence for older AP compatibility.

test-event executes the exact production frequency validation/commit fragment
with a mocked channel lookup, plus hardware-mode failure rollback. test-caller executes the real iface-add caller
using native ucode, checking true, false and null results. Each script supports
--negative-control against the original unpatched source.

These tests do not prove over-the-air MLO association, driver readback or a
specific origin of the live stale channel. Preserve the NAND soak: do not
install the package, reload Wi-Fi, change channels or reboot during it.
Hardware acceptance must follow the soak with operator authorization.

Power setter regression (local shell, no AP):

  python3 tests/hostapd-channel-state/test-txpower.py --source feeds/qca-wifi-7/wifi-scripts/files/lib/netifd/wireless/mac80211.sh
  python3 tests/hostapd-channel-state/test-acs-power.py --source PREPARED_REGULAR_MAC80211_SH

The regular ACS lifecycle regression runs the actual startup tail and setter
with three/four BSS, delayed secondary creation, automatic/fixed channel and
CAC lifecycle actors. The pre-correction source must fail its negative control.
Equivalent secondary AP power inherits a successful PHY request in mac80211;
the primary setter, failed PHY request and differing per-BSS override remain
strict. A differing override before its BSS exists is still rejected, not
reported applied. This does not add deferred override support or demonstrate
physical radio acceptance. QSDK/MLO per-link semantics are not exempted.

Its 22 QSDK controls (6 regular controls) cover legacy and per-link MLO, fixed and automatic power,
successful setting, rejection and invalid argument. A successful offload call
must not hide a failed power request; the device-level setup reports failure.
This verifies error propagation, NOT hardware acceptance. Additional tests run
actual ath11k/ath12k getters with mocked firmware boundaries, including failures,
CAC, cache expiry, missing pdev and link identity. Negative controls demonstrate
the old configured-power fallback. The complete target driver must also compile.

Readback and actual generated configuration (use the SDK's native UCODE):

  python3 tests/hostapd-channel-state/test-driver-power.py --kind ath12k --source PREPARED_BACKPORTS/drivers/net/wireless/ath/ath12k/mac.c
  python3 tests/hostapd-channel-state/test-driver-power.py --kind ath11k --source PREPARED_REGULAR_BACKPORTS/drivers/net/wireless/ath/ath11k/mac.c
  python3 tests/hostapd-channel-state/test-driver-power.py --kind qca-ath11k --source PREPARED_QSDK_BACKPORTS/drivers/net/wireless/ath/ath11k/mac.c
  python3 tests/hostapd-channel-state/test-rrm-power.py --repo REPO --ucode UCODE
  UCODE -L 'REPLAY/system/*.uc' tests/hostapd-channel-state/test-operating.uc
  python3 tests/hostapd-channel-state/test-health-operating.py --health REPLAY/system/health.uc --modules REPLAY/system --ucode UCODE
  BAND_TEMPLATE=REPLAY/renderer/templates/radio.uc UCODE -L 'REPLAY/renderer/*.uc' -L 'REPLAY/system/*.uc' tests/hostapd-channel-state/test-rendered-operating.uc

Replay all pinned schema patches with-F0. Copy package-owned wifi/*.uc helpers
into REPLAY/renderer/wifi and radio_operating.uc into REPLAY/system, matching
installation. Existing tests/mlo-health and tests/mlo-telemetry runners require
a baseline stopping BEFORE104. Capability fixtures are not model hardware proof.
The retained qualified MLO105/106 telemetry/RSSI patches remain in the series;
patch095's malformed hunk counts are repaired without changing authorization.

Health data.radio_operating[wireless-section] carries channel, width and power
with status confirmed/unconfirmed/pending/failed. Channel/width include actual
and requested_match; power includes requested_dbm, reported_dbm and source.
One shared GET_INTERFACE snapshot avoids duplicate firmware power requests.
Exact PHY/BSS/link identity is required; no inferred/default MLO link fallback.
Current mismatches are critical faults, clear with coherent evidence, and do
not replace pre-existing NAND faults. Missing readback is null/unconfirmed,
never synthetic0dBm; actual0dBm is preserved. Lower effective power is reported
as limited without inventing a regulatory/thermal/hardware cause. Requested
channel/width differences remain visible even in legitimate DFS/coexistence
transitions. Unsupported legacy-band readback stays unconfirmed, not a new fault.

ath11k/ath12k expose a read-only strict-readback capability marker. Without it,
schema-only installation cannot claim firmware confirmation on an old kernel.
ath12k retains its five-second firmware throttle, invalidating the bounded
cache on power/TPE changes. Firmware channel power is not per-frame RF power.
Sage/older drivers without a firmware getter report an unconfirmed driver limit;
do not pretend that an unavailable hardware measurement has been implemented.

Preserve each qualified family parent in qualified-family-bases.json. Merge
shared fixes into retained trees, never reset a family to generic main. Keep
private package counters/SDK fixes, unrelated settings and old immutable images.
Commit reviewed source/tests before final package verification as Phil Taylor
<phil@m0vse.uk>; exclude artifacts, credentials, calibration and device data.
All builds use effective nproc CPUs, with only one family compiler at a time.

Before each family build, run the read-only preservation check in its retained
tree (replace FAMILY with sage, jaguar, cheetah, thor or miami):

  python3 tests/hostapd-channel-state/test-source-preservation.py --family FAMILY

It requires the qualified family parent and exact reviewed critical source
blobs, including NAND, MLO, channel/power and Miami's supplementary A/B ABI.
It checks working files too, so an uncommitted replacement cannot hide behind
Git ancestry. No reset, fetch, AP operation or bypass is provided. Intentional
changes require source review and a ledger update. Passing is not hardware
acceptance and does not replace target compilation or the runtime regressions.
Miami must still use its qualified retained tree, not generic main: its private
source history and build inputs are not published by this check. Never replace
those inputs just to satisfy a generic shared build. Private settings, device
data and credentials are excluded from the public ledger.
