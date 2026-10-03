"""Execute actual state source under ARM ucode with service/filesystem boundaries mocked."""
from pathlib import Path
import tempfile,subprocess,sys,re
root,source=map(Path,sys.argv[1:3]);w=Path(tempfile.mkdtemp(prefix='state-led-policy-'))
s=source.read_text();s=re.sub(r'^#![^\n]*\n','',s);s=re.sub(r'^import .*;\n','',s,flags=re.M);s=s.replace('system(', 'mock_system(')
s=s.replace('REQUIRE_SEARCH_PATH =', 'REQUIRE_SEARCH_PATH =')
# Production flow remains intact. Only external modules, services and sysfs are fixtures.
h='''let cmds=[],callbacks=[],published,status={},off=0,phase=false;let green={trigger:'none',brightness:'255'},blue={trigger:'none',brightness:'0'};
let libubus={connect:()=>({STATUS_INVALID_ARGUMENT:2,call:(obj,method)=>obj=='ucentral'?status:{},publish:(name,methods)=>{published=methods;}})};
let libuci={cursor:()=>({load:()=>true,get:()=>off,get_all:()=>({health:{},stats:{},ui:{offline_trigger:0}})})};
let fs={popen:()=>({read:()=> 'green:status',close:()=>true}),readfile:path=>{if(index(path,'aliases/led-running')>=0)return '/leds/green';if(index(path,'/label')>=0)return '';if(index(path,'green:status/trigger')>=0)return green.trigger;return '';},open:(path,mode)=>({write:value=>{if(index(path,'green:status/trigger')>=0)green.trigger=value;},close:()=>true})};
let uloop={init:()=>null,run:()=>null,done:()=>null,timer:(ms,fn)=>{let t={cancelled:false};t.cancel=()=>{t.cancelled=true;};push(callbacks,{fn,t});return t;}};
let ulog_open=()=>null,ulog=()=>null,ULOG_SYSLOG=0,LOG_DAEMON=0,LOG_INFO=0;
function mock_system(cmd){push(cmds,cmd);if(cmd=='/usr/libexec/ucentral-led.sh managed')return 0;if(cmd=='/usr/libexec/ucentral-led.sh phase')return phase?0:1;
 if(index(cmd,'/usr/libexec/ucentral-led.sh')==0){let op=split(cmd,' ')[1];if(op in ['disabled','disabled-pattern']){blue.brightness=green.brightness='0';blue.trigger=green.trigger='none';return 0;}if(op=='pattern'){blue.brightness=green.brightness='0';blue.trigger=green.trigger='none';return 0;}if(index(op,'restore-')==0){blue.trigger=green.trigger='none';op=substr(op,8);}if(phase)return 0;if(op=='on'){blue.brightness='255';green.brightness='0';}else{blue.brightness='0';green.brightness='255';}blue.trigger=green.trigger='none';return 0;}
 if(cmd=='/etc/init.d/led blink'){blue.trigger=green.trigger='timer';return 0;}if(cmd=='/etc/init.d/led turnon'){blue.trigger=green.trigger='none';return 0;}return 0;}
'''
# Test accessors are appended in the same lexical scope after the untouched program.
t='''let checks=0;function check(ok,name){assert(ok,name);checks++;}
function setstate(state,duration){return published.set.call({args:{state,duration}});}
check(green.brightness=='255'&&blue.brightness=='0','initial disconnected green');
status={connected:0};setstate('online');check(blue.brightness=='255'&&green.brightness=='0','authenticated age zero connected');
status={};setstate('offline');check(green.brightness=='255'&&green.trigger=='none'&&blue.brightness=='0','steady disconnected green');
for(let bad in [{},{connected:null},{connected:false},{connected:-1},{connected:'0'}])check(!controller_connected(bad),'reject invalid connected status');
status={connected:1};setstate('online');setstate('blink',5);let timer=callbacks[-1];let before=length(cmds);
status={};setstate('offline');check(current_state=='blink'&&green.trigger=='timer'&&!timer.t.cancelled,'disconnect preserves identify');
status={connected:0};setstate('online');check(current_state=='blink'&&green.trigger=='timer'&&!timer.t.cancelled,'reconnect preserves identify');
check(!length(filter(slice(cmds,before),c=>index(c,'ucentral-led.sh on')>=0||index(c,'ucentral-led.sh off')>=0||c=='/etc/init.d/led turnon')),'no normal writes during identify');
timer.fn();check(blue.brightness=='255'&&green.brightness=='0'&&green.trigger=='none','identify timeout restores connected');
setstate('factory-reset');timer=callbacks[-1];before=length(cmds);setstate('factory-reset');status={};setstate('offline');check(current_state=='factory-reset'&&green.trigger=='timer'&&!timer.t.cancelled&&length(cmds)==before,'repeated factory reset and connection preserve pattern');
timer.fn();check(green.brightness=='255'&&blue.brightness=='0'&&green.trigger=='none','factory reset timeout restores disconnected');
phase=true;before=length(cmds);check(setstate('blink',5)==2&&current_state=='offline','boot phase rejects identify');status={connected:0};setstate('online');check(!length(filter(slice(cmds,before),c=>c=='/etc/init.d/led turnon'||c=='/etc/init.d/led blink')),'phase normal transition never resets phase');phase=false;
off=1;published.reload.call({});check(leds_off&&blue.brightness=='0'&&green.brightness=='0','global off');setstate('blink',5);check(blue.brightness=='0'&&green.brightness=='0','global off rejects identification light');
off=0;published.reload.call({});check(!leds_off&&blue.brightness=='255'&&green.brightness=='0','global off reversible');
setstate('blink',5);timer=callbacks[-1];off=1;published.reload.call({});check(timer.t.cancelled&&current_state=='online'&&blue.brightness=='0','global off cancels active identify');off=0;published.reload.call({});check(blue.brightness=='255'&&green.brightness=='0','restore normal after kill');
printf('PASS %d state arbitration controls\\n',checks);
'''
p=w/'state.uc';p.write_text(h+s+t)
r=subprocess.run(['/usr/bin/qemu-aarch64','-L',str(root),str(root/'usr/bin/ucode'),str(p)],capture_output=True,text=True)
print(r.stdout);print(r.stderr,end='');raise SystemExit(r.returncode)
