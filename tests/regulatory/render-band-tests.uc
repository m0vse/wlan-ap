// Execute the real patched radio template with mocked UCI/PHY/filesystem data.
// No daemon, AP, sysfs, UCI or filesystem writes. Template path comes from fixture.
import { create_wiphy } from 'libs.wiphy';
let count=0;
function check(name, condition) { if (!condition) die(name+'\n'); count++; }
let frequencies=[];let channels=[];
for(let ch=1;ch<=93;ch+=4){push(frequencies,5950+5*ch);push(channels,ch);}
let phys={
	dedicated:{band:['5G'],frequencies:[5180,5200,5220,5240],channels:[36,40,44,48],dfs_channels:[],
		htmode:['HE20','HE40','HE80'],tx_ant_avail:3,rx_ant_avail:3},
	pci:{band:['5G','6G'],frequencies:[5180,5200,5220,5240,...frequencies],channels:[36,40,44,48,...channels],dfs_channels:[],
		htmode:['HE20','HE40','HE80','HE160'],tx_ant_avail:15,rx_ant_avail:15}
};
let config={radio0:{path:'dedicated',band:'5g'},radio2:{path:'pci',band:'6g'}};
let cursor={load:()=>true,get:(pkg,sid,key)=>config[sid]?.[key],
	foreach:(pkg,kind,fn)=>{for(let name,data in config)if(fn({...data,'.name':name})==false)break;}};
let wiphy=create_wiphy(cursor,()=>{});wiphy.phys=phys;
let base={channel:5,channel_mode:'HE',channel_width:80,country:'GB',enable:true,
	allow_dfs:true,tx_power:0,beacon_interval:100,maximum_clients:64,legacy_rates:false};
let five={...base,band:'5G',channel:36,channel_width:40};
let six={...base,band:'6G',he_6ghz_settings:{power_type:'indoor-power-indoor'}};
let state={radios:[five,six]}, snapshot=sprintf('%J',{phys,state}), warnings=[];
let context={wiphy,state,radio:six,cursor,location:'/radios/1',default_config:{country:'GB'},restrict:{},
	fs:{unlink:()=>true,readfile:()=>null,writefile:()=>die('unexpected write')},
	warn:(fmt,...args)=>push(warnings,sprintf(fmt,...args)),b:v=>v?1:0,s:v=>sprintf("'%s'",v),output:[],
	uci_set_string:(output,key,value)=>push(output,`set ${key}='${value}'`)};
let path=getenv('BAND_TEMPLATE');assert(path,'BAND_TEMPLATE must name patched source fixture');
let a=render(path,{...context,radio:five}), b=render(path,context);
config.radio2.band='5g'; // previous UCI state must not govern the new SSID mapping
check('actual rendered5and6SSID mapping',length(wiphy.lookup_by_band('5G',true))==1 && length(wiphy.lookup_by_band('6G',true))==1);
check('real5G render dedicated only',index(a,'set wireless.radio0.')>=0 && index(a,'set wireless.radio2.')<0);
check('real6G render PCI only',index(b,'set wireless.radio2.')>=0 && index(b,'set wireless.radio0.')<0);
check('6G fixed5 does not fall back to ACS',index(b,'set wireless.radio2.channel=5')>=0);
check('6G channels no5G channel36',index(b,'channels=36\n')<0);
check('one channel list entry each',length(match(b,/channels=5\n/g))==1);
check('list reset before add',index(b,'delete wireless.radio2.channels')<index(b,'add_list wireless.radio2.channels'));
check('6G HE80 preserved',index(b,'set wireless.radio2.htmode=HE80')>=0);
check('real render objects not mutated',sprintf('%J',{phys,state})==snapshot);
let again=render(path,context);
check('repeat render identical',again==b);
for(let width in [20,40,80,160]){
	let result=render(path,{...context,radio:{...six,channel_width:width}});
	check('real6G channel5 width'+width,index(result,'set wireless.radio2.channel=5')>=0 &&
		index(result,'set wireless.radio2.htmode=HE'+width)>=0);
}
let wide=render(path,{...context,radio:{...six,channel_mode:'EHT',channel_width:320}});
check('unsupported320 existing fallback160',index(wide,'set wireless.radio2.htmode=HE160')>=0 && index(wide,'htmode=EHT320')<0);
check('disabled6G preserved',index(render(path,{...context,radio:{...six,enable:false}}),'set wireless.radio2.disabled=1')>=0);
let disabledSix={...six,enable:false};
check('disabled6G does not override enabled5G',!length(trim(render(path,{...context,state:{radios:[five,disabledSix]},radio:disabledSix}))));
check('5G lower preserved',index(render(path,{...context,radio:{...five,band:'5G-lower'}}),'set wireless.radio0.')>=0);
print(sprintf('Actual radio template controls: %d PASS\n',count));
