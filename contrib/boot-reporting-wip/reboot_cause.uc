// Recording must never abort reboot just because pmsg or storage is unavailable.
let cause = reason || ARGV[0] || 'orderly-shutdown';
if (cause == 'reboot') cause = 'controller-requested';
if (system(['/usr/libexec/ucentral-boot-report', 'plan', cause]) != 0)
	warn('Unable to persist reboot intent; reboot operation remains permitted\n');
