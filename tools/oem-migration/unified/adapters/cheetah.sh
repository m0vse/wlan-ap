#!/bin/sh
# Cheetah adapter for the single shared OEM installer.
# Converted-stock FORMAT2 tests qualify a different outgoing operation.
# The retained OEM reference writes an additional OpenWrt UBI volume using
# fixed device indices; it is not a production exact-model OEM writer.
# Do not turn either reference into admission for persistent migration.

_cheetah_oem_unavailable() {
    case "${OEM_MODEL:-}" in
        XV2-21X)
            printf '%s\n' 'XV2-21X OEM migration is unavailable: exact OEM write/readback, protected-range and boot-preservation handler is not qualified.' >&2
            ;;
        XV2-22H|XV2-23T)
            printf '%s\n' 'This Cheetah model has no qualified exact OEM layout, asset and boot adapter.' >&2
            ;;
        *)
            printf '%s\n' 'Unknown or mismatched Cheetah model; refusing OEM migration.' >&2
            ;;
    esac
    return 1
}

oem_adapter_inspect() {
    # Failed inspection must not leave inherited identity or slot context.
    OEM_SERIAL=
    OEM_SOURCE_RELEASE=
    OEM_SOURCE_SLOT=
    OEM_TARGET_SLOT=
    _cheetah_oem_unavailable
}

oem_adapter_preflight() { _cheetah_oem_unavailable; }
oem_adapter_recovery() { _cheetah_oem_unavailable; }
oem_adapter_migrate() { _cheetah_oem_unavailable; }
