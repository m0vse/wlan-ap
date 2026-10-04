import * as fs from 'fs';
import { reporter } from '../../feeds/ucentral/ucentral-boot-report/files/usr/share/ucentral/boot_reporting.uc';
let base = ARGV[0], results = [], next = 0;
const A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
function check(name, predicate) { if (!predicate) die('FAIL ' + name + '\n'); push(results, name); }
function fixture(name) {
	let root = base + '/' + name; fs.mkdir(root, 0o700); fs.mkdir(root + '/pstore', 0o700);
	fs.writefile(root + '/boot-id', A); fs.writefile(root + '/uptime', '100.0 0'); fs.writefile(root + '/version', 'TEST-synthetic-firmware');
	let p = { directory: root + '/history', state: root + '/history/history.json', lock: root + '/lock', pstore: root + '/pstore', boot_id: root + '/boot-id', uptime: root + '/uptime', version: root + '/version', cause: root + '/cause' };
	let f = { root, p, now: 1791016870, clock_synced: true, online: false, accepted: true, sent: [], renamed: true, synced: true, cause: null, unlinks: [], sync_calls: 0, sync_fail_at: null };
	f.app = reporter(p, {
		clock_synced: () => f.clock_synced,
		now: () => f.now, sync: function() { f.sync_calls++; return f.synced && f.sync_calls != f.sync_fail_at ? 0 : 1; },
		rename: (a, b) => f.renamed && fs.rename(a, b), reset_cause: () => f.cause,
		unlink: function(path) {
			let state = json(fs.readfile(p.state));
			check('durable-copy-before-unlink-' + next++, length(filter(state.events, e => e.method == 'crashlog')) > 0);
			push(f.unlinks, path); return fs.unlink(path);
		},
		connected: () => f.online,
		send: function(message) { push(f.sent, message); return f.accepted; }
	});
	return f;
}
function reboot(f) { fs.writefile(f.p.boot_id, B); fs.writefile(f.p.uptime, '1.0 0'); f.now += 20; return f.app.collect(); }
function reason(f) { return f.app.state().reason; }
let f = fixture('unknown'); f.app.collect();
check('exact-unexpected-shutdown-first-observation', reason(f) == 'unexpected-shutdown');
f.app.collect(); check('same-boot-no-new-event', length(f.app.state().events) == 1);
check('offline-keeps-pending', f.app.send() == 0 && f.app.state().events[0].delivery == 'pending');
f.online = true; f.accepted = false; f.app.send(); check('write-failure-retains-pending', f.app.state().events[0].delivery == 'pending');
f.accepted = true; f.app.send(); check('successful-write-is-unacknowledged-not-delivered', f.app.state().events[0].delivery == 'transmitted-unacknowledged');
let count = length(f.sent); f.app.collect(); f.app.send(); check('reconnect-no-duplicate-boot-or-report', count == length(f.sent));
f = fixture('controller'); f.app.collect(); f.app.plan('controller-requested'); f.app.plan('orderly-shutdown');
check('generic-shutdown-does-not-overwrite-controller', f.app.state().intent.reason == 'controller-requested');
reboot(f); check('controller-requested-next-boot', reason(f) == 'controller-requested');
f = fixture('cli'); f.app.collect(); f.app.plan('user-requested'); f.app.plan('orderly-shutdown'); reboot(f);
check('interactive-user-intent-precedence', reason(f) == 'user-requested');
f = fixture('stale'); f.app.collect(); f.app.plan('upgrade'); f.now += 301; reboot(f);
check('stale-upgrade-is-not-a-new-reboot-reason', reason(f) == 'unexpected-shutdown');
f = fixture('cancel'); f.app.collect(); f.app.plan('upgrade'); f.app.cancel('upgrade'); reboot(f);
check('cancelled-upgrade-is-not-a-reboot-reason', reason(f) == 'unexpected-shutdown');
f = fixture('expiry-priority'); f.app.collect(); f.app.plan('upgrade'); fs.writefile(f.p.uptime, '221.0 0'); f.app.plan('user-requested');
check('stale-intent-no-longer-blocks-user-request', f.app.state().intent.reason == 'user-requested');
f = fixture('watchdog'); f.cause = { reason: 'watchdog', source: 'TEST-reviewed-reset-register', detail: 'TEST' }; f.app.collect();
check('watchdog-requires-supplied-family-evidence', reason(f) == 'watchdog');
f = fixture('power'); f.cause = { reason: 'power-failure', source: 'TEST-reviewed-PMIC', detail: 'TEST' }; f.app.collect();
check('power-failure-requires-supplied-family-evidence', reason(f) == 'power-failure');
f = fixture('unproven'); f.cause = { reason: 'power-failure', source: '' }; f.app.collect();
check('unproven-power-failure-is-unexpected-shutdown', reason(f) == 'unexpected-shutdown');
f = fixture('panic'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic - not syncing: isolated synthetic fixture\nTEST stack\n');
f.app.collect(); f.online = true; f.app.send();
check('captured-panic-informs-boot-reason', reason(f) == 'confirmed-crash');
check('crash-wire-method-loglines-not-rebootLog-crashlog', f.sent[0].method == 'crashlog' && type(f.sent[0].params.loglines) == 'array');
check('reboot-wire-has-type-date-info', f.sent[1].method == 'rebootLog' && f.sent[1].params.type == 'confirmed-crash' && type(f.sent[1].params.info) == 'array');
check('complete-pstore-source-consumed-after-copy', !fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('oops'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Oops: nonfatal fault evidence\n'); f.app.collect();
check('nonfatal-oops-not-proven-reboot-cause', reason(f) == 'unexpected-shutdown' && f.app.state().events[0].classification == 'kernel-fault');
f = fixture('privacy'); fs.writefile(f.p.pstore + '/console-ramoops-0', 'TEST secret-console'); fs.writefile(f.p.pstore + '/pmsg-ramoops-0', 'TEST marker'); f.app.collect();
check('console-and-pmsg-not-uploaded-or-deleted', length(f.app.state().events) == 1 && fs.stat(f.p.pstore + '/console-ramoops-0') && fs.stat(f.p.pstore + '/pmsg-ramoops-0'));
for (let failure in ['rename', 'sync']) {
	f = fixture(failure); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic: synthetic failure\n');
	if (failure == 'rename') f.renamed = false; else f.synced = false;
	let failed = false; try { f.app.collect(); } catch (e) { failed = true; }
	check(failure + '-failure-keeps-original', failed && fs.stat(f.p.pstore + '/dmesg-ramoops-0') && !length(f.unlinks));
}
let long_text = 'TEST '; for (let i = 0; i < 18000; i++) long_text += 'x';
f = fixture('post-rename-sync'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic: post-rename failure'); f.sync_fail_at = 2;
let post_failed = false; try { f.app.collect(); } catch (e) { post_failed = true; }
f.synced = false; let retry_failed = false; try { f.app.collect(); } catch (e) { retry_failed = true; }
check('post-rename-sync-failure-and-unchanged-retry-retain-source', post_failed && retry_failed && fs.stat(f.p.pstore + '/dmesg-ramoops-0') && !length(f.unlinks));
f.synced = true; f.app.collect(); check('successful-retry-sync-allows-consumption', !fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('truncated'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', long_text); f.app.collect();
check('truncated-dump-bounded-and-original-retained', length(f.app.state().events[0].text) == 16384 && f.app.state().events[0].truncated && fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('binary'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST \x01 bytes'); f.app.collect();
check('sanitized-bytes-reported-but-original-retained', f.app.state().events[0].sanitized && fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('many'); for (let i = 0; i < 12; i++) fs.writefile(f.p.pstore + '/dmesg-ramoops-' + i, 'TEST dump ' + i); f.app.collect();
check('queue-bounded-with-eviction-accounting', length(f.app.state().events) == 8 && f.app.state().evicted == 5);
check('pruned-dumps-not-consumed-without-retained-copy', length(fs.lsdir(f.p.pstore)) == 5);
let before = sprintf('%J', f.app.state()); f.app.collect();
check('retained-pruned-sources-do-not-cycle-queue', before == sprintf('%J', f.app.state()));
f = fixture('fresh-plan'); f.app.plan('upgrade'); reboot(f);
check('first-request-normalized-firmware-upgrade', reason(f) == 'firmware-upgrade');
f = fixture('priority-user'); f.app.collect(); f.app.plan('upgrade'); f.app.plan('user-requested');
check('interactive-reboot-preserves-specific-upgrade', f.app.state().intent.reason == 'firmware-upgrade');
f = fixture('clockless-expiry'); f.now = 1; f.app.collect(); f.app.plan('controller-requested'); fs.writefile(f.p.uptime, '401.0 0'); f.app.collect(); reboot(f);
check('clockless-abandoned-intent-expires-before-next-boot', reason(f) == 'unexpected-shutdown');
f = fixture('late-panic'); f.app.collect(); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic: late source'); f.app.collect();
check('late-confirmed-evidence-updates-local-boot-not-new-boot', reason(f) == 'confirmed-crash' && length(filter(f.app.state().events, e => e.method == 'rebootLog')) == 1);
f = fixture('late-transmitted'); f.app.collect(); f.online = true; f.app.send(); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic: arrived after report'); f.app.collect(); f.app.send();
check('late-evidence-does-not-replay-transmitted-boot', length(filter(f.sent, e => e.method == 'rebootLog')) == 1);
f = fixture('escaped-bounds'); let tabs = 'TEST'; for (let i = 0; i < 16370; i++) tabs += '\t';
for (let i = 0; i < 8; i++) fs.writefile(f.p.pstore + '/dmesg-ramoops-' + i, tabs + i); f.app.collect();
check('encoded-json-byte-bound-prunes-before-consumption', length(fs.readfile(f.p.state)) <= 196608 && length(fs.lsdir(f.p.pstore)) > 0);
for (let invalid in ['method', 'delivery', 'boot_id']) {
 f = fixture('invalid-' + invalid); f.app.collect(); let s = f.app.state();
 if (invalid == 'boot_id') s.boot_id = '------------------------------------'; else s.events[0][invalid] = 'TEST-invalid';
 fs.writefile(f.p.state, sprintf('%J', s)); let rejected = false; try { f.app.collect(); } catch (e) { rejected = true; }
 check('invalid-stored-' + invalid + '-refused-without-overwrite', rejected && fs.readfile(f.p.state) == sprintf('%J', s));
}
f = fixture('cause-link'); fs.writefile(f.root + '/sentinel', 'TEST-safe'); fs.symlink(f.root + '/sentinel', f.p.cause); let cause_failed = false; try { f.app.collect(); } catch (e) { cause_failed = true; }
check('unsafe-volatile-cause-link-refused', cause_failed && fs.readfile(f.root + '/sentinel') == 'TEST-safe');
f = fixture('symlink'); fs.symlink('/tmp', f.p.directory); let failed = false; try { f.app.collect(); } catch (e) { failed = true; }
check('unsafe-history-link-refused', failed);
function radio(f, mutate) {
	fs.mkdir(f.root + '/radio', 0o700); f.p.radio_crash = f.root + '/radio';
	fs.writefile(f.p.radio_crash + '/.lock', ''); fs.chmod(f.p.radio_crash + '/.lock', 0o600);
	let id = A + '-devcd0';
	let m = { version: 1, id, boot_id: A, driver: 'remoteproc-or-ath', source: 'devcoredump',
		byte_count: 12, binaryfile: id + '.bin', complete: false, truncated: true };
	if (mutate) mutate(m);
	fs.writefile(f.p.radio_crash + '/' + id + '.bin', 'SECRETbinary');
	fs.chmod(f.p.radio_crash + '/' + id + '.bin', 0o600);
	fs.writefile(f.p.radio_crash + '/' + id + '.json', sprintf('%J', m));
	fs.chmod(f.p.radio_crash + '/' + id + '.json', 0o600);
	return id;
}
f = fixture('radio-partial'); let rid = radio(f); f.app.collect();
let reports = filter(f.app.state().events, e => e.classification == 'radio-coredump');
check('radio-summary-does-not-attribute-host-reboot', length(reports) == 1 && reason(f) == 'unexpected-shutdown');
check('radio-summary-is-metadata-only', reports[0].truncated && index(reports[0].text, 'SECRETbinary') < 0 && reports[0].radio.byte_count == 12);
f.app.collect(); check('radio-reconnect-deduplicates', length(f.app.state().events) == 2);
f.online = true; f.app.send();
check('radio-wire-is-crashlog-not-reboot-cause', length(filter(f.sent, e => e.method == 'crashlog' && index(e.params.loglines[1], 'not evidence of a host kernel panic') >= 0)) == 1);
check('radio-binary-manifest-retained-after-transport', fs.stat(f.p.radio_crash + '/' + rid + '.bin') && fs.stat(f.p.radio_crash + '/' + rid + '.json') && !length(f.unlinks));
f = fixture('radio-complete'); radio(f, m => { m.complete = true; m.truncated = false; }); f.app.collect();
check('radio-complete-metadata-supported', !filter(f.app.state().events, e => e.classification == 'radio-coredump')[0].truncated);
for (let invalid in ['version', 'boot_id', 'binaryfile', 'byte_count', 'complete', 'truncated', 'driver', 'sha256']) {
	f = fixture('radio-invalid-' + invalid);
	radio(f, function(m) {
		if (invalid == 'version') m.version = 2;
		else if (invalid == 'boot_id') m.boot_id = B;
		else if (invalid == 'binaryfile') m.binaryfile = '../key.pem';
		else if (invalid == 'byte_count') m.byte_count = 4194305;
		else if (invalid == 'complete') m.complete = 0;
		else if (invalid == 'truncated') m.truncated = false;
		else if (invalid == 'driver') m.driver = 'unsafe\nmetadata';
		else m.sha256 = 'bad';
	}); f.app.collect();
	check('radio-invalid-' + invalid + '-ignored-without-source-deletion', length(f.app.state().events) == 1 && !length(f.unlinks));
}
f = fixture('radio-permissions'); rid = radio(f); fs.chmod(f.p.radio_crash + '/' + rid + '.bin', 0o644); f.app.collect();
check('radio-public-binary-refused', length(f.app.state().events) == 1);
f = fixture('radio-size'); radio(f, m => { m.byte_count = 11; }); f.app.collect();
check('radio-size-mismatch-refused', length(f.app.state().events) == 1);
f = fixture('radio-write-failure'); rid = radio(f); f.synced = false; let rf = false;
try { f.app.collect(); } catch (e) { rf = true; }
check('radio-history-sync-failure-retains-evidence', rf && fs.stat(f.p.radio_crash + '/' + rid + '.json') && fs.stat(f.p.radio_crash + '/' + rid + '.bin') && !length(f.unlinks));
f = fixture('radio-locked'); radio(f); let writer = fs.open(f.p.radio_crash + '/.lock', 'a'); writer.lock('xn'); f.app.collect();
check('radio-publish-lock-nonblocking-skip', length(f.app.state().events) == 1);
writer.close(); f.app.collect(); check('radio-after-publish-lock-release-collected', length(f.app.state().events) == 2);
f = fixture('radio-bin-link'); rid = radio(f); fs.unlink(f.p.radio_crash + '/' + rid + '.bin'); fs.symlink(f.p.version, f.p.radio_crash + '/' + rid + '.bin'); f.app.collect();
check('radio-binary-symlink-refused', length(f.app.state().events) == 1);
f = fixture('radio-malformed'); rid = radio(f); fs.writefile(f.p.radio_crash + '/' + rid + '.json', '{broken'); f.app.collect();
check('radio-malformed-manifest-does-not-block-boot-report', length(f.app.state().events) == 1);
f = fixture('radio-newboot'); radio(f); f.app.collect(); reboot(f);
check('radio-does-not-turn-following-boot-into-confirmed-crash', reason(f) == 'unexpected-shutdown' && length(filter(f.app.state().events, e => e.classification == 'radio-coredump')) == 1);
f = fixture('radio-publish-sync'); f.app.collect(); radio(f); f.sync_fail_at = f.sync_calls + 1; f.app.collect();
check('radio-publication-sync-failure-does-not-report-unconfirmed-manifest', length(f.app.state().events) == 1 && !length(f.unlinks));
f.sync_fail_at = null; f.app.collect(); check('radio-publication-sync-successful-retry-collects', length(f.app.state().events) == 2);
f = fixture('stale-restored-clock'); f.clock_synced = false;
fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST Kernel panic: captured before NTP');
f.app.collect(); f.online = true;
check('plausible-restored-clock-not-trusted', f.app.state().events[0].date == null && f.app.state().events[1].date == null);
check('pre-NTP-panic-durable-and-source-consumed', !fs.stat(f.p.pstore + '/dmesg-ramoops-0') && reason(f) == 'confirmed-crash');
check('connected-before-NTP-does-not-send-stale-date', f.app.send() == 0 && !length(f.sent));
let collected_at = f.now + 34000;
f.now = collected_at + 200; fs.writefile(f.p.uptime, '300.0 0'); f.clock_synced = true;
f.app.send();
check('post-NTP-reconstructs-collection-time-from-uptime', f.app.state().events[0].date == collected_at && f.sent[1].params.date == collected_at);
check('estimated-timestamp-explicitly-labelled', f.sent[1].params.info[0].timestamp_basis == 'synchronised-uptime-estimate');
count = length(f.sent); f.app.send(); check('time-fix-does-not-duplicate-reports', count == length(f.sent));
f = fixture('clock-unsync'); f.app.collect(); f.online = true; f.clock_synced = false;
check('loss-of-clock-sync-keeps-queue-pending', f.app.send() == 0 && f.app.state().events[0].delivery == 'pending');
f.clock_synced = true; f.app.send();
check('verified-collection-time-preserved', f.sent[0].params.date == 1791016870 && f.sent[0].params.info[0].timestamp_basis == 'synchronised-collection-time');
f = fixture('legacy-clock'); f.app.collect(); let legacy = f.app.state();
delete legacy.events[0].clock_verified; delete legacy.events[0].observed_boot_id;
legacy.events[0].date -= 35000; fs.writefile(f.p.state, sprintf('%J', legacy));
f.now += 200; fs.writefile(f.p.uptime, '300.0 0'); f.online = true; f.app.send();
check('pending-legacy-boot-date-corrected-with-same-boot-anchor', f.sent[0].params.date == 1791016870);
f = fixture('clock-other-boot'); f.clock_synced = false; f.app.collect(); reboot(f);
f.now = 1791050000; f.clock_synced = true; f.online = true; f.app.send();
check('old-boot-without-anchor-uses-labelled-upload-time', f.sent[0].params.date == f.now && f.sent[0].params.info[0].timestamp_basis == 'upload-time');
f = fixture('clock-retry'); f.clock_synced = false; f.app.collect();
f.clock_synced = true; f.now += 500; fs.writefile(f.p.uptime, '200.0 0'); f.online = true; f.accepted = false; f.app.send();
let corrected_date = f.app.state().events[0].date;
f.now += 100; fs.writefile(f.p.uptime, '300.0 0'); f.accepted = true; f.app.send();
check('corrected-time-durable-across-send-retry', f.app.state().events[0].date == corrected_date && f.sent[1].params.date == corrected_date);
print(sprintf('%J\n', { passed: true, count: length(results), cases: results, synthetic: 'TEST-only private filesystem/clock/transport/reset-cause fixtures; no AP or controller access', directory: base }));
