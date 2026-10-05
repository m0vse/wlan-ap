#!/bin/sh
# Trusted-bundle functions; no AP code is sourced. Only five fixed targets.
bridge_items() {
 cat <<'ITEMS'
cambium-ab.sh /lib/functions/cambium-ab.sh
cambium-ab-upgrade.sh /lib/upgrade/cambium-ab.sh
cambium-ab-certificates.sh /lib/upgrade/cambium-ab-certificates.sh
modules/cambium-ab-cheetah.sh /lib/functions/cambium-ab-cheetah.sh
platform.sh /lib/upgrade/platform.sh
ITEMS
}
bridge_is_target() { bridge_items | awk -v p="$1" '$2==p { good=1 } END { exit !good }'; }
bridge_source_membership() {
 local root=$1 file path
 for file in "$root"/lib/*.sh "$root"/lib/functions/*.sh "$root"/lib/upgrade/*.sh; do
  [ -e "$file" ] || [ -L "$file" ] || continue
  [ -f "$file" ] && [ ! -L "$file" ] || return 1
  path=${file#"$root"}
  awk -v p="$path" '$0==p { good=1 } END { exit !good }' "$bundle/source-sets/required-paths" || return 1
 done
 # Include fixed closure entries outside the wildcard directories and targets
 # whose current state is replaced by the original during composite checking.
 while read -r path; do
  file=$root$path
  [ ! -L "$file" ] || return 1
  [ ! -e "$file" ] || [ -f "$file" ] || return 1
 done < "$bundle/source-sets/required-paths"
}
bridge_private_dir() {
 [ -d "$1" ] && [ ! -L "$1" ] && LC_ALL=C ls -ldn "$1" |
  awk '$1=="drwx------" && $3==0 { good=1 } END { exit !good }'
}
bridge_snapshot() {
 # The required file has already passed the canonical membership/path gate.
 local dest=$1 path live
 while read -r path; do
  live=$BRIDGE_ROOT$path
  [ ! -L "$live" ] || return 1
  if [ -e "$live" ]; then
   [ -f "$live" ] || return 1
   mkdir -p "$dest$(dirname "$path")" || return 1
   cp -p "$live" "$dest$path" || return 1
  fi
 done < "$bundle/source-sets/required-paths"
}
bridge_metadata() {
 local root=$1 src path file
 while read -r src path; do
  file=$root$path
  if [ -f "$file" ] && [ ! -L "$file" ]; then
   printf '%s ' "$path"
   LC_ALL=C ls -ldn "$file" | awk '{ print $1 " " $3 " " $4 }' || return 1
  else
   [ ! -e "$file" ] && [ ! -L "$file" ] || return 1
   printf '%s absent\n' "$path"
  fi
 done <<ITEMS
$(bridge_items)
ITEMS
}
bridge_approved_snapshot() {
 local set metadata
 [ -f "$BRIDGE_JOURNAL/source.set" ] && [ ! -L "$BRIDGE_JOURNAL/source.set" ] &&
  [ -f "$BRIDGE_JOURNAL/METADATA" ] && [ ! -L "$BRIDGE_JOURNAL/METADATA" ] || return 1
 bridge_private_dir "$BRIDGE_JOURNAL/original" || return 1
 metadata=$(bridge_metadata "$BRIDGE_JOURNAL/original") || return 1
 [ "$metadata" = "$(cat "$BRIDGE_JOURNAL/METADATA")" ] || return 1
 for set in "$bundle"/source-sets/outgoing-*.set "$bundle/source-sets/installed-bridge.set"; do
  if cmp -s "$set" "$BRIDGE_JOURNAL/source.set" &&
   ow_source_set_matches "$set" "$bundle/source-sets/required-paths" "$BRIDGE_JOURNAL/original"; then return 0; fi
 done
 return 1
}
bridge_recovery_preflight() {
 runtime_gate || return 1
 local path live original candidate=$BRIDGE_JOURNAL/recovery-check
 bridge_private_dir "$BRIDGE_JOURNAL" || return 1
 [ -f "$BRIDGE_JOURNAL/READY" ] && [ ! -L "$BRIDGE_JOURNAL/READY" ] &&
  [ -f "$BRIDGE_JOURNAL/STATE" ] && [ ! -L "$BRIDGE_JOURNAL/STATE" ] || return 1
 case "$(cat "$BRIDGE_JOURNAL/STATE")" in prepared|committed|restored) ;; *) return 1 ;; esac
 bridge_approved_snapshot || return 1
 # Reject unknown and unsafe live/original entries BEFORE any recovery write.
 bridge_source_membership "$BRIDGE_ROOT" || return 1
 bridge_source_membership "$BRIDGE_JOURNAL/original" || return 1
 # Only exact approved original or exact staged target states may be repaired.
 # Staged files are authenticated separately; no unknown live target overwrite.
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" "$BRIDGE_JOURNAL/staged" || return 1
 while read -r src path; do
  live=$BRIDGE_ROOT$path; original=$BRIDGE_JOURNAL/original$path
  if [ ! -e "$live" ] && [ ! -L "$live" ]; then
   [ ! -e "$original" ] && [ ! -L "$original" ] || return 1
  elif cmp -s "$live" "$original" && bridge_file_metadata_matches "$live" "$original"; then
   :
  else
   cmp -s "$live" "$BRIDGE_JOURNAL/staged$path" && bridge_file_metadata_matches "$live" "$BRIDGE_JOURNAL/staged$path" || return 1
  fi
 done <<ITEMS
$(bridge_items)
ITEMS
 rm -rf "$candidate" || return 1
 mkdir -m 700 "$candidate" || return 1
 while read -r path; do
  live=$BRIDGE_ROOT$path
  original=$BRIDGE_JOURNAL/original$path
  if bridge_is_target "$path"; then live=$original; fi
  [ ! -L "$live" ] || return 1
  if [ -e "$live" ]; then
   [ -f "$live" ] || return 1
   mkdir -p "$candidate$(dirname "$path")" || return 1
   cp -p "$live" "$candidate$path" || return 1
  fi
 done < "$bundle/source-sets/required-paths"
 ow_source_set_matches "$BRIDGE_JOURNAL/source.set" "$bundle/source-sets/required-paths" "$candidate"
}
bridge_file_metadata_matches() {
 local first second
 first=$(LC_ALL=C ls -ldn "$1" | awk '{ print $1 ":" $3 ":" $4 }') || return 1
 second=$(LC_ALL=C ls -ldn "$2" | awk '{ print $1 ":" $3 ":" $4 }') || return 1
 [ -n "$first" ] && [ "$first" = "$second" ]
}
bridge_restore() {
 local src path live original failed=0
 bridge_recovery_preflight || { echo 'Bridge recovery refused: unapproved originals or unrelated source drift' >&2; return 1; }
 while read -r src path; do
  live=$BRIDGE_ROOT$path
  original=$BRIDGE_JOURNAL/original$path
  if [ -f "$original" ]; then
   cp -p "$original" "$live.cheetah-restore" && mv -f "$live.cheetah-restore" "$live" &&
    bridge_file_metadata_matches "$original" "$live" || failed=1
  else
   rm -f "$live" || failed=1
  fi
  rm -f "$live.cheetah-new" "$live.cheetah-restore" || failed=1
 done <<ITEMS
$(bridge_items)
ITEMS
 sync
 [ "$failed" = 0 ] && ow_source_set_matches "$BRIDGE_JOURNAL/source.set" "$bundle/source-sets/required-paths" "$BRIDGE_ROOT" || return 1
 printf '%s\n' restored > "$BRIDGE_JOURNAL/STATE"
}
bridge_archive_journal() {
 local receipt
 receipt=$(mktemp -d "$BRIDGE_ROOT/root/cheetah-upgrader-backup-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX") || return 1
 mv "$BRIDGE_JOURNAL" "$receipt/transaction" || { rmdir "$receipt"; return 1; }
 echo "Bridge transaction receipt: $receipt/transaction"
}
bridge_recover_pending() {
 local pid boot
 [ -e "$BRIDGE_JOURNAL" ] || [ -L "$BRIDGE_JOURNAL" ] || return 0
 bridge_private_dir "$BRIDGE_JOURNAL" || return 1
 # An initializing transaction is busy, never a candidate for deletion.
 [ -f "$BRIDGE_JOURNAL/PID" ] && [ ! -L "$BRIDGE_JOURNAL/PID" ] &&
  [ -f "$BRIDGE_JOURNAL/BOOT" ] && [ ! -L "$BRIDGE_JOURNAL/BOOT" ] || return 1
 if :; then
  pid=$(cat "$BRIDGE_JOURNAL/PID"); boot=$(cat "$BRIDGE_JOURNAL/BOOT")
  case "$pid" in ''|*[!0-9]*) return 1 ;; esac
  if [ "$boot" = "$(cat /proc/sys/kernel/random/boot_id)" ] && kill -0 "$pid" 2>/dev/null; then
   echo 'Another bridge transaction is still running' >&2; return 1
  fi
 fi
 if [ ! -f "$BRIDGE_JOURNAL/READY" ]; then
  # No target writes precede READY. Do not discard an unknown/mixed live set.
  implementation_gate || return 1
  rm -rf "$BRIDGE_JOURNAL" || return 1
  return 0
 fi
 bridge_restore && bridge_archive_journal
}
bridge_exit() {
 local status=$?
 trap - EXIT HUP INT TERM
 if [ "${BRIDGE_ACTIVE:-0}" = 1 ]; then
  if bridge_restore; then
   bridge_archive_journal || echo "Restored source; retained recovery journal: $BRIDGE_JOURNAL" >&2
  else
   echo "Recovery incomplete; no flash permitted; retained journal: $BRIDGE_JOURNAL" >&2
   status=1
  fi
 fi
 exit "$status"
}
bridge_install() {
 release_gate && runtime_gate || return 1
 local src path stage live
 mkdir -m 700 "$BRIDGE_JOURNAL" || return 1
 BRIDGE_ACTIVE=0
 trap bridge_exit EXIT
 trap 'exit 130' HUP INT TERM
 printf '%s\n' "$$" > "$BRIDGE_JOURNAL/PID"
 cat /proc/sys/kernel/random/boot_id > "$BRIDGE_JOURNAL/BOOT"
 cp "$MATCHED_SOURCE_SET" "$BRIDGE_JOURNAL/source.set" || return 1
 mkdir -m 700 "$BRIDGE_JOURNAL/original" "$BRIDGE_JOURNAL/staged" || return 1
 bridge_snapshot "$BRIDGE_JOURNAL/original" || return 1
 bridge_metadata "$BRIDGE_ROOT" > "$BRIDGE_JOURNAL/METADATA" || return 1
 bridge_metadata "$BRIDGE_JOURNAL/original" > "$BRIDGE_JOURNAL/metadata-check" || return 1
 cmp -s "$BRIDGE_JOURNAL/METADATA" "$BRIDGE_JOURNAL/metadata-check" || return 1
 ow_source_set_matches "$MATCHED_SOURCE_SET" "$bundle/source-sets/required-paths" "$BRIDGE_JOURNAL/original" || return 1
 bridge_snapshot "$BRIDGE_JOURNAL/staged" || return 1
 while read -r src path; do
  stage=$BRIDGE_JOURNAL/staged$path
  mkdir -p "$(dirname "$stage")" || return 1
  rm -f "$stage" || return 1
  cp "$bundle/$src" "$stage" && chmod 644 "$stage" && cmp -s "$bundle/$src" "$stage" || return 1
 done <<ITEMS
$(bridge_items)
ITEMS
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" "$BRIDGE_JOURNAL/staged" || return 1
 printf '%s\n' prepared > "$BRIDGE_JOURNAL/STATE"
 : > "$BRIDGE_JOURNAL/READY"
 sync
 BRIDGE_ACTIVE=1
 while read -r src path; do
  live=$BRIDGE_ROOT$path
  cp "$BRIDGE_JOURNAL/staged$path" "$live.cheetah-new" && chmod 644 "$live.cheetah-new" &&
   cmp -s "$BRIDGE_JOURNAL/staged$path" "$live.cheetah-new" && mv -f "$live.cheetah-new" "$live" || return 1
 done <<ITEMS
$(bridge_items)
ITEMS
 ow_source_set_matches "$bundle/source-sets/installed-bridge.set" "$bundle/source-sets/required-paths" "$BRIDGE_ROOT" || return 1
 sync
 printf '%s\n' committed > "$BRIDGE_JOURNAL/STATE"
 bridge_archive_journal || return 1
 BRIDGE_ACTIVE=0
 trap - EXIT HUP INT TERM
}
