#!/bin/sh
# Offline reviewed executable/link/library identity ledger, NOT a live enroll.
# X executable-sha256 /path, F file-sha256 /path,
# L literal-link-target /path, A - /absent-path.
ow_runtime_contract_check() (
 ledger=$1; source_root=${2:-}
 case "$source_root" in ''|/*) ;; *) exit 1 ;; esac
 [ -f "$ledger" ] && [ ! -L "$ledger" ] || exit 1
 LC_ALL=C awk '
  function safe(p) {return p~/^\/[A-Za-z0-9_.\/+:-]+$/ || p~/^\/(bin|sbin|usr\/bin|usr\/sbin)\/\[$/}
  NF!=3 || !safe($3) || $3~/\/\// || $3~/(^|\/)\.\.?($|\/)/ || seen[$3]++ {bad=1}
  $1=="F" || $1=="X" {if(length($2)!=64 || $2~/[^0-9a-f]/) bad=1; next}
  $1=="L" {if($2!~/^[A-Za-z0-9_.\/+:-]+$/) bad=1; next}
  $1=="A" {if($2!="-") bad=1; next}
  {bad=1}
  END {exit (bad || NR==0)}
 ' "$ledger" || { echo 'Runtime contract: malformed reviewed ledger' >&2; exit 1; }
 while read -r kind expected path; do
  candidate=$source_root$path
  case "$kind" in
   F|X)
    [ -f "$candidate" ] && [ ! -L "$candidate" ] && [ -r "$candidate" ] ||
     { echo "Runtime contract: missing/nonregular reviewed component $path" >&2; exit 1; }
    [ "$kind" != X ] || [ -x "$candidate" ] ||
     { echo "Runtime contract: nonexecutable reviewed component $path" >&2; exit 1; }
    actual=$(sha256sum < "$candidate") || exit 1
    [ "${actual%% *}" = "$expected" ] ||
     { echo "Runtime contract: unknown executable/library implementation $path; qualify offline" >&2; exit 1; } ;;
   L)
    [ -L "$candidate" ] && [ "$(readlink "$candidate")" = "$expected" ] ||
     { echo "Runtime contract: incompatible component link $path" >&2; exit 1; } ;;
   A)
    [ ! -e "$candidate" ] && [ ! -L "$candidate" ] ||
     { echo "Runtime contract: unexpected component overrides lookup $path" >&2; exit 1; } ;;
  esac
 done < "$ledger"
)
