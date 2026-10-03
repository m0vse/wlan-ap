# Thor dedicated scanner source controls

Apply schema patch 081 with zero fuzz to a disposable copy of the pinned
command sources. Run `test-owned-scanner.py ROOT CMD_WIFISCAN_SOURCE` and
`test-dispatch.py ROOT CMD_SOURCE CMD_WIFISCAN7_SOURCE` on a host providing
qemu-aarch64 and an extracted Thor root filesystem. The tests execute the
actual target ucode runtime with synthetic netlink, sysfs and controller
boundaries. They do not scan, reconfigure or access a live AP.

Coverage includes topology-dependent PHY renumbering, exact driver identity,
missing/ambiguous scanners, owned temporary station creation and verification,
serving-interface name collisions, preserved agent interfaces, link/trigger
failure, aborted/timeout scans, legal frequency filtering, periodic responses,
and both automatic and explicit alternate dispatch. Generic non-Thor routing
remains covered separately within the same fixtures.

Hardware acceptance remains necessary for driver scan-width/dwell behavior,
controller/RRM concurrency and RF results. Do not treat fixture passes as live
scanner acceptance. Generated expanded source and test outputs remain temporary
and are excluded from source commits.
