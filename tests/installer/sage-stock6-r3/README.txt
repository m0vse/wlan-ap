Sage stock E410/E410B migration, .6 / operator-stock-r3

Use only on the authenticated converted stock release 2026.09.29.0.
This is NOT the existing OpenWiFi .1 preserving-upgrade route.
The observed PHIL-LOFT unit is E410B; its first hardware trial is pending.

After verifying the downloaded archive SHA-256, unpack privately and run:
  sh sage-sysinstall.sh --check
Stop on any refusal; do not force or bypass a check.
After PASS, the human operator may explicitly run:
  sh sage-sysinstall.sh --install

Installation is a clean migration (-n): old configuration/identity/trust is
not imported. Unique OpenWiFi provisioning is still required afterwards.
It writes only the inactive A/B pair and arms one trial. The running pair
remains the rollback bank; no task has flashed or rebooted an AP.

Capacity correction: inactive rootfs 305 -> 285 LEBs frees 20 LEBs, leaving
21 free on the reported free1 layout for the existing preinit allocator to
create the shared 20-LEB certificate store. NVRAM187, running root/kernel,
board/ART data and 67-LEB overlay reservations are not resized. The inactive
root payload is cleared before shrinking, never a live UBIFS filesystem.
The normal clean-upgrade writer resets only the new bank's overlay as usual.
Wrong/same bank, root volume ID/type/geometry, mounted or block-held target,
insufficient space, image/FIT/source mismatches and failed writes refuse.
The new firmware retains the 285-LEB floor for later bank upgrades.

Incoming TIP-sage-2026.10.02.6-9fe7f73a; cambium-ab17; cloud_discovery6.
Image 13865290 bytes; SHA256:
c6c90c009824ef9cc97bf8b855854749455241ed06e5f019421afe61876bd616
Rootfs11110400 bytes fits36188160-byte reserved capacity.
Unchanged .5 kernel FIT and all129 drivers; DFS/model/discovery/certificate
and network fixes retained. Existing .5 releases remain immutable.

Fresh focused checks:12 capacity/write-sequence/refusal cases,20 actual
stock/installed validator cases including E410B,9 wrapper cases,4 retained
RAM/FIT controls each for E410/E410B,static RAM/ELF closure and target ash
syntax. UBI/mount/write boundaries are fixtures; hardware trial, physical
RAM pivot, power-loss and rollback are NOT claimed. Broad unrelated tests
were not rerun; previous evidence is labelled inherited-stock-r2.
