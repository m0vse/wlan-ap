import * as fs from 'fs';
import * as schema from 'schemareader';
let create = require('deferred_settings').create;

const DIRECTORY = '/etc/ucentral/deferred-settings';
const PENDING = DIRECTORY + '/pending.json';
const DEFAULTS = '/certificates/ucentral.defaults';

function directory(path, private) {
	let st = fs.lstat(path);
	if (!st && private) { assert(fs.mkdir(path, 0700), 'Cannot create deferred directory'); st = fs.lstat(path); }
	assert(st?.type == 'directory' && st.uid == 0 && !(st.mode & 0022) &&
	       (!private || st.mode == 0700), 'Unsafe deferred directory');
}

function safe(path, limit, optional, empty) {
	let st = fs.lstat(path);
	if (!st && optional) return false;
	assert(st?.type == 'file' && st.uid == 0 && st.nlink == 1 &&
	       st.mode in [0600, 0440, 0644] && (st.size > 0 || empty && st.size == 0) && st.size <= limit,
	       'Unsafe deferred file: ' + path);
	return true;
}

// ucode's JSON reader accepts duplicate keys. Reject them before reading a
// mutable policy object, including escaped spellings and nested duplicates.
function object(text) {
	let scopes = [], value;
	try { value = json(text); } catch (e) { die('Invalid deferred policy JSON'); }
	assert(type(value) == 'object', 'Deferred policy must be an object');
	for (let i = 0; i < length(text); i++) {
		let c = substr(text, i, 1);
		if (c == '{') { push(scopes, {}); continue; }
		if (c == '}') { pop(scopes); continue; }
		if (c != '"') continue;
		let start = i++;
		for (; i < length(text); i++) {
			if (substr(text, i, 1) == '\\') { i++; continue; }
			if (substr(text, i, 1) == '"') break;
		}
		let end = i + 1;
		while (end < length(text) && match(substr(text, end, 1), /\s/)) end++;
		if (substr(text, end, 1) == ':') {
			let key = json(substr(text, start, i - start + 1)), scope = scopes[length(scopes)-1];
			assert(scope && !exists(scope, key), 'Duplicate deferred policy key');
			scope[key] = true;
		}
	}
	return value;
}

function read(path, limit, optional) {
	return safe(path, limit, optional) ? object(fs.readfile(path)) : null;
}

function output(command) {
	let pipe = fs.popen(command);
	assert(pipe, 'Cannot execute deferred proof');
	let text = pipe.read('all');
	assert(pipe.close() == 0, 'Deferred proof failed');
	return trim(text);
}

function publish(path, text, limit) {
	if (fs.lstat(path)) safe(path, limit, false);
	let temporary = path + '.deferred-new';
	if (fs.lstat(temporary)) {
		safe(temporary, limit, false, true);
		assert(fs.lstat(temporary).mode == 0600, 'Unsafe deferred temporary mode');
		assert(fs.unlink(temporary), 'Cannot remove interrupted deferred temporary');
	}
	let file = fs.open(temporary, 'w', 0600);
	assert(file && fs.chmod(temporary, 0600) && file.write(text) == length(text) &&
	       file.flush() && file.close() && !system('sync') && fs.rename(temporary, path) &&
	       !system('sync') && fs.readfile(path) == text, 'Deferred durable publication failed');
}

function hash(path) {
	return safe(path, 16384, true) ? split(output('sha256sum ' + path), ' ')[0] : null;
}

function context(phase) {
	directory('/etc/ucentral', false);
	directory('/certificates', false);
	if (fs.lstat(DIRECTORY)) directory(DIRECTORY, true);
	let proof = split(output('/usr/libexec/ucentral-deferred-context'), '\t');
	assert(length(proof) == 9, 'Invalid deferred context');
	let capabilities = read('/etc/ucentral/capabilities.json', 131072, true);
	// A managed upgrade can regenerate capabilities only after driver probe.
	// The root-private accepted journal retains the previously validated policy
	// for pre-driver boot; binding and the hardware adapter are still checked.
	let pending_policy = read(PENDING, 262144, true)?.country_policy;
	let restrictions = read('/etc/ucentral/restrictions.json', 16384, true) || {};
	// The actual renderer uses restrictions.country (an array); do not
	// confuse it with the capabilities country_codes field or legacy typo.
	for (let key in ['country', 'country_codes'])
		if (exists(restrictions, key)) assert(type(restrictions[key]) == 'array', 'Invalid country restriction');
	let has_restrictions = length(restrictions.country || []) || length(restrictions.country_codes || []);
	let restricted = length(restrictions.country || []) ? restrictions.country : null;
	if (length(restrictions.country_codes || []))
		restricted = restricted ? filter(restricted, c => c in restrictions.country_codes) : restrictions.country_codes;
	let accepted = false, spki = null;
	if (safe('/certificates/key.pem', 131072, true) &&
	    safe('/certificates/operational.pem', 131072, true) &&
	    safe('/certificates/operational.ca', 2097152, true)) {
		assert(fs.lstat('/certificates/key.pem').mode in [0600, 0440], 'Unsafe private identity key mode');
		// Pre-driver boot precedes NTP. Verify issuer/signature/purpose and the
		// original key here without treating the unverified boot clock as truth.
		// Admission and final readback retain normal validity checks. This does
		// not confirm enrollment, remove bootstrap or change an issuer policy.
		let pre_driver = phase == 'boot';
		assert(!system('openssl pkey -in /certificates/key.pem -check -noout >/dev/null 2>&1') &&
		       (pre_driver || !system('openssl x509 -in /certificates/operational.pem -checkend 0 -noout >/dev/null 2>&1')) &&
		       !system('openssl verify ' + (pre_driver ? '-no_check_time ' : '') +
		       '-purpose sslclient -CAfile /certificates/operational.ca /certificates/operational.pem >/dev/null 2>&1'),
		       'Deferred operational identity is invalid');
		spki = output('openssl pkey -in /certificates/key.pem -pubout -outform DER 2>/dev/null | sha256sum');
		assert(spki == output('openssl x509 -in /certificates/operational.pem -pubkey -noout | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum') &&
		       output('openssl x509 -in /certificates/operational.pem -subject -noout -nameopt RFC2253') == 'subject=CN=' + proof[1], 'Deferred key/serial mismatch');
		spki = split(spki, ' ')[0];
		let gateway = read('/certificates/gateway.json', 16384, true) ||
			read('/certificates/gateway.default.json', 16384, true);
		accepted = gateway?.hostname_validate === 1 && gateway?.['allow-self-signed'] !== true &&
			type(gateway?.server) == 'string' && match(gateway.server, /^[A-Za-z0-9][A-Za-z0-9.-]*$/) &&
			type(gateway?.port) == 'int' && gateway.port > 0 && gateway.port <= 65535 &&
			gateway?.cert == '/etc/ucentral/operational.pem' &&
			gateway?.ca in ['/etc/ucentral/operational.ca', '/etc/ucentral/server-ca.pem', '/etc/ssl/certs/ca-certificates.crt'];
	}
	if (fs.lstat('/certificates/.installer-import')) directory('/certificates/.installer-import', true);
	let journal = read('/certificates/.installer-import/transaction.json', 4096, true);
	if (journal) {
		assert(fs.lstat('/certificates/.installer-import/transaction.json').mode == 0600,
		       'Unsafe native journal mode');
		assert(type(journal.job) == 'string' && match(journal.job, /^[0-9a-f]{64}$/) &&
		       journal.serial == proof[1] && journal.target_slot in [0, 1] &&
		       (journal.accepted === true || journal.target_slot == +proof[2]), 'Native job context mismatch');
		if (proof[3] != '-')
			assert(journal.job == proof[3] && journal.target_slot == +proof[4],
			       'Active installer job differs from durable identity');
		accepted = accepted && journal.committed === true && journal.accepted === true && journal.spki == spki;
	}
	assert(proof[3] == '-' || journal, 'Active installer job has no validated journal');
	let active_country = trim(fs.readfile('/sys/module/cfg80211/parameters/ieee80211_regdom') ||
		fs.readfile('/etc/ucentral/country') || '');
	if (proof[0] == 'cambiumnetworks,x7-35x' &&
	    (!match(active_country, /^[A-Z]{2}$/) ||
	     system('/usr/libexec/ucentral-deferred-miami readback ' + active_country))) active_country = null;
	return { board: proof[0], serial: proof[1], bank: +proof[2], spki,
		installer_pending: proof[3] != '-',
		layout: proof[5], ab_state: proof[6], confirmed: proof[7] == '-' ? null : +proof[7],
		target: proof[8] == '-' ? null : +proof[8],
		job: journal?.job || null, identity_accepted: accepted && proof[3] == '-',
		boot_id: trim(fs.readfile('/proc/sys/kernel/random/boot_id') || ''),
		country_codes: capabilities?.country_codes || pending_policy?.codes,
		restricted_countries: has_restrictions ? restricted : pending_policy?.restricted,
		active_country };
}

function validate_country(country, ctx) {
	if (ctx.board == 'cambiumnetworks,x7-35x') {
		assert(!system('/usr/libexec/ucentral-deferred-miami validate ' + country),
		       'Miami regional board data is unavailable');
		return;
	}
	// This default proves cfg80211's boot-country mechanism. A board that has
	// additional boot-only calibration must opt in with a qualified adapter.
	assert(fs.stat('/sys/module/cfg80211/parameters/ieee80211_regdom') ||
	       length(fs.glob('/lib/modules/*/cfg80211.ko') || []),
	       'No qualified boot-country adapter');
}

function boot_country(document, ctx) {
	// Per-radio country remains live on existing platforms. Only Miami's
	// proven regional-BDF difference requires a cold boot for this setting.
	return ctx.board == 'cambiumnetworks,x7-35x' ? require('deferred_settings').country(document || {}) : null;
}

function needs(document) {
	if (fs.lstat(DIRECTORY)) directory(DIRECTORY, true);
	let record = read(PENDING, 262144, true);
	if (record && !(record.phase in ['active', 'cancelled'])) return true;
	let board = trim(fs.readfile('/tmp/sysinfo/board_name') || '');
	if (board == 'cambiumnetworks,x7-35x') {
		let wanted = require('deferred_settings').country(document);
		if (!wanted) return false;
		return system('/usr/libexec/ucentral-deferred-miami readback ' + wanted) != 0;
	}
	if (board != 'cambiumnetworks,xv3-8') return false;
	return length(probe(document, {board})) > 0;
}

function probe(document, ctx) {
	if (!document || ctx.board != 'cambiumnetworks,xv3-8') return [];
	let logs = [], validated = schema.validate(document, logs);
	assert(validated && !length(filter(logs, m => substr(m, 0, 3) == '[E]')) &&
	       (!validated.strict || !length(logs)), 'Invalid deferred controller document');
	let mode = trim(fs.readfile('/sys/module/ath11k/parameters/xv3_8_hw_mode') || '');
	assert(mode in ['dual-4x4', 'single-8x8'], 'Thor topology is unavailable');
	let cursor = require('uci').cursor();
	let desired = require('thor_topology_policy').select_mode(validated,
		cursor.get('xv3_8_radio', 'main', 'mode') || 'dual-4x4');
	return desired == mode ? [] : [{ setting: 'topology', active: mode, desired }];
}

function baseline() {
	// Refuse malformed/duplicate policy at admission, before acknowledging it.
	read(DEFAULTS, 16384, true);
	return { defaults: hash(DEFAULTS) };
}

function commit(record, ctx) {
	let desired;
	for (let change in record.changes) if (change.setting == 'country') desired = change.desired;
	if (desired) {
		assert(ctx.identity_accepted, 'Country commit waits for accepted native identity');
		directory('/etc', false);
		safe('/etc/modules.conf', 16384, true);
		let defaults = read(DEFAULTS, 16384, true) || {};
		let current_hash = hash(DEFAULTS);
		// Replay after a power loss permits only our exact intended country
		// object, never clobbers an unrelated concurrent policy edit.
		let original = record.baseline.defaults;
		if (current_hash != original) {
			assert(record.defaults_after && current_hash == record.defaults_after,
			       'Durable country policy changed concurrently');
		} else {
			defaults.country = desired;
			let text = sprintf('%J\n', defaults);
			publish(DIRECTORY + '/defaults.after', text, 16384);
			record.defaults_after = hash(DIRECTORY + '/defaults.after');
			publish(PENDING, sprintf('%J\n', record), 262144);
			publish(DEFAULTS, text, 16384);
		}
		assert(!system('/usr/libexec/ucentral-module-country ' + desired), 'Cannot set boot-country module options');
		publish('/etc/ucentral/country', desired + '\n', 16);
	}
	if (record.document) {
		assert(match(record.source || '', /^\/etc\/ucentral\/ucentral\.cfg\.[0-9]+$/), 'Invalid accepted config path');
		publish(record.source, sprintf('%J\n', record.document), 262144);
		if (ctx.board == 'cambiumnetworks,xv3-8')
			assert(!system('/usr/libexec/thor-topology stage ' + record.source), 'Cannot stage accepted Thor topology');
		// Country-only configs are rendered normally at boot by ucentral-network.
		let temporary = '/etc/ucentral/ucentral.active.deferred-new';
		assert(!fs.lstat(temporary), 'Unexpected active config temporary');
		assert(fs.symlink(record.source, temporary) && fs.rename(temporary, '/etc/ucentral/ucentral.active') &&
		       !system('sync'), 'Cannot select accepted boot configuration');
	}
}

function readback(record, ctx) {
	// The early boot step cannot establish validity against an unverified
	// clock. Finish only after the same clock-readiness gate used by native
	// enrollment, in addition to strict identity and actual driver readback.
	if (!fs.stat('/tmp/ntp.set')) return false;
	for (let change in record.changes) {
		if (change.setting == 'topology' && trim(fs.readfile('/sys/module/ath11k/parameters/xv3_8_hw_mode') || '') != change.desired) return false;
		if (change.setting == 'country') {
			if (ctx.active_country != change.desired) return false;
			if (ctx.board == 'cambiumnetworks,x7-35x' &&
			    system('/usr/libexec/ucentral-deferred-miami readback ' + change.desired)) return false;
		}
	}
	return true;
}

function replay(record, ctx) {
	assert(ctx.identity_accepted && ctx.board == record.binding.board &&
	       ctx.serial == record.binding.serial && ctx.spki == record.binding.spki,
	       'Completed setting identity continuity failed');
	let defaults = read(DEFAULTS, 16384, false), country = defaults.country;
	assert(type(country) == 'string' && match(country, /^[A-Z]{2}$/) &&
	       country in require('deferred_countries').codes &&
	       country in (ctx.country_codes || []) &&
	       (ctx.restricted_countries == null || country in ctx.restricted_countries),
	       'Durable boot country is not authorized');
	validate_country(country, ctx);
	directory('/etc', false);
	safe('/etc/modules.conf', 16384, true);
	assert(!system('/usr/libexec/ucentral-module-country ' + country), 'Cannot replay boot country');
	publish('/etc/ucentral/country', country + '\n', 16);
}

function backend() {
	return create({ context, probe, country: boot_country, validate_country, baseline, commit, readback, replay,
		current: function() { return {
			country: trim(fs.readfile('/sys/module/cfg80211/parameters/ieee80211_regdom') || ''),
			topology: trim(fs.readfile('/sys/module/ath11k/parameters/xv3_8_hw_mode') || '')
		}; },
		load: function() {
			directory('/etc/ucentral', false);
			if (fs.lstat(DIRECTORY)) directory(DIRECTORY, true);
			let record = read(PENDING, 262144, true);
			if (record) {
				assert(fs.lstat(PENDING).mode == 0600, 'Unsafe deferred journal mode');
				assert(record.version === 1 && record.phase in ['accepted', 'committing', 'boot-staged', 'active', 'cancelled'] &&
				       type(record.uuid) == 'int' && record.uuid >= 0 && record.uuid <= 4294967295 &&
				       type(record.id) == 'int' && record.id >= 0 && record.id <= 4294967295 &&
				       type(record.changes) == 'array' && length(record.changes) > 0 &&
				       type(record.binding) == 'object' && type(record.accepted_boot) == 'string' && length(record.accepted_boot),
				       'Invalid deferred journal');
				for (let change in record.changes)
					assert(change.setting in ['country', 'topology'] && type(change.desired) == 'string',
					       'Unknown deferred setting');
				if (record.document) assert(record.document.uuid == record.uuid,
				                            'Accepted document UUID changed');
			}
			return record;
		},
		save: function(record) { directory(DIRECTORY, true); publish(PENDING, sprintf('%J\n', record), 262144); },
		check_baseline: function(value) { assert(value.defaults == hash(DEFAULTS), 'Country baseline changed'); }
	});
}

return { object, backend, needs };
