// Renderer adapter: called only after validation, before any live effects.
function prepare(source, document, id) {
	let fs = require('fs');
	let board = trim(fs.readfile('/tmp/sysinfo/board_name') || '');
	// Unregistered hardware continues its existing renderer. It cannot use
	// the fixedconfig command to bypass the strict deferred storage guard.
	if (!fs.stat('/lib/functions/cambium-ab.sh') ||
	    !match(board, /^(cambium|cambiumnetworks),/)) return null;
	assert(!fs.stat('/tmp/ucentral-deferred.failed'), 'Deferred boot activation failed');
	assert(match(source, /^\/etc\/ucentral\/ucentral\.cfg\.[0-9]+$/) &&
	       type(+id) == 'int' && +id >= 0, 'Invalid deferred configuration correlation');
	// Capture the exact validated document. The native client may receive
	// another request with the same UUID and overwrite its canonical filename
	// while this renderer is running; never re-read that mutable payload.
	let directory = '/etc/ucentral/deferred-settings', parent = fs.lstat('/etc/ucentral');
	assert(parent?.type == 'directory' && parent.uid == 0 && !(parent.mode & 0022), 'Unsafe deferred parent');
	if (!fs.lstat(directory)) assert(fs.mkdir(directory, 0700), 'Cannot create deferred request directory');
	let st = fs.lstat(directory);
	assert(st?.type == 'directory' && st.uid == 0 && st.mode == 0700, 'Unsafe deferred request directory');
	let allocate = fs.popen('umask 077; mktemp ' + directory + '/request.XXXXXX');
	assert(allocate, 'Cannot allocate deferred snapshot');
	let snapshot = trim(allocate.read('all') || ''), allocated = allocate.close();
	assert(allocated == 0 && match(snapshot, /^\/etc\/ucentral\/deferred-settings\/request\.[A-Za-z0-9]+$/), 'Invalid deferred snapshot');
	st = fs.lstat(snapshot);
	assert(st?.type == 'file' && st.uid == 0 && st.mode == 0600 && st.nlink == 1 && st.size == 0, 'Unsafe deferred snapshot');
	try {
		let text = sprintf('%J\n', document), file = fs.open(snapshot, 'w', 0600);
		assert(length(text) <= 262144 && file && file.write(text) == length(text) &&
		       file.flush() && file.close(), 'Cannot capture accepted document');
		let pipe = fs.popen('/usr/libexec/ucentral-deferred stage-config ' + source + ' ' + +id + ' ' + snapshot);
		assert(pipe, 'Cannot prepare deferred configuration');
		let response = json(pipe.read('all') || 'null'), rc = pipe.close();
		assert(rc == 0 && (!response || response.uuid == document.uuid && response.id == +id), 'Deferred configuration was not accepted');
		assert(fs.unlink(snapshot), 'Cannot remove deferred snapshot');
		return response;
	} catch (e) {
		fs.unlink(snapshot);
		die('Deferred configuration was not accepted');
	}
}

return { prepare };
