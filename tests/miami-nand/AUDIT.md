# X7-35X .11.4 NAND audit and first-failure diagnostics

Audit date: 2026-10-13. No firmware deployment or AP mutation performed.

## Exact baseline and retained mitigations

Running AP reports `miami-2026.10.11.4-0a1f5467`, Linux 6.6.88.
Released source: `0a1f5467a9a2cb9287ad544d8c7f5ee070eec957`;
qualified generated SDK: `ec2a03dd3463be8c9c96272ea6687e0bad4fb698`.
Retained compiled driver source SHA256:
`aeed1a4f0c817f6bc3b0a460a3d1ee2e213942d483656a331d59f19cc7ff4ba4`.

The driver source was last written on 10 October before the .11.4 release.
Recompiling it with the retained object command and GCC 14.3 reproduces
all 14 allocated ELF sections of the original `qcom_nandc.o` exactly.
The release receipt separately confirms both .11.4 kernels are byte-identical
to qualified .11.3 kernels. This audit is of that retained driver, not an
assumption based on the latest source HEAD.

Read-only hardware inspection after an operator power cycle confirms:

- 24 MHz feedback clock before NAND probing.
- B0 configuration before/wanted/after is 0x01: QE enabled, OTP/on-die ECC off.
- Miami skips destructive NAND serial training and preserves training data.
- Six physical NAND partitions; both rootfs banks are 96 MiB.
- Slot0 confirmed in shared A/B mode; board data from vault.
- Overlay and certificate volumes mounted separately and read/write.

The RAM-only recovery read-only partition policy remains in source; it does
not apply to the persistent writable build and is not runtime recovery.
There is no implemented controller recovery sequence on a read failure:
`submit_descs()` can return a timeout and its caller frees descriptors.
This is an audit concern, not evidence that the current failure was a DMA
timeout. The retained incident log has ECC/read errors, not an explicit
BAM timeout.

## Comparison with cited upstream fixes

| Fix | Exact .11.4 result | Current upstream result |
| --- | --- | --- |
| SET_FEATURE operand before EXEC (`8fd62901d6bf`) | Already equivalent: `qcom_serial_set_feature()` queues FEATURES before EXEC in the same submission. GET_FEATURE synchronizes the response for CPU. | Present in Linux 6.18.55 `spi-qpic-snand.c`. |
| Resize BAM allocation after page geometry | Already equivalent: `qcom_nand_attach_chip()` frees initial allocation and reallocates after max codewords is known; four codewords for this chip. | Present in 6.18.55. |
| FLASH_STATUS DMA synchronization (`bc3686021122`) | Present in `check_flash_errors()` and `parse_read_errors()`. | Present in 6.18.55 raw driver. |
| Avoid obsolete EBI2_ECC_BUF_CFG on QPIC v2 | Present: staging/read/write accesses are guarded by `!qpic_v2`; IPQ5332 is v2. | Present in 6.18.55 SPI driver and raw driver. |
| BAM v1.6 read-mask address bits | Equivalent read workaround present: reads use `bam_prep_ce()`, which explicitly clears mask; writes use `bam_prep_ce_le32()`. | Constructor handles command-dependent mask in 6.18.55. |
| Parallel Linux/modem access locking | No BAM inter-processor locking found. No second NAND owner established on Miami. | Related MDM9607 report is not an IPQ5332 diagnosis. |

Official OpenWrt main inspected at
`3fba6794e24542494853454cdaf52595dab4a37b`: qualcommax uses Linux 6.18.55,
and lists ipq807x/ipq60xx/ipq50xx, not an ipq53xx target.
Thus there is no like-for-like upstream main X7 implementation to call
unaffected. QSDK's raw NAND/page-scope path differs from the modern upstream
SPI-NAND path. The existing equivalent fixes also occur below OpenWiFi's
controller/application layer. An OpenWiFi-specific root cause is unproven.

Potential downstream issue to measure: completed page-scope status is copied
from an unmapped DMA status buffer into the persistently DMA-mapped register
buffer, then `parse_read_errors()` synchronizes the latter for CPU. This
ordering deserves a DMA-ownership audit; it is not proof of corruption.
The diagnostic stores both versions before erased-page fallback reads.

## First-failure record

`1006-mtd-qcom-miami-first-failure-diagnostics.patch` adds an immutable
per-boot record at:
`/sys/bus/platform/devices/79b0000.nand/miami_first_failure`.

The diagnostic is gated to X7-35X, serial NAND ID c2:a6, 256 MiB,
2 KiB pages, 128 KiB eraseblocks and four ECC codewords.

Triggers:

- Confirmed uncorrectable ECC after existing erased-page checks.
- Operational error in a completed ECC page read.
- Failed DMA submission/completion in the ECC page path.
- An existing sampled EC-header read changes from previously observed
  `UBI#` to invalid magic, including all-FF reads with errno zero.

The immutable record contains boottime, absolute page/PEB, result, original
command, feedback clock, ECC counters before fallback, controller registers,
per-codeword parsed and page-scope status, and BAM positions/cookies/status.
Only four header bytes are included; no page data, certificates, keys,
environment, or firmware contents are dumped.

Controller/codeword state is captured before the driver's ordinary
erased-page fallback. Records are published only for a confirmed error, so
normal erased pages do not consume the record. A0/B0/C0 GET_FEATURE commands
run after that check while the existing NAND core locks remain held, only
when every submitted channel is complete. A failed GET stops the sequence;
timeout/unfinished DMA skips it. These later feature values are explicitly
labelled; they are not represented as contemporaneous pre-fallback values.

Reading sysfs copies the stored record only. The attribute cannot reset or
rearm diagnostics. No SET_FEATURE, reset, extra NAND page read, automatic
recovery or flash write is added. The existing canary supplies the page reads;
only previously valid sampled headers qualify, preventing false alerts on
bad/free/unformatted blocks. The record disappears on reboot/power loss.

The native storage probe reads at most 2047 bytes of the cached attribute and
includes JSON-escaped `nand_first_failure` facts. The shared fault evaluator
exports these in `values.faults.monitoring`, without changing other families'
radio logic or the existing fault lifetime/debounce policy. Old kernels
report the diagnostic as unavailable. Controller-side retention of received
health records preserves the snapshot after it has been uploaded; there is
no claim of retention across a power loss before upload.

## Validation and limitations

- Isolated target compilation against retained kernel headers/toolchain: PASS.
- Actual diagnostic observer/publisher and `parse_read_errors()` extracted
  from the candidate C: PASS (first record, boundary addresses, erased-page
  suppression, genuine errors, no features for unfinished DMA, stop on failed
  GET, disabled gate).
- Native actual storage probe: PASS (old kernel, armed/captured state,
  JSON escaping, bounded output, invalid input).
- Existing 27 actual target-ucode evaluator controls: PASS.

These tests verify implementation, not physical QPIC commands or the next
48-hour soak. The new kernel must be built and installed before it can
capture the next fault. No conclusion that the hardware fault is fixed is
supported by this audit.

## Missing UI fault indication

The main task found four stored X7 health reports with sanity100 and
12/12/25/12 active critical faults, including uncorrectable ECC and canary
failure. Ingestion succeeded. The main device badge, health history and
detail percentage use numeric sanity alone, so remain green. This is a
separate UI presentation defect; critical storage faults should override
the healthy presentation while preserving the independent numeric score.

## Primary references

- https://cos.googlesource.com/third_party/kernel/+/581e5166f0780103dc91c0d8ebc801f9af4824b0%5E%21/
- https://github.com/openwrt/openwrt/issues/24708
- https://lkml.iu.edu/2505.3/00538.html
- https://lkml.iu.edu/2012.3/02141.html
- https://lkml.iu.edu/hypermail/linux/kernel/2609.1/04707.html
- https://lkml.iu.edu/hypermail/linux/kernel/2510.1/06422.html
- https://lists.openwall.net/linux-kernel/2026/07/08/1327
- https://github.com/openwrt/openwrt/blob/3fba6794e24542494853454cdaf52595dab4a37b/target/linux/qualcommax/Makefile
- https://github.com/openwrt/openwrt/blob/3fba6794e24542494853454cdaf52595dab4a37b/target/linux/generic/kernel-6.18
- https://github.com/gregkh/linux/blob/v6.18.55/drivers/spi/spi-qpic-snand.c

### Procd startup: complete configfs writes

The 18.2 launcher retry did not address the boot failure. On hardware, procd
sets `LD_PRELOAD=/lib/libsetlbf.so`; its constructor calls `setbuf(stdout, NULL)`.
The shipped BusyBox `printf '%s\n' value` then sends the value and newline in
separate writes. Configfs parses each write independently: the newline clears
the device/IP attributes, and fails MAC parsing. A manual shell without that
preload combines the output, explaining the misleading successful manual tests.

The setup helper now uses BusyBox echo, which assembles the complete value and
newline before a direct write, and checks every attribute by reading it back.
An enabled target also has to match the configured local port. The RAM watcher
starts only after the target is verified. The kernel marker uses the same
complete-write rule. No controller, driver, radio or network settings change.

`test-configfs-writes.py --root <extracted-target-root>` executes the actual
ARM BusyBox with the actual procd preload using QEMU syscall tracing. It proves
the released printf path splits under procd while succeeding without the preload,
and requires a single complete write for all seven fixed attributes. Existing
launcher readiness/disabled controls remain applicable. Hardware reboot evidence
is kept privately; this source test does not itself establish boot acceptance.

### 20 October: RAM-only first-failure capture

A real captured external abort occurred in miami_diag_take at the direct
NAND_VERSION MMIO read (offset0xf08), during read-error handling. This
explains the diagnostic panic/reset, not the original NAND lockup.

Patch1008 removes all diagnostic-time register reads, clock-provider queries,
DMA-provider status calls and optional feature commands. Existing RAM status,
ECC counters, command, cookies and BAM positions remain available; the clock
is cached from existing normal setup queries. Unavailable fields are explicitly
labelled and never represented as measured zero values. Normal NAND operations
and erased-page error handling are unchanged.

The native regression now compiles the actual snapshot function as well as
the actual publisher, header observer, error parser and sysfs formatter. All
hardware/provider hooks are poisoned. The released snapshot is a failing
negative control. The worst-case formatted record is1662bytes, below the
existing2047byte storage-probe and4095byte exporter limits. Synthetic tests
do not reproduce or establish a cure for the original NAND failure.

# X7-35X one-shot RESET/feature measurement

This proposal extends the qualified 20.1 source (187defc7). It is an approved
measurement, not a repair of the original NAND fault. No AP action has been
performed while preparing it.

The existing immutable RAM-only first-failure cache and printk export complete
before the probe. The probe is called only at the completed ECC callback return
boundary, after descriptor cleanup, under the existing NAND controller lock.
A separate once-per-boot flag is set before any probe command or eligibility
abort. Normal and nested probe reads retain their original return values.

Eligibility retains the exact X7-35X / c2:a6 / 256 MiB / 2048+128 / 128 KiB /
4x512 / strength-8 / CS0 gate. Buffer allocation and healthy A0/B0 sampling happen
at normal boot. A0 is restored to that healthy value, including a nonzero value;
B0 must have been 01 at healthy boot. Missing baseline/buffer, unsafe DMA, boot
layout or an unqualified other-bank page consume the attempt and log an abort.
The other-bank page is selected only from already-observed valid UBI EC headers.

READ-ID and RESET retain the legacy void interface; the helper's actual build
or submission result is cached so the experiment can stop on an error. RESET
also checks the completed RAM flash status. GET/SET errors or readback mismatch
abort. The 10 ms OIP readiness budget is checked between completed GET transactions.
Phil explicitly approved keeping the existing two-second command transport
timeout rather than adding a premature-return DMA path. Elapsed time is logged
honestly: a single command can overrun the readiness budget. All normal driver
completion waits and cleanup semantics remain unchanged. There is no DMA-provider or direct MMIO diagnostic query.
A timed-out transfer latches unsafe-buffer state: no subsequent probe command
or second read reuses its buffers. Descriptor cleanup alone is not quiescence.

The re-reads use private boot-allocated DMA-capable memory, normal internal ECC
read setup and read_page_ecc(), never MTD/NAND-core re-entry. During these two
reads only, uncorrectable codewords are reported directly, without erased-page
raw re-reads. Their ECC-stat changes are measured then restored so the original
caller's ECC outcome is unchanged. Normal erased-page logic is retained.
Only the first four data bytes are logged. No array program/erase, training,
clock/phase adjustment, or data payload export is added.

Each command has a printk(KERN_ERR) begin record before attempting it, then a
result. The sysfs cache contains completed results and the current pending
operation; a compact original snapshot omits unavailable register placeholders,
retaining actual CW/page-scope statuses, cookies and explicit unavailable flags.
Native maximum-capacity formatter test is 1978 bytes, below the existing 2047
byte storage-probe limit. Actual full successful trace plus maximal original
fields is 1590 bytes. Console transport has the full begin/result stream.

Later ECC page reads are counted exclusively as ok/corrected/fail for ten minutes;
fail includes negative operational/transport errors and new ECC failures. Probe
reads and the original failing read are excluded. A delayed work item logs counts
every 60 seconds even if no further NAND reads happen; it issues no commands and
is cancelled on device cleanup. Sysfs retains the current cumulative counts.

A root-only write-only miami_probe_test attribute is never armed automatically.
It accepts only a previously-qualified canary page. Only a reader named
miami-ecc-test can consume the arm: ordinary UBI/app reads cannot be injected.
After a real read DMA completes, the test changes only cached ECC status and
labels the record synthetic_ecc_probe / synthetic=1; no array bits are changed.
bench-read.c is the explicit one-page read-only MTD reader, not a daemon.
The synthetic run consumes the same once-per-boot probe: a subsequent human
reboot is necessary to arm natural-failure measurement again. It cannot rearm
in place. The bench read must not be described as a reproduced NAND lockup.

Native tests execute the actual probe, ECC outer callback, error parser, sysfs
formatter, injection gate and command-result helper. They cover every command
failure position, OIP timeout, bad ID, disabled/missing baseline/unsafe DMA gates,
no other-bank canary, partial reads, recursive callbacks, second attempt,
preservation of original EIO/ETIMEDOUT and ECC stats, counter expiry, maximum
record size, and exclusion of ordinary UBI from injection. Existing snapshot
poison and released-driver negative tests are retained.

Live acceptance remains pending a test firmware installation by Phil: check A/B
confirmation and automatic capture first; verify healthy A0/B0, then run the
explicit bench once and compare all printk steps with Mac netconsole and serial
logs. Check the AP remains reachable and subsequent ordinary reads work. Do not
claim live bench acceptance before doing this. Keep U-Boot serial capture and
read-only checks before any power cycle after a natural failure.

Interpretation: success shows that this complete command sequence restored
these two reads. The sequence does not contain a read between RESET and SET,
so it cannot distinguish RESET-only success from SET-dependent success. A reset
can also clear hardware state; failure can originate in the controller/DMA path.
Neither outcome alone proves software versus physical/power root cause.

Optional setup failures never propagate a NAND-driver startup error. The
actual void setup helper attempts the original RAM-snapshot attribute even
when cleanup-action or private-buffer allocation fails; those failures disable
probe commands, timer work and the bench hook for the boot. Snapshot and bench
attribute failures also return normally. Native tests execute each allocation
and attribute failure and the healthy nonzero-A0/verified-B0 setup path.
