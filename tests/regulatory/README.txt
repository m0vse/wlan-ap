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
