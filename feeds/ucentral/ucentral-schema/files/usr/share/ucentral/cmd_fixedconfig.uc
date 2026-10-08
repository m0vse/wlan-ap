// Legacy RPC name, common safe lifecycle. No reset, reboot or live changes.
try {
	assert(type(args) == 'object' && length(keys(args)) == 1 &&
	       type(args.country) == 'string' && match(args.country, /^[A-Z]{2}$/),
	       'Only a country setting is supported');
	let active = json(fs.readfile('/etc/ucentral/ucentral.active') || '{}');
	assert(type(active.uuid) == 'int' && active.uuid >= 0 && type(+id) == 'int' && +id >= 0,
	       'Configuration correlation is unavailable');
	let pipe = fs.popen('/usr/libexec/ucentral-deferred stage-country ' +
		args.country + ' ' + active.uuid + ' ' + +id);
	assert(pipe, 'Cannot stage country');
	let response = json(pipe.read('all') || 'null'), rc = pipe.close();
	assert(rc == 0, 'Country setting was not accepted');
	if (response) ctx.call('ucentral', 'result', response);
	else result_json({error: 0, text: 'Country already active', reboot_required: false});
} catch (e) {
	result_json({error: 2, text: 'Country setting refused'});
}
