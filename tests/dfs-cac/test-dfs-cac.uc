// Execute with the existing native ucode runtime; no wireless/AP operations.
REQUIRE_SEARCH_PATH = [ replace(ARGV[0], /[^/]+$/, '*.uc'), ...REQUIRE_SEARCH_PATH ];
let cac = require('dfs_cac');
let count = 0;
function check(label, result) {
	if (!result) die('FAIL: ' + label + '\n');
	count++;
}
function text(state, remaining, duration) {
	return 'state=' + state + '\nphy=phy0\ncac_time_seconds=' + (duration ?? 600) +
		'\ncac_time_left_seconds=' + remaining + '\nbss[0]=wlan0\nssid[0]=Shine Systems\n';
}
let config = {
	radio0: { '.type': 'wifi-device' },
	radio1: { '.type': 'wifi-device' },
	bss0: { '.type': 'wifi-iface', device: 'radio0', mode: 'ap', ssid: 'Shine Systems', network: 'up0v0' },
	bss1: { '.type': 'wifi-iface', device: 'radio1', mode: 'ap', ssid: 'Other', network: 'up0v0' }
};
let runtime = {
	radio0: { interfaces: [{ section: 'bss0', ifname: 'wlan0', config: { ssid: 'Shine Systems' } }] },
	radio1: { interfaces: [{ section: 'bss1', ifname: 'wlan1', config: { ssid: 'Other' } }] }
};
let response = text('DFS', 600);
function query(name) { return name == 'wlan0' ? cac.parse_status(response) : null; }
function phy(name) { return name == 'wlan0' ? 'phy0' : 'phy1'; }
let failure = { sanity: 75, data: { radios: { radio0: { failed_ssids: { 'Shine Systems': 'missing' } } } } };
for (let elapsed in [0,120,240,360,480,599]) {
	response = text('DFS', 600-elapsed);
	let pending = cac.collect(config, runtime, query, phy);
	check('initial/pre-BSS CAC section at '+elapsed, pending.sections.bss0);
	check('no six-minute heal at '+elapsed, !cac.has_wifi_failures(failure, config, pending));
}
for (let value in ['0','N/A','-1','garbage','601']) {
	response = text('DFS', value);
	let pending = cac.collect(config, runtime, query, phy);
	check('invalid/expired CAC resumes failure '+value, cac.has_wifi_failures(failure, config, pending));
}
for (let state in ['ENABLED','DISABLED','ACS','NO_IR','UNINITIALIZED']) {
	response = text(state, 600);
	check('non-CAC state '+state, !cac.parse_status(response));
}
response = text('DFS', 599);
let pending = cac.collect(config, runtime, query, phy);
let mixed = { sanity:50, data:{radios:{ radio0:failure.data.radios.radio0, radio1:{failed_ssids:{Other:'missing'}}}}};
check('other radio genuine failure survives CAC', cac.has_wifi_failures(mixed,config,pending));
check('unavailable runtime fails closed', cac.has_wifi_failures(failure,config,cac.collect(config,null,query,phy)));
check('missing hostapd status fails closed', cac.has_wifi_failures(failure,config,cac.collect(config,runtime,()=>null,phy)));
check('wrong PHY fails closed', cac.has_wifi_failures(failure,config,cac.collect(config,runtime,query,()=> 'phy99')));
response = replace(text('DFS',599),'ssid[0]=Shine Systems','ssid[0]=Another SSID');
check('wrong actual SSID fails closed', !cac.collect(config,runtime,query,phy).sections.bss0);
response = replace(text('DFS',599),'bss[0]=wlan0','bss[0]=wlan99');
check('wrong actual BSS fails closed', !cac.collect(config,runtime,query,phy).sections.bss0);
response = text('DFS',599)+'state=DFS\n';
check('duplicate fields fail closed', !cac.parse_status(response));
response = text('DFS',899,900);
check('reported regulatory duration not capped at600', !!cac.parse_status(response));
check('invalid overflowing duration rejected', !cac.parse_status(text('DFS',1,'999999999999999999999')));
response = text('DFS',599);
pending = cac.collect(config,runtime,query,phy);
let interface_failure = { data: { interfaces: {up0v0:{ssids:{'Shine Systems':false}}} } };
check('only attributable interface failure deferred', !cac.has_wifi_failures(interface_failure,config,pending));
interface_failure.data.interfaces.up0v0.ssids.Other=false;
check('independent interface SSID failure retained', cac.has_wifi_failures(interface_failure,config,pending));
check('unknown interface failure retained', cac.has_wifi_failures({data:{interfaces:{unknown:{ssids:{'Shine Systems':false}}}}},config,pending));
check('escaped SSID quote',cac.encoded_ssid('a"b')=='a\\"b');
check('escaped SSID slash',cac.encoded_ssid('a\\b')=='a\\\\b');
check('escaped SSID newline',cac.encoded_ssid('a\nb')=='a\\nb');
check('escaped SSID UTF8',cac.encoded_ssid('café')=='caf\\xc3\\xa9');
config.bss2={'.type':'wifi-iface',device:'radio0',mode:'ap',ssid:'Missing',network:'up0v0'};
check('same radio different SSID still fails',cac.has_wifi_failures({data:{radios:{radio0:{failed_ssids:{Missing:'missing'}}}}},config,pending));
config.bss2.ssid='Shine Systems';
check('same radio duplicate SSID uncovered BSS fails',cac.has_wifi_failures(failure,config,cac.collect(config,runtime,query,phy)));
config.bss0.disabled='1';
check('disabled iface never positive CAC',!cac.collect(config,runtime,query,phy).sections.bss0);
check('oversize status rejected',!cac.parse_status(sprintf('%16385s','x')));
let multi_config = { radio0: { '.type': 'wifi-device' } };
let multi_runtime = { radio0: { interfaces: [] } };
let multi_text = 'state=DFS\nphy=phy0\ncac_time_seconds=600\ncac_time_left_seconds=543\n';
for (let i, ssid in ['Shine Systems', 'phil 5Ghz', 'Dante']) {
	let section = 'bss' + i;
	let ifname = i ? 'wlan0-' + i : 'wlan0';
	multi_config[section] = { '.type': 'wifi-iface', device: 'radio0', mode: 'ap', ssid, network: 'up0v0' };
	push(multi_runtime.radio0.interfaces, { section, ifname, config: { ssid } });
	multi_text += 'bss[' + i + ']=' + ifname + '\nssid[' + i + ']=' + ssid + '\n';
}
let multi_pending = cac.collect(multi_config, multi_runtime,
	()=>cac.parse_status(multi_text), ()=>'phy0');
for (let i in [0,1,2])
	check('multi-BSS positive CAC section '+i, multi_pending.sections['bss'+i]);
let multi_failure = { data: { radios: { radio0: { failed_ssids: {
	'Shine Systems': 'missing', 'phil 5Ghz': 'missing', 'Dante': 'missing'
} } } } };
check('all three same-PHY CAC failures deferred', !cac.has_wifi_failures(multi_failure, multi_config, multi_pending));
multi_pending = cac.collect(multi_config, multi_runtime,
	()=>cac.parse_status(multi_text), (name)=>name=='wlan0'?'phy0':null);
check('missing secondary PHY links covered by exact anchored hostapd BSS evidence',
	!cac.has_wifi_failures(multi_failure, multi_config, multi_pending));
check('no PHY anchor never defers failures', cac.has_wifi_failures(multi_failure, multi_config,
	cac.collect(multi_config, multi_runtime, ()=>cac.parse_status(multi_text), ()=>null)));
multi_pending = cac.collect(multi_config, multi_runtime,
	()=>cac.parse_status(multi_text), (name)=>name=='wlan0'?'phy0':'phy99');
check('contradictory secondary PHY links retain failures', cac.has_wifi_failures(multi_failure, multi_config, multi_pending));
check('contradictory secondary not deferred', !multi_pending.sections.bss1 && !multi_pending.sections.bss2);
let reversed = {radio0:{interfaces:[...multi_runtime.radio0.interfaces]}};
reverse(reversed.radio0.interfaces);
check('primary anchor independent of interface ordering', !cac.has_wifi_failures(multi_failure, multi_config,
	cac.collect(multi_config, reversed, ()=>cac.parse_status(multi_text), (name)=>name=='wlan0'?'phy0':null)));
printf('%.J\n',{passed:true,count,scope:'Actual CAC classifier/mapping/healing filter, injected pre-BSS hostapd STATUS and netifd/sysfs fixtures; no AP or wireless operations.'});
