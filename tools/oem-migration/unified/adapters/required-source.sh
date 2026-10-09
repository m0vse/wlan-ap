#!/bin/sh
# Family admission checks, not an ELF/libc implementation admission gate.
# The full authenticated ledger remains publisher evidence. On-device checks
# retain the exact source release and reviewed boot/updater/identity shell hooks.
oem_required_source_check() (
 ledger=$1; source_root=$2; release_path=$3; shift 3
 [ -f "$ledger" ] && [ ! -L "$ledger" ] || exit 1
 case "$release_path" in /etc/version|/etc/openwrt_release) ;; *) exit 1;; esac
 # Commands are those used by this phase, not every executable in the ledger.
 for tool do
  command -v "$tool" >/dev/null 2>&1 || {
   echo "Required native command unavailable: $tool" >&2; exit 1;
  }
 done
 awk -v release="$release_path" '
  $3==release {if($1!="F" || length($2)!=64 || $2~/[^0-9a-f]/)bad=1;n++}
  END{exit bad || n!=1}' "$ledger" || exit 1
 while read -r kind expected path; do
  case "$path" in
   /etc/version|/etc/openwrt_release|/lib/functions.sh|/lib/functions/system.sh|/lib/config/uci.sh|/usr/share/libubox/jshn.sh|/lib/functions/cambium-ab.sh|/lib/functions/cambium-ab-sage.sh|/lib/functions/cambium-ab-jaguar.sh|/lib/functions/cambium-sage.sh|/usr/sbin/cambium-ab-status|/lib/upgrade/platform.sh|/lib/upgrade/stage2|/lib/upgrade/cambium-ab.sh|/lib/upgrade/cambium-ab-certificates.sh) ;;
   *) continue;;
  esac
  candidate=$source_root$path
  case "$kind" in
   F|X)
    [ "${#expected}" = 64 ] || exit 1
    case "$expected" in *[!0-9a-f]*) exit 1;; esac
    [ -f "$candidate" ] && [ ! -L "$candidate" ] && [ -r "$candidate" ] || exit 1
    [ "$kind" != X ] || [ -x "$candidate" ] || exit 1
    actual=$(sha256sum < "$candidate") || exit 1
    [ "${actual%% *}" = "$expected" ] || {
     echo "Required source release/boot/updater hook changed: $path" >&2; exit 1;
    };;
   L) [ -L "$candidate" ] && [ "$(readlink "$candidate")" = "$expected" ] || exit 1;;
   A) [ ! -e "$candidate" ] && [ ! -L "$candidate" ] || exit 1;;
   *) exit 1;;
  esac
 done < "$ledger"
)
