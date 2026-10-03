import * as fs from 'fs';
import { reporter } from './package/files/usr/share/ucentral/boot_reporting.uc';
let base = ARGV[0], results = [], next = 0;
const A = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', B = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
function check(name, predicate) { if (!predicate) die('FAIL ' + name + '\n'); push(results, name); }
function fixture(name) {
	let root = base + '/' + name; fs.mkdir(root, 0o700); fs.mkdir(root + '/pstore', 0o700);
	fs.writefile(root + '/boot-id', A); fs.writefile(root + '/uptime', '100.0 0'); fs.writefile(root + '/version', 'TEST-synthetic-firmware');
	let p = { directory: root + '/history', state: root + '/history/history.json', lock: root + '/lock', pstore: root + '/pstore', boot_id: root + '/boot-id', uptime: root + '/uptime', version: root + '/version', cause: root + '/cause' };
	let f = { root, p, now: 1791016870, online: false, accepted: true, sent: [], renamed: true, synced: true, cause: null, unlinks: [] };
	f.app = reporter(p, {
		now: () => f.now, sync: () => f.synced ? 0 : 1,
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
check('captured-panic-informs-boot-reason', reason(f) == 'kernel-crash');
check('crash-wire-method-loglines-not-rebootLog-crashlog', f.sent[0].method == 'crashlog' && type(f.sent[0].params.loglines) == 'array');
check('reboot-wire-has-type-date-info', f.sent[1].method == 'rebootLog' && f.sent[1].params.type == 'kernel-crash' && type(f.sent[1].params.info) == 'array');
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
f = fixture('truncated'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', long_text); f.app.collect();
check('truncated-dump-bounded-and-original-retained', length(f.app.state().events[0].text) == 16384 && f.app.state().events[0].truncated && fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('binary'); fs.writefile(f.p.pstore + '/dmesg-ramoops-0', 'TEST \x01 bytes'); f.app.collect();
check('sanitized-bytes-reported-but-original-retained', f.app.state().events[0].sanitized && fs.stat(f.p.pstore + '/dmesg-ramoops-0'));
f = fixture('many'); for (let i = 0; i < 12; i++) fs.writefile(f.p.pstore + '/dmesg-ramoops-' + i, 'TEST dump ' + i); f.app.collect();
check('queue-bounded-with-eviction-accounting', length(f.app.state().events) == 8 && f.app.state().evicted == 5);
check('pruned-dumps-not-consumed-without-retained-copy', length(fs.lsdir(f.p.pstore)) == 5);
f = fixture('symlink'); fs.symlink('/tmp', f.p.directory); let failed = false; try { f.app.collect(); } catch (e) { failed = true; }
check('unsafe-history-link-refused', failed);
print(sprintf('%J\n', { passed: true, count: length(results), cases: results, synthetic: 'TEST-only private filesystem/clock/transport/reset-cause fixtures; no AP or controller access', directory: base }));
