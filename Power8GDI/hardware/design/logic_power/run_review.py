"""Reproduce exports/tests with the project's pinned KiCad9 image."""
from pathlib import Path
import subprocess,json,sys
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
IMAGE='kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729'
BASE='/repo/Power8GDI/hardware/design/logic_power'
def docker(entry,*args):
    subprocess.run(['docker','run','--rm','--network','none','--mount',f'type=bind,source={REPO},target=/repo','--entrypoint',entry,IMAGE,*args],check=True)
def main():
    (HERE/'work').mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(HERE/'build_logic_power.py')],check=True)
    subprocess.run([sys.executable,str(HERE/'calculate.py')],check=True,stdout=subprocess.DEVNULL)
    for name in ['logic_5v','logic_3v3']:
        docker('kicad-cli','sch','export','netlist','--format','kicadxml','-o',f'{BASE}/work/{name}.xml',f'{BASE}/{name}.kicad_sch')
        docker('kicad-cli','sch','erc','--format','json','-o',f'{BASE}/work/{name}.erc.json',f'{BASE}/{name}.kicad_sch')
        docker('kicad-cli','sch','export','svg','-o',f'{BASE}/work/svg',f'{BASE}/{name}.kicad_sch')
    docker('python3',BASE+'/check_footprints.py')
    subprocess.run([sys.executable,str(HERE/'check_logic_power.py')],check=True)
    erc={name:json.loads((HERE/'work'/f'{name}.erc.json').read_text()) for name in ['logic_5v','logic_3v3']}
    counts={name:len([v for s in r['sheets'] for v in s['violations']]) for name,r in erc.items()}
    (HERE/'validation.json').write_text(json.dumps({'image':IMAGE,'checks':'8 independent electrical and mutation tests PASS;32 footprint pad checks PASS','erc_counts':counts,'erc_disposition':'Visible standalone power-source / cross-sheet diagnostics. Not a clean full-board ERC or DRC report.','standalone_erc':erc},indent=2)+'\n')
    print('PASS: independent netlist/pad checks. Standalone ERC:',counts)
if __name__=='__main__':main()
