// TEST-only download, ubus, filesystem, archive and process stubs. Never flashes.
let count = 0;
function check(test, condition) { if (!condition) die('TEST ' + test + '\n'); count++; }
for (let scenario in ['none', 'config', 'redirector', 'both', 'archive-failure', 'download-failure']) {
	let calls = [], result_code = null;
	let args = { uri: 'https://TEST.invalid/firmware', 'keep-config': scenario == 'config' || scenario == 'both', 'keep-redirector': scenario == 'redirector' || scenario == 'both' };
	include(ARGV[0], {
		args, restrict: { sysupgrade: false },
		fs: { stat: () => ({ type: 'file' }), readfile: () => '{}', readlink: () => '/etc/ucentral/TEST.active.uc',
			popen: () => ({ read: () => scenario == 'download-failure' ? '403' : '200', close: () => 0 }) },
		ctx: { call: (object, method, params) => ({ valid: true }), error: () => null },
		include: function(file, variables) { push(calls, ['intent', variables.reason]); },
		system: function(command) { push(calls, command); return type(command) == 'array' && command[0] == 'tar' && scenario == 'archive-failure' ? 1 : 0; },
		result: function(code) { result_code = code; }, result_json: function(result) { result_code = result.error; },
		warn: () => null, log: () => null, sleep: () => null
	});
	if (scenario == 'download-failure') { check('failed download records no reboot request', !length(calls) && result_code == 2); continue; }
	check('request precedes managed archive', calls[0][0] == 'intent' && calls[0][1] == 'upgrade' && calls[1][0] == 'tar');
	check('history and rendered config preserved irrespective UI flags', index(calls[1], '/etc/ucentral/boot-reporting') >= 0 && index(calls[1], '/etc/config') >= 0 && index(calls[1], '/etc/config-shadow') >= 0);
	check('Thor pending topology survives combined managed archive', index(calls[1], '/etc/ucentral/thor-topology.pending.json') >= 0 && index(calls[1], '/etc/ucentral/thor-topology.pending') >= 0);
	if (scenario == 'archive-failure') { check('failed archive cancels matching request', calls[2][1] == 'cancel' && calls[2][2] == 'upgrade' && result_code == 2); continue; }
	let background = filter(calls, c => type(c) == 'string' && index(c, 'sysupgrade -f /upgrade.tgz') >= 0);
	check('preserving upgrade and late failure cancellation', length(background) == 1 && index(background[0], 'cancel firmware-upgrade') >= 0 && index(background[0], 'rc=$?') >= 0 && index(background[0], ' -n ') < 0);
}
print(sprintf('TEST actual managed command preservation, ordering and failed request controls: %d PASS\n', count));
