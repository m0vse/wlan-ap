import * as reg from '../../feeds/ucentral/ucentral-schema/files/usr/share/ucentral/wifi/regulatory.uc';
let count=0;
function check(name, condition) { if (!condition) die(name+'\n'); count++; }
function fixture(country, paths) {
	let calls=[];
	let live=[{wiphy:0,wiphy_bands:[{freqs:[
		{freq:5180},{freq:5220},{freq:5260,radar:true,no_ir:true,dfs_state:0},
		{freq:5500,radar:true,dfs_state:1},{freq:5745,disabled:true},
		{freq:5785,disabled:true},{freq:5825,no_ir:true}]}]}];
	let io={list:()=>live,country:(i)=>{push(calls,i);return country;},
		readphy:(i)=>filter(live,p=>p.wiphy==i)[0],
		paths:()=>paths || ['/mock/phy0'],now:()=>1234567};
	let phys={'platform/soc/c000000.wifi:5G':{band:['5G'],
		frequencies:[5180,5220,5260,5500,5745,5785,5825],channels:[36,44,52,100,149,157,165],dfs_channels:[52,100]}};
	return {io,phys,live,calls};
}
let f=fixture('GB'); let path='platform/soc/c000000.wifi:5G';
let s=reg.sample(f.phys,f.io), t=reg.telemetry(s[path],'GB');
check('GB excludes disabled149/157', !(149 in t.channels) && !(157 in t.channels));
check('NO_IR nonDFS excluded from AP', !(165 in t.channels));
check('DFS CAC usable retained', 52 in t.channels && 52 in t.dfs_channels);
check('DFS unavailable excluded', !(100 in t.channels));
check('exact PHY GET_REG not global', length(f.calls)==2 && f.calls[0]==0 && f.calls[1]==0);
check('fresh timestamp', t.timestamp==1234567);
check('country mismatch unavailable', reg.telemetry(s[path],'US')==null);
f.phys = reg.intersect_phys(f.phys,[{band:'5G',country:'GB'}],'US',s);
check('stale board channels filtered', !(149 in f.phys[path].channels) && !(157 in f.phys[path].channels));
check('AP renderer noIR excluded', !(165 in f.phys[path].channels));
check('frequencies and channels stay paired', !(5745 in f.phys[path].frequencies));
f=fixture('00');check('world domain not country evidence', !length(reg.sample(f.phys,f.io)));
f=fixture('GB');f.io.list=()=>false;check('query failed absent', !length(reg.sample(f.phys,f.io)));
f=fixture('GB');f.io.country=()=>{die('GET_REG failure');};check('reg query throw absent', !length(reg.sample(f.phys,f.io)));
f=fixture('GB',[]);check('missing path absent', !length(reg.sample(f.phys,f.io)));
f=fixture('GB');push(f.live,{...f.live[0],wiphy:1});f.io.paths=()=>['/mock/phy0','/mock/phy1'];
check('dual sameband PHY ambiguous absent', !length(reg.sample(f.phys,f.io)));
f=fixture('GB'); f.phys={'platform/soc/c000000.wifi+0':f.phys[path]};
push(f.live,{...f.live[0],wiphy:1});f.io.paths=()=>['/mock/phy0','/mock/phy1'];
check('explicit dual PHY index exact', length(reg.sample(f.phys,f.io))==1);
f=fixture('GB');s=reg.sample(f.phys,f.io);reg.intersect_phys(f.phys,[{band:'5G',country:'US'}],'US',s);
check('unsettled country not misrepresented',149 in f.phys[path].channels);
f=fixture('GB'); f.phys[path].band=['HaLow'];check('HaLow shim not treated as 5GHz',!length(reg.sample(f.phys,f.io)));
f=fixture('GB');s=reg.sample(f.phys,f.io);
f.phys = reg.intersect_phys(f.phys,[{band:'5G',country:'GB'}],'US',s,
	[{ssids:[{bss_mode:'sta',wifi_bands:['5G']}]}]);
check('STA renderer noIR preserved',165 in f.phys[path].channels);
check('STA still excludes disabled149',!(149 in f.phys[path].channels));
f=fixture('GB');let transitions=0;f.io.country=()=>++transitions==1?'GB':'US';
check('country transition invalidates read',!length(reg.sample(f.phys,f.io)));
f=fixture('GB');f.io.readphy=()=>null;
check('fresh PHY query failure absent',!length(reg.sample(f.phys,f.io)));
f=fixture('GB');f.io.readphy=()=>({...f.live[0],wiphy:1});
check('wrong PHY reply refused',!length(reg.sample(f.phys,f.io)));
print(sprintf('Live regulatory source controls: %d PASS\n',count));
