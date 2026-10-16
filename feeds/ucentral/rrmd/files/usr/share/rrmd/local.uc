let nl80211 = require("nl80211");
let def = nl80211.const;
let interfaces_subscriber;
let ucentral_subscriber;
let state = {};
let interfaces = {};
let handlers = {};
let mlo_views = require('mlo_views');
let reported_bsses = {};
let links_timer;
let last_links_refresh;
let links_refreshing = false;

function refresh_bsses(force) {
	if (links_refreshing) return;
	let now = time();
	if (!force && last_links_refresh != null && now >= last_links_refresh && now - last_links_refresh < 5) return;
	// A long-lived global UCI cursor can retain an old generated configuration.
	let config = require('uci').cursor().get_all('wireless') || {};
	let candidates = mlo_views.candidates(config, interfaces);
	if (!force && !length(candidates)) { last_links_refresh = now; return; }
	links_refreshing = true;
	let links;
	try {
		links = mlo_views.collect(interfaces, config, {
			interface: dev => nl80211.request(def.NL80211_CMD_GET_INTERFACE, 0, { dev }),
			config: section => uci.get_all('rrmd', section) || {},
			neighbor_report: row => {
				let current = global.ubus.conn.call('hostapd.' + row.ifname, 'get_status');
				if (lc(current?.bssid || '') != row.bssid || current.freq != row.freq || current.channel != row.channel) return null;
				return global.ubus.conn.call('hostapd.' + row.ifname, 'rrm_nr_get_own')?.value;
			},
		});
	} catch (e) {
		// Failed MLO proof withdraws stale links; never substitute the parent.
		links = candidates;
	}
	for (let dev in interfaces) {
		if (exists(links, dev)) interfaces[dev].mlo_links = links[dev];
		else delete interfaces[dev].mlo_links;
	}
	let previous = reported_bsses;
	reported_bsses = mlo_views.bsses(interfaces, links);
	last_links_refresh = now;
	links_refreshing = false;
	mlo_views.diff(previous, reported_bsses, (type, payload) => global.event.send(type, payload));
	if (length(candidates) && !links_timer)
		links_timer = global.uloop.timer(5000, () => {
			links_timer = null;
			refresh_bsses(true);
		});
	else if (!length(candidates) && links_timer) {
		links_timer.cancel();
		links_timer = null;
	}
}


function channel_to_freq(cur_freq, channel) {

	let band;
	if (cur_freq <= 2484)
		band = '2G';
	else if (cur_freq <= 5885)
		band = '5G';
	else
		band = '6G';

	if (band == '2G' && channel >= 1 && channel <= 13)
		return 2407 + channel * 5;
	else if (band == '2G' && channel == 14)
		return 2484;
	else if (band == '5G' && channel >= 7 && channel <= 177)
		return 5000 + channel * 5;
	else if (band == '5G' && channel >= 183 && channel <= 196)
		return 4000 + channel * 5;
        else if (band == '6G' && channel >= 5)
                return 5950 + channel * 5; 
	else if (band == '60G' && channel >= 1 && channel <= 6)
		return 56160 + channel * 2160;

       return null;
}

function freq2band(freq) {
	if (freq < 2500) {
		return "2G";
	} else if (freq <= 5885) {
		return "5G";
	} else if (freq < 7115){
		return "6G";
	}
	return "na"
}

function channel_survey(dev) {
	/* trigger the nl80211 call that gathers channel survey data */
	let res = nl80211.request(def.NL80211_CMD_GET_SURVEY, def.NLM_F_DUMP, { dev });

	if (!res) {
		ulog_err(sprintf('failed to update survey for %s', dev));
		return;
	}

	/* iterate over the result and filter out the correct channel */
	for (let survey in res) {
		if (survey?.survey_info?.frequency != interfaces[dev].freq)
			continue;
		if (survey.survey_info.noise)
			interfaces[dev].noise = survey.survey_info.noise;
		if (survey.survey_info.time && survey.survey_info.busy) {
			let time = survey.survey_info.time - (state[dev].time || 0);
			let busy = survey.survey_info.busy - (state[dev].busy || 0);
			state[dev].time = survey.survey_info.time;
			state[dev].busy = survey.survey_info.busy;

			let load = (100 * busy) / time;
			if (interfaces[dev].load)
				interfaces[dev].load = 0.85 * interfaces[dev].load + 0.15 * load;
			else
				interfaces[dev].load = load;
		}
	}
}

function interfaces_update() {
	/* todo: prefilter frequency */
	for (let key in state)
		channel_survey(key);
	return 5000;
}

let prev_station = {};
let stations_stats;
stations_stats = {
	run: function() {
		if (+global.config.station_stats_interval)
			this.timer = global.uloop.timer(+global.config.station_stats_interval, stations_stats.run);
		let stations = { };
		let next_stations = { };

		for (let iface in interfaces) {
			let clients = global.ubus.conn.call('hostapd.' + iface, 'get_clients');
			for (let k, v in clients?.clients) {
				stations[k] =  {};
				next_stations[k] =  {};
				for (let val in [ 'bytes', 'airtime', 'packets', ])
					if (v[val]) {
						stations[k][val] = v[val];
						next_stations[k][val] = v[val];
						if (prev_station[k])
							for (let type in [ 'tx', 'rx' ])
								stations[k][val][type] -= prev_station[k][val][type];

					}
				for (let val in [ 'rate', 'mcs', 'signal', 'signal_mgmt', 'retries', 'failed', ])
					stations[k][val] = v[val];
				if (global.station.stations[k]) {
					stations[k].bssid = global.station.stations[k].bssid;
					stations[k].ssid = global.station.stations[k].ssid;
				}
			}
		}
		prev_station = next_stations;
		global.event.send('rrm.stations', stations);
	}
};

function interfaces_subunsub(path, sub) {
	/* check if this is a hostapd instance */
	let prefix = 'hostapd.';
	if (substr(path, 0, length(prefix)) != prefix)
		return;
	let name = substr(path, length(prefix));

	ulog_info(sprintf('%s %s\n', sub ? 'add' : 'remove', path));

	/* the hostapd instance disappeared */
	if (!sub) {
		global.neighbor.local_del(name);
		delete interfaces[name];
		delete state[name];
		refresh_bsses(true);
		return;
	}

	/* gather initial data from hostapd */
	let status = global.ubus.conn.call(path, 'get_status');
	if (!status)
		return;

	let cfg = uci.get_all('rrmd', status.uci_section);
	if (!cfg)
		cfg = {};

	/* subscibe to hostapd */
	if (!interfaces[name]) interfaces_subscriber.subscribe(path);

	/* tell hostapd to wait for a reply before answering probe requests */
	//global.ubus.conn.call(path, 'notify_response', { 'notify_response': 1 });

	/* tell hostapd to enable rrm/roaming */
	global.ubus.conn.call(path, 'bss_mgmt_enable', { 'neighbor_report': 1, 'beacon_report': 1, 'bss_transition': 1 });

	/* instantiate state */
	interfaces[name] = { };
	state[name] = { };

	for (let prop in [ 'ssid', 'bssid', 'freq', 'channel', 'op_class', 'uci_section' ])
		if (status[prop])
			interfaces[name][prop] = status[prop];
	interfaces[name].config = cfg;
	interfaces[name].phy = status.phy;
	interfaces[name].virtual_phys = length(split(status.phy, ".")) > 1 ? true : false;
	interfaces[name].band = freq2band(status?.freq);

	/* ask hostapd for the local neighbourhood report data */
	let rrm = global.ubus.conn.call(path, 'rrm_nr_get_own');
	if (rrm && rrm.value) {
		interfaces[name].rrm_nr = rrm.value;
		global.neighbor.local_add(name, rrm.value);
	}

	global.neighbor.update();
	
	/* trigger an initial channel survey */
	//channel_survey(name);

	/* Publish proven per-BSSID views, not one parent row for an MLD. */
	refresh_bsses(true);

	/* tell the scanning code about the device */
	global.scan.add_wdev(name, status.phy); 
}

function ucentral_subunsub(sub) {
	if (!sub)
		return;
	ucentral_subscriber.subscribe('ucentral');
}

function interfaces_listener(event, msg) {
	interfaces_subunsub(msg.path, event == 'ubus.object.add');

	if (msg.path == 'ucentral')
		ucentral_subunsub(event == 'ubus.object.add');
}

function interfaces_handle_event(req) {
	/* iterate over all handlers for this event type, if 1 or more handlers replied with false, do not reply to the notification */
	let reply = true;
	for (let handler in handlers[req.type])
		if (!handler(req.type, req.data))
			reply = false;
	if (!reply)
		return;
	req.reply();
}

function ucentral_handle_event(req) {
	printf('%.J\n', req);
}

function channel_switch_handler(type, data) {
	if (length(filter(values(reported_bsses), row => row.mlo_link_id != null && row.bssid == lc(data.bssid || '')))) {
		refresh_bsses(true);
		return;
	}
	global.event.send('rrm.bss.channel-switch', { bssid: data.bssid, freq: data.freq });
}


// Resolve power operations from one fresh interface snapshot per candidate.
// Cached hostapd status may expose only one BSSID of an MLO interface.
function resolve_power_target(bssid) {
	if (type(bssid) != 'string' || !match(lc(bssid), /^[0-9a-f]{2}(:[0-9a-f]{2}){5}$/))
		return null;
	bssid = lc(bssid);
	let matches = [];
	for (let dev, cached in interfaces) {
		let current = global.nl80211.request(global.nl80211.const.NL80211_CMD_GET_INTERFACE, 0, { dev });
		if (type(current) != 'object')
			continue;
		if (exists(current, 'mlo_links')) {
			if (type(current.mlo_links) != 'array')
				return null;
			for (let link in current.mlo_links) {
				if (type(link) != 'object' || type(link.mac) != 'string')
					return null;
				if (lc(link.mac || '') != bssid)
					continue;
				if (type(link.link_id) != 'int' || link.link_id < 0 || link.link_id > 15)
					return null;
				push(matches, { dev, mlo_link_id: link.link_id,
					wiphy_tx_power_level: link.wiphy_tx_power_level });
			}
		} else if (lc(current.mac || '') == bssid) {
			push(matches, { dev, wiphy_tx_power_level: current.wiphy_tx_power_level });
		}
	}
	return length(matches) == 1 ? matches[0] : null;
}

return {
	interfaces,

	status: function() {
		refresh_bsses(false);
		return interfaces;
	},

	bsses: function() {
		refresh_bsses(false);
		return reported_bsses;
	},

	init: function() {
		interfaces_subscriber = global.ubus.conn.subscriber(
			interfaces_handle_event,
			function(msg) {	});
		ucentral_subscriber = global.ubus.conn.subscriber(
			ucentral_handle_event,
			function(msg) { });

		/* register a callback that will monitor hostapd instances spawning and disappearing */
		global.ubus.conn.listener('ubus.object.add', interfaces_listener);
		global.ubus.conn.listener('ubus.object.remove', interfaces_listener);

		/* iterade over all existing hostapd instances and subscribe to them */
		for (let path in global.ubus.conn.list()) {
			interfaces_subunsub(path, true);
			if (path == 'ucentral')
				ucentral_subunsub(true);
		}

//		uloop_timeout(interfaces_update, 5000);
		global.local.register_handler('channel-switch', channel_switch_handler);

		refresh_bsses(false);
	},

	register_handler: function(event, handler) {
		/* a policy requested to be notified of action frames, register the callback */
		handlers[event] ??= [];
		push(handlers[event], handler);
	},

	switch_chan: function(msg) {
		if (!msg.bssid || !msg.channel)
			return false;
		// hostapd's shared ubus switch_chan cannot select an MLO link.
		let target = resolve_power_target(msg.bssid);
		if (!target || target.mlo_link_id != null) return false;
		for (let bss, v in interfaces) {
			if (v.bssid != lc(msg.bssid))
				continue;
			if (exists(v, 'mlo_links')) return false;
			return global.ubus.conn.call('hostapd.' + bss, 'switch_chan', {
				freq: channel_to_freq(v.freq, msg.channel),
				bcn_count: 10
			}) == null;
		}
		return false;
	},

	bssid_to_phy: function(bssid) {
		refresh_bsses(false);
		let row = reported_bsses[lc(bssid || '')];
		if (!row) return -1;
		if (row.mlo_link_id != null) return row.wiphy;
		let iface = nl80211.request(def.NL80211_CMD_GET_INTERFACE, 0, { dev: row.ifname });
		return iface?.wiphy ?? -1;
	},

	bssid_to_ifname: function(bssid) {
		refresh_bsses(false);
		return reported_bsses[lc(bssid || '')]?.ifname;
	},

	txpower_target: function(bssid) {
		return resolve_power_target(bssid);
	},

	txpower: function(bssid) {
		return resolve_power_target(bssid)?.wiphy_tx_power_level;
	},

	lookup: function(phy) {
		for (let bss, v in interfaces)
			if (v.phy == phy)
				return bss;
			return null;
	},

	reload: function() {
		refresh_bsses(true);
	},
};
