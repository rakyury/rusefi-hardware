"""Rebuild the electrical review in pinned KiCad; record failed release gates."""
from pathlib import Path
from collections import Counter
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
BASE='Power8GDI/hardware/design/'
IMAGE='kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729'

def main():
    # Generated KiCad text and primary-source comments are UTF-8 on Windows too.
    os.environ['PYTHONUTF8']='1'
    parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');parser.add_argument('--skip-board-build',action='store_true')
    parser.add_argument('--schematic-only',action='store_true',help='Validate the current schematic without claiming verification of an older PCB')
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
        # Linux bind mounts retain host ownership; the image's default UID is
        # not necessarily the CI runner's UID. Windows Docker handles this itself.
        identity=[] if os.name=='nt' else ['--user',f'{os.getuid()}:{os.getgid()}',
            '--env','HOME=/tmp','--env','XDG_CONFIG_HOME=/tmp/.config','--env','XDG_CACHE_HOME=/tmp/.cache']
        return run(['docker','run','--rm','--network','none',*identity,'--mount',f'type=bind,source={REPO},target=/src','-w','/src',IMAGE,*a],allowed)
    out=HERE/'board/review';out.mkdir(exist_ok=True,parents=True)
    summary={'release_status':'BLOCKED','qualification':'INCOMPLETE_ENGINEERING_REVIEW','image':IMAGE,'commands':commands}
    try:
        for script in ['logic_power/build_logic_power.py','logic_power/calculate.py','motor4/build_motor4.py','safety/generate.py','board/build_connector_schematic.py','interfaces/build_interfaces.py','interfaces_aux/build_aux.py','gdi/generate.py','gdi/build_protection.py','wbo/build_wbo.py','build_core_schematic.py']:
            host(BASE+script)
        (HERE/'logic_power/work').mkdir(exist_ok=True)
        # GDI reference sources remain unchanged; re-export their actual leaves.
        leaves=['safety/safety_gate','board/connectors','gdi/stage_a','gdi/stage_b','Power8GDI_Core']
        leaves=leaves[:-1]+[s['name'] for s in json.loads((HERE/'interfaces/interfaces_manifest.json').read_text())['sheets']]+['interfaces_aux/'+s['name'] for s in json.loads((HERE/'interfaces_aux/interface.json').read_text())['sheets']]+[s['name'] for s in json.loads((HERE/'gdi/protection_manifest.json').read_text())['sheets']]+[s['name'] for s in json.loads((HERE/'wbo/interface.json').read_text())['sheets']]+[s['name'] for s in json.loads((HERE/'logic_power/interface.json').read_text())['sheets']]+[s['name'] for s in json.loads((HERE/'motor4/interface.json').read_text())['sheets']]+['Power8GDI_Core']
        for name in leaves:
            target='core.net' if name=='Power8GDI_Core' else name.replace('logic_power/','logic_power/work/')+'.xml'
            cad('kicad-cli','sch','export','netlist','--format','kicadxml','-o',BASE+target,BASE+name+'.kicad_sch')
        doc=ET.parse(HERE/'core.net')
        with (HERE/'integrated_bom.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(['Reference','Value','Footprint','DNP','Sheet'])
            for c in doc.findall('components/comp'):
                w.writerow([c.get('ref'),c.findtext('value'),c.findtext('footprint'),any(p.get('name')=='dnp' for p in c.findall('property')),c.find('sheetpath').get('names')])
        summary['erc_native_exit']=cad('kicad-cli','sch','erc','--format','json','--exit-code-violations','-o',BASE+'core_erc.json',BASE+'Power8GDI_Core.kicad_sch',allowed=(0,5))
        host(BASE+'verify_core.py','--erc',BASE+'core_erc.json','--output',BASE+'core_checks.json')
        host(BASE+'verify_integration.py')
        host('-m','unittest','discover','-s',BASE+'core_tests','-v')
        cad('python3','-m','unittest','discover','-s',BASE+'board/tests','-v')
        for script in ['outputs/check_outputs.py','interfaces/check_interfaces.py','interfaces_aux/test_aux.py','safety/test_safety.py','gdi/test_schematic.py']:
            host(BASE+script)
        cad('python3',BASE+'logic_power/check_footprints.py')
        host(BASE+'logic_power/check_logic_power.py')
        host(BASE+'logic_power/check_logic_power.py',BASE+'core.net')
        cad('python3',BASE+'motor4/verify_motor4.py')
        host(BASE+'interfaces/test_interfaces.py')
        host(BASE+'interfaces_aux/test_aux.py','--netlist',BASE+'core.net')
        host(BASE+'gdi/test_protection.py')
        cad('python3',BASE+'wbo/verify_wbo.py')
        host('Power8GDI/hardware/audit_resources.py','--gate','structure','--output','Power8GDI/hardware/resource_audit_report.json')
        host('-m','unittest','discover','-s','Power8GDI/hardware/tests','-v')
        host(BASE+'ignition/test_ignition.py')
        if args.schematic_only:
            erc=json.loads((HERE/'core_erc.json').read_text())
            summary['erc_counts']=dict(Counter(v['type'] for s in erc['sheets'] for v in s['violations']))
            summary['structural_checks']='PASS'
            summary['scope']='SCHEMATIC_ONLY; PCB not built or verified by this run'
            summary['source_sha256']={'core.net':hashlib.sha256((HERE/'core.net').read_bytes()).hexdigest()}
            (HERE/'review_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps({k:v for k,v in summary.items() if k!='commands'},indent=2))
            return 2 if args.release else 0
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
