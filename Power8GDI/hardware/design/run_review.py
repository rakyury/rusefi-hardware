"""Rebuild the electrical review in pinned KiCad; record failed release gates."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
BASE='Power8GDI/hardware/design/'
IMAGE='kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');parser.add_argument('--skip-board-build',action='store_true')
    args=parser.parse_args();commands=[]
    def run(cmd,allowed=(0,)):
        r=subprocess.run(cmd,cwd=REPO,text=True,encoding='utf-8',errors='replace',capture_output=True)
        commands.append({'command':cmd,'returncode':r.returncode,'output':r.stdout+r.stderr})
        print(f'{cmd[-1]}: exit {r.returncode}',flush=True)
        if r.returncode not in allowed:
            print(r.stdout+r.stderr);raise RuntimeError('Required check failed')
        return r.returncode
    def host(*a):return run([sys.executable,*a])
    def cad(*a,allowed=(0,)):
        return run(['docker','run','--rm','--network','none','--mount',f'type=bind,source={REPO},target=/src','-w','/src',IMAGE,*a],allowed)
    out=HERE/'board/review';out.mkdir(exist_ok=True,parents=True)
    summary={'release_status':'BLOCKED','qualification':'INCOMPLETE_ENGINEERING_REVIEW','image':IMAGE,'commands':commands}
    try:
        for script in ['power_input/build_power_input.py','motor/build_motor.py','safety/generate.py','board/build_connector_schematic.py','build_core_schematic.py']:
            host(BASE+script)
        # GDI reference sources remain unchanged; re-export their actual leaves.
        leaves=['power_input/power_input','motor/dbw_driver','motor/ewg_driver','safety/safety_gate','board/connectors','gdi/stage_a','gdi/stage_b','Power8GDI_Core']
        for name in leaves:
            target='core.net' if name=='Power8GDI_Core' else name+'.xml'
            cad('kicad-cli','sch','export','netlist','--format','kicadxml','-o',BASE+target,BASE+name+'.kicad_sch')
        summary['erc_native_exit']=cad('kicad-cli','sch','erc','--format','json','--exit-code-violations','-o',BASE+'core_erc.json',BASE+'Power8GDI_Core.kicad_sch',allowed=(0,5))
        host(BASE+'verify_core.py','--erc',BASE+'core_erc.json','--output',BASE+'core_checks.json')
        host(BASE+'verify_integration.py')
        for folder in ['core_tests','board/tests']:
            host('-m','unittest','discover','-s',BASE+folder,'-v')
        for script in ['power_input/check_power_input.py','motor/check_motor.py','safety/test_safety.py','gdi/test_schematic.py']:
            host(BASE+script)
        host('-m','unittest','discover','-s','Power8GDI/hardware/tests','-v')
        host('Power8GDI/hardware/audit_resources.py','--gate','structure','--output','Power8GDI/hardware/resource_audit_report.json')
        if not args.skip_board_build:cad('python3',BASE+'board/build_board.py')
        board=BASE+'board/review/Power8GDI_Review.kicad_pcb'
        cad('python3',BASE+'board/verify_board.py',board,BASE+'core.net')
        summary['drc_native_exit']=cad('python3',BASE+'board/run_drc.py',board,'--output',BASE+'board/review/drc.json',allowed=(0,5))
        cad('python3',BASE+'board/summarize_drc.py',board,BASE+'board/review/drc.json',BASE+'board/review/net_coverage.json')
        cad('kicad-cli','sch','export','pdf','-o',BASE+'core_preview.pdf',BASE+'Power8GDI_Core.kicad_sch')
        for label,layers in [('front','F.Cu,F.SilkS,Edge.Cuts'),('back','B.Cu,B.SilkS,Edge.Cuts')]:
            cad('kicad-cli','pcb','export','svg','--layers',layers,'--mode-single','--page-size-mode','2','--exclude-drawing-sheet','-o',BASE+'board/review/'+label+'.svg',board)
        doc=ET.parse(HERE/'core.net')
        with (HERE/'integrated_bom.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['Reference','Value','Footprint','DNP','Sheet'])
            for c in doc.findall('components/comp'):
                w.writerow([c.get('ref'),c.findtext('value'),c.findtext('footprint'),any(p.get('name')=='dnp' for p in c.findall('property')),c.find('sheetpath').get('names')])
        erc=json.loads((HERE/'core_erc.json').read_text());summary['erc_counts']=dict(Counter(v['type'] for s in erc['sheets'] for v in s['violations']))
        coverage=json.loads((out/'net_coverage.json').read_text());summary['drc_counts']=coverage['violations'];summary['unconnected_items']=coverage['unconnected_items']
        if coverage['violations'].get('shorting_items',0):
            raise RuntimeError('PCB contains cross-net shorts; review regression rejected')
        summary['structural_checks']='PASS';summary['source_sha256']={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'core.net',out/'Power8GDI_Review.kicad_pcb',out/'Power8GDI_Review.kicad_pro']}
    except Exception as e:
        summary['structural_checks']='FAIL';summary['error']=str(e)
    (HERE/'review_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='commands'},indent=2))
    return 1 if summary['structural_checks']=='FAIL' else 2 if args.release else 0

if __name__=='__main__':raise SystemExit(main())
