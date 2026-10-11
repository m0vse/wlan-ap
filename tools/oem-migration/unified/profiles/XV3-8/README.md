# XV3-8 retained OEM 7.2-r1 inputs

This source profile is derived from the retained OEM DT SHA256
`35d46f0960dd687f5a42e6af16f054955d4d6f88d1a535fc8299c57494266d68`
and the independently signature-verified shared vendor container SHA256
`66a9b4bb558bf18a8e678d65ecf3857065683ba1da60885fa416d27a40f15192`.
Actual decoded `/etc/version` confirms PRODUCT thor, VERSION 7.2-r1, build
2026-06-15T10:28:04+00:00 and changeset
b169bb7e02ecbf1cdf31152220f63b30959ec9c2. Directory names are not the version
proof. The shared container also supports XE5-8; these profiles cover only
XV3-8/SKU 19 and do not admit XE5-8.

The verified binary body has a declarative manifest followed by the IMAGE
delimiter and a raw 45,875,200-byte UBI image. There is no xz layer in this
FORMAT3 payload; blindly applying the older generic DER→xz pipeline is wrong.
No manifest script, updater, reset/discovery program or decoded executable was
run. External signer bytes match the independently retained public reference,
not a key selected from the container. No new issuer or signing service exists.
`vendor-source.json` records exact container/body/UBI and padded/meaningful
kernel/root pins, original dynamic volume IDs 0/1 and build provenance. It is
static public source metadata, not a generated execution receipt or firmware.

`mtd-slotN.tsv` means target slot N, source slot 1-N, following the common
profile convention. It transcribes all 26 DT-declared partitions into the
existing eight-column physical format. NOR uses the existing 4096/1 physical
erase/write interface; NAND uses 131072/2048. Actual sysfs attributes, physical
chip domains, offsets and complete inventory still must match. DT does not
prove whether a kernel exposes extra whole-chip master MTD nodes. Such nodes
require their genuine live container rows; do not invent their names, omit
them from complete-inventory checks or permit them as write targets. No
partition is invented for the unused NOR tail.

Manufacturing is now resolved as `mfginfo`, NOR 0x3d0000, 64 KiB. Own ART is
256 KiB at 0x5d0000. ENV is 64 KiB at 0x6a0000. Both BOOTCONFIG records are
128 KiB at 0x60000/0x80000. `critical.tsv` captures only these five indispensable
own-device regions (640 KiB total), using the existing backup/upload API.
No kernel/root/bank/NAND/customer-config dump is an installer prerequisite.
PHY firmware is preserved unchanged and model/release assets are reused.

The actual OEM NOR `config` is 64 KiB at 0x6b0000. Converted OpenWrt exposes a
different tail mapping; never use this OEM profile against that source or erase
the whole converted config mapping. NVRAM and config remain protected because
the exact clean-defaults reset operation is not established here. The vendor
discovery script only sends a CLI `delete config` over SSH; it is not a physical
reset recipe and is not reused. No discovery/SSH/credential action occurred.

The shared vendor root actually contains ubiformat, ubiattach, ubidetach,
ubimkvol, ubirmvol, ubiupdatevol, ubirename, fw_printenv and fw_setenv. The direct
original Thor factory writer therefore has real tools in this release; a new
RAM carrier is not required merely on the assumption ubiformat is missing.
Reuse its existing protected inactive-bank procedure with fully local current
OpenWiFi payloads, exact source/profile validation and the published one-shot
boot contract. Its old generic lazy fetch/full-bank backup behavior must not
be inherited. No per-device raw bank is the reusable OEM restore payload.

The current OpenWiFi .8 image and actual kernel/root contents pins are now
resolved. The Thor preparation wrapper reuses the existing allocator and the
FORMAT2 wrapper reuses the existing stager; focused fixture results and their
limits are recorded in `../../tests/family-thor-writer-fields.md`.

The real reusable BDF map, own-vault binding/readback, full forward phase
composition, native mixed-bank confirmation and converted-to-OEM writer are
now implemented and fixture-tested. Exact local member names and result scope
are in `../../tests/family-thor-release-interface.md`. Unknown/resumed targets
remain refused. Physical qualification, actual installed first-normal-sysupgrade support
and an explicit OEM defaults/reset step remain separate; no AP readiness is
claimed.

The common owner fixed the named BOOTCONFIG allowance to accept the actual
131072-byte records. Use the updated shared helper with the exact source
profile; do not truncate records or invent smaller limits. No AP write, build
or reboot was performed, and no firmware or private capture is committed.

The shared backup plan binds BOOTCONFIG0 only to BOOTCONFIG and BOOTCONFIG1
only to BOOTCONFIG1, with or without the OEM `0:` prefix. Larger records,
swapped names and other partitions refuse.
