#!/usr/bin/env python3
"""Real bounded subprocess mechanics, fake STATUS-only CLI, no AP/socket."""
import hashlib,json,os,pathlib,subprocess,tempfile,time
source=pathlib.Path(os.environ['OW_DFS_MODULE'])
ucode=os.environ['OW_TEST_UCODE']
work=pathlib.Path(tempfile.mkdtemp(prefix='cac-subprocess-tests.'))
cli=work/'hostapd_cli'
cli.write_text('''#!/usr/bin/python3
import os,sys,time,subprocess
from pathlib import Path
assert sys.argv[1:]==['-p','/var/run/hostapd','-i','global','raw','IFNAME=wlan0','STATUS'],sys.argv
p=Path(os.environ['CAC_TEST_WORK'])
with (p/'requests').open('a') as f:f.write('STATUS\\n')
mode=(p/'mode').read_text()
if mode=='sleep':
 child=subprocess.Popen(['/bin/sleep','30'])
 (p/'child-pid').write_text(str(child.pid))
 time.sleep(30)
if mode=='fail':raise SystemExit(7)
if mode=='oversize':print('x'*20000);raise SystemExit(0)
print((p/'status').read_text())
''');cli.chmod(0o755)
text=source.read_text().replace('/usr/libexec/timeout-coreutils','/usr/bin/timeout').replace('/usr/sbin/hostapd_cli',str(cli))
(work/'dfs_cac.uc').write_text(text)
(work/'status').write_text('state=DFS\nphy=phy0\ncac_time_seconds=600\ncac_time_left_seconds=480\nbss[0]=wlan0\nssid[0]=Shine Systems\n')
driver=work/'driver.uc'
driver.write_text('''REQUIRE_SEARCH_PATH=[ARGV[0]+'/*.uc',...REQUIRE_SEARCH_PATH];
let cac=require('dfs_cac');
let config={radio0:{'.type':'wifi-device'},bss0:{'.type':'wifi-iface',device:'radio0',mode:'ap',ssid:'Shine Systems',network:'up0v0'}};
let runtime={radio0:{interfaces:[{section:'bss0',ifname:ARGV[1],config:{ssid:'Shine Systems'}}]}};
printf('%.J\\n',cac.collect(config,runtime,null,()=> 'phy0'));
''')
cases=[]
for mode,name,expected in [('normal','wlan0',True),('fail','wlan0',False),('oversize','wlan0',False),('sleep','wlan0',False),('normal','wlan0;touch unsafe',False)]:
 (work/'mode').write_text(mode)
 started=time.monotonic()
 p=subprocess.run([ucode,str(driver),str(work),name],env=dict(os.environ,CAC_TEST_WORK=str(work)),capture_output=True,text=True,timeout=6)
 elapsed=time.monotonic()-started
 assert p.returncode==0,(mode,p.stderr)
 result=json.loads(p.stdout)
 assert bool(result['sections'].get('bss0'))==expected,(mode,name,result)
 assert elapsed<5,(mode,elapsed)
 if mode=='sleep':
  assert elapsed>=1.8,(mode,elapsed)
  pid=int((work/'child-pid').read_text())
  status=pathlib.Path('/proc')/str(pid)/'status'
  for _ in range(10):
   if not status.exists() or '\nState:\tZ' in status.read_text():break
   time.sleep(.05)
  assert not status.exists() or '\nState:\tZ' in status.read_text(),('timeout left running child',pid)
 cases.append({'case':mode+'-'+name,'passed':True,'elapsed_seconds':round(elapsed,3)})
assert (work/'requests').read_text().splitlines()==['STATUS']*4
print(json.dumps({'passed':True,'count':len(cases),'cases':cases,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
 'scope':'Actual query/parse/mapping logic; executable locations only redirected to native GNU timeout and a fake STATUS-only CLI. Real timeout/exit/oversize/input-refusal behavior. No AP/socket access.'},indent=2))
