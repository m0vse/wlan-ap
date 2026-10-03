// TEST-only injected process execution; this never invokes reboot or pmsg.
let calls = [], warnings = [], fail = false;
for (let reason in ['reboot', 'upgrade', 'factory', 'certupdate', 'fixedconfig', 'transfer']) {
	include(ARGV[0], { reason, system: function(args) { push(calls, args); return fail ? 1 : 0; }, warn: message => push(warnings, message) });
}
if (length(calls) != 6 || calls[0][2] != 'controller-requested' || calls[1][2] != 'upgrade') die('TEST incorrect include reason propagation\n');
fail = true;
include(ARGV[0], { reason: 'reboot', system: function(args) { push(calls, args); return 1; }, warn: message => push(warnings, message) });
if (length(warnings) != 1 || length(calls) != 7) die('TEST unavailable helper aborted or failed silently\n');
print('TEST absent-pmsg helper and request propagation: 7 PASS\n');
