# Persistent external kernel capture candidate

This source candidate sends kernel console messages directly to a wired external
UDP collector using netconsole/netpoll. The collector synchronizes each complete
received raw datagram to private persistent storage. It does not require a RAM
reservation, alter the A/B banks or reuse OEM crash/certificate partitions.
It is a potential kernel panic capture solution pending family hardware testing.

## Firmware changes

Patch 0154 enables dynamic netconsole and its configfs dependency in the existing
kernel package. The shared ucentral-netconsole package installs an opt-in service
and persistent UCI configuration. Family profiles select the package, which
selects kmod-netconsole, kmod-fs-configfs and the required ucode modules. Default
`enabled=0` loads no capture target and changes no network configuration.
The helper requires an already-up wired device with carrier; it never raises a
down interface, changes an address, restarts networking or unloads netconsole.
Only the fixed `ucentral` target is configured or removed. It remains enabled
through shutdown so shutdown failures can still be observed.

## Operator setup after approval

Run the collector on persistent storage on the wired management network using
an explicit bind address, UDP port and AP sender allowlist:

    python3 collector.py --bind COLLECTOR_IPV4 --directory PRIVATE_DIRECTORY \
        --allow AP_IPV4 --port 6666

This document provides placeholders; no endpoint or host service is deployed.
Configure `netconsole.capture` with enabled=1, the actual physical wired device,
AP local IPv4, collector IPv4, UDP ports and the verified unicast next-hop MAC.
Use a stable DHCP reservation or otherwise reviewed local address. For a routed
collector the next-hop MAC is the gateway's MAC, not the remote host's. Endpoint
setup and service activation on an AP require separate operator authorization.
Do not use a wireless interface, guessed MAC, broadcast destination or bridge
name without reviewing the actual family netpoll path.

## Storage and reporting

The collector requires an owned real mode-700 directory and creates mode-600
JSONL files. It stores receipt time, sender IP/port, a truncation flag and base64
of the raw message, preserving non-UTF8 bytes. Defaults retain eight 1-MiB
segments per allowlisted AP, at most 32 APs (256 MiB total), with explicit
configurable bounds. A packet is capped at 8192 bytes and truncation is recorded.
Files and rotation directory entries are synchronized; a failed sync cannot be
reported as successful persistence. Partial last records are discarded on retry.
No socket is opened by the storage tests and no external listener is deployed.

The activation marker includes the AP boot ID, permitting correlation with the
existing bounded uCentral boot report. Normal boot reporting continues through
the reviewed client path. External kernel records remain on the collector; they
are not automatically uploaded through the AP's rebootLog/crash-log transport.
Operator/controller ingestion of these external records is a separate integration
step, and an AP without local confirmed evidence must still report
`unexpected-shutdown`. Received panic text can provide confirmed crash evidence
for review; absence of packets cannot prove power loss or a watchdog reset.

## Limits and finite acceptance

UDP has no delivery acknowledgement. A dead Ethernet controller, netpoll lockup,
switch/collector outage, sudden power loss, early panic before target activation
or lost datagrams can prevent capture. No complete-memory vmcore is produced.
One-second panic timeout may permit only a partial trace. The external collector
must already be running and preserve storage across the AP's reset. These limits
are separate from optional durable radio devcoredump capture while Linux lives.

1. Compile the selected family kernel/package capability without changing its
   baseline, and run actual target helper plus collector storage fixtures.
2. With operator approval, start the collector and configure one test AP; verify
   an ordinary kernel message and boot-ID marker arrive and survive collector
   restart. Verify local networking/radios and target ownership remain intact.
3. With separate explicit approval and recovery access, test one controlled panic
   on each relevant Ethernet implementation; verify the trace persists after
   reset and correlate its boot ID with the next boot report. Do not infer this
   result from userspace UDP transmission, a radio restart or a synthetic fixture.
4. If a family cannot transmit through its wired panic path, keep capture disabled
   and use an external persistent UART recorder or a separately reviewed ramoops
   region. Do not invent a reserved memory address to complete acceptance.

## Family source readiness

Thor .10 Linux 6.12.85 lacks netconsole/pstore. qca-nss-dp IPQ8074 EDMA-v1 uses
NAPI attached to a netdevice and performs TX cleanup at budget zero. Kernel
netpoll polls NAPI with budget zero and permits an absent ndo_poll_controller;
this is source compatibility evidence, not proof of panic packet delivery. The
normal ath11k AHB coredump hook is absent, so DEV_COREDUMP=y alone is insufficient.
Thor's existing upstream CE/quiesce recovery patches and single-8x8 topology
remain separate and unchanged.

Jaguar/Cheetah use related Ethernet drivers but their selected EDMA implementation
and NAPI attachment must be checked individually. Sage uses a different wired
path and kernel baseline; its inherited ramoops declaration is not retention
proof. Gambit has no available hardware and no build is authorized: profile and
capture source are candidates only, with ag71xx/netpoll support to be reviewed.
Per-family source checks and hardware acceptance must accompany integration.
