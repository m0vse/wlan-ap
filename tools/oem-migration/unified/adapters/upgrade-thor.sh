#!/bin/sh
# Observe installed support, never substitute the publisher's runtime cache.
oem_upgrade_inspect() {
    local thor_root=${OEM_SYS_ROOT:-} thor_file thor_expected thor_actual thor_release thor_prior
    OEM_UPGRADE_STATUS=unsupported OEM_UPGRADE_REASON=installed-family-hook-unavailable
    [ "${OEM_FAMILY:-}:${OEM_MODEL:-}:${OEM_SKU:-}" = thor:XV3-8:00000013 ] || return 1
    thor_release=$(sed -n "s/^DISTRIB_TIP_VERSION='\([^']*\)'$/\1/p" "$thor_root/etc/openwrt_release") || return 1
    [ "$thor_release" = "${OEM_SUPPORTED_RELEASE:-}" ] && [ "$thor_release" = thor-2026.10.05.8 ] || return 1
    for thor_file in "$thor_root/lib/functions/system.sh" "$thor_root/lib/functions/cambium-ab.sh"; do
        [ -f "$thor_file" ] && [ ! -L "$thor_file" ] || return 1
        . "$thor_file" || return 1
    done
    ab_identity && [ "$AB_FAMILY:$AB_MODEL" = thor:XV3-8 ] || return 1
    case "$AB_ACTIVE:$AB_TARGET" in 0:1|1:0) ;; *) return 1 ;; esac
    [ "$(ab_getenv thor_ab_confirmed)" = "$AB_ACTIVE" ] &&
        [ "$(ab_getenv thor_ab_state)" = confirmed ] || { OEM_UPGRADE_REASON=native-trial-not-confirmed;return 0; }
    [ -z "$(ab_getenv thor_installer_target)$(ab_getenv thor_installer_job)$(ab_getenv thor_installer_image)" ] || { OEM_UPGRADE_REASON=native-onboarding-pending;return 0; }
    if ! ab_converted; then
        OEM_UPGRADE_STATUS=onboarded OEM_UPGRADE_REASON=actual-native-conversion-required
        return 0
    fi
    thor_actual=$(ab_trial_command "$AB_ACTIVE" "$AB_TARGET") || return 1
    thor_expected="setenv bootcmd run thor_boot$AB_ACTIVE && setenv image $AB_ACTIVE && setenv thor_ab_state trial-started && saveenv && run thor_boot$AB_TARGET; run thor_boot$AB_ACTIVE"
    [ "$thor_actual" = "$thor_expected" ] || { OEM_UPGRADE_REASON=installed-trial-command-not-prior-only;return 0; }
    thor_file=$thor_root/lib/upgrade/cambium-ab.sh
    [ -f "$thor_file" ] && [ ! -L "$thor_file" ] || { OEM_UPGRADE_REASON=installed-upgrade-helper-unavailable;return 0; }
    CAMBIUM_AB_LIB=$thor_root/lib/functions/cambium-ab.sh
    CAMBIUM_AB_CERTIFICATE_LIB=$thor_root/lib/upgrade/cambium-ab-certificates.sh
    . "$thor_file" || return 1
    command -v ab_persist_prior_boot >/dev/null 2>&1 || { OEM_UPGRADE_REASON=installed-source-persistence-hook-unavailable;return 0; }
    thor_expected=$(ab_thor_boot_command "$AB_ACTIVE") || return 1
    case "$thor_expected" in 'aq_load_fw; '*) thor_expected="aq_load_fw && ${thor_expected#aq_load_fw; }" ;; esac
    thor_prior=$(ab_getenv "thor_boot$AB_ACTIVE") || return 1
    [ "$thor_prior" = "$thor_expected" ] || [ "$thor_prior" = "aq_load_fw; ${thor_expected#aq_load_fw && }" ] || { OEM_UPGRADE_REASON=stored-source-routing-unqualified;return 0; }
    ab_upgrade_preflight || { OEM_UPGRADE_REASON=installed-upgrade-preflight-refused;return 0; }
    [ "$AB_VAULT" != 1 ] || "$thor_root/usr/sbin/cambium-board-data" --check-vault || { OEM_UPGRADE_REASON=own-vault-unverified;return 0; }
    OEM_UPGRADE_STATUS=ready OEM_UPGRADE_REASON=installed-native-upgrade-preflight-passed
}
