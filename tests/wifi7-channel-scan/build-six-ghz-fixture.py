"""Build a native ucode fixture from the actual prepared generic scanner.

Netlink, filesystem and ubus boundaries are mocked; no RF scan is performed.
"""
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()

def function(name):
    start = source.index('function ' + name + '(')
    end = source.index('\n}', start) + 2
    return source[start:end]

constants = source[source.index('const SCAN_FLAG_AP'):source.index('function frequency_to_channel')]
functions = '\n'.join(function(name) for name in [
    'frequency_to_channel', 'iface_find', 'scan_trigger', 'trigger_scan_width',
    'phy_get_frequencies', 'phy_frequency_dfs', 'phy_is_halow', 'intersect',
    'thor_scan_failed', 'wifi_scan',
])
harness = r'''
let test=+ARGV[0];
let args={periodic:false}; let active=true; let verbose=false; let override_dfs=false;
let bandwidth=0; let thor_scanner=false; let six_ghz_scan_failures=0;
let scan_name='fixture-scan'; let calls=[]; let cache_reads=[];
let def={NL80211_CMD_TRIGGER_SCAN:1,NL80211_CMD_NEW_SCAN_RESULTS:2,
 NL80211_CMD_SCAN_ABORTED:3,NL80211_CMD_GET_SCAN:4,NL80211_CMD_DEL_INTERFACE:5,NLM_F_DUMP:4};
let fs={stat:()=>false}; let ctx={call:()=>die('unexpected channel change')};
let result_json=()=>die('unexpected Thor error');
let phys=[]; let ifaces=[];
let frequencies=test==0?[2412]:test==1?[5180]:test==2?[2412,5180]:
 test==4?[2412,5180,5955]:[5955];
for(let frequency in frequencies) {
 let phy=length(phys);
 push(phys,{wiphy:phy,wiphy_bands:[{freqs:[{freq:frequency,disabled:test==5}]}]});
 push(ifaces,{wiphy:phy,iftype:3,dev:'fixture'+phy,channel_width:3,wiphy_freq:frequency});
}
let nl={
 request:(command,flags,params)=>{
  if(command==1){push(calls,params);return test==8?false:{};}
  if(command==4){push(cache_reads,params.dev);return [];}
  die('unexpected netlink mutation');
 },
 waitfor:()=>test==6?null:{cmd:test==7?3:2},
 error:()=> 'synthetic error'
};
'''
checks = r'''
let rows=wifi_scan();
let six_calls=filter(calls,c=>c.scan_frequencies && c.scan_frequencies[0]>=5935);
let expected_six=test>=3&&test!=5?1:0;
if(length(six_calls)!=expected_six)die('unsupported/missing 6 GHz scan');
for(let call in six_calls) {
 if(call.scan_ssids!=null)die('6 GHz must use passive discovery');
 if(length(call.scan_frequencies)!=1||call.scan_frequencies[0]!=5955)
  die('scanned frequency absent from enabled capabilities');
}
for(let call in calls) {
 if(call.scan_frequencies?.[0]<5935 && !call.scan_ssids)
  die('existing active scan changed');
}
let expected_fail=test==6||test==7||test==8?1:0;
if(six_ghz_scan_failures!=expected_fail)die('6 GHz error not reported');
if(expected_fail&&length(cache_reads))die('failed scan reused stale cache');
if(test==5&&length(calls))die('disabled-only frequencies scanned');
printf('PASS generic capability case%d scans=%d failures=%d\n',test,length(calls),six_ghz_scan_failures);
'''
Path(sys.argv[2]).write_text(harness + constants + functions + checks)
