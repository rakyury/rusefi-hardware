"""Recreate exports with --kicad; --require-ready fails until electrical release."""
from pathlib import Path
from collections import Counter
import argparse
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
IMAGE='kicad/kicad:9.0'
BASE='/repo/Power8GDI/hardware/design/safety/'

def docker(entry,*args,allowed=(0,)):
    cmd=['docker','run','--rm','--network','none','--mount',f'type=bind,source={ROOT},target=/repo','--entrypoint',entry,IMAGE,*args]
    r=subprocess.run(cmd,text=True,capture_output=True)
    if r.stdout.strip():print(r.stdout.strip())
    if r.returncode not in allowed:print(r.stderr,file=sys.stderr);raise SystemExit(r.returncode)
    return r

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kicad',action='store_true');parser.add_argument('--require-ready',action='store_true');a=parser.parse_args()
    reports=HERE/'reports';reports.mkdir(exist_ok=True)
    if a.kicad:
        version=docker('kicad-cli','version').stdout.strip()
        docker('kicad-cli','sch','export','netlist','--format','kicadxml','-o',BASE+'safety_gate.xml',BASE+'safety_gate.kicad_sch')
        result=docker('kicad-cli','sch','erc','--exit-code-violations','--format','json','-o',BASE+'reports/erc.json',BASE+'safety_gate.kicad_sch',allowed=(0,5))
        docker('kicad-cli','sch','export','svg','-o',BASE+'reports/',BASE+'safety_gate.kicad_sch')
        docker('python3',BASE+'footprints.py')
        svg=reports/'safety_gate.svg';svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n')
        erc=json.loads((reports/'erc.json').read_text());v=[v for s in erc['sheets'] for v in s['violations']]
        summary={'kicad_version':version,'erc_exit':result.returncode,'erc_count':len(v),'by_type':dict(Counter(x['type'] for x in v)),'by_severity':dict(Counter(x['severity'] for x in v)),'release_status':'BLOCKED','hardware_tests':'NOT RUN','analogue_simulation':'NOT RUN'}
        (reports/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    r=subprocess.run([sys.executable,str(HERE/'test_safety.py')])
    if r.returncode:return r.returncode
    print('Offline safety connectivity and logical transitions PASS. Physical/release qualification BLOCKED.')
    return 2 if a.require_ready else 0

if __name__=='__main__':raise SystemExit(main())
