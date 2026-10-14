// Run the actual radio template, then verify the generated channel/width/power.
// Capabilities and driver replies are fixtures; no UCI, AP, radio or sysfs writes.
import { create_wiphy } from 'libs.wiphy';
let operating=require('radio_operating'),checks=0;
function check(v,label){assert(v,label);checks++;}
let cases=[['sage','2G','HT',20,1],['sage','5G','VHT',80,36],
 ['jaguar','2G','HE',20,1],['jaguar','5G','HE',80,36],['jaguar','6G','HE',160,1],
 ['cheetah','2G','HE',20,1],['cheetah','5G','HE',80,36],
 ['thor','2G','HE',20,1],['thor','5G-lower','HE',80,36],['thor','5G-upper','HE',80,149],['thor','6G','HE',160,1],
 ['miami','2G','EHT',20,1],['miami','5G','EHT',80,36],['miami','6G','EHT',160,1]];
let template=getenv('BAND_TEMPLATE');assert(template,'set BAND_TEMPLATE to the replayed real radio.uc');
for(let item in cases){
 let family=item[0],band=item[1],mode=item[2],width=item[3],chan=item[4];
 let baseband=band in ['5G-lower','5G-upper']?'5G':band,frequencies=[],channels=[];
 if(baseband=='2G')for(let c=1;c<=13;c++){push(channels,c);push(frequencies,2407+c*5);}
 else if(baseband=='6G')for(let c=1;c<=93;c+=4){push(channels,c);push(frequencies,5950+c*5);}
 else for(let c in [36,40,44,48,52,56,60,64,149,153,157,161,165,169,173,177]){push(channels,c);push(frequencies,5000+c*5);}
 let config={r:{path:'fixture',band:lc(baseband)}};
 let cursor={load:()=>true,get:(pkg,sid,key)=>config[sid]?.[key],foreach:(pkg,kind,fn)=>{for(let name,data in config)if(fn({...data,'.name':name})==false)break;}};
 let wiphy=create_wiphy(cursor,()=>{});wiphy.phys={fixture:{band:[baseband],frequencies,channels,dfs_channels:[],htmode:[mode+width],tx_ant_avail:3,rx_ant_avail:3}};
 let radio={band,channel:chan,channel_mode:mode,channel_width:width,country:'GB',enable:true,allow_dfs:true,tx_power:17,
  beacon_interval:100,maximum_clients:64,legacy_rates:false,he_6ghz_settings:{power_type:'indoor-power-indoor'}};
 let context={wiphy,state:{radios:[radio]},radio,cursor,location:'/radios/0',default_config:{country:'GB'},restrict:{},
  fs:{unlink:()=>true,readfile:()=>null,writefile:()=>die('unexpected write')},warn:()=>null,b:v=>v?1:0,s:v=>sprintf("'%s'",v),output:[],
  uci_set_string:(output,key,value)=>push(output,`set ${key}='${value}'`)};
 let generated=render(template,context);
 let c=match(generated,/set wireless\.r\.channel=([0-9]+)/),h=match(generated,/set wireless\.r\.htmode=([A-Z0-9]+)/),p=match(generated,/set wireless\.r\.txpower=([0-9]+)/);
 check(c&&h&&p,family+'/'+band+' generated all three actual settings');
 let requested={channel:c[1],htmode:h[1],txpower:p[1]};
 let freq=baseband=='2G'?2407+5*chan:baseband=='6G'?5950+5*chan:5000+5*chan;
 let status={state:'ENABLED',freq:''+freq,channel:''+chan,secondary_channel:'0'};
 if(mode=='EHT'){status.ieee80211be='1';status.eht_oper_chwidth=width==160?'2':width==80?'1':'0';}
 else if(mode=='HE'){status.ieee80211ax='1';status.he_oper_chwidth=width==160?'2':width==80?'1':'0';}
 else if(mode=='VHT'){status.ieee80211ac='1';status.vht_oper_chwidth=width==80?'1':'0';}
 let observed={wiphy_freq:freq,center_freq1:freq+width/2-10,channel_width:width==160?5:width==80?3:1,wiphy_tx_power_level:1700};
 let provenance={source:family=='sage'?'driver_limit':'firmware',confirmed:family!='sage'};
 let result=operating.inspect(requested,{},observed,status,provenance);
 check(result.channel.status=='confirmed'&&result.width.status=='confirmed'&&result.channel.requested_match===true&&result.width.requested_match===true,family+'/'+band+' real rendered request verified');
 check(result.power.status==(family=='sage'?'unconfirmed':'confirmed'),family+'/'+band+' power provenance retained');
 check(operating.inspect(requested,{},{...observed,wiphy_freq:freq+20},status,provenance).status=='failed',family+'/'+band+' wrong actual channel refused');
 check(operating.inspect(requested,{},observed,{...status,channel:'255'},provenance).status=='failed',family+'/'+band+' stale daemon channel refused');
}
print(sprintf('PASS %d actual rendered-config operating checks across five families; capabilities and readback are fixtures, not hardware acceptance\n',checks));
