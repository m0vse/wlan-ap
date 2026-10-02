#!/usr/bin/ucode

import * as libubus from 'ubus';
import * as fs from 'fs';
import { select_controller } from './discovery_policy.uc';

let cmd = ARGV[0];
let ifname = getenv("interface");

if (cmd == 'deconfig' || cmd == 'release') {
	let previous = null;
	try { previous = json(fs.readfile('/tmp/cloud.json')); }
	catch (e) {}
	// A secondary DHCP client must not clear the selected lease's state.
	if (previous?.lease_interface && previous.lease_interface != ifname)
		exit(0);
	fs.writefile('/tmp/cloud.json', { lease: false, lease_interface: ifname });
	fs.unlink('/tmp/dhcp-option-138');
	fs.unlink('/tmp/dhcp-option-224');
	let ubus = libubus.connect();
	if (ubus)
		ubus.call('cloud', 'renew');
	exit(0);
}

let opt138 = fs.readfile('/tmp/dhcp-option-138');
let opt224 = fs.readfile('/tmp/dhcp-option-224');

if (cmd != 'bound' && cmd != 'renew')
	exit(0);

/*let file = fs.readfile('/etc/ucentral/gateway.json');
if (file)
	file = json(file);
file ??= {};
if (file.server && file.port && file.valid)
	exit(0);
*/

let cloud = {
	lease: true,
	lease_interface: ifname,
};
let policy_file = fs.readfile('/etc/ucentral/discovery-policy.json');
let policy = null;
if (policy_file != null) {
	try { policy = json(policy_file); }
	catch (e) { policy = {}; }
	/* Explicit JSON null is not permission to use arbitrary DHCP hints. */
	policy ??= {};
}
let selected = select_controller(opt138, opt224, policy);
if (selected)
	for (let key, value in selected)
		cloud[key] = value;
fs.writefile('/tmp/cloud.json', cloud);

if (cmd == 'renew') {
	let ubus = libubus.connect();
	if (ubus)
		ubus.call('cloud', 'renew');
}

exit(0);
