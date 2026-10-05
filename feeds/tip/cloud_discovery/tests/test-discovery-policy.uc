import { select_controller } from '../files/usr/share/ucentral/discovery_policy.uc';
let policy = { default: 'fallback.example:15002', allowed: ['fallback.example:15002'] };
let count = 0;
function check(a, b, p, host, port) {
	let result = select_controller(a, b, p);
	if (host == null ? result != null : (!result || result.dhcp_server != host || result.dhcp_port != port || result.no_validation != false))
		die(sprintf('Unexpected selection: %J\n', result));
	count++;
}
check(null, 'fallback.example', policy, 'fallback.example', 15002);
check('192.0.2.1', 'fallback.example:15002', policy, 'fallback.example', 15002);
check(null, null, policy, 'fallback.example', 15002);
check(null, 'attacker.example:15002', policy, 'fallback.example', 15002);
for (let value in ['https://fallback.example', 'x:0', 'x:65536', 'x:bad', 'x:22:33', '-x:22', 'x..y:22', 'x/path:22', 'x:']) {
	check(null, value, null, null, null);
	check(null, value, policy, 'fallback.example', 15002);
}
check('192.0.2.1', null, null, null, null);
check('192.0.2.1', 'controller.example:22', null, 'controller.example', 22);
check(null, 'fallback.example', {}, null, null);
check(null, 'fallback.example', {default: 'other.example', allowed: policy.allowed}, null, null);
let fallback={mode:'default',default:'fallback.example:15002'};
check('ignored.example','other.example:16000',fallback,'other.example',16000);
check('ignored.example',null,fallback,'fallback.example',15002);
check(null,'https://bad/path',fallback,'fallback.example',15002);
printf('%d discovery policy cases passed\n', count);
