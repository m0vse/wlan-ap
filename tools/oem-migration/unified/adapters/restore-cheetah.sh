#!/bin/sh
# Adapter for the single shared restore entrypoint; no standalone launcher.
# No verified OEM payload/boot/reset writer exists in this source contract.
_cheetah_restore_unavailable() {
    printf '%s\n' 'Cheetah OEM restore lacks a qualified exact payload, protected write plan and OEM boot/reset handler; refusing before mutation.' >&2
    return 1
}
oem_restore_inspect() {
    OEM_SERIAL=
    OEM_SOURCE_RELEASE=
    OEM_SOURCE_SLOT=
    OEM_TARGET_SLOT=
    _cheetah_restore_unavailable
}
oem_restore_preflight() { _cheetah_restore_unavailable; }
oem_restore_recovery() { _cheetah_restore_unavailable; }
oem_restore_migrate() { _cheetah_restore_unavailable; }
oem_restore_boot_preflight() {
    OEM_BOOT_PRIOR_SLOT=
    OEM_BOOT_TARGET_SLOT=
    OEM_BOOT_MODE=
    OEM_BOOT_WATCHDOG=
    _cheetah_restore_unavailable
}
