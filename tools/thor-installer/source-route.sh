#!/bin/sh
# Pure complete-tuple classifier; never source AP files or infer trust from credentials.
ow_thor_route() (
 bundle=$1
 source_root=${2:-}
 ow_source_wildcards_known "$bundle/source-sets/required-paths" "$source_root" || exit 1
 for route in stock openwifi; do
  for phase in outgoing installed; do
   if ow_release_contract_check "$bundle/release-policies/$route.policy" "$source_root" && ow_runtime_contract_check "$bundle/runtime-sets/$route.set" "$source_root" && ow_source_set_matches "$bundle/source-sets/$phase-$route.set" "$bundle/source-sets/required-paths" "$source_root"; then
    echo "$route"; exit 0
   fi
  done
 done
 exit 1
)

ow_thor_installed_matches() (
 bundle=$1 route=$2 source_root=${3:-}
 ow_source_wildcards_known "$bundle/source-sets/required-paths" "$source_root" || exit 1
 ow_release_contract_check "$bundle/release-policies/$route.policy" "$source_root" || exit 1
 ow_runtime_contract_check "$bundle/runtime-sets/$route.set" "$source_root" || exit 1
 ow_source_set_matches "$bundle/source-sets/installed-$route.set" "$bundle/source-sets/required-paths" "$source_root"
)

ow_thor_metadata_fingerprint() (
 source_root=${1:-}
 for path in /etc/openwrt_release /etc/cambium-openwrt-release; do
  candidate=$source_root$path
  if [ -f "$candidate" ] && [ ! -L "$candidate" ]; then
   sha256sum < "$candidate" || exit 1
  elif [ ! -e "$candidate" ] && [ ! -L "$candidate" ]; then
   echo absent
  else exit 1; fi
 done
)
