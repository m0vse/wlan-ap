# Attribute only the interactive command; never replace BusyBox or /sbin/reboot.
case "$-" in
*i*)
reboot() {
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
