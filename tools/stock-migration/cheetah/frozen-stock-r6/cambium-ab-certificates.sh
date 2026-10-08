# OpenWiFi bank-local certificate retention. No raw UBIFS copying.
# platform_pre_upgrade must call ab_certificate_export after services stop.
# The archive and descriptor must be included in RAMFS_COPY_DATA.
AB_CERTIFICATE_CONTENT_VERSION=1
AB_CERTIFICATE_ARCHIVE=${AB_CERTIFICATE_ARCHIVE:-/tmp/cambium-ab-certificates.tar}
AB_CERTIFICATE_DESCRIPTOR=${AB_CERTIFICATE_DESCRIPTOR:-/tmp/cambium-ab-certificates.descriptor}

ab_certificate_binding() {
	local boot
	boot=$(cat "${AB_BOOT_ID:-/proc/sys/kernel/random/boot_id}") || return 1
	printf '%s:%s:%s:%s:%s:%s:%s:%s\n' "$boot" "$AB_FAMILY" "$AB_MODEL" "$AB_SKU" \
		"$AB_ACTIVE" "$AB_TARGET" "$AB_ACTIVE_MTD" "$AB_TARGET_MTD"
}

ab_certificate_private_file() {
	[ -f "$1" ] && [ ! -L "$1" ] &&
		LC_ALL=C ls -ldn "$1" | awk -v owner="${AB_CERTIFICATE_OWNER:-0}" \
			'$1=="-rw-------" && $3==owner { good=1 } END { exit !good }'
}

ab_certificate_tree_safe() {
	# The supported identity store contains only ordinary files/directories.
	# Reject links, devices and unsafe archive names before copying/extraction.
	[ -z "$(find "$1" ! -type f ! -type d -print)" ] || return 1
	(cd "$1" && find . -print) | LC_ALL=C awk '
		/[^A-Za-z0-9_.\/-]/ { bad=1 }
		END { exit bad }'
}

# Operator-only migration policy. The incoming firmware retains the canonical
# preservation helper. This exact reviewed stock release starts unprovisioned.
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

ab_certificate_clean_stock_source() {
 ow_release_contract_check_values stock cheetah 2026.09.29.0 qualcommax/ipq50xx aarch64_cortex-a53
}

ab_certificate_export() {
	local work source volume mounted=0 runtime=${AB_CERTIFICATE_RUNTIME:-/etc/ucentral}
	local store=${AB_CERTIFICATE_STORE:-/certificates} hash binding rc=0 file magic
	[ "$(ab_certificate_lebs)" = 20 ] || return 0
	[ "${SAVE_CONFIG:-0}" = 0 ] && ab_certificate_clean_stock_source ||
		{ ab_fail 'clean stock route requires SAVE_CONFIG=0 and a qualified stock release'; return 1; }
	ab_identity || return 1
	[ "$AB_LAYOUT" = banks ] || return 0 # Sage's store is shared, not bank-local.
	[ "$(cat "${AB_UBI_SYS:-/sys/class/ubi}/$AB_ACTIVE_UBI/mtd_num")" = "$AB_ACTIVE_MTD" ] ||
		{ ab_fail 'certificate source is not the active bank'; return 1; }
	umask 077
	work=$(mktemp -d /tmp/cambium-ab-certificate-export.XXXXXX) || return 1
	mkdir "$work/tree" "$work/source" || return 1

	if [ -f "$work/tree/key.pem" ] || [ -f "$work/tree/cert.pem" ]; then
		command -v openssl >/dev/null 2>&1 ||
			{ ab_fail 'openssl is required to validate outgoing credentials'; return 1; }
		[ -f "$work/tree/key.pem" ] && [ -f "$work/tree/cert.pem" ] ||
			{ ab_fail 'incomplete bootstrap credential pair'; return 1; }
		# Verify key match without exposing private material in output/logs.
		openssl x509 -in "$work/tree/cert.pem" -pubkey -noout > "$work/cert-public" 2>/dev/null &&
			openssl pkey -in "$work/tree/key.pem" -pubout > "$work/key-public" 2>/dev/null &&
			cmp -s "$work/cert-public" "$work/key-public" ||
			{ ab_fail 'bootstrap certificate and key do not match'; return 1; }
	fi
	ab_certificate_tree_safe "$work/tree" || return 1
	# Normalize privacy regardless of source modes; source is not modified.
	find "$work/tree" -type d -exec chmod 0700 {} \;
	find "$work/tree" -type f -exec chmod 0600 {} \;
	(cd "$work/tree" && find . -type f ! -name .cambium-ab-manifest -exec sha256sum {} \; > .cambium-ab-manifest &&
		tar cf "$work/archive" .) || return 1
	[ "$(wc -c < "$work/archive")" -le $((20 * AB_LEB)) ] ||
		{ ab_fail 'certificate snapshot exceeds reserved volume capacity'; return 1; }
	hash=$(sha256sum "$work/archive"); hash=${hash%% *}
	binding=$(ab_certificate_binding) || return 1
	printf '%s\n%s\n' "$binding" "$hash" > "$work/descriptor" || return 1
	chmod 0600 "$work/archive" "$work/descriptor" || return 1
	mv -f "$work/archive" "$AB_CERTIFICATE_ARCHIVE" &&
		mv -f "$work/descriptor" "$AB_CERTIFICATE_DESCRIPTOR" || return 1
	RAMFS_COPY_DATA="${RAMFS_COPY_DATA:-} $AB_CERTIFICATE_ARCHIVE $AB_CERTIFICATE_DESCRIPTOR"
	RAMFS_COPY_BIN="${RAMFS_COPY_BIN:-} cmp mktemp sha256sum"
	# Temporary source copies intentionally remain private on error for diagnosis.
	rm -rf "$work"
}

ab_certificate_validate_snapshot() {
	local hash expected binding
	[ "$(ab_certificate_lebs)" = 20 ] || return 0
	[ "$AB_LAYOUT" = banks ] || return 0
	ab_certificate_private_file "$AB_CERTIFICATE_ARCHIVE" &&
		ab_certificate_private_file "$AB_CERTIFICATE_DESCRIPTOR" ||
		{ ab_fail 'missing or unsafe RAM-stage certificate snapshot'; return 1; }
	binding=$(ab_certificate_binding) || return 1
	[ "$(sed -n '1p' "$AB_CERTIFICATE_DESCRIPTOR")" = "$binding" ] ||
		{ ab_fail 'certificate snapshot belongs to another boot or bank'; return 1; }
	hash=$(sha256sum "$AB_CERTIFICATE_ARCHIVE"); hash=${hash%% *}
	expected=$(sed -n '2p' "$AB_CERTIFICATE_DESCRIPTOR")
	[ "$hash" = "$expected" ] || { ab_fail 'certificate snapshot checksum failed'; return 1; }
	# Bound the archive again after the RAM copy, and reject special entries.
	[ "$(wc -c < "$AB_CERTIFICATE_ARCHIVE")" -le $((20 * AB_LEB)) ] || return 1
	tar tf "$AB_CERTIFICATE_ARCHIVE" | LC_ALL=C awk '
		/^\// || /(^|\/)\.\.(\/|$)/ || /[^A-Za-z0-9_.\/-]/ { bad=1 }
		END { exit bad }' || return 1
	tar tvf "$AB_CERTIFICATE_ARCHIVE" | awk 'substr($0,1,1)!="-" && substr($0,1,1)!="d" { bad=1 } END { exit bad }' || return 1
}

ab_certificate_restore() {
	local work rc=0
	[ "$(ab_certificate_lebs)" = 20 ] || return 0
	[ "$AB_LAYOUT" = banks ] || return 0
	ab_certificate_validate_snapshot || return 1
	[ "$(cat "${AB_UBI_SYS:-/sys/class/ubi}/$AB_TARGET_UBI/mtd_num")" = "$AB_TARGET_MTD" ] &&
		[ "$AB_TARGET_MTD" != "$AB_ACTIVE_MTD" ] || return 1
	umask 077
	work=$(mktemp -d /tmp/cambium-ab-certificate-restore.XXXXXX) || return 1
	mount -t ubifs "${AB_DEV:-/dev}/$(ab_ubi_volume "$AB_TARGET_UBI" certificates)" "$work" || return 1
	tar xf "$AB_CERTIFICATE_ARCHIVE" -C "$work" &&
		(cd "$work" && { [ ! -s .cambium-ab-manifest ] || sha256sum -c .cambium-ab-manifest >/dev/null 2>&1; }) &&
		ab_certificate_tree_safe "$work" || rc=1
	sync
	umount "$work" || rc=1
	rmdir "$work" || rc=1
	[ "$rc" = 0 ] || ab_fail 'inactive certificate store restore or verification failed'
}
