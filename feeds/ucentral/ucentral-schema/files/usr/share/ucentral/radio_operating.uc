// Read-only operating-state verification. Never scan, reconfigure or recover radios.
import * as fs from 'fs';
let mlo = require('mlo_health');

function number(value) {
	if (type(value) == 'int' || type(value) == 'double') return value;
	return type(value) == 'string' && match(value, /^-?[0-9]+(\.[0-9]+)?$/) ? +value : null;
}
function channel(freq) {
	if (freq == 2484) return 14;
	if (freq == 5935) return 2;
	if (freq >= 2412 && freq <= 2472 && (freq - 2407) % 5 == 0) return (freq - 2407) / 5;
	if (freq >= 4910 && freq <= 4980 && freq % 5 == 0) return (freq - 4000) / 5;
	if (freq >= 5000 && freq < 5925 && freq % 5 == 0) return (freq - 5000) / 5;
	if (freq >= 5955 && freq <= 7115 && (freq - 5950) % 5 == 0) return (freq - 5950) / 5;
	return null;
}
function query(ifname, link_id) {
	if (!match(ifname || '', /^[A-Za-z0-9_.:-]{1,15}$/)) return null;
	if (link_id != null) {
		if (type(link_id) != 'int' || link_id < 0 || link_id > 15) return null;
		ifname += '_link' + link_id;
	}
	let p = fs.popen('/usr/libexec/timeout-coreutils -s KILL 2 /usr/sbin/hostapd_cli -p /var/run/hostapd -i ' + ifname + ' status 2>/dev/null', 'r');
	if (!p) return null;
	let text = p.read(16385), rc = p.close();
	return rc == 0 ? mlo.fields(text) : null;
}
function driver(phy, io) {
	io ??= fs;
	if (!match(phy || '', /^phy[0-9]+$/)) return { source: 'kernel', confirmed: false };
	let path = io.readlink('/sys/class/ieee80211/' + phy + '/device/driver');
	let name = path ? split(path, '/')[-1] : '';
	for (let module in ['ath12k', 'ath11k']) {
		if (!wildcard(name, module + '*')) continue;
		let marker = io.readfile('/sys/module/' + module + '/parameters/txpower_readback_strict');
		if (trim(marker || '') != 'Y') return { source: 'kernel', confirmed: false };
		return { source: 'firmware', confirmed: true, max_age_ms: module == 'ath12k' ? 5000 : 0 };
	}
	// Older drivers may report only their accepted/configured limit, not RF power.
	return { source: 'driver_limit', confirmed: false };
}
function host_width(status) {
	let value = status.ieee80211be == '1' ? number(status.eht_oper_chwidth) : null;
	if (value == null && status.ieee80211ax == '1') value = number(status.he_oper_chwidth);
	if (value == null && status.ieee80211ac == '1') value = number(status.vht_oper_chwidth);
	if (value == 1) return '80';
	if (value == 2) return '160';
	if (value == 3) return '80p80';
	if (value == 9) return '320';
	if (value == null || value == 0) {
		let secondary = number(status.secondary_channel);
		return secondary == null ? null : secondary == 0 ? '20' : '40';
	}
	return null;
}
function inspect(radio, iface, observed, status, provenance) {
	let result = { status: 'unconfirmed', channel: { status: 'unconfirmed' }, width: { status: 'unconfirmed' }, power: { status: 'unconfirmed' } };
	let requested = number(iface.vif_txpower ?? radio.txpower);
	if (requested != null) result.power.requested_dbm = requested;
	if (radio.channel != null) result.channel.requested = radio.channel;
	if (radio.htmode != null) result.width.requested = radio.htmode;
	if (!observed || !status) return result;
	if (status.state == 'DFS') { result.status = 'pending'; result.reason = 'dfs_cac'; return result; }
	let freq = number(observed.wiphy_freq), actual_channel = channel(freq);
	if (status.state != 'ENABLED' || observed.mlo_link_disabled === true) { result.status = 'failed'; result.reason = 'not_enabled'; return result; }
	if (freq == 0) { result.status = 'failed'; result.reason = 'no_channel'; return result; }
	if (freq > 0 && (freq < 2400 || freq > 7200)) { result.reason = 'band_readback_unsupported'; return result; }
	if (freq != null && actual_channel != null) {
		result.channel.frequency = freq; result.channel.actual = actual_channel;
		let requested_channel = number(radio.channel);
		if (requested_channel > 0) result.channel.requested_match = requested_channel == actual_channel;
		let host_freq = number(status.freq), host_channel = number(status.channel);
		if (host_freq != null && host_channel != null)
			result.channel.status = host_freq == freq && host_channel == actual_channel ? 'confirmed' : 'mismatch';
	}
	let widths = { '0': '20', '1': '20', '2': '40', '3': '80', '4': '80p80', '5': '160', '6': '5', '7': '10', '13': '320' };
	let width = widths['' + observed.channel_width], expected = host_width(status);
	if (width != null) result.width.actual = width;
	let configured_width = match(radio.htmode || '', /^(HT|VHT|HE|EHT)(80\+80|[0-9]+)/);
	if (configured_width && width != null) result.width.requested_match = replace(configured_width[2], '+', 'p') == width;
	if (width != null && expected != null) {
		result.width.status = width == expected ? 'confirmed' : 'mismatch';
		let center = number(observed.center_freq1), span = width == '80p80' ? 80 : number(width);
		if (span >= 40 && center == null && result.width.status != 'mismatch') result.width.status = 'unconfirmed';
		if (center != null && freq != null && span != null) {
			let delta = center >= freq ? center - freq : freq - center;
			if ((span == 20 && delta != 0) || (span >= 40 && (delta < 10 || delta >= span / 2 || (delta - 10) % 20 != 0))) result.width.status = 'mismatch';
		}
		if (width == '80p80') {
			let other = number(observed.center_freq2);
			if (!(other > 0) && result.width.status != 'mismatch') result.width.status = 'unconfirmed';
			if (other > 0 && center != null && (other >= center ? other - center : center - other) <= 80) result.width.status = 'mismatch';
		}
		let key = status.ieee80211be == '1' ? 'eht' : status.ieee80211ax == '1' ? 'he' : 'vht';
		for (let pair in [['0', 'center_freq1'], ['1', 'center_freq2']]) {
			let index = number(status[key + '_oper_centr_freq_seg' + pair[0] + '_idx']);
			let center = number(observed[pair[1]]);
			if (index > 0 && center == null && result.width.status != 'mismatch') result.width.status = 'unconfirmed';
			if (index > 0 && center != null && channel(center) != index) result.width.status = 'mismatch';
		}
	}
	let power = number(observed.wiphy_tx_power_level);
	// nl80211 exports signed mBm through a u32 attribute on some kernels.
	if (power > 2147483647) power -= 4294967296;
	if (power != null && power >= -10000 && power <= 10000) {
		result.power.reported_dbm = power / 100;
		result.power.source = provenance?.source || 'kernel';
		if (provenance?.max_age_ms != null) result.power.max_age_ms = provenance.max_age_ms;
		if (provenance?.confirmed === true) {
			result.power.status = requested == null ? 'confirmed' :
				power / 100 > requested + 0.5 ? 'mismatch' :
				power / 100 < requested - 1 ? 'limited' : 'confirmed';
			if (result.power.status == 'limited') result.power.reason = 'effective_limit';
		}
	}
	let states = [result.channel.status, result.width.status, result.power.status];
	result.status = index(states, 'mismatch') >= 0 ? 'failed' : index(states, 'unconfirmed') >= 0 ? 'unconfirmed' : 'confirmed';
	return result;
}
function collect(config, runtime, proof, raw, read_status, read_driver) {
	let report = {}, cache = {};
	read_status ??= query; read_driver ??= driver;
	if (raw == null) raw = interfaces();
	for (let section, iface in config || {}) {
		let radio = config[iface.device];
		if (iface['.type'] != 'wifi-iface' || (iface.mode && iface.mode != 'ap') || iface.disabled == '1' ||
		    radio?.['.type'] != 'wifi-device' || radio.disabled == '1' || !iface.ssid) continue;
		let entries = filter(runtime?.[iface.device]?.interfaces || [], i => i.section == section);
		let entry = length(entries) == 1 ? entries[0] : null;
		let roots = filter(raw || [], i => i.ifname == entry?.ifname && i.iftype == 3 && i.ssid == iface.ssid);
		let root = length(roots) == 1 ? roots[0] : null;
		let view = proof?.links?.[section], observed = root, link_id = null, phy = root ? 'phy' + root.wiphy : null;
		if (iface.mld) {
			observed = null;
			if (view && root && view.ifname == root.ifname) {
				let links = filter(root.mlo_links || [], l => l.link_id == view.link_id && lc(l.mac || '') == view.bssid);
				if (length(links) == 1) { observed = links[0]; link_id = view.link_id; phy = view.phy; }
			}
		} else if (length(root?.mlo_links)) observed = null;
		let key = (root?.ifname || '') + ':' + (link_id ?? 'ordinary');
		if (root && observed && !exists(cache, key)) cache[key] = read_status(root.ifname, link_id);
		let status = cache[key], identity = false;
		if (status && root && observed) {
			let status_phy = match(status.phy || '', /^phy([0-9]+)(\.([0-9]+))?$/);
			if (status_phy && +status_phy[1] == root.wiphy &&
			    (radio.radio == null || status_phy[3] == null || +radio.radio == +status_phy[3])) {
				for (let name, value in status) {
					let bss = match(name, /^bss\[([0-9]+)\]$/);
					if (bss && value == root.ifname && status['ssid[' + bss[1] + ']'] == mlo.encoded_ssid(iface.ssid) &&
					    lc(status['bssid[' + bss[1] + ']'] || '') == lc(observed.mac || 'invalid')) identity = true;
				}
			}
		}
		let result = inspect(radio, iface, observed, identity ? status : null, read_driver(phy));
		result.radio = iface.device;
		if (root) result.ifname = root.ifname;
		if (link_id != null) result.link_id = link_id;
		report[section] = result;
	}
	return report;
}
function interfaces(nl) {
	try {
		nl ??= require('nl80211');
		let raw = nl.request(nl.const.NL80211_CMD_GET_INTERFACE, nl.const.NLM_F_DUMP);
		return type(raw) == 'array' ? raw : [];
	} catch(e) { return []; }
}
return { collect, inspect, channel, host_width, driver, interfaces };
