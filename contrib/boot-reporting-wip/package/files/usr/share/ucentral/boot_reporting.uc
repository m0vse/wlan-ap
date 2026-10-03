// Bounded overlay-backed boot history. Transport acceptance is NOT a server ACK.
import * as fs from 'fs';

function reporter(p, io) {
	let collect;
	const max_events = 8, max_state = 196608, max_dump = 16384;
	const reasons = ['controller-requested', 'user-requested', 'orderly-shutdown', 'firmware-upgrade', 'factory', 'certupdate', 'fixedconfig', 'transfer', 'confirmed-crash', 'watchdog', 'power-failure', 'unexpected-shutdown'];
	function uuid(id) { return type(id) == 'string' && !!match(id, /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/); }
	function bounded(value, size) { return type(value) == 'string' && length(value) <= size; }
	function normalized(reason) { return reason == 'upgrade' ? 'firmware-upgrade' : reason == 'kernel-crash' ? 'confirmed-crash' : reason; }
	function safe(path, dir) {
		let s = fs.lstat(path);
		return !s || (s.type == (dir ? 'directory' : 'file') && s.uid == 0 && !(s.mode & 0o077));
	}
	function read(path, limit) {
		let f = fs.open(path, 'r');
		if (!f) return null;
		let data = f.read(limit); f.close(); return data;
	}
	function boot_id() {
		let id = trim(read(p.boot_id, 128) || '');
		if (!uuid(id)) die('No trustworthy kernel boot ID\n');
		return id;
	}
	function uptime() { return +split(read(p.uptime, 128) || '0', ' ')[0]; }
	function stamp() { let t = io.now(); return t >= 1577836800 ? t : null; }
	function state() {
		if (!safe(p.directory, true) || !safe(p.state, false)) die('Unsafe history path\n');
		let raw = read(p.state, max_state + 1);
		if (raw == null) {
			if (fs.lstat(p.state)) die('Unreadable history\n');
			return { version: 1, events: [] };
		}
		if (length(raw) > max_state) die('Oversized history\n');
		let s = json(raw);
		if (s.version != 1 || type(s.events) != 'array' || length(s.events) > max_events) die('Invalid history\n');
		if (s.boot_id != null && !uuid(s.boot_id)) die('Invalid stored boot ID\n');
		if (s.reason != null && index(reasons, s.reason) < 0) die('Invalid stored reason\n');
		if (s.intent && (!uuid(s.intent.boot_id) || index(reasons, s.intent.reason) < 0 || s.intent.uptime < 0)) die('Invalid stored intent\n');
		if (s.seen != null && (type(s.seen) != 'array' || length(s.seen) > 32 || length(filter(s.seen, key => !bounded(key, 180))))) die('Invalid captured-source ledger\n');
		for (let e in s.events) {
			if (type(e) != 'object' || !bounded(e.id, 256) || index(['pending', 'transmitted-unacknowledged'], e.delivery) < 0) die('Invalid report record\n');
			if (e.method == 'rebootLog') {
				if (!uuid(e.boot_id) || index(reasons, e.reason) < 0 || !bounded(e.firmware, 512)) die('Invalid boot report\n');
			} else if (e.method == 'crashlog') {
				if (!bounded(e.text, max_dump) || !bounded(e.source, 128) || !bounded(e.capture_key, 180)) die('Invalid kernel report\n');
			} else die('Invalid report method\n');
		}
		return s;
	}
	function save(s) {
		while (length(s.events) > max_events) { shift(s.events); s.evicted = (s.evicted || 0) + 1; }
		let raw = sprintf('%J', s);
		while (length(raw) > max_state && length(s.events) > 1) {
			shift(s.events); s.evicted = (s.evicted || 0) + 1; raw = sprintf('%J', s);
		}
		if (length(raw) > max_state) die('History bound exceeded\n');
		if (!safe(p.directory, true)) die('Unsafe history directory\n');
		if (!fs.stat(p.directory) && !fs.mkdir(p.directory, 0o700)) die('History unavailable\n');
		let tmp = p.state + '.new';
		if (!safe(tmp, false)) die('Unsafe history staging file\n');
		let f = fs.open(tmp, 'w', 0o600);
		if (!f) die('History write refused\n');
		if (!fs.chmod(tmp, 0o600)) { f.close(); die('History permissions refused\n'); }
		let n = f.write(raw), flushed = f.flush(), closed = f.close();
		if (n != length(raw) || !flushed || !closed || io.sync() != 0) die('History write/sync failed\n');
		if (!io.rename(tmp, p.state) || io.sync() != 0) die('History commit failed\n');
	}
	function locked(fn) {
		if (!safe(p.lock, false)) die('Unsafe history lock\n');
		let lock = fs.open(p.lock, 'a', 0o600);
		if (!lock) die('History lock unavailable\n');
		let acquired = false;
		for (let n = 0; n < 20; n++) {
			if (lock.lock('xn')) { acquired = true; break; }
			sleep(50);
		}
		if (!acquired) { lock.close(); die('History busy\n'); }
		try { let result = fn(); lock.close(); return result; }
		catch (e) { lock.close(); die(e); }
	}
	function priority(reason) { return reason == 'orderly-shutdown' ? 1 : reason == 'user-requested' ? 2 : 3; }
	function plan(reason) {
		reason = normalized(reason);
		const allowed = ['controller-requested', 'user-requested', 'orderly-shutdown', 'firmware-upgrade', 'factory', 'certupdate', 'fixedconfig', 'transfer'];
		if (index(allowed, reason) < 0) die('Invalid reboot intent\n');
		// Ensure a first-ever request has a trustworthy previous-boot observation.
		collect();
		return locked(function() {
			let s = state(), id = boot_id(), up = uptime();
			let previous = s.intent;
			if (previous && previous.boot_id == id && up >= previous.uptime && up - previous.uptime <= 120 && priority(previous.reason) > priority(reason)) return false;
			s.intent = { boot_id: id, reason, uptime: up, date: stamp() };
			save(s); return true;
		});
	}
	function cancel(reason) {
		reason = normalized(reason);
		return locked(function() {
			let s = state();
			if (s.intent && s.intent.boot_id == boot_id() && s.intent.reason == reason) { delete s.intent; save(s); }
			return true;
		});
	}
	function fingerprint(text) {
		// Identity of bounded captured text only, not a security/authentication hash.
		let h = 2166136261;
		for (let i = 0; i < length(text); i++) h = ((h ^ ord(substr(text, i, 1))) * 16777619) & 0xffffffff;
		return sprintf('%08x:%d', h, length(text));
	}
	collect = function() {
		return locked(function() {
			let s = state(), id = boot_id(), changed = false, captured = [];
			let crash = false;
			let directory = fs.opendir(p.pstore);
			for (let n = 0; directory && n < 34; n++) {
				let name = directory.read(); if (name == null) break;
				if (!match(name, /^dmesg-[a-zA-Z0-9_-]+$/)) continue;
				let src = p.pstore + '/' + name, meta = fs.lstat(src);
				if (!meta || meta.type != 'file') continue;
				let raw = read(src, max_dump);
				if (!raw) continue;
				let text = replace(raw, /[^\x09\x0a\x0d\x20-\x7e]/g, '?');
				let key = name + ':' + fingerprint(text);
				let existing = filter(s.events, e => e.capture_key == key && e.text == text);
				if (!length(existing) && index(s.seen || [], key) < 0) {
					let panic = !!match(text, /Kernel panic -|Kernel panic:/);
					let fault = !!match(text, /Oops:|BUG:/);
					let event = { id: id + ':dump:' + key, method: 'crashlog', date: stamp(), source: name,
						capture_key: key, classification: panic ? 'kernel-panic' : fault ? 'kernel-fault' : 'kernel-dump',
						truncated: meta.size > length(raw), sanitized: text != raw, text, delivery: 'pending' };
					push(s.events, event); changed = true;
					s.seen = s.seen || []; push(s.seen, key); while (length(s.seen) > 32) shift(s.seen);
					crash = crash || panic;
				}
				push(captured, { src, key, text, complete: meta.size <= length(raw) && text == raw });
			}
			if (directory) directory.close();
			if (s.boot_id != id) {
				let intent = s.intent, cause = io.reset_cause();
				let reason = 'unexpected-shutdown';
				let evidence = null;
				if (cause && index(['watchdog', 'power-failure', 'confirmed-crash', 'kernel-crash'], cause.reason) >= 0 && type(cause.source) == 'string' && length(cause.source)) {
					reason = normalized(cause.reason); evidence = { reason, source: substr(cause.source, 0, 160), detail: type(cause.detail) == 'string' ? substr(cause.detail, 0, 512) : '' };
				} else if (crash) reason = 'confirmed-crash';
				else if (intent && intent.boot_id == s.boot_id) {
					// Intent is evidence of a request, never proof of the hardware reset cause.
					let now = stamp();
					if (!now || !intent.date || (now >= intent.date && now - intent.date <= 300)) reason = intent.reason;
				}
				push(s.events, { id: id + ':boot', method: 'rebootLog', reason, date: stamp(), boot_id: id,
					initial_observation: !s.boot_id, previous_intent: intent || null, reset_evidence: evidence,
					firmware: trim(read(p.version, 512) || ''), observed_uptime: uptime(), delivery: 'pending' });
				s.boot_id = id; s.reason = reason; delete s.intent; changed = true;
			} else {
				// Expire abandoned requests even when there is no usable wall clock.
				if (s.intent && s.intent.boot_id == id && uptime() - s.intent.uptime > 300) { delete s.intent; changed = true; }
				if (crash && s.reason == 'unexpected-shutdown') {
					s.reason = 'confirmed-crash';
					for (let e in s.events) if (e.id == id + ':boot') { e.reason = s.reason; e.late_kernel_evidence = true; }
					changed = true;
				}
			}
			if (changed) save(s);
			// Never consume persistent kernel evidence until its private durable copy committed.
			for (let c in captured)
				if (c.complete && length(filter(s.events, e => e.capture_key == c.key && e.text == c.text))) io.unlink(c.src);
			if (!safe(p.cause, false)) die('Unsafe boot cause path\n');
			if (!fs.writefile(p.cause, s.reason || 'unexpected-shutdown') || !fs.chmod(p.cause, 0o600)) die('Cannot store private boot cause\n');
			return s;
		});
	};
	function send() {
		return locked(function() {
			let s = state(), sent = 0;
			if (!io.connected()) return 0;
			for (let event in s.events) {
				if (event.delivery != 'pending') continue;
				let details = { report_id: event.id, source: event.source || 'kernel-boot-id',
					classification: event.classification, initial_observation: event.initial_observation,
					previous_intent: event.previous_intent, reset_evidence: event.reset_evidence,
					firmware: event.firmware, observed_uptime: event.observed_uptime, truncated: event.truncated,
					late_kernel_evidence: event.late_kernel_evidence,
					sanitized: event.sanitized, evicted_local_reports: s.evicted || 0,
					timestamp_basis: event.date ? 'collection-time' : 'upload-time', delivery: 'no-server-ack' };
				let params = event.method == 'crashlog' ? { loglines: [sprintf('OpenWiFi kernel dump %J', details), event.text] } :
					{ type: event.reason, date: event.date || io.now(), info: [details] };
				if (!io.send({ method: event.method, params })) break;
				event.delivery = 'transmitted-unacknowledged'; event.transmitted_at = stamp();
				// Retain local history; do not automatically duplicate successfully written notifications.
				save(s); sent++;
			}
			return sent;
		});
	}
	return { collect, plan, cancel, send, state };
}
export { reporter };
