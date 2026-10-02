# Stock Sage clean-migration policy only; no legacy identity/config import.
sage_stock_store_check() {
	local sys=${AB_UBI_SYS:-/sys/class/ubi} mounts=${AB_PROC_MOUNTS:-/proc/mounts}
	local dev=${AB_DEV:-/dev} store=${AB_CERTIFICATE_STORE:-/certificates}
	local volume reserved geometry free entries
	[ -r "$mounts" ] || return 1
	[ "${SAVE_CONFIG:-0}" = 0 ] || return 1
	[ "$AB_FAMILY" = sage ] && [ "$AB_LAYOUT" = pair ] &&
		[ "$AB_ACTIVE_MTD" = "$AB_TARGET_MTD" ] || return 1
	[ "$(cat "$sys/$AB_ACTIVE_UBI/mtd_num")" = "$AB_ACTIVE_MTD" ] || return 1
	geometry=$(cat "$sys/$AB_ACTIVE_UBI/eraseblock_size") || return 1
	[ "$geometry" = 126976 ] && [ "$geometry" = "$AB_LEB" ] || return 1
	volume=$(ab_ubi_volume "$AB_ACTIVE_UBI" certificates) || volume=
	if [ -z "$volume" ]; then
		# The incoming allocator consumes actual free space. The reviewed
		# outgoing writer first reclaims only its inactive replacement rootfs.
		! awk -v path="$store" '$2==path { found=1 } END { exit !found }' "$mounts" || return 1
		free=$(cat "$sys/$AB_ACTIVE_UBI/avail_eraseblocks") || return 1
		case "$free" in ''|*[!0-9]*) return 1 ;; esac
		[ "$free" -ge 20 ] || ab_sage_certificate_capacity || return 1
		return 0
	fi
	reserved=$(cat "$sys/$volume/reserved_ebs") || return 1
	case "$reserved" in ''|*[!0-9]*) return 1 ;; esac
	[ "$reserved" -ge 20 ] && [ "$(cat "$sys/$volume/usable_eb_size")" = "$geometry" ] || return 1
	if awk -v path="$store" '$2==path { found=1 } END { exit !found }' "$mounts"; then
		awk -v path="$store" -v node="$dev/$volume" -v named="$AB_ACTIVE_UBI:certificates" \
			'$2==path { count++; if(($1==node || $1==named) && $3=="ubifs") good++ } END { exit !(count==1 && good==1) }' "$mounts" || return 1
		[ -d "$store" ] && [ ! -L "$store" ] || return 1
		entries=$(find "$store" -mindepth 1 -print) || return 1
		[ -z "$entries" ] || return 1
	else
		# No raw-header assumption establishes that an unmounted store is empty.
		return 1
	fi
}
