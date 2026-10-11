# Jaguar physical profiles: source-slot convention

A single provider contains both authenticated physical inventories:

- Forward: `profiles/MODEL/mtd-slot0.tsv`, `mtd-slot1.tsv`.
- Return: `profiles/MODEL/restore/mtd-slot0.tsv`, `mtd-slot1.tsv`.

The suffix is the **inspected running SOURCE slot**, never the target slot.
Slot 0 assigns NAND `rootfs` to `active-oem` (existing protected-source role
name) and `rootfs_1` to `target`; slot 1 reverses those two roles. Physical
names, chip domains, offsets, sizes, type, erase/write geometry and unrelated
NOR/protected roles remain the actual model-specific captured values. The
existing eight-column inventory schema is unchanged.

The adapter resolves the exact filename from `OEM_SOURCE_SLOT` 0/1 and checks
its authenticated bundle membership/hash before reading. Role checks still
bind that map to the actual source/target MTDs. There is no silent fallback to
the ambiguous older `mtd.tsv` filename and no inference of a sibling's physical
map. A missing selected map or a map with wrong source/target roles refuses
before ENV or inactive-bank writes.

Fixtures now contain **both maps at once**. Both-source-slot successes and
wrong-slot role refusals no longer regenerate one ambiguous filename per test.
Their NOR offsets are deliberately synthetic and are not published physical
capture evidence. Actual provider qualification uses retained model-specific
running maps, independently bound public firmware and source evidence.
