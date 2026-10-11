import importlib.util,subprocess,tempfile,unittest
from pathlib import Path
from test_unified import BASE,BUILDER,Fixture,MODELS,digest

class ReleaseTests(unittest.TestCase):
    def test_metadata_first_package_retains_map_and_omits_all_declared_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();provider=root/'provider';provider.mkdir()
            (provider/'models.tsv').write_text('0000002c\tmiami\tX7-35X\t-\t7.2-r1\n')
            rows=[]
            for model in ('X7-35X','E410'):
                name=f'payloads/{model}/kernel.itb';p=provider/name;p.parent.mkdir(parents=True);p.write_bytes(model.encode())
                rows.append(f'{model}\tinstall\t{name}\tobjects/{model}.itb\t{p.stat().st_size}\t{digest(p)}\n')
            (provider/'payload-map.tsv').write_text(''.join(rows))
            (provider/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(provider))+'\n' for p in sorted(provider.rglob('*')) if p.is_file()))
            output=root/'output'
            BUILDER.prepare(provider,digest(provider/'SHA256SUMS'),output,'controller.example.test','http://download.example.test','http://backup.example.test',metadata_first=True)
            self.assertTrue((output/'payload-map.tsv').is_file());self.assertFalse((output/'payloads').exists())
            self.assertIn('payload-map.tsv',(output/'SHA256SUMS').read_text())
            self.assertNotIn('kernel.itb',(output/'SHA256SUMS').read_text())
            self.assertTrue((output/'cambium-oem-install').is_file())

    def test_source_package_freezes_verified_members_and_canonical_aliases(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();provider=root/'provider';provider.mkdir()
            (provider/'models.tsv').write_text('0000002c\tmiami\tX7-35X\t-\t7.2-r1\n')
            (provider/'SHA256SUMS').write_text(digest(provider/'models.tsv')+'  models.tsv\n')
            output=root/'output'
            pin=BUILDER.prepare(provider,digest(provider/'SHA256SUMS'),output,'controller.example.test','http://download.example.test','http://backup.example.test')
            self.assertEqual(pin,digest(output/'SHA256SUMS'))
            for canonical,legacy in [('cambium-oem-install','installer.sh'),('cambium-oem-restore-test','oem-restore-test.sh'),('cambium-ab-ready','check-sysupgrade-ready.sh')]:
                self.assertEqual((output/canonical).read_bytes(),(output/legacy).read_bytes())
                self.assertEqual((output/canonical).stat().st_mode&0o777,0o700)
                p=subprocess.run(['sh',str(output/canonical),'--help'],capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr);self.assertIn('Usage:',p.stdout)
            self.assertEqual(output.stat().st_mode&0o777,0o700)
    def test_untrusted_input_and_framework_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();provider=root/'provider';provider.mkdir()
            (provider/'models.tsv').write_text('0000002c\tmiami\tX7-35X\t-\t7.2-r1\n')
            (provider/'SHA256SUMS').write_text(digest(provider/'models.tsv')+'  models.tsv\n')
            with self.assertRaises(ValueError):BUILDER.prepare(provider,'0'*64,root/'out','controller.example.test','http://download.example.test','http://backup.example.test')
            self.assertFalse((root/'out').exists())
            (provider/'lib').mkdir();(provider/'lib/common.sh').write_text('malicious source\n')
            (provider/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(provider))+'\n' for p in (provider/'models.tsv',provider/'lib/common.sh')))
            with self.assertRaises(ValueError):BUILDER.prepare(provider,digest(provider/'SHA256SUMS'),root/'out','controller.example.test','http://download.example.test','http://backup.example.test')
            self.assertFalse((root/'out').exists())
    def test_documented_commands_exist_and_help_is_consistent(self):
        docs=(BASE/'README.md').read_text()
        for source,command in [('installer.sh','cambium-oem-install'),('oem-restore-test.sh','cambium-oem-restore-test'),('check-sysupgrade-ready.sh','cambium-ab-ready')]:
            self.assertIn(command,docs)
            p=subprocess.run(['sh',str(BASE/source),'--help'],capture_output=True,text=True)
            self.assertEqual(p.returncode,0);self.assertIn(command,p.stdout)
    def test_actual_installed_readiness_command_uses_shared_hook(self):
        repo=BASE.parents[2];command=repo/'feeds/tip/certificates/files/usr/sbin/cambium-ab-ready'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'system.sh').write_text('')
            fixture=command.read_text().replace('/lib/functions/system.sh',str(root/'system.sh')).replace('/lib/functions/cambium-ab.sh',str(root/'ab.sh'))
            script=root/'ready';script.write_text(fixture)
            for status,code in [('unsupported',1),('onboarded',1),('ready',0)]:
                (root/'ab.sh').write_text('ab_family(){ AB_FAMILY=miami;AB_MODEL=X7-35X; };ab_identity(){ AB_ACTIVE=0; };ab_sysupgrade_readiness(){ AB_UPGRADE_READY='+status+';AB_UPGRADE_REASON=fixture; };\n')
                p=subprocess.run(['sh',str(script)],capture_output=True,text=True)
                self.assertEqual(p.returncode,code,p.stderr);self.assertIn('schema\t1',p.stdout);self.assertIn('status\t'+status,p.stdout)
            for args in (['--help'],['bad']):
                p=subprocess.run(['sh',str(script),*args],capture_output=True,text=True);self.assertEqual(p.returncode,0 if args==['--help'] else 2)


class PatchedRuntimeTests(unittest.TestCase):
    def test_readiness_dispatcher_applies_to_actual_core_and_never_mutates(self):
        repo=BASE.parents[2];creation=(repo/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
        mark='+++ b/package/cambium/cambium-ab/files/cambium-ab.sh\n';section=creation[creation.index(mark):];section=section[:section.index('\ndiff --git ')]
        original='\n'.join(r[1:] for r in section.splitlines() if r.startswith('+') and not r.startswith('+++'))+'\n'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);target=root/'package/cambium/cambium-ab/files/cambium-ab.sh';target.parent.mkdir(parents=True);target.write_text(original)
            result=subprocess.run(['patch','--fuzz=0','-p1','-i',str(repo/'patches-25.12/0183-cambium-ab-readonly-upgrade-readiness.patch')],cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for family in ('sage','jaguar','cheetah','thor','miami','gambit'):
                for state in ('missing','onboarded','ready','invalid'):
                    script='. "'+str(target)+'"; AB_FAMILY='+family+';'
                    if state!='missing':script+='ab_'+family+'_sysupgrade_readiness(){ AB_UPGRADE_READY='+state+'; AB_UPGRADE_REASON=fixture; };'
                    script+='fw_setenv(){ echo FORBIDDEN; return 99; };ab_sysupgrade_readiness; result=$?;printf "%s:%s" "$AB_UPGRADE_READY" "$AB_UPGRADE_REASON";exit "$result"'
                    result=subprocess.run(['sh','-c',script],capture_output=True,text=True)
                    self.assertEqual(result.returncode,1 if state=='invalid' else 0,result.stderr)
                    self.assertNotIn('FORBIDDEN',result.stdout)
                    if state=='missing':self.assertIn('unsupported:readiness-hook-unavailable',result.stdout)

    def test_actual_base_status_patch_all_model_cli_and_legacy_output(self):
        repo=BASE.parents[2]
        creation=(repo/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
        mark='+++ b/package/cambium/cambium-ab/files/cambium-ab-status\n';section=creation[creation.index(mark):];section=section[:section.index('\ndiff --git ')]
        original='\n'.join(r[1:] for r in section.splitlines() if r.startswith('+') and not r.startswith('+++'))+'\n'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);target=root/'package/cambium/cambium-ab/files/cambium-ab-status';target.parent.mkdir(parents=True);target.write_text(original)
            p=subprocess.run(['patch','--fuzz=0','-p1','-i',str(repo/'patches-25.12/0185-cambium-ab-versioned-readonly-status.patch')],cwd=root,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            system=root/'system';system.write_text('')
            for model in MODELS:
                with self.subTest(model=model['model']):
                    lib=root/'ab';lib.write_text('ab_family(){ AB_FAMILY='+model['family']+';AB_MODEL='+model['model']+';AB_ENV='+model['family']+'; };ab_converted(){ return 0; };ab_running_slot(){ echo 0; };ab_getenv(){ echo confirmed; };\n')
                    env={'PATH':'/usr/bin:/bin','CAMBIUM_SYSTEM_FUNCTIONS':str(system),'CAMBIUM_AB_LIB':str(lib),'CAMBIUM_BDF_STATUS':str(root/'missing')}
                    for args in ([],['--format','tsv'],['--help'],['bad']):
                        p=subprocess.run(['sh',str(target),*args],env=env,capture_output=True,text=True)
                        self.assertEqual(p.returncode,2 if args==['bad'] else 0,p.stderr)
                        if not args:self.assertIn('family='+model['family'],p.stdout)
                        if args==['--format','tsv']:self.assertIn('schema\t1',p.stdout);self.assertIn('family\t'+model['family'],p.stdout)
            lib.write_text('ab_family(){ return 1; };\n')
            p=subprocess.run(['sh',str(target)],env=env,capture_output=True,text=True);self.assertEqual(p.returncode,0);self.assertEqual(p.stdout,'mode=none\n')
            p=subprocess.run(['sh',str(target),'--format','tsv'],env=env,capture_output=True,text=True);self.assertEqual(p.returncode,1);self.assertIn('status\tunsupported',p.stdout)

if __name__=='__main__':unittest.main()

class LegacySafetyTests(unittest.TestCase):
    def test_conversion_override_refuses_before_any_runtime_library(self):
        repo=BASE.parents[2];creation=(repo/'patches-25.12/0124-qualcommax-add-Cambium-Jaguar-OpenWiFi-family.patch').read_text()
        mark='+++ b/package/cambium/cambium-ab/files/cambium-ab-convert\n';section=creation[creation.index(mark):];section=section[:section.index('\ndiff --git ')]
        original='\n'.join(r[1:] for r in section.splitlines() if r.startswith('+') and not r.startswith('+++'))+'\n'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);target=root/'package/cambium/cambium-ab/files/cambium-ab-convert';target.parent.mkdir(parents=True);target.write_text(original)
            p=subprocess.run(['patch','--fuzz=0','-p1','-i',str(repo/'patches-25.12/0186-cambium-ab-reject-untested-conversion-override.patch')],cwd=root,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            marker=root/'library-ran';lib=root/'library';lib.write_text('touch "'+str(marker)+'"\n')
            env={'PATH':'/usr/bin:/bin','CAMBIUM_SYSTEM_FUNCTIONS':str(lib),'CAMBIUM_AB_LIB':str(lib),'CAMBIUM_AB_UPGRADE_LIB':str(lib)}
            for args in (['--allow-untested'],['--yes','--allow-untested'],['--resume','--yes','--allow-untested']):
                p=subprocess.run(['sh',str(target),*args],env=env,capture_output=True,text=True)
                self.assertEqual(p.returncode,2);self.assertFalse(marker.exists());self.assertIn('no longer supported',p.stderr)
