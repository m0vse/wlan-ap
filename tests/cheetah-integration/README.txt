Cheetah profile and source integration

The qualified XV2-21X profile and hardware implementation come from published Cheetah .13 source4a893a76. Sibling models remain unqualified. Keep the hardware patch at0125a, before the existing0126..0130 certificate series. The separate0131 patch preserves the tested Cheetah bank certificate policy and pre-RAM certificate export. Do not replace shared certificate patches or other family profiles.

Validation performed before this source-only preservation: nine ordered source patches apply in isolation; Cheetah and generic A/B changed source matches the .13 build tree. Main's existing Jaguar02_network MAC case is appended after exit0 and requires a separate shared correction. This proposal does not claim a new build or AP qualification. Original .13 firmware and source provenance remain unchanged.

Only deliberate source patches, profile and instructions are published here. Generated configurations, source snapshots, results, binaries and private inputs remain outside this candidate. Shared main integration is serialized by the repository owner.
