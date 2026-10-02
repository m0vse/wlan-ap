#!/bin/sh
# Manual migration of qualified converted OpenWrt XV2-2/XV2-2T1 devices.
# Default --check has no flash writes. Phil controls --install execution.
set -eu
mode=${1:---check}
case "$mode" in --check|--install) ;; *) echo 'Usage: jaguar-sysinstall.sh --check|--install' >&2; exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image_name=$(cat "$here/IMAGE")
case "$image_name" in ''|*/*|*..*) echo 'Invalid bundled image name' >&2; exit 1 ;; esac
image=$here/$image_name
(cd "$here" && sha256sum -c SHA256SUMS)
if [ "$mode" = --install ]; then
 # Explicit installation permits recovery of our own approved pending journal.
 sh "$here/prepare-upgrader.sh" --recover "$image"
fi
sh "$here/prepare-upgrader.sh" --check "$image"
[ "$mode" = --install ] || exit 0

# Stock migration deliberately discards configuration. The qualified A/B
# helper protects the board-data vault and certificate identity separately;
# an ordinary config archive must not reintroduce the outgoing configuration.

# Update only the outgoing updater files, verify every byte, then run the
# normal platform/metadata preflight with the corrected stage2 policy.
sh "$here/prepare-upgrader.sh" --install "$image"
sh "$here/prepare-upgrader.sh" --verify-installed "$image"
sysupgrade -n -T "$image"
echo 'Starting operator-authorized A/B trial; running bank remains the rollback bank.'
sysupgrade -v -n "$image"
