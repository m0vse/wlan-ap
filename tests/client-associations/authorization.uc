import { station_authorized } from './wifi/station_authorization.uc';
let cases = [
	[[254, 174], true], [[254, 172], false], [[2, 0], false],
	[[2, 2], true], [[0, 2], null], [[252, 172], null],
	[null, null], [[], null], [[2], null], [['2', 2], null],
	[[2, '2'], null], [[-2, 2], null]
];
for (let c in cases)
	if (station_authorized(c[0]) !== c[1])
		die(sprintf('FAIL: %J\n', c));
print('PASS: 12 authorization flag mask, false, unknown and malformed cases\n');
