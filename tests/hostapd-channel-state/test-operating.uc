let m = require('radio_operating'), count = 0;
function check(v, label) { assert(v, label); count++; }
let radio = { channel: '1', htmode: 'EHT160', txpower: '23' };
let iface = { ssid: 'Fixture' };
let actual = { wiphy_freq: 5955, channel_width: 5, center_freq1: 6025, wiphy_tx_power_level: 2300 };
let status = { state: 'ENABLED', freq: '5955', channel: '1', ieee80211be: '1', eht_oper_chwidth: '2', eht_oper_centr_freq_seg0_idx: '15' };
let fw = { confirmed: true, source: 'firmware', max_age_ms: 5000 };
function inspect(a, s, p, r, i) { return m.inspect(r || radio, i || iface, a || actual, s || status, p || fw); }
check(inspect().status == 'confirmed', 'coherent 6GHz160 firmware readback');
check(inspect(null, { ...status, channel: '36' }).status == 'failed', 'stale hostapd 36 with actual 5955 rejected');
check(inspect(null, { ...status, freq: '5975' }).channel.status == 'mismatch', 'hostapd frequency differs');
check(inspect({ ...actual, wiphy_freq: 5765 }).status == 'failed', 'wrong actual operating band');
check(inspect({ ...actual, channel_width: 3 }).width.status == 'mismatch', 'rejected width cannot appear successful');
check(inspect({ ...actual, center_freq1: 6105 }).width.status == 'mismatch', 'wrong center segment');
check(inspect(null, { ...status, state: 'DISABLED' }).status == 'failed', 'disabled not green');
check(inspect({ ...actual, mlo_link_disabled: true }).status == 'failed', 'disabled link not credited');
check(inspect({ ...actual, wiphy_freq: 0 }).status == 'failed', 'explicit no-channel not healthy');
check(inspect(null, { ...status, state: 'DFS' }).status == 'pending', 'DFS is pending, not confirmation or hardware fault');
check(inspect({ ...actual, wiphy_tx_power_level: null }).power.status == 'unconfirmed', 'missing readback is not zero');
let zero = inspect({ ...actual, wiphy_tx_power_level: 0 }, null, null, { ...radio, txpower: '0' });
check(zero.power.status == 'confirmed' && zero.power.reported_dbm == 0, 'real zero dBm preserved');
let limited = inspect({ ...actual, wiphy_tx_power_level: 1700 });
check(limited.power.status == 'limited' && limited.status == 'confirmed', 'effective limiting is explicit, not a failed request');
check(inspect({ ...actual, wiphy_tx_power_level: 2500 }).status == 'failed', 'power above requested limit rejected');
check(inspect(null, null, { source: 'driver_limit', confirmed: false }).power.status == 'unconfirmed', 'old driver limit never firmware confirmation');
check(inspect(null, null, { source: 'kernel', confirmed: false }).status == 'unconfirmed', 'old kernel without strict-readback marker unconfirmed');
check(inspect(null, null, null, { ...radio, txpower: null }).power.status == 'confirmed', 'automatic power accepts actual report');
check(inspect({ ...actual, wiphy_tx_power_level: 1700 }, null, null, { ...radio, txpower: '17.5' }).power.status == 'confirmed', 'firmware half-dBm integer precision tolerance');
let negative = inspect({ ...actual, wiphy_tx_power_level: 4294967196 }, null, null, { ...radio, txpower: '-1' });
check(negative.power.reported_dbm == -1 && negative.power.status == 'confirmed', 'signed mBm u32 normalized');
check(inspect({ ...actual, wiphy_tx_power_level: 999999 }).power.status == 'unconfirmed', 'invalid power unavailable');
check(inspect(null, null, null, null, { ...iface, vif_txpower: '20' }).power.status == 'mismatch', 'per-interface power overrides radio');
check(inspect(null, null, null, {...radio,channel:'5'}).channel.requested_match===false,'requested channel difference exposed even when driver and hostapd agree');
check(m.inspect(radio, iface, null, status, fw).status == 'unconfirmed', 'missing driver evidence unavailable');
check(m.inspect(radio, iface, actual, null, fw).status == 'unconfirmed', 'missing hostapd evidence unavailable');
for (let pair in [[2412,1],[2484,14],[4920,184],[5180,36],[5765,153],[5935,2],[5955,1],[7115,233]])
	check(m.channel(pair[0]) == pair[1], 'frequency/channel map ' + pair[0]);
check(m.channel(5956) == null && m.channel(9999) == null, 'invalid frequencies rejected');
for (let pair in [['20',1],['40',2],['80',3],['160',5],['80p80',4],['320',13]]) {
	let width = pair[0], code = pair[1];
 let f = { state:'ENABLED',freq:'5955',channel:'1',ieee80211be:'1',eht_oper_chwidth:width=='320'?'9':width=='80p80'?'3':width=='160'?'2':width=='80'?'1':'0',secondary_channel:width=='40'?'1':'0' };
	let span = width=='80p80'?80:+width;
	check(inspect({wiphy_freq:5955,channel_width:code,center_freq1:5955+span/2-10,center_freq2:width=='80p80'?6305:0,wiphy_tx_power_level:2300},f).width.status == 'confirmed', 'width ' + width);
}
// Exact runtime section and link identity: never infer band from link ID.
let cfg={r:{'.type':'wifi-device',...radio},s:{'.type':'wifi-iface',device:'r',...iface}};
let runtime={r:{interfaces:[{section:'s',ifname:'wlan-fixture'}]}};
let root={...actual,iftype:3,ifname:'wlan-fixture',ssid:'Fixture',wiphy:8,mac:'02:00:00:00:00:01'};
let read=(name,id)=>({...status,phy:'phy8','bss[0]':name,'ssid[0]':'Fixture','bssid[0]':root.mac});
for(let family in ['sage','jaguar','cheetah','thor','miami']) {
	let report=m.collect(cfg,runtime,{},[root],read,phy=>fw);
	check(report.s.status=='confirmed'&&report.s.ifname=='wlan-fixture',family+' ordinary reporting preserved');
}
let mlcfg={...cfg,s:{...cfg.s,mld:'ml0_0'}};
let mlroot={...root,mlo_links:[{...actual,link_id:7,mac:'02:00:00:00:00:01'}]};
let proof={links:{s:{ifname:root.ifname,link_id:7,bssid:'02:00:00:00:00:01',phy:'phy8'}}};
let report=m.collect(mlcfg,runtime,proof,[mlroot],(name,id)=>{assert(id==7);return read(name,id);},phy=>fw);
check(report.s.status=='confirmed'&&report.s.link_id==7,'MLO exact link 7 not radio/index guess');
check(m.collect(mlcfg,runtime,{},[mlroot],read,phy=>fw).s.status=='unconfirmed','missing MLO proof does not fall back to default link');
check(m.collect(cfg,runtime,{},[mlroot],read,phy=>fw).s.status=='unconfirmed','ordinary cannot claim MLD root values');
check(m.collect(cfg,runtime,{},[{...root,ssid:'Other'}],read,phy=>fw).s.status=='unconfirmed','other SSID not credited');
check(m.collect(cfg,{r:{interfaces:[]}}, {},[root],read,phy=>fw).s.status=='unconfirmed','missing runtime map unavailable');
check(!length(m.collect({...cfg,r:{...cfg.r,disabled:'1'}},runtime,{},[root],read,phy=>fw)),'disabled radios skipped');
check(!length(m.collect({...cfg,s:{...cfg.s,mode:'sta'}},runtime,{},[root],read,phy=>fw)),'STA not misreported as AP');
check(m.collect(cfg,runtime,{},[root],(name,id)=>({...read(name,id),phy:'phy9'}),phy=>fw).s.status=='unconfirmed','same SSID on another PHY never supplies confirmation');
check(m.collect(cfg,runtime,{},[root],(name,id)=>({...read(name,id),'bssid[0]':'04:00:00:00:00:01'}),phy=>fw).s.status=='unconfirmed','other BSSID cannot supply status');
let thorcfg={rlo:{'.type':'wifi-device',band:'5g-lower'},rhi:{'.type':'wifi-device',band:'5g-upper'},
 slo:{'.type':'wifi-iface',device:'rlo',ssid:'Fixture'},shi:{'.type':'wifi-iface',device:'rhi',ssid:'Fixture'}};
let thorlive={rlo:{interfaces:[{section:'slo',ifname:'lo-ap'}]},rhi:{interfaces:[{section:'shi',ifname:'hi-ap'}]}};
let thorraw=[{...root,ifname:'lo-ap',wiphy:8,wiphy_freq:5180,center_freq1:5210,channel_width:3,mac:'02:00:00:00:00:01'},
 {...root,ifname:'hi-ap',wiphy:9,wiphy_freq:5765,center_freq1:5775,channel_width:3,mac:'04:00:00:00:00:01'}];
let thorstatus=name=>({state:'ENABLED',phy:name=='lo-ap'?'phy8':'phy9',freq:name=='lo-ap'?'5180':'5765',channel:name=='lo-ap'?'36':'153',
 ieee80211ax:'1',he_oper_chwidth:'1','bss[0]':name,'ssid[0]':'Fixture','bssid[0]':name=='lo-ap'?'02:00:00:00:00:01':'04:00:00:00:00:01'});
let tr=m.collect(thorcfg,thorlive,{},thorraw,thorstatus,phy=>fw);
check(tr.slo.status=='confirmed'&&tr.shi.status=='confirmed'&&tr.slo.channel.actual==36&&tr.shi.channel.actual==153,'Thor dual5GHz sameSSID remains distinct');
let swapped={rlo:{interfaces:[{section:'slo',ifname:'lo-ap'}]},rhi:{interfaces:[{section:'shi',ifname:'hi-ap'}]}};
tr=m.collect(thorcfg,swapped,{},thorraw,name=>thorstatus(name=='lo-ap'?'hi-ap':'lo-ap'),phy=>fw);
check(tr.slo.status=='unconfirmed'&&tr.shi.status=='unconfirmed','swapped Thor sameSSID evidence cannot confirm either radio');
for(let kind in ['ath11k','ath12k']) {
	let yes=m.driver('phy8',{readlink:()=>'/drivers/'+kind+'_ahb',readfile:()=> 'Y\n'});
	check(yes.confirmed&&yes.source=='firmware',kind+' exact loaded-kernel marker');
	let no=m.driver('phy8',{readlink:()=>'/drivers/'+kind+'_ahb',readfile:()=>null});
	check(!no.confirmed&&no.source=='kernel',kind+' unpatched kernel cannot claim strict firmware evidence');
}
check(!m.driver('phy8',{readlink:()=>'/drivers/ath10k_ahb',readfile:()=> 'Y'}).confirmed,'Sage driver without firmware getter stays unconfirmed');
check(!m.driver('../wrong',{readlink:()=>die('must not read bad phy')}).confirmed,'invalid PHY rejected before sysfs');
check(!length(m.interfaces({const:{},request:()=>false})),'failed netlink dump unavailable, no retry loop');
check(!length(m.interfaces({const:{},request:()=>({})})),'non-array dump rejected');
check(length(m.interfaces({const:{},request:()=>[root]}))==1,'one reusable kernel snapshot for both collectors');
print(sprintf('PASS %d actual operating-state checks; netlink/status/driver boundaries injected, no AP I/O\n',count));
