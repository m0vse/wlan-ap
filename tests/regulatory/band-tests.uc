import * as bands from '../../feeds/ucentral/ucentral-schema/files/usr/share/ucentral/wifi/band_channels.uc';
import * as reg from '../../feeds/ucentral/ucentral-schema/files/usr/share/ucentral/wifi/regulatory.uc';
import { create_wiphy } from 'libs.wiphy';
let count = 0;
function check(name, condition) { if (!condition) die(name+'\n'); count++; }
let pci = { band:['5G','6G'], frequencies:[5180,5745,5955,5975,5995,6015,6415,7115],
	channels:[36,149,1,5,9,13,93,233,149], dfs_channels:[36], htmode:['HE20','HE40','HE80','HE160'],
	tx_ant_avail:15, rx_ant_avail:15, section:'radio2' };
let original = sprintf('%J', pci);
let five = bands.select_band(pci, '5G'), six = bands.select_band(pci, '6G');
check('5G paired only', join(',',five.channels)=='36,149');
check('6G paired only', join(',',six.channels)=='1,5,9,13,93,233');
check('clone requested band', six.band[0]=='6G' && length(six.band)==1);
check('6G not 5G DFS', !length(six.dfs_channels));
check('source PHY unchanged', sprintf('%J',pci)==original);
bands.select_band(pci,'6G'); bands.select_band(pci,'5G');
check('twice reverse lookup unchanged', sprintf('%J',pci)==original);
check('ambiguous channels-only multi-band refused', bands.select_band({...pci,frequencies:[]},'6G')==null);
check('single-band channels-only works', bands.select_band({...pci,band:['6G'],frequencies:[]},'6G').channels[0]==1);
check('5G lower frequencies', bands.select_band(pci,'5G-lower').channels[0]==36);
check('5G upper frequencies', bands.select_band(pci,'5G-upper').channels[0]==149);
check('5G lower channel-only', join(',',bands.select_band({...pci,band:['5G'],frequencies:[]},'5G-lower').channels)=='36');
check('off-grid 6G refused', bands.frequency_channel(5960,'6G')==null);
check('band overlap numeric149', bands.frequency_channel(5745,'5G')==149 && bands.frequency_channel(6695,'6G')==149);
check('6G lower boundary', bands.frequency_channel(5955,'6G')==1);
check('6G upper boundary', bands.frequency_channel(7115,'6G')==233);
check('2G preserved', bands.frequency_channel(2484,'2G')==14);
check('HaLow passthrough', bands.select_band({band:['HaLow'],channels:[12]},'HaLow').channels[0]==12);
let full = []; for (let ch=1; ch<=233; ch+=4) push(full,ch);
for (let width in [20,40,80,160,320])
	check('6G valid width '+width, bands.primary_6g_allowed(5,width,full));
check('6G 80 does not use 5G table', bands.primary_6g_allowed(5,80,[1,5,9,13]));
check('6G missing bonded subchannel refused', !bands.primary_6g_allowed(5,80,[1,5,13]));
check('6G incomplete top 40 refused', !bands.primary_6g_allowed(233,40,full));
check('6G top20 accepted', bands.primary_6g_allowed(233,20,full));
check('6G off-grid primary refused', !bands.primary_6g_allowed(36,80,full));
check('6G unspecified80+80 refused', !bands.primary_6g_allowed(5,8080,full));
check('6G invalid width refused', !bands.primary_6g_allowed(5,10,full));
let gb=[];for(let ch=1;ch<=93;ch+=4)push(gb,ch);
check('GB upper80 fits',bands.primary_6g_allowed(93,80,gb));
check('GB upper160 fits',bands.primary_6g_allowed(93,160,gb));
check('GB channel beyond allowed list refused',!bands.primary_6g_allowed(97,80,gb));
let phys={dedicated:{...five,section:'radio0'},pci};
let config={radio0:{path:'dedicated',band:'5g',disabled:'0'},radio2:{path:'pci',band:'6g',disabled:'0'}};
let cursor={load:()=>true,get:(pkg,sid,key)=>config[sid]?.[key],
	foreach:(pkg,kind,fn)=>{for(let name,data in config)if(fn({...data,'.name':name})==false)break;}};
let wiphy=create_wiphy(cursor,()=>{});wiphy.phys=phys;
let both=[{band:'5G',enable:true},{band:'6G',enable:true}];
let allocated5=bands.reserve_switchable(wiphy.lookup_by_band('5G'),'5G',both);
check('dedicated5G retained with6G request',length(allocated5)==1 && allocated5[0].section=='radio0');
check('disabled6G does not reserve',length(bands.reserve_switchable(wiphy.lookup_by_band('5G'),'5G',[{band:'6G',enable:false}]))==2);
check('disabled6G does not disable enabled5G allocation',!length(bands.reserve_switchable(wiphy.lookup_by_band('6G'),'6G',[{band:'5G',enable:true},{band:'6G',enable:false}])));
check('SSID active5G only dedicated',length(wiphy.lookup_by_band('5G',true))==1);
check('SSID active6G only PCI',length(wiphy.lookup_by_band('6G',true))==1);
config.radio2.disabled='1';check('disabledradio noSSID',!length(wiphy.lookup_by_band('6G',true)));
config.radio2.disabled='0';
wiphy.operating_bands={radio0:{band:'5g',disabled:false},radio2:{band:'6g',disabled:false}};
config.radio2.band='5g';
check('first5to6transition uses newly rendered band',length(wiphy.lookup_by_band('6G',true))==1 && length(wiphy.lookup_by_band('5G',true))==1);
wiphy.operating_bands.radio2.disabled=true;
check('new disabled state wins over old UCI',!length(wiphy.lookup_by_band('6G',true)));
wiphy.operating_bands.radio2.disabled=false;
check('lookup does not mutate capability',sprintf('%J',pci)==original);
let views=reg.intersect_phys({pci},[{band:'6G',country:'GB'}],'US',{
	pci:{country:'GB',channels:[1,5,9,13],ap_channels:[1,5,9,13],dfs_channels:[],ap_dfs_channels:[],frequencies:[5955,5975,5995,6015]}});
check('regulatory view no mutation',sprintf('%J',pci)==original);
check('regulatory view paired filtered',length(views.pci.channels)==4 && length(views.pci.frequencies)==4);
print(sprintf('Operating-band source controls: %d PASS\n', count));
