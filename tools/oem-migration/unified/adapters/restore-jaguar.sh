#!/bin/sh
# Source-preserving OEM-return inspection. An OpenWiFi factory image is not an
# OEM restore payload; exact extracted OEM kernel/UBIFS and boot mapping needed.
oem_restore_jaguar_unavailable() {
 case "${OEM_MODEL:-}:${OEM_SKU:-}" in
  XV2-2:00000014|XV2-2T1:0000001f|XE3-4:00000020)
   oem_fail "$OEM_MODEL: exact extracted OEM image/volume/defaults tuple is not yet source-closed; retained OpenWiFi bank and factory data remain untouched";;
  *) oem_fail 'this Jaguar model/SKU has no OEM-return mapping';;
 esac
}
oem_restore_inspect() {
 OEM_SERIAL= OEM_SOURCE_RELEASE= OEM_SOURCE_SLOT= OEM_TARGET_SLOT=
 oem_restore_jaguar_unavailable
}
oem_restore_preflight() { oem_restore_jaguar_unavailable; }
oem_restore_boot_preflight() { oem_restore_jaguar_unavailable; }
oem_restore_recovery() { oem_restore_jaguar_unavailable; }
oem_restore_migrate() { oem_restore_jaguar_unavailable; }
