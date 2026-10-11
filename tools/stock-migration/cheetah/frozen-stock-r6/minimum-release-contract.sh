#!/bin/sh
# Trusted bundle policy + untrusted release DATA. Never source/eval AP metadata.
# POLICY: one line: stock|tip family YYYY.MM.DD.N target architecture
# SOURCE_ROOT: empty for live root, absolute private root for offline fixtures.
ow_release_contract_check() (
 policy=$1; source_root=${2:-}
 [ -f "$policy" ] && [ ! -L "$policy" ] || { echo 'Release contract: unsafe policy' >&2; exit 1; }
 case "$source_root" in ''|/*) ;; *) exit 1 ;; esac
 # Policy belongs to the already SHA-verified operator bundle.
 read -r namespace family minimum target architecture extra < "$policy" || exit 1
 [ -z "${extra:-}" ] && [ "$(wc -l < "$policy")" -eq 1 ] || exit 1
 ow_release_contract_check_values "$namespace" "$family" "$minimum" "$target" "$architecture" "$source_root"
)

# Trusted literal argument form for a source-authenticated clean-route helper
# that must recheck its namespace after service shutdown without environment
# flags or a policy file that is not retained across the RAM pivot.
ow_release_contract_check_values() (
 namespace=$1; family=$2; minimum=$3; target=$4; architecture=$5; source_root=${6:-}
 case "$source_root" in ''|/*) ;; *) exit 1 ;; esac
 case "$namespace:$family" in stock:sage|stock:jaguar|stock:cheetah|stock:thor|stock:gambit|tip:sage|tip:jaguar|tip:cheetah|tip:thor|tip:gambit) ;; *) exit 1 ;; esac
 release=$source_root/etc/openwrt_release
 stock=$source_root/etc/cambium-openwrt-release
 [ -f "$release" ] && [ ! -L "$release" ] && [ "$(wc -c < "$release")" -le 16384 ] ||
  { echo 'Release contract: missing/unsafe OpenWrt release metadata' >&2; exit 1; }
 if [ "$namespace" = stock ]; then
  [ -f "$stock" ] && [ ! -L "$stock" ] && [ "$(wc -c < "$stock")" -le 16384 ] ||
   { echo 'Release contract: missing/unsafe stock release metadata' >&2; exit 1; }
 else
  [ ! -e "$stock" ] && [ ! -L "$stock" ] ||
   { echo 'Release contract: mixed stock/TIP markers are not qualified' >&2; exit 1; }
  stock=/dev/null
 fi
 LC_ALL=C awk -v ns="$namespace" -v family="$family" -v minimum="$minimum" \
  -v target="$target" -v arch="$architecture" '
 function refuse(reason) { print "Release contract: " reason > "/dev/stderr"; bad=1; exit 1 }
 function valid_version(v, a, n, leap, days) {
  n=split(v,a,".")
  if(n!=4 || length(a[1])!=4 || length(a[2])!=2 || length(a[3])!=2 || length(a[4])>6) return 0
  for(n=1;n<=4;n++) if(a[n]!~/^[0-9]+$/) return 0
  if(a[1]+0<2000 || a[2]+0<1 || a[2]+0>12 || a[3]+0<1 || a[4]+0>999999) return 0
  if(length(a[4])>1 && substr(a[4],1,1)=="0") return 0
  leap=(a[1]%4==0 && (a[1]%100!=0 || a[1]%400==0))
  days=(a[2]+0==2 ? 28+leap : (a[2]+0==4 || a[2]+0==6 || a[2]+0==9 || a[2]+0==11 ? 30 : 31))
  return a[3]+0<=days
 }
 function at_least(v,m, a,b,i) {
  split(v,a,"."); split(m,b,".")
  for(i=1;i<=4;i++) { if(a[i]+0>b[i]+0) return 1; if(a[i]+0<b[i]+0) return 0 }
  return 1
 }
 /^[[:space:]]*$/ || /^#/ { next }
 {
  # Deliberately support only the literal format emitted by qualified builds.
  # No escapes, shell substitutions, duplicate keys or executable statements.
  if($0!~/^[A-Z][A-Z0-9_]*=/) refuse("malformed literal metadata")
  key=$0; sub(/=.*/,"",key)
  # Some authenticated stock scripts source these files later. Permit only
  # release-data keys, never PATH/IFS/ENV/FORCE or other shell control names.
  if(FILENAME==ARGV[1]) {
   if(key!~/^DISTRIB_(ID|RELEASE|REVISION|TARGET|ARCH|DESCRIPTION|TAINTS|TIP|TIP_VERSION|UCENTRAL_SCHEMA_REVISION)$/) refuse("unreviewed release metadata key")
  } else if(key!~/^(CAMBIUM_FAMILY|CAMBIUM_CHANNEL|CAMBIUM_SOURCE_COMMIT|OPENWRT_UPSTREAM_COMMIT)$/ && key!=toupper(family) "_BUILD_ID") refuse("unreviewed stock metadata key/family marker")
  value=substr($0,length(key)+2)
  quote=sprintf("%c",39)
  if(substr(value,1,1)!=quote || substr(value,length(value),1)!=quote || length(value)<2) refuse("metadata must be single-quoted literals")
  value=substr(value,2,length(value)-2)
  if(value ~ /[^A-Za-z0-9_ \/.:+@,=-]/ || seen[key]++) refuse("unsafe or duplicate metadata")
  values[key]=value
 }
 END {
  if(bad) exit 1
  if(!valid_version(minimum)) refuse("malformed trusted minimum")
  if(values["DISTRIB_ID"]!="OpenWrt" || values["DISTRIB_TARGET"]!=target || values["DISTRIB_ARCH"]!=arch) refuse("incompatible target/architecture")
  if(ns=="stock") {
   if(seen["DISTRIB_TIP"] || seen["DISTRIB_TIP_VERSION"]) refuse("TIP marker on stock route")
   if(tolower(values["CAMBIUM_FAMILY"])!=family) refuse("wrong stock family")
   version=values[toupper(family) "_BUILD_ID"]
  } else {
   prefix=family "-"
   marker=values["DISTRIB_TIP_VERSION"]
   if(substr(marker,1,length(prefix))!=prefix) refuse("wrong TIP family/namespace")
   version=substr(marker,length(prefix)+1)
   fullprefix=values["DISTRIB_DESCRIPTION"] " / TIP-" marker "-"
   full=values["DISTRIB_TIP"]
   suffix=substr(full,length(fullprefix)+1)
   if(values["DISTRIB_DESCRIPTION"]!~/^OpenWrt / || substr(full,1,length(fullprefix))!=fullprefix || length(suffix)<8 || length(suffix)>40 || suffix~/[^0-9a-f]/) refuse("inconsistent TIP version/full marker/source suffix")
  }
  if(!valid_version(version)) refuse("malformed version; expected YYYY.MM.DD.N")
  if(!at_least(version,minimum)) refuse("below qualified minimum " minimum)
 }
 ' "$release" "$stock"
)
