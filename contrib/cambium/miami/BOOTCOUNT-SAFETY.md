# Miami OEM pending bank switch safeguard

The matching packaged Miami OEM 7.2-r1 U-Boot is v2.7.5c (15 June 2026,
10:18:56), SHA256 `8aa2a31b57565305c03b4c6f473cbde21710063f900dcd85e2f67bde0b28d2c0`.
Its OEM `bootalt.sh` sets `bootcount=9`, and `clear_bootcount.sh` deliberately
preserves 9 as an upgrade bank-switch request. Independent disassembly of this Miami binary confirms its own Thumb bootipq
helper reads the first counter digit, switches image for 8/9, saves count 1,
then re-selects the bank. This is packaged OEM evidence, not a new installed
APPSBL dump. Jaguar addresses were not reused as Miami proof.

A manual RAM loader bypasses the stock loader. Restoring `bootcmd=bootipq`
without clearing the pending counter can therefore retain an unintended bank
switch after the other OEM bank has been replaced.

The reviewed source now clears bootcount to zero and verifies readback plus
unchanged verified OEM image selection before persistent install/update writes,
bank-backed RAM writes and arming. Read-only checks and backup preparation do
not alter the environment. Every new RAM/persistent restore prefix clears the
counter before saving the default. The matching Miami guarded-command consumer
uses this new exact contract. OEM-entry confirmation and its OpenWiFi rollback
both cancel the pending counter and verify it. No `nvram_badcount` changes.

This source change is not deployed. Published .11.4 images and historical
hash-pinned installer bundles are unchanged. Those bundles need newly versioned
replacement artifacts; never overwrite an immutable copy or reuse an old
receipt/hash. Replacing updater files alone does not rewrite saved boot commands. Deployment
must explicitly coordinate verified environment updates and re-arming with a
matching new producer and consumer. The old
legacy entry helper remains tied to its specific qualified source release.

Tests execute the actual installer and RAM helpers against disposable filesystem
and environment fixtures beginning at counter 9, including reset write failure,
read failure, stale readback and unexpected image selector changes. No AP, real
MTD, U-Boot environment, build or deployment is modified by these tests.

The new boot entry is an if-block: failure to set or save the restored default
reaches no candidate, OEM loader or reset. Native OEM fallback is permitted only
after a successful durable save of counter zero. Persistent candidate load has
no reset suffix. The exact producer and guarded-command consumer change together.
Critical setters/getters have explicit status checks even under conditional
imports that suppress errexit. Correct-looking stdout with failed exit is refused.

The retained cambium-return-oem source is included as a provenance-verified test
fixture only. The current Miami module lacks return-arm hooks; its 11 dispatch
controls prove refusal/synthetic hooks, not full legacy or current OEM return
qualification. Full confirmation tests separately exercise the actual entry
confirmation helper with explicit filesystem/UID/network/timer boundaries.
