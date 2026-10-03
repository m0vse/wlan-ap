# Attribute only the interactive command; never replace BusyBox or /sbin/reboot.
case "$-" in
*i*)
reboot() {
	# Help, delayed and nonstandard invocations bypass attribution, not reboot.
	case "$*" in
	''|-f|-n|'-n -f'|'-f -n') ;;
	*) /sbin/reboot "$@"; return $? ;;
	esac
	/usr/libexec/ucentral-boot-report plan user-requested || :
	if /sbin/reboot "$@"; then
		return 0
	else
		local rc=$?
		/usr/libexec/ucentral-boot-report cancel user-requested || :
		return "$rc"
	fi
}
;;
esac
