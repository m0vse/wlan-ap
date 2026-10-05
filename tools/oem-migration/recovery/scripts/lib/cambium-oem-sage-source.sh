#!/bin/sh
# Concrete read-only source/pending callbacks for the sealed OEM Sage runner.
# COS_READERS_DIR is the authenticated sibling script directory, not settings.
cos_source_check() {
    local context serial family model source index
    [ -n "${COS_READERS_DIR:-}" ] && [ -d "$COS_READERS_DIR" ] || return 1
    context=$(sh "$COS_READERS_DIR/cambium-oem-sage-context.sh" check) || return 1
    [ "$(printf '%s\n' "$context" | wc -l)" -eq 1 ] || return 1
    # Empty trailing pending fields are intentionally allowed for a fresh job.
    serial=$(printf '%s\n' "$context" | cut -f1)
    family=$(printf '%s\n' "$context" | cut -f2)
    model=$(printf '%s\n' "$context" | cut -f3)
    source=$(printf '%s\n' "$context" | cut -f4)
    [ "$serial" = "$OW_EXPECT_SERIAL" ] && [ "$family" = sage ] &&
    [ "$model" = "$OW_EXPECT_MODEL" ] && [ "$source" = "$OW_EXPECT_SOURCE" ] || return 1
    index=$(awk '$4=="\"fs\"" {sub(/mtd/,"",$1);sub(/:/,"",$1);v=$1;n++} END {if(n!=1)exit 1;print v}' /proc/mtd) || return 1
    [ "$index" = "$CSP_FS_MTD" ] || return 1
    # The reader has verified all competing configs against named APPSBLENV.
    # Reuse its exact existing mapping; never create a guessed configuration.
    COS_ENV_CONFIG=/etc/fw_env.config
    [ -r "$COS_ENV_CONFIG" ] || COS_ENV_CONFIG=/tmp/fw_env.config
    [ -r "$COS_ENV_CONFIG" ] && [ ! -L "$COS_ENV_CONFIG" ]
}
cos_refuse_pending() {
    local snapshot
    [ -n "${COS_ENV_CONFIG:-}" ] || return 1
    # Per-key absence can hide an unreadable ENV. Require a complete successful
    # read and inspect only exact installer keys; never print the ENV contents.
    snapshot=$(fw_printenv -c "$COS_ENV_CONFIG" 2>/dev/null) || return 1
    printf '%s\n' "$snapshot" | awk -F '=' '
        $1=="sage_installer_target" || $1=="sage_installer_job" || $1=="sage_installer_image" {
            if(seen[$1]++ || NF!=2 || length($2))bad=1
        }
        END {exit bad}'
}
