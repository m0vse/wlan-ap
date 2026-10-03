#!/bin/sh
# Pure outgoing-source gate. Source this only from an operator-approved bundle.
# A set is a COMPLETE reviewed tuple, not a mix-and-match list of file hashes.
# Format: SHA256 SPACE absolute-path; '-' records an expected absent file.
# required-paths contains one absolute path per line. No device writes occur.
ow_source_set_matches() (
    set_file=$1
    required_file=$2
    source_root=${3:-}
    [ -f "$set_file" ] && [ ! -L "$set_file" ] || exit 1
    [ -f "$required_file" ] && [ ! -L "$required_file" ] || exit 1
    case "$source_root" in ''|/*) ;; *) exit 1 ;; esac
    # Validate exact membership BEFORE reading any AP file. Reject duplicates,
    # unsafe paths and malformed hashes, including empty manifests.
    LC_ALL=C awk '
      function safe(p) {
        return p ~ /^\/[A-Za-z0-9_.\/-]+$/ && p !~ /(^|\/)\.\.?($|\/)/ && p !~ /\/\//
      }
      NR==FNR {
        if (NF!=1 || !safe($1) || required[$1]++) bad=1
        total++; next
      }
      {
        if (NF!=2 || !safe($2) || !($2 in required) || seen[$2]++) bad=1
        if ($1!="-" && (length($1)!=64 || $1 ~ /[^0-9a-f]/)) bad=1
        count++
      }
      END { exit (bad || total==0 || count!=total) }
    ' "$required_file" "$set_file" || exit 1
    while read -r digest path; do
        candidate=$source_root$path
        if [ "$digest" = - ]; then
            [ ! -e "$candidate" ] && [ ! -L "$candidate" ] || exit 1
        else
            [ -f "$candidate" ] && [ ! -L "$candidate" ] || exit 1
            actual=$(sha256sum < "$candidate") || exit 1
            [ "${actual%% *}" = "$digest" ] || exit 1
        fi
    done < "$set_file"
)

# Reject every additional script loaded by stage2 or retained in the RAM root.
# The optional root is solely for offline fixture tests, never live approval.
ow_source_wildcards_known() (
 required_file=$1
 source_root=${2:-}
 for candidate in "$source_root"/lib/*.sh "$source_root"/lib/functions/*.sh "$source_root"/lib/upgrade/*.sh; do
  [ -e "$candidate" ] || [ -L "$candidate" ] || continue
  path=${candidate#"$source_root"}
  grep -Fxq "$path" "$required_file" || exit 1
 done
)
