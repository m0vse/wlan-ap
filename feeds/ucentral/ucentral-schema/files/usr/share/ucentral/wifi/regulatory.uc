// Hardware capabilities are not authority to transmit under the current country.
// All queries are read-only. Never substitute a global regdomain for a self-managed PHY.
function channel(freq) {
	if (freq == 2484) return 14;
	if (freq >= 2412 && freq <= 2472) return (freq - 2407) / 5;
	if (freq >= 4910 && freq <= 4980) return (freq - 4000) / 5;
	if (freq >= 5955 && freq <= 7115) return (freq - 5950) / 5;
	if (freq >= 5160 && freq <= 5885) return (freq - 5000) / 5;
	return null;
}

export function select_frequencies(bands, wanted) {
	let out = { frequencies: [], channels: [], dfs_channels: [], ap_channels: [], ap_dfs_channels: [] };
	for (let band in bands || [])
		for (let f in band.freqs || []) {
			let ch = channel(f.freq);
			let b = f.freq < 2500 ? '2G' : f.freq < 5925 ? '5G' : '6G';
			if (f.disabled || ch == null || !(b in wanted)) continue;
			push(out.frequencies, f.freq);
			push(out.channels, ch);
			if (f.radar) push(out.dfs_channels, ch);
			// NO_IR prohibits AP initiation, except DFS channels after CAC.
			// DFS_UNAVAILABLE is 1. An unknown DFS state is not eligible.
			if (f.radar && !(f.dfs_state in [0, 2])) continue;
			if (f.no_ir && !f.radar) continue;
			push(out.ap_channels, ch);
			if (f.radar) push(out.ap_dfs_channels, ch);
		}
	for (let name in out) out[name] = uniq(sort(out[name], (a,b) => a-b));
	return out;
};

// Injectable readers allow tests without network, sysfs, UCI or AP access.
export function sample(phys, io) {
	let result = {};
	try {
		if (!io) {
			let fs = require('fs'), nl = require('nl80211');
			io = {
				list: () => nl.request(nl.const.NL80211_CMD_GET_WIPHY,
					nl.const.NLM_F_DUMP, {split_wiphy_dump:true}),
				country: (index) => nl.request(nl.const.NL80211_CMD_GET_REG, 0, {wiphy:index})?.reg_alpha2,
				readphy: (index) => nl.request(nl.const.NL80211_CMD_GET_WIPHY, 0,
					{wiphy:index, split_wiphy_dump:true}),
				paths: (path) => sort(fs.glob('/sys/devices/' + path + '/ieee80211/phy*') ||
					fs.glob('/sys/devices/platform/' + path + '/ieee80211/phy*') || []),
				now: () => int(time())
			};
		}
		let all = io.list();
		if (type(all) != 'array') return result;
		let now = io.now();
		for (let path, phy in phys || {}) {
			if (!length(phy.band) || 'HaLow' in phy.band) continue;
			let base = replace(path, /:(2G|5G|6G)$/, '');
			let suffix = match(base, /\+([0-9]+)$/);
			if (suffix) base = replace(base, /\+[0-9]+$/, '');
			let paths = io.paths(base), matches = [];
			if (suffix) paths = paths[+suffix[1]] ? [paths[+suffix[1]]] : [];
			for (let candidate in all) {
				if (!exists(candidate, 'wiphy')) continue;
				let name = 'phy' + candidate.wiphy;
				if (!length(filter(paths, p => split(p, '/')[-1] == name))) continue;
				let data = select_frequencies(candidate.wiphy_bands, phy.band);
				if (length(data.frequencies)) push(matches, {candidate, data});
			}
			// Never cross-attribute multiple same-band PHYs (Thor dual 5 GHz).
			if (length(matches) != 1) continue;
			let country = io.country(matches[0].candidate.wiphy);
			if (type(country) != 'string' || !match(country, /^[A-Z]{2}$/)) continue;
			// Bracket a fresh per-PHY frequency read with country reads. A country
			// transition must not label old-country frequencies with a new country.
			let current = io.readphy(matches[0].candidate.wiphy);
			if (!current || current.wiphy != matches[0].candidate.wiphy ||
			    io.country(current.wiphy) != country) continue;
			result[path] = { ...select_frequencies(current.wiphy_bands, phy.band), country, timestamp:now };
		}
	} catch (e) {
		// Partial or failed reads do not establish a coherent snapshot.
		return {};
	}
	return result;
};

export function telemetry(entry, configured_country) {
	if (!entry || entry.country != configured_country) return null;
	return { country:entry.country, timestamp:entry.timestamp,
		channels:entry.ap_channels, dfs_channels:entry.ap_dfs_channels };
};

export function intersect_phys(phys, radios, default_country, live, interfaces) {
	for (let path, phy in phys || {}) {
		let entry = live[path];
		if (!entry) continue;
		let requested = filter(radios || [], r => r.band in phy.band ||
			(r.band in ['5G-lower','5G-upper'] && '5G' in phy.band));
		if (!length(requested) || length(filter(requested,
			r => (r.country || default_country) != entry.country))) continue;
		// Only the settled matching-country snapshot filters rendering. This
		// does not alter static capabilities or assert a country has been applied.
		let station = false;
		for (let iface in interfaces || [])
			for (let ssid in iface.ssids || [])
				if (ssid.bss_mode in ['sta','wds-sta','wds-repeater'] &&
				    length(filter(ssid.wifi_bands || [], b => b in phy.band ||
					(b in ['5G-lower','5G-upper'] && '5G' in phy.band))))
					station = true;
		let channels = station ? entry.channels : entry.ap_channels;
		let dfs = station ? entry.dfs_channels : entry.ap_dfs_channels;
		phy.frequencies = filter(phy.frequencies || [], f =>
			f in entry.frequencies && channel(f) in channels);
		phy.channels = filter(phy.channels || [], c => c in channels);
		phy.dfs_channels = filter(phy.dfs_channels || [], c => c in dfs);
	}
	return phys;
};
