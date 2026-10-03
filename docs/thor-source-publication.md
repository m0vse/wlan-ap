# Thor source publication

The reviewed profile and hardware integration preserve the deployed XV3-8 `.10` feature set: Aquantia Clause45 identification, bank-specific persistent/recovery/installer trees, protected storage, pre-module dual4x4/single8x8 selection and scanner exclusion from serving radio capabilities. Dedicated controller-scan routing and crash reporting remain separate unfinished features.

Original deployed revision: TIP-thor-2026.10.02.10-62111889; original source:621118890178b7bb09c7ccda90b85fd791f3e891. Firmware SHA256:957ea3fd638dc1842a9c4581012018e1991b2f47f7a3445fc0eb17d16a4ccaa7. This corrected-lineage source publication does not recreate or relabel that binary.

Apply the normal wlan-ap patch series in lexical order. Shared A/B certificate and management guards are already provided by main patches0126–0130; Thor is0141 to avoid other-family numbering. Keep current shared discovery and certificate implementations. The profile selects persistent, installer and recovery targets, with per-device root filesystems. Build through the repository standard workflow in an authorised build checkout, not through the historical deployed tree. Before publishing a new image, allocate a new release version, run full image/DT/storage/network/radio/installer checks and regenerate authenticated source/runtime manifests.

Original `.10` offline evidence included6compiledDT comparisons,20unchanged network files,7actualARMstartup controls,213transaction checks and34classifier checks. Later hardware booted confirmedbank1, with DHCP/default route, SSH and controller connection; working8x8 was reported. These are prior-release results, not qualification of a newly built main image. The publication audit tests patch application only.

No build artifacts, extracted filesystems, generated staged/unstaged diffs, configuration snapshots, generated result JSON/ledgers, private keys/certificates or raw hardware captures are included. Historical reproduction snapshots remain local.
