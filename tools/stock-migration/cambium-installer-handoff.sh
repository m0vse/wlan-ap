# Dedicated stock-to-OpenWiFi settings handoff. No source-side crypto.
# The authenticated wrapper sets OW_EXPECT_* from its exact source contract.
# All FORMAT2 parsing/publication is owned by the shared settings library.
. "${CAMBIUM_INSTALLER_SETTINGS_LIB:-/lib/upgrade/cambium-installer-settings.sh}" || return 1
AB_INSTALLER_INPUT=${AB_INSTALLER_INPUT:-/root/.cambium-installer-input}
AB_INSTALLER_ARCHIVE=${AB_INSTALLER_ARCHIVE:-/tmp/cambium-installer-settings.tar}
AB_INSTALLER_DESCRIPTOR=${AB_INSTALLER_DESCRIPTOR:-/tmp/cambium-installer-settings.descriptor}

ab_installer_refuse_pending() {
	local snapshot
	ab_identity || return 1
	ab_env_config || return 1
	# Reading an absent key and failing to read ENV are not equivalent.
	# Authenticate a complete successful read; never print its contents.
	snapshot=$(fw_printenv -c "$AB_ENV_CONFIG" 2>/dev/null) || return 1
	# Fresh installation is never an automatic destructive retry.
	# A separate verified no-format rearm route is not implemented here.
	printf '%s\n' "$snapshot" | awk -F '=' -v prefix="$AB_ENV" '
	 $1==prefix "_installer_target" || $1==prefix "_installer_job" || $1==prefix "_installer_image" {
	  if (seen[$1]++ || NF!=2 || length($2)) bad=1
	 }
	 END {exit bad}'
}

ab_installer_live_context() {
	local serial native
	ab_identity || return 1
	[ "${AB_QUALIFIED:-0}" = 1 ] || return 1
	serial=$(get_mac_label_dt | tr -d ':' | tr 'A-F' 'a-f') || return 1
	native=$(get_mac_label | tr -d ':' | tr 'A-F' 'a-f') || return 1
	[ "$serial" = "$native" ] && [ "$serial" = "$OW_EXPECT_SERIAL" ] &&
	[ "$AB_FAMILY" = "$OW_EXPECT_FAMILY" ] && [ "$AB_MODEL" = "$OW_EXPECT_MODEL" ] &&
	[ "$AB_ACTIVE" = "$OW_EXPECT_SOURCE" ] && [ "$AB_TARGET" = "$OW_EXPECT_TARGET" ]
}

ab_installer_export() {
	local image=$1 work boot digest
	[ "${SAVE_CONFIG:-0}" = 0 ] && ab_installer_refuse_pending || return 1
	ow_settings_tree "$AB_INSTALLER_INPUT" && ow_settings_context "$image" && ab_installer_live_context || return 1
	umask 077
	work=$(mktemp -d /tmp/cambium-settings-export.XXXXXX) || return 1
	work=$(readlink -f "$work") || return 1
	cp "$AB_INSTALLER_INPUT"/* "$work/" || return 1
	ow_settings_tree "$work" && ow_settings_context "$image" && ab_installer_live_context || return 1
	[ ! -e "$AB_INSTALLER_ARCHIVE" ] && [ ! -L "$AB_INSTALLER_ARCHIVE" ] &&
	[ ! -e "$AB_INSTALLER_DESCRIPTOR" ] && [ ! -L "$AB_INSTALLER_DESCRIPTOR" ] || return 1
	tar cf "$AB_INSTALLER_ARCHIVE" -C "$work" . || return 1
	[ "$(wc -c < "$AB_INSTALLER_ARCHIVE")" -le 1048576 ] || return 1
	boot=$(cat "${AB_BOOT_ID:-/proc/sys/kernel/random/boot_id}") || return 1
	digest=$(ow_settings_hash "$AB_INSTALLER_ARCHIVE") || return 1
	printf 'boot\t%s\narchive\t%s\nserial\t%s\nfamily\t%s\nmodel\t%s\noperation\t%s\nrelease\t%s\ncontract\t%s\nsource\t%s\ntarget\t%s\njob\t%s\n' \
		"$boot" "$digest" "$OW_EXPECT_SERIAL" "$OW_EXPECT_FAMILY" "$OW_EXPECT_MODEL" \
		"$OW_EXPECT_OPERATION" "$OW_EXPECT_RELEASE" "$OW_EXPECT_CONTRACT" \
		"$OW_EXPECT_SOURCE" "$OW_EXPECT_TARGET" "$OW_EXPECT_JOB" > "$AB_INSTALLER_DESCRIPTOR" || return 1
	chmod 600 "$AB_INSTALLER_ARCHIVE" "$AB_INSTALLER_DESCRIPTOR" || return 1
	ab_installer_ramfs
}

ab_installer_ramfs() {
	RAMFS_COPY_DATA="${RAMFS_COPY_DATA:-} $AB_INSTALLER_ARCHIVE $AB_INSTALLER_DESCRIPTOR /lib/upgrade/cambium-installer-handoff.sh /lib/upgrade/cambium-installer-settings.sh"
	# Additional core/writer tools remain covered by the authenticated stock
	# runtime closure; include every extra operation introduced by this glue.
	RAMFS_COPY_BIN="${RAMFS_COPY_BIN:-} ls wc awk readlink sha256sum cat mkdir cp chmod sync mv tar tr mktemp mount umount rmdir fw_printenv"
}

ab_installer_validate_ram() {
	local image=$1 key value tab boot digest members work
	[ "${SAVE_CONFIG:-0}" = 0 ] && ab_installer_refuse_pending || return 1
	ow_settings_private "$AB_INSTALLER_DESCRIPTOR" || return 1
	awk -F '\t' '
	 BEGIN {split("boot archive serial family model operation release contract source target job",keys," ")}
	 NF!=2 || $1!=keys[NR] {bad=1}
	 END {exit bad || NR!=11}
	' "$AB_INSTALLER_DESCRIPTOR" || return 1
	[ "$(wc -l < "$AB_INSTALLER_DESCRIPTOR")" -eq 11 ] || return 1
	tab=$(printf '\t')
	while IFS="$tab" read -r key value; do
		case "$key" in
		boot) boot=$value ;; archive) digest=$value ;;
		serial) OW_EXPECT_SERIAL=$value ;; family) OW_EXPECT_FAMILY=$value ;;
		model) OW_EXPECT_MODEL=$value ;; operation) OW_EXPECT_OPERATION=$value ;;
		release) OW_EXPECT_RELEASE=$value ;; contract) OW_EXPECT_CONTRACT=$value ;;
		source) OW_EXPECT_SOURCE=$value ;; target) OW_EXPECT_TARGET=$value ;; job) OW_EXPECT_JOB=$value ;;
		*) return 1 ;;
		esac
	done < "$AB_INSTALLER_DESCRIPTOR"
	[ "$boot" = "$(cat "${AB_BOOT_ID:-/proc/sys/kernel/random/boot_id}")" ] || return 1
	[ -f "$AB_INSTALLER_ARCHIVE" ] && [ ! -L "$AB_INSTALLER_ARCHIVE" ] &&
	[ "$(ow_settings_metadata "$AB_INSTALLER_ARCHIVE")" = "${OW_SETTINGS_OWNER:-0}:600:1" ] &&
	[ "$(wc -c < "$AB_INSTALLER_ARCHIVE")" -le 1048576 ] &&
	[ "$digest" = "$(ow_settings_hash "$AB_INSTALLER_ARCHIVE")" ] || return 1
	members=$(tar tf "$AB_INSTALLER_ARCHIVE") || return 1
	printf '%s\n' "$members" | awk '
	 seen[$0]++ {bad=1}
	 $0!~/^\.\/$/ && $0!~/^\.\/(binding.tsv|files.sha256|est.json|gateway.json|est-bootstrap.conf|insta.pem|server-ca.pem)$/ {bad=1}
	 END {exit bad}
	' || return 1
	tar tvf "$AB_INSTALLER_ARCHIVE" | awk 'substr($1,1,1)!="-" && substr($1,1,1)!="d" {bad=1} END {exit bad}' || return 1
	umask 077
	work=$(mktemp -d /tmp/cambium-settings-ram.XXXXXX) || return 1
	work=$(readlink -f "$work") || return 1
	tar xf "$AB_INSTALLER_ARCHIVE" -C "$work" || return 1
	OW_STAGE_ADMISSION=qualified
	ow_settings_tree "$work" && ow_settings_context "$image" && ab_installer_live_context || return 1
	AB_INSTALLER_VALIDATED=$work
	ab_installer_ramfs
}

ab_installer_pending() {
	[ -n "${AB_INSTALLER_VALIDATED:-}" ] || return 1
	printf '%s_installer_target %s\n%s_installer_job %s\n%s_installer_image %s\n' \
		"$AB_ENV" "$OW_EXPECT_TARGET" "$AB_ENV" "$OW_EXPECT_JOB" "$AB_ENV" "$OW_IMAGE" >> "$1"
}

ab_installer_install_settings() {
	local image=$1 ubi volume active mnt rc=0
	[ -n "${AB_INSTALLER_VALIDATED:-}" ] && ab_installer_live_context || return 1
	case "$AB_LAYOUT" in
	pair)
		ubi=$AB_ACTIVE_UBI
		[ "$(cat "${AB_UBI_SYS:-/sys/class/ubi}/$ubi/mtd_num")" = "$AB_ACTIVE_MTD" ] || return 1
		volume=$(ab_ubi_volume "$ubi" "rootfs_data$AB_TARGET") || return 1
		active=$(ab_ubi_volume "$ubi" "rootfs_data$AB_ACTIVE") || active=$(ab_ubi_volume "$ubi" "rootfs$AB_ACTIVE") || return 1
		[ "$volume" != "$active" ] || return 1 ;;
	banks)
		ubi=$AB_TARGET_UBI
		[ "$AB_ACTIVE_MTD" != "$AB_TARGET_MTD" ] &&
		[ "$(cat "${AB_UBI_SYS:-/sys/class/ubi}/$ubi/mtd_num")" = "$AB_TARGET_MTD" ] || return 1
		volume=$(ab_ubi_volume "$ubi" rootfs_data) || return 1 ;;
	*) return 1 ;;
	esac
	[ "$(ab_getenv "${AB_ENV}_installer_target")" = "$OW_EXPECT_TARGET" ] &&
	[ "$(ab_getenv "${AB_ENV}_installer_job")" = "$OW_EXPECT_JOB" ] &&
	[ "$(ab_getenv "${AB_ENV}_installer_image")" = "$OW_IMAGE" ] || return 1
	OW_EXPECT_TARGET_VOLUME=$volume
	OW_EXPECT_TARGET_MTD=$AB_TARGET_MTD
	umask 077
	mnt=$(mktemp -d /tmp/cambium-settings-target.XXXXXX) || return 1
	mnt=$(readlink -f "$mnt") || return 1
	mount -t ubifs "${AB_DEV:-/dev}/$volume" "$mnt" || return 1
	ow_settings_stage_overlay "$AB_INSTALLER_VALIDATED" "$image" "$mnt" || rc=1
	sync || rc=1
	umount "$mnt" || rc=1
	rmdir "$mnt" || rc=1
	[ "$rc" = 0 ]
}
