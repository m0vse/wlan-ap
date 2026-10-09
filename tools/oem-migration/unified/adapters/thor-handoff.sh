#!/bin/sh
# Loaded by .8's existing cambium-ab module glob from the staged overlay.
# One native bank and one retained OEM bank are not reported as converted.
ab_thor_takeover() {
    local oem state target
    oem=$(ab_getenv thor_migration_oem_slot) || oem=
    [ -n "$oem" ] || return 2
    case "$oem" in 0|1) ;; *) return 1 ;; esac
    ab_identity || return 1
    [ "$AB_FAMILY:$AB_MODEL" = thor:XV3-8 ] || return 1
    # A genuine later conversion belongs to the existing normal A/B guard.
    ab_converted && return 2
    state=$(ab_getenv thor_ab_state) || return 1
    target=$(ab_getenv thor_ab_target) || target=
    case "$state" in
        trial-started) [ "$AB_ACTIVE" != "$oem" ] && [ "$target" = "$AB_ACTIVE" ] || return 1; ab_guard ;;
        confirmed)
            [ "$AB_ACTIVE" != "$oem" ] && [ "$(ab_getenv thor_ab_confirmed)" = "$AB_ACTIVE" ] &&
                [ "$(ab_getenv bootcmd)" = "run thor_stable$AB_ACTIVE" ] || return 1
            ab_guard ;;
        *) return 1 ;;
    esac
}
