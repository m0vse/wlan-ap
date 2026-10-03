Live regulatory eligibility candidate (source-only; no AP or build changes)

Contract: state.radios[].regulatory = {country, timestamp, channels, dfs_channels}.
Use the existing radio.phy path, not array position or band-only lookup. Country
is read with per-wiphy NL80211 GET_REG and must equal active configured country.
Country reads bracket a fresh per-PHY GET_WIPHY frequency query; mismatched
before/after countries or an incorrect PHY reply invalidate the snapshot.
Missing data, failed reads, ambiguous mapping or mismatch means unavailable.
Controller consumers must require recent telemetry and never fall back to static
capability channels. channels denotes primary-channel eligibility only, not
permission to operate at a particular width. DFS candidates still need CAC and
the consumer's allow-DFS policy. Missing DFS state and DFS_UNAVAILABLE are refused.

The renderer separately intersects enumerated board/current capabilities with
fresh non-disabled NL80211 frequencies once the requested country matches the
live PHY country. Static capabilities are not rewritten. NO_IR-only frequencies
remain available for station rendering, but are excluded from AP telemetry.
The normal stock country-change path is retained while the country has not
settled; regulatory telemetry is absent then, so RRM must hold. This is not a
claim that a first render under an old country proves the next country's channel
legality or that regulatory transitions are instantaneous.

Run tests/regulatory/tests.uc with target ucode (QEMU ARM/AArch64 and the matching
root library path). All readers in the test are synthetic and source-only.
Replay all schema patches with tests/boot-reporting/test-schema-series.sh using
the pinned d1e90a04 source archive; the replay must pass with zero fuzz.

2026-10-03 validation: 23 focused source controls PASS under both actual Sage
ARM and Jaguar AArch64 image runtimes; patched installed-layout renderer and
state/wifi compile-only imports PASS under both; the complete pinned schema
patch series replays with -F0. Pinned ucode 85922056 binding source confirms
GET_REG reg_alpha2/wiphy, NO_IR, DFS_STATE and merged single-PHY GET_WIPHY.
No firmware build, AP configuration, regulatory mutation or reboot was performed.

Hardware acceptance remains: after country GB settles, the corresponding PHY's
state regulatory channels must match live allowed frequencies, exclude the
observed disabled149/157 and carry country GB and a fresh timestamp. Verify a
failed/transitioning snapshot causes RRM to hold, and verify dual-5GHz topology
does not mix PHYs. No hardware acceptance is claimed by source fixture tests.

Operating-band follow-up (patch 093, schema release 21)

The physical capability list is not an operating-band list. The renderer now
builds pure paired-frequency band views, deduplicates channels, and uses 6GHz
bonded-primary geometry independently of the existing 5GHz tables. Enabled6G
reserves a switchable5/6PHY; dedicated5G continues operating. Disabled6G does
not reserve it. SSID lookup uses this render's selected band/disabled state,
not old UCI state, so a first5-to6transition is mapped correctly. HaLow and
60GHz retain their prior lookup behavior. Regulatory filtering returns a new
per-render view and never shrinks cached hardware capabilities permanently.
Each generated channel list is deleted before add_list, avoiding accumulation.

These checks are not width authorization: primary/bonded geometry is necessary
but hostapd/kernel still enforce live regulatory and hardware width limits.
320MHz geometry tests do not claim XE3-4 hardware support; the actual radio
template test verifies its existing EHT320-to-HE160 fallback instead.

Replay the complete series with test-schema-series.sh, then copy both helper
files into FIXTURE/renderer/wifi/. Supply that renderer directory with -L:

qemu-aarch64 -L TARGET_ROOT TARGET_ROOT/usr/bin/ucode \
  -L TARGET_ROOT/usr/lib/ucode -L FIXTURE/renderer tests/regulatory/band-tests.uc
BAND_TEMPLATE=FIXTURE/renderer/templates/radio.uc \
  qemu-aarch64 -L TARGET_ROOT TARGET_ROOT/usr/bin/ucode \
  -L TARGET_ROOT/usr/lib/ucode -L FIXTURE/renderer tests/regulatory/render-band-tests.uc

Repeat with qemu-arm and the Sage target root. tests.uc retains its23 controls;
band-tests.uc executes43 controls including the real patched wiphy module;
render-band-tests.uc executes18 controls against the real patched radio
template with mocked configuration, PHY and filesystem data. No AP access,
daemon startup, UCI changes or filesystem writes occur in those tests.

Live XE3-4 notes: the regular-hostapd key fix was accepted, but ACS caused
ath11k scan/WMI timeouts and CE descriptor exhaustion on a clean reboot. The
single fixed-channel attempt through UCI was overwritten to ACS by early
cached-config rendering, so it did not test fixed-channel operation. No6GHz
beacon/client or regulatory hardware acceptance is claimed by this candidate.
