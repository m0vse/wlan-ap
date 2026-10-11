# Jaguar incoming-consumer compatibility scope

Selected incoming reference: published `jaguar-2026.10.05.8-112421ad`, image
SHA-256 `b14232bb788f7385f96db1fc63110e6d58b14da6db42c493cac30075a040dbd3`.
`fixtures/jaguar-2026.10.05.8-consumer-receipt.json` records actual extracted
kernel/root and five consumer hashes. Host `unsquashfs4 -cat` read the scripts
from the hash-bound image, not a mutable build-tree copy. Fixtures enforce those
exact script hashes before extracting/replaying source functions.

## Format-1 radio vault

The actual reader compares manifest `board` literally with `board_name`; its
`board_files` supports `cambiumnetworks,xv2-2`, `cambiumnetworks,xv2-2t1` and
`cambiumnetworks,xe3-4` for the qualified model FITs. Controller compatible names
(`cambium_xv2-2t1`), `cambium,MODEL`, and generic Jaguar are not reader aliases.
The writer therefore accepts only the exact incoming board labels. This is a
format compatibility fix, not additional hardware qualification or a DT change.

`test-jaguar-consumers.py` runs the actual `board_files`, `manifest_value`,
`sha256` and `vault_check` functions against archives built by the real forward
writer. Only board/SKU/ART media getters are inert. All three models pass;
wrong board, SKU, own ART, file path, byte size or digest fail. The informational
`nvram_sha256_at_capture unknown` is not consulted by the existing reader and
is accepted. The writer's existing authenticated asset-table uniqueness and
model-specific file counts prevent extra/duplicate assets; the consumer is not
claimed to reject every arbitrary extra archive member on its own.

For raw-vault reduction, the fixture verifies meaningful archive bytes and
reader acceptance before/after changing only zero padding from 8 LEBs to the
archive's rounded LEB count. XV2-2's OEM 369 LEBs plus that archive and retained
20-LEB certificate store fit its 392-LEB budget. This is not a physical resize
test, permission to resize a formatted store, or implementation of OEM return.

## FORMAT2 first-boot handoff

The arm batch now publishes and reads back `jaguar_installer_target`,
`jaguar_installer_job`, and `jaguar_installer_image`; the job/image must match
the source-first journal and real staged binding. Triplet readback repeats after
the caller's protected-state check, immediately before the final boot selector.
Initial foreign/partial pending fields refuse before any transaction mutation.
These are fields required by the existing boot protocol, not a new gate.

Six real writer successes (three models/two slots) replay the actual identity
consumer's `CONTEXT_COMMAND`, pending boot script, empty-store mount guard and
installer health/clear-pending/confirmed-cleanup shell functions. Inert source
libraries provide only hardware identity and ENV reads; mount proof is a fixture
table and acceptance calls are inert. Exact namespace/target/job/image agreement
with the staged FORMAT2 binding is checked, including valid-looking foreign and
partial metadata negatives. Native boot-component tests inject each metadata
readback failure and each late triplet change: neither may select the candidate.

Full Ucode validation, enrollment cryptography, controller acceptance, actual
mount/flash/ENV durability, U-Boot and power-cut recovery are **not** executed or
claimed. A different incoming image needs its own actual consumer binding; this
receipt is not an unrestricted future-image or sibling-model approval. No new
firmware build, AP operation or stock-source modification was performed.
