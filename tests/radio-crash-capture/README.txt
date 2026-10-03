POTENTIAL PERSISTENT RADIO CAPTURE: XV2-21X

Scope and status
This is a source/offline-test candidate, not an installed package or enabled
AP service. Cheetah qualification covers XV2-21X only. Whole-kernel panic
capture is the separate shared external netconsole candidate owned by Thor.
No pstore/ramoops region is proposed; no radio reservation is repurposed.

Evidence from the retained Cheetah kernel 6.12.85/backports 6.18.7
CONFIG_DEV_COREDUMP=y, CONFIG_REMOTEPROC=y, CONFIG_QCOM_Q6V5_WCSS_SEC=y.
The generic ipq5018.dtsi declares qcom,ipq5018-wcss-sec-pil, but the actual
XV2-21X QCN6122 include OVERRIDES it with qcom,ipq5018-q6-mpd. Read-only live
verification on 2026-10-03 confirmed qcom-q6-mpd binding and all remoteproc
coredump settings disabled. The selected MPD root/user-PD rproc_ops have no
parse_fw/coredump segment producer. Thus the current Cheetah built-in radios
do NOT have a qualified devcoredump producer; this collector cannot create
one. MPD is deliberately excluded from its eligibility allowlist.
The separately compiled SEC implementation does register DT-supplied dump
segments and selects INLINE dumps, but is not evidence for the MPD binding.
Where a reviewed producer exists, remoteproc INLINE waits for release or
framework timeout (five minutes). drivers/base/devcoredump.c emits ADD.
Reading data does not consume it; writing data initiates release.
ath11k AHB has no coredump_download callback. Do not attribute the producer
to ath11k_coredump_collect just because that function is present.
Potential fixable MPD producer work remains: review root and user-PD fatal
paths, existing q6_alloc_memory_region mappings and q6_wcss_da_to_va, and
provide a bounded nonblocking snapshot through devcoredump using those existing
DT-owned radio mappings. Do not invent a new RAM reservation. Preserve normal
recovery ordering and label partial snapshots; do not introduce an unreviewed
five-minute INLINE recovery stall. This needs isolated kernel compile and
synthetic lifecycle tests before adding MPD to the allowlist. Actual contents
and crash-time mapping safety require separately authorised hardware testing.
PSTORE is disabled in the frozen image. No authenticated OEM or actual
Cheetah DT establishes a qualified persistent ramoops reservation.

Collector prototype
collector.c reads only a devcdN data node; it never writes sysfs, changes
remoteproc recovery policy, deletes source evidence, or uploads a binary.
The production path is /etc/ucentral/radio-crash, with root-only 0700 directory
and 0600 files. Its immutable <bootUUID>-devcdN.json manifests use version1,
id, boot_id, driver, source, byte_count, binaryfile, complete and truncated.
source is devcoredump; driver is explicitly generic remoteproc-or-ath until
producer eligibility is checked by the integrated dispatcher. No claimed
wall clock, digest, or proven firmware fault is invented.

Common capacity default: two 1MiB binary records, plus one fixed-name 1MiB
temporary and small manifests. At least 2MiB free space plus metadata margin
must remain; the check runs before capture and each write. This is compatible
in principle with Sage's small overlay and is not a promise of free capacity.
Other writers can consume space concurrently; ENOSPC/write failure aborts.
An oversized dump stores a labelled prefix and remains incomplete; it is
not a full ELF dump or sufficient evidence to reconstruct every crash.
No record eviction or automatic source release is implemented. Full spool
and low-space conditions refuse new captures. Existing records survive.

Commit protocol: exclusive flock; private temporary data; file fsync;
private manifest fsync; rename data; directory fsync; rename manifest last;
directory fsync before unlock. Reporter must take a nonblocking shared flock
on .lock while reading manifests. Binary is never read by the reporter.
Acquiring that lock alone does not prove the final directory fsync succeeded:
a failed publisher can release its lock with an existing manifest. Reporter
must independently confirm durability before trusting that manifest and retain
all evidence if confirmation fails. Existing-event collector retries hold the
exclusive lock while repeating directory fsync and return success only after
it succeeds. These rules do not turn filesystem sync into hardware proof.
Fixed temporary names bound leftovers after interruption and fail closed;
operator review is required to clear abandoned temporary/orphan data.
The source remains intact on every failure, including incomplete capture.
This prototype does not protect an underlying flash device from failure or
prove power-loss durability on UBIFS. Atomic publication is not an ACK from
the controller, and the reporter's transmitted-unacknowledged semantics apply.

Integration plan (required before claiming a deployed working backend)
1. Shared owner packages the collector, with source eligibility allowlist
   for reviewed ath/remoteproc failing_device driver bindings. Never ingest
   arbitrary device dumps merely because a devcdN exists. Generic driver
   metadata must not be presented as a verified ath11k device identifier.
2. An explicitly enabled procd dispatcher handles devcoredump ADD and scans
   already present entries at startup; bound invocation time and serialize
   capture. Missing/disabled collector is harmless. No boot or shutdown reset
   policy changes, recovery release writes, or guessed physical memory maps.
3. Shared reporting owner validates safe manifests under shared lock, adds
   bounded crashlog/loglines radio-coredump summaries with seen keys, and
   leaves host reboot reasons unchanged. Raw binary stays private local.
4. Add this bounded directory to normal managed upgrade archive and keep.d;
   validate archive/free-space budgets including simultaneous boot history.
   Explicit -n/factory reset erases it. Pending data should not be silently
   evicted to make an archive fit. Existing preservation gates remain.
5. Provide a clear operator diagnostic for full spool, incomplete copy,
   absent producer, permission/storage failures and unconfigured netconsole.

Hardware qualification, separately agreed with the operator
Read-only inventory first: actual failing_device bindings, rootfs capacity,
remoteproc identities and dump mode; confirm real firmware source provenance.
Then an explicitly authorised controlled radio crash on a spare AP must show
the expected uevent, safe read, prefix/complete flags, bounded private durable
record, unchanged recovery behavior and matching controller summary.
Normal reboot after successful capture must preserve the record; interruption
during publication needs a separate authorised power-loss test. Confirm real
dump content: the current WCSS copy_segment boundary behavior needs review,
so compile/source evidence alone is not a guarantee of useful dump bytes.
Whole-kernel panic before userspace scheduling, a hard lockup, sudden power
loss, lost dump uevent, or flash/network failure may prevent capture. No
current radio collector can promise retention in those cases. Netconsole
needs a reachable, configured external durable receiver and driver netpoll
qualification; it also cannot record trace data that never gets emitted.

Offline test invocation (never AP paths)
sudo python3 test-collector.py EXISTING_EXTRACTED_ROOT TARGET_GCC collector.c
The test compiles fixture roots into a temporary executable and runs it with
the actual target runtime under QEMU. It uses synthetic bytes and test-only
fsync/free-space wrappers, not real kernel dumps, resets or controllers.
No firmware package, link, or complete image is built.
