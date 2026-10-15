#!/bin/sh
# Public pilot operator helper: consume environment key without forwarding it.
set +x
set +a
umask 077
unset key credential expected actual
key=${OPENWIFI_ONBOARD_KEY:-}
unset OPENWIFI_ONBOARD_KEY
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$here/../cambium-installer-settings.sh" || exit 1
dest=/root/.cambium-installer-input
ow_settings_binding "$here/binding.tsv" || exit 1
if [ -e "$dest" ] || [ -L "$dest" ]; then
    ow_settings_tree "$dest" || exit 1
    for name in binding.tsv est.json gateway.json; do
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
ow_settings_prepare "$here/binding.tsv" "$here/est.json" "$here/gateway.json" "$key" "$dest"
result=$?
key=
[ "$result" = 0 ] || exit "$result"
echo 'Onboarding settings ready; no upgrade started.'
