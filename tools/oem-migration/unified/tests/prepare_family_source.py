"""Prepare package sources from repository patches; never build firmware."""
from pathlib import Path
import subprocess


def prepare_thor(repo: Path, root: Path):
    prefixes = ('package/cambium/cambium-ab/',
                'package/cambium/cambium-thor-support/')
    applied = []
    for patch in sorted((repo / 'patches-25.12').glob('*.patch')):
        if patch.name[:4].isdigit() and int(patch.name[:4]) >= 181:
            continue
        sections = []
        lines = patch.read_text().splitlines(keepends=True)
        starts = [i for i, line in enumerate(lines) if line.startswith('--- ')
                  and i + 1 < len(lines) and lines[i + 1].startswith('+++ ')]
        for position, start in enumerate(starts):
            target = lines[start + 1].split()[1]
            if not target.startswith(tuple('b/' + p for p in prefixes)):
                continue
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            body = lines[start:end]
            for i, line in enumerate(body):
                if line.startswith('diff --git ') or line.startswith('-- \n'):
                    body = body[:i]
                    break
            sections.append(''.join(body))
        if not sections:
            continue
        selected = root / 'selected.patch'
        selected.write_text(''.join(sections))
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(selected)],
                       cwd=root, check=True, capture_output=True, text=True)
        applied.append(patch.name)
    (root / 'selected.patch').unlink(missing_ok=True)
    for relative in ('cambium-ab/files/cambium-ab.sh',
                     'cambium-ab/files/cambium-ab-upgrade.sh',
                     'cambium-thor-support/files/cambium-ab-thor.sh'):
        if not (root / 'package/cambium' / relative).is_file():
            raise RuntimeError('Prepared Thor source is incomplete: ' + relative)
    print('Thor prepared source patches: ' + ', '.join(applied), flush=True)
    return root
