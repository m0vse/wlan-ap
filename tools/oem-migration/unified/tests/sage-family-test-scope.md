# Sage source fixture scope

The adapter targets the retained exact `4.2.3.3-r10` OEM baseline. E410 and
E410B have separate factory/SKU/FIT mappings; enclosure and capacity are not
revision identifiers. OEM-return/defaults are currently mapped only for the
retained E410-A/EU U-Boot binary. No E410B return is inferred.

`test-sage-forward.py` now exercises the actual forward adapter, pair writer,
FORMAT2 producer and overlay stager together. It covers both models/both slots,
ten persistence/write/readback/mount/arming failure cases and legitimate
external source activity. Only device/ENV/mount/sync/UID metadata boundaries,
the off-device receipt and nonflashable provider inputs are simulated. It
checks source-first persistence, unmount-before-arm, original protected bytes,
upper 0755/private 0700/credential 0600 and no key in mocked child args/env or
event logs. This is not real flash durability, hardware power loss, or proof
that a production provider has its complete actual runtime/ELF/FIT closure.

`test-sage-inspection.py` exercises actual readers and physical range admission,
not a full forward transaction. Its runtime ledger and payloads are synthetic,
nonflashable fixtures. A published provider still needs the complete actual
OEM runtime ledger, extracted FIT binding and independently pinned payloads.
The full runtime/ELF ledger is publisher evidence, not a device admission gate:
runtime admission checks exact release/build and reviewed boot/updater/identity
hooks plus required native command presence, not every libc/interpreter/library
checksum. Missing unrelated library and missing required hook/wrong-build
fixtures distinguish that boundary.

The recovery `test_cambium_sage_oem_deferred.py` suite runs the actual pair
writer, preflight, source-first environment persistence and final OEM armer.
Device/ENV tools, physical-range callback and the known bootloader hash boundary
are inert fixture implementations. It covers both slots, write/persistence
faults, protected-byte equality and original uploaded uppercase backup names.
This is not U-Boot, watchdog, flash interruption or hardware acceptance proof.

Immutable source kernel/root, config NOR, ART/MFG and bootloader retain their
byte/hash checks. Writable source overlays, shared nvram/certificates and the
OEM writable UBIFS root retain identity/parent/name/size/health proof and exact
target-only writer exclusion; normal external daemon writes are not treated as
corruption. The writer never freezes/remounts source storage or stops arbitrary
daemons. Fixtures distinguish allowed external nvram activity from a wrong
source-kernel write and an explicitly rejected active-child write request.

`test-sage-confirmation.py` runs the actual confirmation adapter and compiled
OEM defaults helper. Source metadata, vendor executable hash and critical
backup transport/device boundaries are isolated. It preserves source data and
checks refusal paths, but does not qualify the real OEM runtime/ELF closure.

`CONFIRM OEM` is not a factory-reset authorization. The independently matched
native `delconfig.sh force` reboots; it is only displayed as a separate action.
After that reset/default regeneration, native `savecfg2nor.sh` refreshes the
named config NOR. That script masks `flashcp` failure: read back its gzip/tar
`config.txt` and compare with `/mnt/flash/config/config.txt`; exit zero is not
sufficient. No vendor script, AP action or firmware build runs in these tests.

Native certificates are never wiped or revoked here. A fresh forward migration
with an existing shared certificate volume remains a distinct lifecycle case;
the existing fresh-only transaction refuses rather than silently erasing it.
The separate post-confirmation retirement action and existing server reset flow
are documented in `sage-jaguar-clean-return-operator.md`. Confirmation and native
factory reset are not proof that the old private identity has been cleared.
