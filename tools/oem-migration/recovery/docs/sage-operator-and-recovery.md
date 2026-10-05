# Sage operator migration and emergency OEM recovery

These sources belong to OpenWiFi (`wlan-ap`). All production model entries remain disabled until exact source, model, artifact and hardware qualification is complete. Known unsupported models stop before device changes. There is no trial exemption. Stock OpenWrt migration remains maintained separately in `tools/stock-migration`.

## Operator source freeze

`prepare-sage-operator.py OEM_ROOT REVIEWED_ROOT_TAR NEW_OUTPUT --model E410 --image-sha256 IMAGE_SHA --kernel-sha256 KERNEL_SHA --root-sha256 ROOT_SHA` freezes the independently reviewed Sage 4.2.3.3-r10 root, implementation, runtime dependency closure and exact model. The reviewed TAR digest is fixed in the generator. Candidate digests are required explicit inputs. Output has no firmware, installable checksum seal or model qualification override.

After independent qualification and publication, verify the launcher itself before execution. Its `--check BUNDLE_SHA256` and `--install BUNDLE_SHA256 PAYLOAD_DIR SETTINGS_DIR RECOVERY_DIR RECEIPT IMAGE_SHA KERNEL_SHA ROOT_SHA` interfaces require an independently published digest of the bundle SHA256SUMS. The launcher checks this digest and the bundle before sourcing helpers. Installation also checks the three candidate pins, complete frozen source runtime and exact factory identity.

The recovery directory contains this AP’s own 64 KiB ENV, ART and MFG captures and checksum manifest. Copy it off-device and verify all checksums before placing a private receipt containing the SHA256 digest of its SHA256SUMS file on the AP. A missing receipt prevents firmware writes. Shared clean OEM kernel/root assets are held once per qualified exact model/variant. No donor environment or bootloader is restored.

The outgoing source stages protected FORMAT2 settings, writes and independently reads back the inactive candidate, then arms the existing one-shot contract. Incoming OpenWiFi performs native enrollment and confirmation after authenticated connection and applied configuration. Source enrollment and private-key generation are absent.

## Emergency factory reset and boot defaults

The bounded recovery libraries validate the own-device recovery receipt, independent OEM artifact pins, source bank, partition geometry, pending-state absence and source boot command pin before writing an inactive OEM bank. They erase only the exact 64 KiB NOR config partition and truncate only the shared NVRAM volume, verify both are entirely erased, and then arm the existing recoverable one-shot boot. Calibration, manufacturing data, bootloader, source bank and native certificate volume are protected. These libraries are not standalone deployment commands.

After independently verified OEM boot, factory-reset behavior and management access, the defaults adapter restores the compiled defaults of the independently retained E410-A/EU bootloader (SHA256 `066bfcc317291b23e44bd42f1d10c4d08ca82ded6ca05abd15f5da280ae4dba1`). These include `bootcmd=bootipq`, `bootdelay=2`, baud rate 115200, IP 192.168.1.11, server IP 192.168.1.120, the actual OEM bank and bootcount zero. It removes only reviewed migration overrides and checks that every unlisted factory/custom environment entry remains unchanged. E410B defaults are unqualified. No recovery helper reboots automatically.

## Qualification and physical blocker

The generator has run successfully against the retained authenticated OEM root on cnbeacon. Source fixtures exercise admission, checksum/receipt refusal, inactive-write/reset/arm ordering, interruption and readback failures, compiled defaults and preservation of device identity. These are source checks, not physical recovery proof.

The named pilot at 192.168.99.196 has a read-only NOR config partition (MTD flags `0x800`, without writeable `0x400`). Its 64 KiB content SHA256 is `1a380579973691d013803bfe1a5c0a0af1b1039ad8684462d47f1ebd31bd1fa3`, different from erased SHA256 `71189f7fb6aed638640078fba3a35fda6c39c8962e74dcc75935aac948da9063`. Complete factory reset therefore cannot proceed in its current kernel. The adapter refuses before candidate writes.

The smallest proposed separate recovery artifact is a RAM-only E410-A/EU profile using the existing hardware/FIT definition, removing read-only only from `partition@1a0000` (label config, 64 KiB). Normal Sage DTS permissions must remain unchanged. All boot code, ART, MFG and other factory NOR stay protected; ENV retains only its existing explicit mapping. The historical E410 recovery DTS also leaves config read-only and does not solve this blocker.

A narrow RAM phase could clear and verify only NOR, then return to the unchanged working OpenWiFi source for the remaining transaction. That requires an explicitly qualified phase/source-bank proof and already-empty-NOR mode; neither is implemented or admitted here. Building this dedicated artifact and physically booting the pilot require separate release. No live permission bypass has been attempted.

Other families remain blocked by their exact model/source/recovery qualification. Cheetah/Gambit additionally lack an independently verified matching vendor signer. No all-platform OEM recovery claim is made.
