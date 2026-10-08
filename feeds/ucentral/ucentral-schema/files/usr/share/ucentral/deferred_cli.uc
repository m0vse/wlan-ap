#!/usr/bin/ucode
REQUIRE_SEARCH_PATH = ['/usr/share/ucentral/*.uc', ...REQUIRE_SEARCH_PATH];
import * as schema from 'schemareader';
let fs = require('fs'), service = require('deferred_backend').backend();
let mode = ARGV[0], record;
try {
	if (mode == 'stage-config') {
		assert(match(ARGV[1] || '', /^\/etc\/ucentral\/ucentral\.cfg\.[0-9]+$/), 'Invalid controller source');
		assert(match(ARGV[3] || '', /^\/etc\/ucentral\/deferred-settings\/request\.[A-Za-z0-9]+$/), 'Invalid accepted snapshot');
		let st = fs.lstat(ARGV[3]), directory = fs.lstat('/etc/ucentral/deferred-settings');
		assert(directory?.type == 'directory' && directory.uid == 0 && directory.mode == 0700 &&
		       st?.type == 'file' && st.uid == 0 && st.nlink == 1 && st.mode == 0600 &&
		       st.size > 0 && st.size <= 262144, 'Unsafe controller source');
		let document = require('deferred_backend').object(fs.readfile(ARGV[3]));
		let logs = [], validated = schema.validate(document, logs);
		assert(validated && !length(filter(logs, m => substr(m, 0, 3) == '[E]')) &&
		       (!validated.strict || !length(logs)), 'Invalid deferred configuration');
		assert(match(ARGV[2] || '', /^[0-9]+$/), 'Invalid controller request ID');
		if (!require('deferred_backend').needs(document)) { print('null\n'); exit(0); }
		record = service.prepare({ document, uuid: document.uuid, id: +ARGV[2], source: ARGV[1] });
	} else if (mode == 'stage-country') {
		assert(match(ARGV[1] || '', /^[A-Z]{2}$/) && match(ARGV[2] || '', /^[0-9]+$/) &&
		       match(ARGV[3] || '', /^[0-9]+$/), 'Invalid country request');
		record = service.prepare({ country: ARGV[1], uuid: +ARGV[2], id: +ARGV[3] });
	} else if (mode == 'boot') record = service.boot();
	else if (mode == 'confirm') record = service.confirm();
	else if (mode == 'state') { print(sprintf('%J\n', service.state())); exit(0); }
	else die('Unknown deferred operation');
	if (mode in ['boot', 'confirm']) {
		print(sprintf('%J\n', record ? {uuid:record.uuid,phase:record.phase} : null)); exit(0);
	}
	print(sprintf('%J\n', record ? { uuid: record.uuid, id: record.id,
		status: require('deferred_settings').status(record) } : null));
	exit(0);
} catch (e) {
	warn('Deferred settings refused: ', e, '\n');
	exit(1);
}
