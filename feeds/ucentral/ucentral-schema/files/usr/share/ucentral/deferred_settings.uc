// Shared accepted-but-not-applied settings. The backend owns trusted I/O and
// hardware checks; adapters may describe changes, never run a family RPC.
const DEFERRED_EXIT = 75;

function status(record) {
	let response = { error: 0, text: 'Reboot required', reboot_required: true,
		pending: record.changes, applied: false };
	for (let change in record.changes) {
		if (change.setting == 'topology') {
			response.active_topology = change.active;
			response.desired_topology = change.desired;
		}
		if (change.setting == 'country') {
			response.active_country = change.active;
			response.desired_country = change.desired;
		}
	}
	return response;
}

function country(document) {
	let selected;
	for (let radio in document.radios || []) {
		if (!radio.country || radio.country == '00') continue;
		assert(type(radio.country) == 'string' && match(radio.country, /^[A-Z]{2}$/),
		       'Invalid radio country');
		assert(!selected || selected == radio.country, 'Conflicting radio countries');
		selected = radio.country;
	}
	return selected;
}

function binding(context) {
	return { board: context.board, serial: context.serial, bank: context.bank,
		spki: context.spki || null, job: context.job || null };
}

function same(left, right) { return sprintf('%J', left) == sprintf('%J', right); }

function create(io) {
	function authorize_country(wanted, context) {
		assert(type(wanted) == 'string' && match(wanted, /^[A-Z]{2}$/) &&
		       wanted in require('deferred_countries').codes && type(context.country_codes) == 'array' &&
		       wanted in context.country_codes, 'Country is not authorized by hardware policy');
		assert(context.restricted_countries == null || type(context.restricted_countries) == 'array' &&
		       wanted in context.restricted_countries, 'Country is not authorized by deployment policy');
		io.validate_country(wanted, context);
	}

	function prepare(request) {
		assert(type(request.id) == 'int' && request.id >= 0 && request.id <= 4294967295 &&
		       type(request.uuid) == 'int' && request.uuid >= 0 && request.uuid <= 4294967295,
		       'Invalid request correlation');
		let context = io.context('stage');
		let wanted = request.country || (io.country ? io.country(request.document, context) : country(request.document || {}));
		let changes = io.probe(request.document, context) || [];
		if (wanted) {
			authorize_country(wanted, context);
			if (wanted != context.active_country)
				push(changes, { setting: 'country', active: context.active_country, desired: wanted });
		}
		let previous = io.load();
		// S98 may run before NTP/readiness. A later real controller request can
		// finish readback, but never from the original request's boot.
		if (previous?.phase == 'boot-staged' && context.identity_accepted &&
		    context.boot_id != previous.accepted_boot &&
		    same(previous.binding, binding(context)) && io.readback(previous, context)) {
			previous.phase = 'active';
			io.save(previous);
		}
		// Do not silently supersede a boot transaction or another controller UUID.
		if (previous && previous.phase != 'active') {
			if (previous.phase == 'cancelled') previous = null;
		}
		if (previous && previous.phase != 'active') {
			let compatible = same(previous.binding, binding(context));
			// A still-unaccepted native job can publish its original key after
			// this journal. Retry/cancel is read-only with respect to that key;
			// only boot() after accepted closure may finish the key binding.
			if (!compatible && previous.blocked_enrollment && !previous.binding.spki &&
			    previous.binding.job && context.job == previous.binding.job)
				compatible = same({ ...previous.binding, spki: context.spki || null }, binding(context));
			assert(compatible, 'Pending settings belong to another identity');
			if (!length(changes) && previous.phase == 'accepted') {
				previous.phase = 'cancelled';
				previous.cancelled_by = request.uuid;
				io.save(previous);
				return null;
			}
			assert(previous.uuid == request.uuid && same(previous.document, request.document || null) &&
			       same(previous.changes, changes), 'Another accepted setting is awaiting reboot');
			return { ...previous, id: request.id };
		}
		if (!length(changes)) return null;
		assert(context.identity_accepted || context.job && context.installer_pending ||
		       !length(filter(changes, c => c.setting == 'country')),
		       'Country staging requires an existing identity or validated native job');
		let record = { version: 1, uuid: request.uuid, id: request.id,
			document: request.document || null, source: request.source || null,
			binding: binding(context), accepted_boot: context.boot_id,
			changes, baseline: io.baseline(), phase: 'accepted',
			country_policy: { codes: context.country_codes, restricted: context.restricted_countries || null },
			blocked_enrollment: !context.identity_accepted };
		// One authoritative durable record contains the complete accepted document.
		// No live UCI/module/store/active-symlink effect precedes this publication.
		io.save(record);
		return record;
	}

	function boot() {
		let record = io.load();
		if (!record || record.phase == 'cancelled') return record;
		if (record.phase == 'active') {
			// Completed settings are history, not an immutable bank binding.
			// A later managed upgrade uses the current validated bank's durable
			// country authority; it must not restore a prior identity snapshot.
			if (io.replay && length(filter(record.changes, c => c.setting == 'country')))
				io.replay(record, io.context('boot'));
			return record;
		}
		let context = io.context('boot');
		// A normal managed A/B upgrade already validated and restored the
		// certificate snapshot before arming this trial. Preserve accepted
		// settings only for that explicit old-confirmed -> running-target
		// transition, with the same device/key and unchanged country baseline.
		// An initial enrollment transaction is never migrated by this path.
		if (record.phase == 'accepted' && !record.blocked_enrollment && context.identity_accepted &&
		    context.layout in ['banks', 'pair'] && context.ab_state == 'trial-started' &&
		    context.target == context.bank && context.confirmed == record.binding.bank &&
		    context.bank != record.binding.bank &&
		    same({ ...record.binding, bank: context.bank }, binding(context))) {
			io.check_baseline(record.baseline);
			record.bank_transition = { source: record.binding.bank, target: context.bank };
			record.binding.bank = context.bank;
			io.save(record);
		}
		// Initial enrollment may generate its original key after the request.
		// Only the same validated, now-accepted job can complete this binding.
		if (record.blocked_enrollment && !record.binding.spki && record.binding.job &&
		    context.identity_accepted && context.job == record.binding.job &&
		    context.serial == record.binding.serial && context.bank == record.binding.bank &&
		    context.board == record.binding.board) {
			record.binding.spki = context.spki;
			io.save(record);
		}
		assert(same(record.binding, binding(context)), 'Deferred identity or bank changed');
		assert(record.accepted_boot != context.boot_id, 'Deferred settings require a new boot');
		if (!context.identity_accepted && record.blocked_enrollment) return record;
		for (let change in record.changes)
			if (change.setting == 'country') authorize_country(change.desired, context);
		// Commit is individually atomic and replayable, not a claim of multi-file
		// power-cut atomicity. Persist phase before any boot-only writes.
		if (record.phase == 'accepted') {
			io.check_baseline(record.baseline);
			record.phase = 'committing';
			io.save(record);
		}
		io.commit(record, context);
		record.blocked_enrollment = false;
		record.phase = 'boot-staged';
		io.save(record);
		return record;
	}

	function confirm() {
		let record = io.load();
		if (!record || record.phase in ['active', 'cancelled']) return record;
		let context = io.context('confirm');
		assert(same(record.binding, binding(context)), 'Deferred readback identity changed');
		assert(record.phase == 'boot-staged' && context.boot_id != record.accepted_boot,
		       'Deferred settings have not been activated at boot');
		assert(context.identity_accepted && io.readback(record, context),
		       'Deferred hardware settings have not been verified');
		record.phase = 'active';
		io.save(record);
		return record;
	}

	return { prepare, boot, confirm, state: function() {
		let record = io.load();
		let active = io.current ? io.current() : null;
		return record ? { uuid: record.uuid, id: record.id, phase: record.phase,
			changes: record.changes, active, reboot_required: !(record.phase in ['active', 'cancelled']),
			blocked_enrollment: record.blocked_enrollment } : null;
	} };
}

return { DEFERRED_EXIT, status, country, create };
