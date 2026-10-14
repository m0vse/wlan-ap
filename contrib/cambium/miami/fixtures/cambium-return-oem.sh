#!/bin/sh
# Read-only retained OEM check, or a reviewed one-shot return. No implicit reboot.
set -e
. /lib/functions/system.sh
. /lib/functions/cambium-ab.sh
[ "$#" = 1 ] || { echo 'usage: cambium-return-oem --check|--arm' >&2; exit 2; }
case "$1" in --check|--arm) ;; *) echo 'usage: cambium-return-oem --check|--arm' >&2; exit 2 ;; esac
ab_identity >/dev/null || exit 1
! ab_converted || { echo 'OEM return unavailable after bank conversion' >&2; exit 1; }
ab_hook oem_return_ready && "ab_${AB_FAMILY}_oem_return_ready" || exit 1
[ "$1" != --check ] || { echo 'Retained OEM mapping verified; no return boot armed.'; exit 0; }
# The family hook must preserve and save the exact current OpenWiFi source
# before loading OEM once. Its absence never permits a permanent bootipq flip.
ab_hook oem_return_trial_ready && ab_hook oem_return_arm_trial || {
 echo 'Retained OEM one-shot return unavailable; no guard or boot state changed.' >&2
 exit 1
}
"ab_${AB_FAMILY}_oem_return_trial_ready" || exit 1
"ab_${AB_FAMILY}_oem_return_arm_trial" || exit 1
echo 'Retained OEM one-shot armed. Reboot manually; OEM needs separate verified confirmation.'
