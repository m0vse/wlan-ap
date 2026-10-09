# Optional installer-specific gate. Normal upgrades without pending fields
# keep their existing health contract. No controller credential or endpoint.

ab_installer_health() {
	local target job image seed=${AB_INSTALLER_INCOMING_SEED:-/root/.cambium-installer-settings}
	local accept=${AB_INSTALLER_ACCEPT:-/usr/libexec/ucentral-installer-identity} value
	target=$(ab_getenv "${AB_ENV}_installer_target") || target=
	job=$(ab_getenv "${AB_ENV}_installer_job") || job=
	image=$(ab_getenv "${AB_ENV}_installer_image") || image=
	[ -n "$target$job$image" ] || return 0
	case "$target" in 0|1) ;; *) return 1 ;; esac
	# The old fallback bank is NOT required to import/accept the candidate.
	[ "$target" = "$AB_ACTIVE" ] || return 0
	for value in "$job" "$image"; do
		case "$value" in ''|*[!0-9a-f]*) return 1 ;; esac
		[ "${#value}" = 64 ] || return 1
	done
	[ -f "$seed/binding.tsv" ] && [ ! -L "$seed/binding.tsv" ] || return 1
	[ "$(awk -F '\t' '$1=="job_id" && NF==2 {v=$2;n++} END {if(n!=1)exit 1;print v}' "$seed/binding.tsv")" = "$job" ] &&
	[ "$(awk -F '\t' '$1=="image_sha256" && NF==2 {v=$2;n++} END {if(n!=1)exit 1;print v}' "$seed/binding.tsv")" = "$image" ] &&
	[ "$(awk -F '\t' '$1=="target_slot" && NF==2 {v=$2;n++} END {if(n!=1)exit 1;print v}' "$seed/binding.tsv")" = "$target" ] || return 1
	[ -x "$accept" ] && "$accept" accepted "$seed"
}

ab_installer_clear_pending() {
	local target
	ab_installer_health || return 1
	target=$(ab_getenv "${AB_ENV}_installer_target") || target=
	[ "$target" = "$AB_ACTIVE" ] || return 0
	printf '%s_installer_target\n%s_installer_job\n%s_installer_image\n' \
		"$AB_ENV" "$AB_ENV" "$AB_ENV" >> "$1"
}

ab_installer_cleanup_confirmed() {
 local job=$1 slot=$2 seed=${AB_INSTALLER_INCOMING_SEED:-/root/.cambium-installer-settings}
 local accept=${AB_INSTALLER_ACCEPT:-/usr/libexec/ucentral-installer-identity}
 [ -d "$seed" ] || return 0
 [ "$slot" = "$AB_ACTIVE" ] &&
 [ "$(ab_getenv "${AB_ENV}_ab_confirmed")" = "$slot" ] &&
 [ "$(ab_getenv "${AB_ENV}_ab_state")" = confirmed ] &&
 [ "$(ab_getenv bootcmd)" = "run ${AB_ENV}_stable$slot" ] || return 1
 [ -x "$accept" ] && "$accept" cleanup-confirmed "$seed"
}
