"""Prepare the actual shared package from this checkout's ordered source hunks."""
from pathlib import Path
import subprocess

def prepare_package(repo: Path, root: Path):
 root.mkdir(parents=True,exist_ok=True)
 for patch in sorted((repo/'patches-25.12').glob('*.patch')):
  lines=patch.read_text().splitlines(keepends=True)
  starts=[i for i,l in enumerate(lines) if l.startswith('--- ') and i+1<len(lines) and lines[i+1].startswith('+++ ')]
  parts=[]
  for pos,i in enumerate(starts):
   if not lines[i+1].split()[1].startswith('b/package/cambium/cambium-ab/'):continue
   part=lines[i:starts[pos+1] if pos+1<len(starts) else len(lines)]
   for j,l in enumerate(part):
    if l.startswith(('diff --git ','-- \n')):part=part[:j];break
   parts.append(''.join(part))
  if not parts:continue
  selected=root/'selected.patch';selected.write_text(''.join(parts))
  result=subprocess.run(['patch','--forward','--batch','--fuzz=0','-p1','-i',str(selected)],cwd=root,capture_output=True,text=True)
  assert result.returncode==0,(patch.name,result.stdout,result.stderr)
  if patch.name.startswith('0169-'):assert 'offset' not in result.stdout,(patch.name,result.stdout)
 package=root/'package/cambium/cambium-ab'
 for path in (package/'files').iterdir():
  if path.suffix not in ('.orig','.rej'):subprocess.run(['sh','-n',str(path)],check=True)
 return package
