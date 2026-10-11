"""Exercise actual recipe make expansion with isolated PatchDir recording."""
from pathlib import Path
import subprocess,sys,tempfile
source=Path(sys.argv[1]).read_text()
start=source.index('ifdef CONFIG_TARGET_PROFILE')
end=source.index('define Build/Compile',start)
body=source[start:end]
with tempfile.TemporaryDirectory(prefix='regdb-profile-') as td:
 p=Path(td)/'Makefile'
 p.write_text('PKG_BUILD_DIR:=fixture\nBuild/Patch/Default=$(info DEFAULT-PATCH)\nPatchDir=$(info PROFILE-PATCH:$(2))\n'+body+'\nall:\n\t$(Build/Patch)\n\t@true\n')
 for value in [None,'','""','"DEVICE_example"']:
  args=['make','-s','-f',str(p)]
  if value is not None:args.append('CONFIG_TARGET_PROFILE='+value)
  text=subprocess.check_output(args,text=True)
  assert 'DEFAULT-PATCH' in text,text
  if value=='"DEVICE_example"':assert 'PROFILE-PATCH:patches-example/' in text,text
  else:assert 'PROFILE-PATCH:' not in text,text
print('PASS: default patch pass retained; absent/empty/quoted-empty profile never reads /; selected profile preserved')
