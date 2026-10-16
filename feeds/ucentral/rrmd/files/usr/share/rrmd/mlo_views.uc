// Logical BSS views never replace real hostapd transport interface names.
// Reuse the qualified state/health identity proof; do not equate link/radio IDs.
function mac(value) {
	return type(value) == 'string' && match(value, /^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$/) ? lc(value) : null;
}

function candidates(config, interfaces) {
	let result = {};
	for (let dev, row in interfaces) if (exists(row, 'mlo_links')) result[dev] = [];
	for (let section, s in config || {}) {
		if (s?.['.type'] != 'wifi-iface' || !s.mld || s.disabled == '1' ||
		    (s.mode && s.mode != 'ap') || s.ifname != s.mld || !interfaces[s.ifname])
			continue;
		result[s.ifname] = [];
	}
	return result;
}

function collect(interfaces, config, io) {
	let result = candidates(config, interfaces);
	if (!length(result)) return result;
	let roots = [], statuses = {};
	for (let dev in result) {
		let raw = io.interface(dev);
		if (type(raw) != 'object' || raw.ifname != dev || type(raw.mlo_links) != 'array') continue;
		let ids = {}, addresses = {}, valid = true;
		for (let link in raw.mlo_links) {
			let address = mac(link?.mac);
			if (!address || type(link.link_id) != 'int' || link.link_id < 0 || link.link_id > 15 ||
			    exists(ids, '' + link.link_id) || exists(addresses, address)) { valid = false; break; }
			ids['' + link.link_id] = true; addresses[address] = true;
		}
		if (valid) push(roots, raw);
	}
	if (!length(roots)) return result;
	let health = io.health;
	if (!health) {
		try { health = require('/usr/share/ucentral/mlo_health.uc'); }
		catch (e) { return result; }
	}
	let read_status = (dev, id) => {
		let key = dev + ':' + id;
		if (exists(statuses, key)) return statuses[key];
		let fields;
		if (io.status) fields = io.status(dev, id);
		else {
			if (!match(dev, /^[A-Za-z0-9_.:-]{1,15}$/) || type(id) != 'int' || id < 0 || id > 15) return null;
			let p = require('fs').popen('/usr/libexec/timeout-coreutils -s KILL 2 /usr/sbin/hostapd_cli -p /var/run/hostapd -i ' + dev + '_link' + id + ' status 2>/dev/null', 'r');
			if (p) { let text = p.read(16385), rc = p.close(); if (rc == 0) fields = health.fields(text); }
		}
		statuses[key] = fields;
		return fields;
	};
	let proof = health.collect(config, read_status, roots, io.phy_index, io.radio_phy);
	let seen = {}, ambiguous = {};
	for (let section, view in proof.links) {
		if (!view.ready || !exists(result, view.ifname)) continue;
		let root = filter(roots, r => r.ifname == view.ifname)[0];
		let link = filter(root.mlo_links, l => l.link_id == view.link_id)[0];
		let fields = statuses[view.ifname + ':' + view.link_id];
		if (!match(fields?.channel || '', /^[0-9]{1,3}$/) || +fields.channel < 1 || +fields.channel > 233) continue;
		let bssid = mac(view.bssid);
		if (!bssid) continue;
		if (seen[bssid]) { ambiguous[view.ifname] = true; ambiguous[seen[bssid]] = true; continue; }
		seen[bssid] = view.ifname;
		let row = {
			ifname: view.ifname, mlo_link_id: view.link_id, mld_address: mac(root.mac),
			bssid, ssid: config[section].ssid, uci_section: section,
			device: config[section].device, radio_index: view.radio_index,
			phy: view.phy + '.' + view.radio_index, physical_phy: view.phy, wiphy: root.wiphy,
			virtual_phys: true, freq: view.frequency, channel: +fields.channel,
			band: view.frequency < 2500 ? '2G' : view.frequency < 5925 ? '5G' : '6G',
			config: io.config ? io.config(section) : {},
			wiphy_tx_power_level: link.wiphy_tx_power_level ?? null,
			channel_width: link.channel_width ?? null,
		};
		if (match(fields.op_class || '', /^[0-9]{1,3}$/) && +fields.op_class > 0 && +fields.op_class <= 255)
			row.op_class = +fields.op_class;
		// A shared ubus object may only answer for one link. Never copy its
		// cached neighbor report to another link, or label stale data fresh.
		if (io.neighbor_report) {
			let own = io.neighbor_report(row);
			if (type(own) == 'array' && length(own) == 3 && mac(own[0]) == bssid &&
			    own[1] == row.ssid && type(own[2]) == 'string') row.rrm_nr = own;
		}
		push(result[view.ifname], row);
	}
	for (let dev in result) {
		if (ambiguous[dev]) result[dev] = [];
		else sort(result[dev], (a, b) => a.mlo_link_id - b.mlo_link_id);
	}
	return result;
}

function bsses(interfaces, links) {
	let result = {};
	for (let dev, parent in interfaces) {
		let rows = exists(links, dev) ? links[dev] : [{ ...parent, ifname: dev }];
		for (let row in rows) if (mac(row.bssid)) result[lc(row.bssid)] = row;
	}
	return result;
}

function event(row) {
	let payload = {};
	for (let key in ['bssid', 'ssid', 'freq', 'channel', 'op_class', 'rrm_nr'])
		if (exists(row, key)) payload[key] = row[key];
	if (row.mlo_link_id != null)
		for (let key in ['ifname', 'mlo_link_id', 'mld_address', 'phy', 'radio_index', 'uci_section', 'band']) payload[key] = row[key];
	return payload;
}

function diff(previous, current, send) {
	for (let bssid, row in previous)
		if (!current[bssid] || row.ifname != current[bssid].ifname || row.mlo_link_id !== current[bssid].mlo_link_id)
			send('rrm.bss.del', { bssid });
	for (let bssid, row in current) {
		let old = previous[bssid];
		if (!old || old.ifname != row.ifname || old.mlo_link_id !== row.mlo_link_id)
			send('rrm.bss.add', event(row));
		else if (old.freq != row.freq || old.channel != row.channel)
			send('rrm.bss.channel-switch', { bssid, freq: row.freq });
	}
}

return { candidates, collect, bsses, diff };
