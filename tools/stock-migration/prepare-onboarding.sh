#!/bin/sh
# Shared Sage operator helper: consume environment key without forwarding it.
set +x
set +a
umask 077
unset key credential expected actual
key=${OPENWIFI_ONBOARD_KEY:-}
unset OPENWIFI_ONBOARD_KEY
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
bundle=${here%/*}
image_name=$(cat "$bundle/IMAGE") || exit 1
case "$image_name" in ''|*/*|*..*) exit 1 ;; esac
image=$bundle/$image_name
context=$(mktemp -d /tmp/sage-onboarding-context.XXXXXX) || exit 1
trap 'rm -f "$context/binding.tsv"; rmdir "$context"' EXIT
trap 'exit 1' HUP INT TERM
# This authenticates the bundle, outgoing runtime/source, live identity/slots,
# storage and candidate before we load any preparation library or accept a key.
sh "$bundle/prepare-upgrader.sh" --context "$image" "$context/binding.tsv" || exit 1
. "$here/../cambium-installer-settings.sh" || exit 1
dest=/root/.cambium-installer-input
ow_settings_binding "$context/binding.tsv" || exit 1
OW_EXPECT_SERIAL=$OW_SERIAL OW_EXPECT_FAMILY=$OW_FAMILY OW_EXPECT_MODEL=$OW_MODEL
OW_EXPECT_SOURCE=$OW_SOURCE OW_EXPECT_TARGET=$OW_TARGET
OW_EXPECT_OPERATION=$OW_OPERATION OW_EXPECT_RELEASE=$OW_RELEASE
OW_EXPECT_CONTRACT=$OW_CONTRACT
OW_STAGE_ADMISSION=qualified
if [ -e "$dest" ] || [ -L "$dest" ]; then
    ow_settings_tree "$dest" || exit 1
    # Preserve the original job on an unchanged, not-yet-started transaction.
    OW_EXPECT_JOB=$OW_JOB
    ow_settings_context "$image" || {
        echo 'Existing settings have a different context; retained unchanged.' >&2
        exit 1
    }
    for name in est.json gateway.json; do
        cmp -s "$here/$name" "$dest/$name" || {
            echo 'Existing settings have a different context; retained unchanged.' >&2
            exit 1
        }
    done
    if [ -n "$key" ]; then
        expected=$(printf 'user = "%s:%s"\n' "$OW_SERIAL" "$key")
        actual=$(cat "$dest/est-bootstrap.conf")
        [ "$expected" = "$actual" ] || {
            echo 'Existing settings use a different key; retained unchanged.' >&2
            exit 1
        }
    fi
    key= expected= actual=
    echo 'Existing onboarding settings verified and retained.'
    exit 0
fi
[ -n "$key" ] || {
    echo 'Set OPENWIFI_ONBOARD_KEY in this shell first.' >&2
    exit 1
}
ow_settings_prepare "$context/binding.tsv" "$here/est.json" "$here/gateway.json" "$key" "$dest"
result=$?
key=
[ "$result" = 0 ] || exit "$result"
echo 'Onboarding settings ready; no upgrade started.'
