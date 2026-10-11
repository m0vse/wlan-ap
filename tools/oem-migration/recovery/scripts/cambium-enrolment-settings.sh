#!/bin/sh
# Shared local preparation only; the family installer owns admission and arm.
set +x
umask 077
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$here/lib/cambium-installer-settings.sh" || exit 1
binding= est= gateway= key= output=
while [ "$#" -gt 0 ]; do
    [ "$#" -ge 2 ] || { ow_settings_fail; exit 1; }
    case "$1" in
        --binding) [ -z "$binding" ] || exit 1; binding=$2 ;;
        --est) [ -z "$est" ] || exit 1; est=$2 ;;
        --gateway) [ -z "$gateway" ] || exit 1; gateway=$2 ;;
        --enrolment-key) [ -z "$key" ] || exit 1; key=$2 ;;
        --output) [ -z "$output" ] || exit 1; output=$2 ;;
        *) ow_settings_fail; exit 1 ;;
    esac
    shift 2
done
[ -n "$binding" ] && [ -n "$est" ] && [ -n "$gateway" ] &&
    [ -n "$key" ] && [ -n "$output" ] || { ow_settings_fail; exit 1; }
ow_settings_prepare "$binding" "$est" "$gateway" "$key" "$output" || {
    key=
    ow_settings_fail
    exit 1
}
key=
printf 'Protected native enrolment settings prepared; no installation or boot armed.\n'
