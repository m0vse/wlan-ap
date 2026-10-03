OFFLINE SHARED BOOT/CRASH REPORTING CONTROLS

All events are TEST-labelled and all files/process calls are synthetic.
No test may submit events to a production controller or operate an AP.
Run module fixtures only in a new root-owned private temporary directory.

Host or extracted target ucode:
  ucode tests/boot-reporting/tests.uc PRIVATE_FIXTURE_DIRECTORY
Actual target runtime under emulation:
  sudo qemu-ARCH -L ROOT ROOT/usr/bin/ucode -L ROOT/usr/lib/ucode \
    tests/boot-reporting/tests.uc PRIVATE_FIXTURE_DIRECTORY
Create PRIVATE_FIXTURE_DIRECTORY with sudo mktemp -d, not an AP path.
The module controls cover 82 assertions including unknown reason, request
precedence/expiry/cancellation, bounded JSON/event queues, late evidence,
reconnect/retry, invalid state/links, and pre/post-rename sync failures.

Actual CLI, helper, interactive and shutdown tests (no real reboot):
  sudo unshare --mount --propagation private sh \
    tests/boot-reporting/test-entrypoint.sh SOURCE_ROOT ROOT QEMU_EXECUTABLE
This runner refuses the host mount namespace. It binds synthetic /etc,
/run, /sys, boot-ID and uptime files privately, and maps reboot paths ONLY
to harmless fixtures. It does not expose a configurable production path.

Apply client patch to private upstream cb48fe27 source copies, then:
  python3 tests/boot-reporting/test-client.py PATCHED_CLIENT_DIRECTORY
This compiles a HOST TEST executable using exact send functions; it is not
a firmware build. Check the full modified C files with target compiler
-fsyntax-only and existing target headers; do not produce package objects.

After applying all existing schema patches plus 090 to private sources:
  ucode tests/boot-reporting/upgrade-tests.uc PATCHED_CMD_UPGRADE
  sh feeds/ucentral/ucentral-schema/scripts/validate-managed-upgrade.sh \
    PATCHED_CMD_UPGRADE
The 16 managed-command controls stub download, RPC, archive, sleep and all
process execution; no firmware is downloaded or installed. The absent-pmsg
helper runner has 7 reason/failure checks and no real helper invocation.

Package closure:
  ucentral-schema -> ucentral-boot-report -> ucentral-client
  ucentral-state -> ucentral-schema
Reporter also requires ucode fs/ubus and coreutils-timeout. Its START79
collector precedes START80 state. Legacy S80 pstore conversion is removed,
not merely skipped after a reporter error; backup rotation is unchanged.
Client start repeats collection before network/identity readiness guards.
STOP85 records generic orderly intent before unmount; service stop/restart
alone does not record a human reboot. Ordinary interactive reboot records
user-requested, without overriding specific controller/upgrade requests.
Direct /sbin/reboot and delayed/nonstandard invocations may bypass it.
Managed upgrade preserves local history regardless of keep flags; keep.d
also covers ordinary preserving sysupgrade. Factory reset / sysupgrade -n
intentionally erase overlay history and cannot promise its survival.

Wire/storage semantics:
  rebootLog/type/date/info is the stock reboot-history protocol.
  crashlog/loglines is the distinct stock kernel-crash protocol.
  full write is transmitted-unacknowledged, NEVER server storage ACK.
Failed sends remain pending; successful writes are not replayed by default.
A persistence failure after a write can still cause a duplicate: there is
no gateway event deduplication or exactly-once/delivery guarantee.
Unknown cause is exactly unexpected-shutdown. confirmed-crash needs panic
text or a reviewed reset-cause hook. Nonfatal Oops is not a reboot cause.
Power-failure/watchdog attribution requires reviewed hardware evidence.

Radio dump metadata adapter (separate capture producer)
Only root-private version1 manifests from /etc/ucentral/radio-crash are
accepted, under the producer's nonblocking shared .lock and a successful
durability confirmation. Each manifest is at most 4096 bytes; the matching
private regular binary must have exactly the declared length (at most
4MiB). IDs, source, driver, boolean completeness and optional producer
digest are strictly bounded. The digest is a producer claim, not an
independent binary verification: the adapter never reads binary data.

The common collector uses smaller capacity-safe defaults: two 1MiB
records plus one temporary, preserving at least 2MiB free space. The
adapter's maximum accepted length is not a promise of overlay capacity.
Invalid, locked or unconfirmed manifests do not block boot reporting.
Immutable radio IDs deduplicate within the bounded seen ledger; source
manifests and binaries are never deleted, released, acknowledged or
uploaded here. Raw binary remains private on the AP.

The crashlog summary is explicitly classified radio-coredump, describes
complete versus partial retention and never changes the host reboot
reason to confirmed-crash. The summary transport has the same no-ACK
limitations as kernel reports. This adapter does not enable a devcoredump
producer or collector service; producer/package/eligibility, normal
managed-archive preservation and hardware proof are separate integration
requirements. Explicit -n/factory reset still erases overlay evidence.

No physical reboot, power-retention, kernel panic, gateway database or
firmware-package acceptance is established by these offline controls.

Full-series integration regression (2026-10-03):
  sh tests/boot-reporting/test-schema-series.sh SOURCE.tar.zst PATCH_DIRECTORY
replays every schema patch in lexical order against freshly extracted source
with patch -F0; it never modifies retained build inputs. Use the pinned
ucentral-schema-2026.08.26~d1e90a04 archive and the canonical schema patches.
The combined 072/090 archive includes both Thor pending topology paths and
boot-reporting history. upgrade-tests.uc verifies their presence for every
managed upgrade UI-flag combination, plus intent ordering and cancellation.
Full pristine series and validate-managed-upgrade.sh passed on cnbeacon;
21 mocked upgrade controls passed each actual Sage ARM and Jaguar AArch64
runtime. This is source/runtime qualification, not a firmware build receipt.
