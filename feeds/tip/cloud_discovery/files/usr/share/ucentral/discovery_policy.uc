/* DHCP supplies a destination hint, never a TLS validation policy. */
function endpoint(value) {
	if (type(value) != 'string' || !length(value))
		return null;
	let parts = split(trim(value), ':');
	if (length(parts) > 2)
		return null;
	let host = parts[0];
	if (!length(host) || length(host) > 253)
		return null;
	for (let label in split(host, '.'))
		if (!match(label, /^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/))
			return null;
	let port = parts[1] ?? '15002';
	if (!match(port, /^[1-9][0-9]{0,4}$/) || int(port) > 65535)
		return null;
	return { dhcp_server: host, dhcp_port: int(port), no_validation: false };
}

export function select_controller(opt138, opt224, policy) {
	// Option 138 is excluded: it carries unrelated controller hints.
	let selected = endpoint(opt224);
	if (policy == null)
		return selected;
	/* Malformed local policy fails closed, not back to unrestricted DHCP. */
	if (type(policy) != 'object' || type(policy.allowed) != 'array')
		return null;
	let fallback = endpoint(policy.default);
	let approved = false;
	for (let value in policy.allowed) {
		let candidate = endpoint(value);
		if (candidate && fallback && candidate.dhcp_server == fallback.dhcp_server &&
		    candidate.dhcp_port == fallback.dhcp_port)
			approved = true;
	}
	if (!approved)
		return null;
	for (let value in policy.allowed) {
		let candidate = endpoint(value);
		if (candidate && selected && candidate.dhcp_server == selected.dhcp_server &&
		    candidate.dhcp_port == selected.dhcp_port)
			return selected;
	}
	fallback.dhcp_policy_rejected = !!selected;
	fallback.dhcp_source = 'policy-default';
	return fallback;
};
