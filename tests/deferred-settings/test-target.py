#!/usr/bin/env python3
"""Actual target ucode with isolated filesystem and hardware/process proofs."""
from pathlib import Path
import argparse,json,subprocess,tempfile,shutil,os,difflib

def main():
    ap=argparse.ArgumentParser();ap.add_argument('root',type=Path);ap.add_argument('repo',type=Path);ap.add_argument('baseline',type=Path);a=ap.parse_args()
    assert os.geteuid()==0,'Run isolated filesystem controls as root'
    work=Path(tempfile.mkdtemp(prefix='deferred-target-',dir=a.repo.parent));results=[]
    try:
        src=a.repo/'feeds/ucentral/ucentral-schema/files/usr/share/ucentral';modules=work/'modules';modules.mkdir()
        for n in ('deferred_settings.uc','deferred_backend.uc','deferred_apply.uc','deferred_countries.uc','cmd_fixedconfig.uc'):
            s=(src/n).read_text()
            if n=='deferred_backend.uc':
                s=s.replace("import * as fs from 'fs';","let fs = require('test_fs');\nlet system = require('test_ops').system;")
            if n in ('cmd_fixedconfig.uc','deferred_apply.uc'):
                s=s.replace("require('fs')","require('test_fs')")
            (modules/n).write_text(s)
        (modules/'schemareader.uc').write_text('function validate(doc,logs){return doc;} export {validate};\n')
        q=['/usr/bin/qemu-aarch64','-L',str(a.root),str(a.root/'usr/bin/ucode'),'-L',str(a.root/'usr/lib/ucode'),'-L',str(modules)]
        config=work/'fixture.json'
        # Fixed path redirection exists in test copies only. Production has no
        # environment/test-root bypass. All metadata and writes use real fs.
        common=f"const CONFIG={json.dumps(str(config))};\n"
        (modules/'test_ops.uc').write_text("import * as fs from 'fs';\n"+common+r'''
function system(cmd){
 let c=json(fs.readfile(CONFIG));
 let f=fs.open(c.log,'a');f.write(cmd+'\n');f.close();
 if(c.fail && index(cmd,c.fail)>=0)return 1;
 return 0;
}
return {system};
''')
        (modules/'test_fs.uc').write_text("import * as real from 'fs';\n"+common+r'''
function cfg(){return json(real.readfile(CONFIG));}
function path(p){return substr(p,0,1)=='/'?cfg().root+p:p;}
function lstat(p){return real.lstat(path(p));}
function stat(p){return real.stat(path(p));}
function readfile(p){return real.readfile(path(p));}
function mkdir(p,m){return real.mkdir(path(p),m);}
function chmod(p,m){return real.chmod(path(p),m);}
function unlink(p){return real.unlink(path(p));}
function rename(p,q){if(cfg().rename_fail && index(p,cfg().rename_fail)>=0)return false;return real.rename(path(p),path(q));}
function symlink(p,q){return real.symlink(path(p),path(q));}
function glob(p){return real.glob(path(p));}
function open(p,mode,perms){
 let f=real.open(path(p),mode,perms);if(!f)return null;
 return {write:function(t){return cfg().write_fail && index(p,cfg().write_fail)>=0?0:f.write(t);},flush:()=>f.flush(),close:()=>f.close()};
}
function popen(cmd){
 let c=cfg(),text='',rc=0;
 if(cmd=='/usr/libexec/ucentral-deferred-context'){text='cambiumnetworks,xv3-8\t001122334455\t'+(exists(c,'bank')?c.bank:1)+'\t-\t-\tbanks\t'+(c.ab_state||'confirmed')+'\t'+(exists(c,'confirmed')?c.confirmed:1)+'\t'+(exists(c,'target')?c.target:'-')+'\n';rc=c.bad_context?1:0;}
 else if(substr(cmd,0,10)=='sha256sum '){return real.popen('sha256sum '+path(substr(cmd,10)));}
 else if(index(cmd,'-subject')>=0)text='subject=CN=001122334455\n';
 else if(index(cmd,'openssl')==0)text='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  -\n';
 else if(cmd=='umask 077; mktemp /etc/ucentral/deferred-settings/request.XXXXXX'){
  text='/etc/ucentral/deferred-settings/request.TEST001';let f=real.open(path(text),'w',0600);f.close();
 }
 else if(index(cmd,'ucentral-deferred stage-country')>=0){text=c.response? sprintf('%J',c.response):'null';rc=c.rpc_fail?1:0;}
 else if(index(cmd,'ucentral-deferred stage-config')>=0){text=c.response? sprintf('%J',c.response):'null';rc=c.rpc_fail?1:0;}
 else die('Unisolated process command: '+cmd);
 return {read:()=>text,close:()=>rc};
}
return {lstat,stat,readfile,mkdir,chmod,unlink,rename,symlink,glob,open,popen};
''')
        def fixture(extra=None):
            root=work/'fs';shutil.rmtree(root,ignore_errors=True);root.mkdir(mode=0o700)
            for d in ('etc/ucentral','certificates','proc/sys/kernel/random','sys/module/cfg80211/parameters','lib/functions','tmp/sysinfo'):
                (root/d).mkdir(parents=True,exist_ok=True);(root/d).chmod(0o755)
            files={'etc/ucentral/capabilities.json':{'country_codes':['US','GB']},
                   'certificates/gateway.json':{'server':'controller.example','port':15002,'cert':'/etc/ucentral/operational.pem','ca':'/etc/ucentral/operational.ca','hostname_validate':1},
                   'certificates/ucentral.defaults':{'country':'US','unrelated':{'keep':True}},
                   'certificates/key.pem':'synthetic-private-key','certificates/operational.pem':'synthetic-leaf','certificates/operational.ca':'synthetic-ca',
                   'proc/sys/kernel/random/boot_id':'boot-one','sys/module/cfg80211/parameters/ieee80211_regdom':'US',
                   'lib/functions/cambium-ab.sh':'synthetic-provider','tmp/sysinfo/board_name':'cambiumnetworks,xv3-8',
                   'tmp/ntp.set':'verified-clock-fixture',
                   'etc/modules.conf':'options ath12k panic_on_fw_error=1\noptions cfg80211 debug=1 ieee80211_regdom=US\n'}
            for name,value in files.items():
                p=root/name;p.write_text(json.dumps(value) if isinstance(value,dict) else value);p.chmod(0o600)
            c={'root':str(root),'log':str(work/'commands.log'),**(extra or {})};config.write_text(json.dumps(c));(work/'commands.log').write_text('')
            return root,c
        def run(code,ok=True):
            p=work/'test.uc';p.write_text(code);r=subprocess.run(q+[str(p)],text=True,capture_output=True)
            assert (r.returncode==0)==ok,(code,r.stdout,r.stderr)
            return r
        def case(name,fn):fn();results.append(name)
        prepare="let service=require('deferred_backend').backend(); let r=service.prepare({country:'GB',uuid:1234,id:9});assert(r.phase=='accepted');"
        def accepted():
            root,c=fixture();run(prepare);p=root/'etc/ucentral/deferred-settings/pending.json';assert p.stat().st_mode&0o777==0o600
            assert p.parent.stat().st_mode&0o777==0o700
            assert json.loads((root/'certificates/ucentral.defaults').read_text())['country']=='US'
            assert 'ucentral-module-country' not in (work/'commands.log').read_text()
        case('real-private-accepted-journal-no-live-write',accepted)
        for name,change in [('store-symlink',lambda r:(r/'certificates').rename(r/'real-store')),
                            ('unsafe-store-mode',lambda r:(r/'certificates').chmod(0o777)),
                            ('key-symlink',lambda r:(r/'certificates/key.pem').unlink()),
                            ('unsafe-key-mode',lambda r:(r/'certificates/key.pem').chmod(0o666)),
                            ('wrong-active-mount',lambda r:None)]:
            def reject(name=name,change=change):
                root,c=fixture({'bad_context':name=='wrong-active-mount'});change(root)
                if name=='store-symlink':(root/'certificates').symlink_to(root/'real-store')
                if name=='key-symlink':(root/'certificates/key.pem').symlink_to(root/'certificates/operational.pem')
                run(prepare,False);assert not (root/'etc/ucentral/deferred-settings/pending.json').exists()
            case(name,reject)
        def hardlink():
            root,c=fixture();os.link(root/'certificates/key.pem',root/'extra-link');run(prepare,False)
        case('hardlinked-identity-refused',hardlink)
        for text in ['{"country":"US","country":"GB"}','{"country":"US","\\u0063ountry":"GB"}','{"nested":{"x":1,"x":2}}']:
            case('duplicate-policy-'+str(len(results)),lambda text=text:run('require(\'deferred_backend\').object('+json.dumps(text)+');',False))
        def bad_defaults():
            root,c=fixture();(root/'certificates/ucentral.defaults').write_text('{broken');run(prepare,False)
            assert not (root/'etc/ucentral/deferred-settings/pending.json').exists()
        # Admission must reject malformed policy before returning accepted.
        # The backend baseline parses defaults as well as hashing it.
        case('malformed-defaults-refused',bad_defaults)
        for key in ('write_fail','rename_fail'):
            def failure(key=key):
                root,c=fixture({key:'pending.json'});run(prepare,False);assert json.loads((root/'certificates/ucentral.defaults').read_text())['country']=='US'
            case('journal-'+key+'-no-live-write',failure)
        def retry_empty():
            root,c=fixture({'write_fail':'pending.json'});run(prepare,False)
            del c['write_fail'];config.write_text(json.dumps(c));run(prepare)
            assert json.loads((root/'etc/ucentral/deferred-settings/pending.json').read_text())['phase']=='accepted'
        case('empty-interrupted-journal-retry',retry_empty)
        def commit():
            root,c=fixture();run(prepare);before={p.name:p.read_bytes() for p in (root/'certificates').iterdir() if p.name!='ucentral.defaults'}
            (root/'proc/sys/kernel/random/boot_id').write_text('boot-two');run("let s=require('deferred_backend').backend();assert(s.boot().phase=='boot-staged');")
            defaults=json.loads((root/'certificates/ucentral.defaults').read_text());assert defaults=={'country':'GB','unrelated':{'keep':True}}
            assert before=={p.name:p.read_bytes() for p in (root/'certificates').iterdir() if p.name!='ucentral.defaults'}
            assert (root/'etc/ucentral/country').read_text()=='GB\n'
            run("require('deferred_backend').backend().confirm();",False)
            (root/'sys/module/cfg80211/parameters/ieee80211_regdom').write_text('GB');run("assert(require('deferred_backend').backend().confirm().phase=='active');")
        case('real-country-commit-preserves-identity-and-other-defaults',commit)
        def partial():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two')
            c['rename_fail']='ucentral.defaults';config.write_text(json.dumps(c));run("require('deferred_backend').backend().boot();",False)
            assert json.loads((root/'certificates/ucentral.defaults').read_text())['country']=='US'
            del c['rename_fail'];config.write_text(json.dumps(c));run("assert(require('deferred_backend').backend().boot().phase=='boot-staged');")
        case('partial-defaults-rename-restart-recovery',partial)
        def clock():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two');(root/'tmp/ntp.set').unlink()
            run("require('deferred_backend').backend().boot();")
            run("require('deferred_backend').backend().confirm();",False)
            assert json.loads((root/'etc/ucentral/deferred-settings/pending.json').read_text())['phase']=='boot-staged'
            (root/'tmp/ntp.set').write_text('verified');(root/'sys/module/cfg80211/parameters/ieee80211_regdom').write_text('GB')
            run("assert(require('deferred_backend').backend().confirm().phase=='active');")
        case('pre-driver-stage-is-not-clock-verified-activation',clock)
        def expiry():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two');c['fail']='-checkend';config.write_text(json.dumps(c))
            run("require('deferred_backend').backend().boot();")
            run("require('deferred_backend').backend().confirm();",False)
            assert json.loads((root/'etc/ucentral/deferred-settings/pending.json').read_text())['phase']=='boot-staged'
        case('time-independent-boot-chain-still-requires-final-validity',expiry)
        def replay():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two');run("require('deferred_backend').backend().boot();")
            (root/'sys/module/cfg80211/parameters/ieee80211_regdom').write_text('GB');run("require('deferred_backend').backend().confirm();")
            (root/'proc/sys/kernel/random/boot_id').write_text('boot-three');(root/'etc/ucentral/country').write_text('US')
            c['bank']=0;config.write_text(json.dumps(c));run("require('deferred_backend').backend().boot();")
            assert (root/'etc/ucentral/country').read_text()=='GB\n'
            assert json.loads((root/'certificates/ucentral.defaults').read_text())['unrelated']=={'keep':True}
        case('completed-country-replay-on-managed-upgrade-new-bank',replay)
        def migrate():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two')
            c.update(bank=0,ab_state='trial-started',confirmed=1,target=0);config.write_text(json.dumps(c))
            run("require('deferred_backend').backend().boot();")
            record=json.loads((root/'etc/ucentral/deferred-settings/pending.json').read_text());assert record['binding']['bank']==0 and record['bank_transition']=={'source':1,'target':0}
        case('accepted-pending-migration-only-to-tracked-trial-target',migrate)
        def restriction():
            root,c=fixture();p=root/'etc/ucentral/restrictions.json';p.write_text('{"country":["US"]}');p.chmod(0o600)
            run(prepare,False)
        case('actual-renderer-country-restriction-field',restriction)
        def concurrent():
            root,c=fixture();run(prepare);(root/'proc/sys/kernel/random/boot_id').write_text('boot-two');(root/'certificates/ucentral.defaults').write_text('{"country":"US","operator":"new"}')
            run("require('deferred_backend').backend().boot();",False);assert json.loads((root/'certificates/ucentral.defaults').read_text())['operator']=='new'
        case('concurrent-defaults-edit-not-overwritten',concurrent)
        # Run the real override command with command/ubus boundaries isolated.
        def rpc(ok):
            response={'uuid':1234,'id':9,'status':{'error':0,'text':'Reboot required','reboot_required':True,'applied':False}}
            root,c=fixture({'response':response,'rpc_fail':not ok});(root/'etc/ucentral/ucentral.active').write_text('{"uuid":1234}')
            script="let fs=require('test_fs');let ctx={call:function(o,m,v){print(sprintf('%J\\n',v));}};function result_json(v){ctx.call('ucentral','result',{id:9,status:v});}include("+json.dumps(str(modules/'cmd_fixedconfig.uc'))+",{fs,ctx,result_json,args:{country:'GB'},id:9});"
            r=run(script);events=[json.loads(x) for x in r.stdout.splitlines()];assert len(events)==1
            assert events[0]==response if ok else events[0]['status']['error']==2
        case('actual-fixedconfig-one-correlated-deferred-reply',lambda:rpc(True))
        case('actual-fixedconfig-stage-failure-one-error-reply',lambda:rpc(False))
        # Verify renderer patch applies to the real qualified renderer. Run its
        # exact pre-apply block with schema/process/ubus boundaries isolated.
        patched=work/'schema';shutil.copytree(a.baseline,patched,ignore=shutil.ignore_patterns('*.new','native'))
        subprocess.run(['patch','--fuzz=0','-p1','-d',str(patched),'-i',str((a.repo/'feeds/ucentral/ucentral-schema/patches/099-common-deferred-configuration.patch').resolve())],check=True,capture_output=True)
        source=(patched/'renderer/ucentral.uc').read_text();block=source[source.index('// Validate and durably accept'):source.index('function wait_wireless_ready()')]
        for name,response,fail,expected in [('renderer-deferred',{'uuid':1234,'id':9,'status':{'error':0,'text':'Reboot required','reboot_required':True}},False,75),('renderer-normal',None,False,0),('renderer-stage-failure',None,True,1)]:
            root,c=fixture({'response':response,'rpc_fail':fail})
            code="import * as schemareader from 'schemareader';let ubus={call:function(o,m,v){print(sprintf('%J\\n',v));}};let inputjson={uuid:1234,radios:[]};let boot_render=false,custom_config=false,logs=[];"+block+"print('LIVE_EFFECT_BOUNDARY\\n');"
            script=work/'renderer-test.uc';script.write_text(code);r=subprocess.run(q+[str(script),'/etc/ucentral/ucentral.cfg.0000001234','9'],text=True,capture_output=True)
            assert r.returncode==expected,(name,r.stdout,r.stderr)
            if expected:assert 'LIVE_EFFECT_BOUNDARY' not in r.stdout and len(r.stdout.splitlines())==1
            else:assert 'LIVE_EFFECT_BOUNDARY' in r.stdout
            results.append(name)
        (a.repo/'target-test-receipt.json').write_text(json.dumps({'passed':True,'count':len(results),'cases':results,'scope':'Actual target ucode and real root-owned fixture filesystem; production backend source with fixed-path redirection in test copies only. Cryptographic, hardware, schema and process boundaries explicitly isolated; actual shared renderer pre-apply block, RPC override, private publication and restart logic executed. No firmware/AP actions.'},indent=2)+'\n')
        print(json.dumps({'passed':True,'count':len(results),'cases':results},indent=2))
    finally:shutil.rmtree(work)

if __name__=='__main__':main()
