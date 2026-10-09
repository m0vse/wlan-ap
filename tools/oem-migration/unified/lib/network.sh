#!/bin/sh
# Bounded local staging only. No firmware/device writes, no enrollment secret.
# Conservative aggregate budget: reserve an entire attempt before starting it.
oem_stage_space_check() (
 directory=$1 bytes=$2
 case "$bytes" in ''|*[!0-9]*) return 1;; esac
 oem_private_directory "$directory" || return 1
 available=$(df -Pk "$directory" | awk 'NR==2 && $4~/^[0-9]+$/{print $4;good=1}END{if(!good)exit 1}') || return 1
 [ "$available" -ge "$(((bytes+1023)/1024))" ] || {
  oem_fail 'insufficient space for the actual local staging plan';return 1
 }
)

# A validated existing cache consumes space already counted by df. Anything
# else needs its full bounded object size, and an unsafe existing path refuses.
oem_stage_missing_bytes() (
 output=$1 expected=$2 size=$3
 oem_hex64 "$expected" || return 1
 case "$size" in ''|*[!0-9]*) return 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 268435456 ] || return 1
 if [ -e "$output" ] || [ -L "$output" ]; then
  oem_private_file "$output" && [ "$(wc -c < "$output")" -eq "$size" ] &&
   [ "$(oem_sha "$output")" = "$expected" ] || return 1
  printf '0\n'
 else
  printf '%s\n' "$size"
 fi
)

oem_pid_stamp() {
 [ -r "/proc/$1/stat" ] || return 1
 awk '{print $22}' "/proc/$1/stat"
}
oem_kill_owned_tree() (
 pid=$1 stamp=$2
 [ "$(oem_pid_stamp "$pid" 2>/dev/null || true)" = "$stamp" ] || return 0
 if [ -r "/proc/$pid/task/$pid/children" ]; then
  children=$(cat "/proc/$pid/task/$pid/children")
  for child in $children; do
   childstamp=$(oem_pid_stamp "$child" 2>/dev/null || true)
   [ -z "$childstamp" ] || oem_kill_owned_tree "$child" "$childstamp"
  done
 fi
 [ "$(oem_pid_stamp "$pid" 2>/dev/null || true)" != "$stamp" ] || kill -KILL "$pid" 2>/dev/null || true
)
oem_bounded_run() {
 budget=$1;shift
 case "$budget" in ''|*[!0-9]*) return 1;; esac
 [ "$budget" -ge 1 ] && [ "$budget" -le 60 ] || return 1
 [ -r /proc/self/stat ] || return 1
 "$@" &
 worker=$!
 stamp=$(oem_pid_stamp "$worker" 2>/dev/null || true)
 (
  sleep "$budget"
  [ -z "$stamp" ] || oem_kill_owned_tree "$worker" "$stamp"
 ) &
 timer=$!
 status=0;wait "$worker" || status=$?
 kill "$timer" 2>/dev/null || true
 wait "$timer" 2>/dev/null || true
 return "$status"
}
oem_fetch_local() {
 name=$1 expected=$2 size=$3 output=$4
 oem_hex64 "$expected" && oem_token "$name" || return 1
 case "$size" in ''|*[!0-9]*) return 1;; esac
 [ "$size" -gt 0 ] && [ "$size" -le 268435456 ] || return 1
 directory=$(dirname "$output")
 oem_private_directory "$directory" || return 1
 [ ! -L "$output" ] && [ ! -L "$output.part" ] || return 1
 if oem_private_file "$output" && [ "$(wc -c < "$output")" -eq "$size" ] && [ "$(oem_sha "$output")" = "$expected" ]; then return 0;fi
 # Keep at most a bounded partial regular file; never overwrite known data.
 [ ! -e "$output" ] && [ ! -e "$output.part" ] || return 1
 extra=${OEM_STAGE_EXTRA_BYTES:-0}
 case "$extra" in ''|*[!0-9]*) return 1;; esac
 oem_stage_space_check "$directory" "$((size+extra))" || return 1
 attempt=0
 while [ "$attempt" -lt 2 ]; do
  [ "${OEM_NETWORK_BUDGET_LEFT:-0}" -ge 15 ] || return 1
  OEM_NETWORK_BUDGET_LEFT=$((OEM_NETWORK_BUDGET_LEFT-15));attempt=$((attempt+1))
  # File-size ulimit bounds even a server which sends an endless response.
  # BusyBox implementations use 512/1024-byte units; provision twice size.
  oem_bounded_run 15 sh -c 'umask 077; ulimit -f "$1" || exit 1; exec wget -q -O "$2" "$3"' sh "$(((size+511)/512))" "$output.part" "${OEM_DOWNLOAD_URL%/}/$name" || true
  if [ -f "$output.part" ] && [ ! -L "$output.part" ] && [ "$(wc -c < "$output.part")" -eq "$size" ] && [ "$(oem_sha "$output.part")" = "$expected" ]; then
   chmod 600 "$output.part" && mv "$output.part" "$output" || return 1
   oem_private_file "$output" && sync || return 1
   return 0
  fi
  [ ! -L "$output.part" ] || return 1
  [ ! -e "$output.part" ] || rm -f "$output.part" || return 1
 done
 return 1
}
