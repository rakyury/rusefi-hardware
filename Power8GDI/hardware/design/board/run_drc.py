"""Run the unchanged KiCad DRC with local copies of custom footprint libraries.

Docker Desktop bind-mounted libraries are slow to compare per footprint. This
copies bytes to a temporary Linux directory, not a modified board/ruleset.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();board=args.board.resolve();output=args.output.resolve()
    with tempfile.TemporaryDirectory(prefix='power8gdi-drc-') as temporary:
        target=Path(temporary);project=board.with_suffix('.kicad_pro')
        shutil.copy2(board,target/board.name);shutil.copy2(project,target/project.name)
        table=(board.parent/'fp-lib-table').read_text()
        def localize(match):
            uri=match.group(1)
            if '${KIPRJMOD}' not in uri:return match.group(0)
            source=Path(uri.replace('${KIPRJMOD}',str(board.parent))).resolve()
            if not source.is_dir():raise FileNotFoundError(source)
            shutil.copytree(source,target/source.name,dirs_exist_ok=True)
            return '(uri "${KIPRJMOD}/'+source.name+'")'
        (target/'fp-lib-table').write_text(re.sub(r'\(uri "([^"]+)"\)',localize,table))
        command=['kicad-cli','pcb','drc','--format','json','--all-track-errors','--severity-all','--exit-code-violations',
                 '-o',str(output),str(target/board.name)]
        completed=subprocess.run(command,check=False)
        metadata={'board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),
                  'project_sha256':hashlib.sha256(project.read_bytes()).hexdigest(),
                  'command':command,'returncode':completed.returncode,'rule_exclusions_added':False}
        output.with_suffix('.provenance.json').write_text(json.dumps(metadata,indent=2)+'\n')
        raise SystemExit(completed.returncode)
