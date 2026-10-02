import { select_controller } from '../files/usr/share/ucentral/discovery_policy.uc';
let policy = { default: 'openwifi.shinesystems.co.uk:15002', allowed: ['openwifi.shinesystems.co.uk:15002'] };
let count = 0;
function check(a, b, p, host, port) {
	let result = select_controller(a, b, p);
	if (host == null ? result != null : (!result || result.dhcp_server != host || result.dhcp_port != port || result.no_validation != false))
		die(sprintf('Unexpected selection: %J\n', result));
	count++;
}
check(null, 'openwifi.shinesystems.co.uk', policy, 'openwifi.shinesystems.co.uk', 15002);
check('192.0.2.1', 'openwifi.shinesystems.co.uk:15002', policy, 'openwifi.shinesystems.co.uk', 15002);
check(null, null, policy, 'openwifi.shinesystems.co.uk', 15002);
check(null, 'attacker.example:15002', policy, 'openwifi.shinesystems.co.uk', 15002);
for (let value in ['https://openwifi.shinesystems.co.uk', 'x:0', 'x:65536', 'x:bad', 'x:22:33', '-x:22', 'x..y:22', 'x/path:22', 'x:']) {
	check(null, value, null, null, null);
	check(null, value, policy, 'openwifi.shinesystems.co.uk', 15002);
}
check('192.0.2.1', null, null, '192.0.2.1', 15002);
check('192.0.2.1', 'controller.example:22', null, 'controller.example', 22);
check(null, 'openwifi.shinesystems.co.uk', {}, null, null);
check(null, 'openwifi.shinesystems.co.uk', {default: 'other.example', allowed: policy.allowed}, null, null);
printf('%d discovery policy cases passed\n', count);
