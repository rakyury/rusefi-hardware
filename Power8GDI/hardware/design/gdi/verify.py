"""Reproduce schematic exports/ERC and source topology validation.

  python verify.py --kicad     # requires Docker kicad/kicad:9.0 (tested 9.0.9)
  python verify.py             # checks committed export snapshots
  python verify.py --require-ready  # intentionally exits 2 while release blocked
"""
from pathlib import Path
from collections import Counter
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from test_schematic import nets, pin_nets, topology_errors

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
IMAGE='kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729'


def cli(*args,allowed=(0,)):
    command=['docker','run','--rm','--network','none','--mount',f'type=bind,source={ROOT},target=/repo',
             '--entrypoint','kicad-cli',IMAGE,*args]
    result=subprocess.run(command,text=True,capture_output=True)
    print(result.stdout.strip())
    if result.returncode not in allowed:
        print(result.stderr,file=sys.stderr);raise SystemExit(result.returncode)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kicad',action='store_true');parser.add_argument('--require-ready',action='store_true')
    args=parser.parse_args();reports=HERE/'reports';reports.mkdir(exist_ok=True);work=HERE/'work';work.mkdir(exist_ok=True)
    mapping=json.loads((HERE/'reference_mapping.json').read_text())
    if args.kicad:
        version=cli('version').stdout.strip()
        base='/repo/Power8GDI/hardware/design/gdi/'
        cli('sch','export','netlist','--format','kicadxml','-o',base+'work/reference.xml','/repo/GDI-4ch/GDI-4ch.kicad_sch')
        source=ET.parse(work/'reference.xml')
        expected=json.loads((HERE/'source_pin_nets.json').read_text())['nets']
        selected=mapping['A']['reference_map']
        fresh={n.attrib['name']:sorted([dict(p.attrib) for p in n.findall('node') if p.attrib['ref'] in selected],key=lambda p:(p['ref'],p['pin'])) for n in source.findall('.//nets/net')}
        fresh={n:p for n,p in fresh.items() if p}
        if fresh!=expected:raise SystemExit('Fresh source XML differs from reviewed source_pin_nets.json')
        summary={'kicad_version':version,'source_pin_parity':'PASS','source_nets':len(fresh),'source_pins_per_stage':sum(map(len,fresh.values())),'stages':{}}
        for stage in 'ab':
            name='stage_'+stage
            cli('sch','export','netlist','--format','kicadxml','-o',base+name+'.xml',base+name+'.kicad_sch')
            erc=cli('sch','erc','--exit-code-violations','--format','json','-o',base+'reports/'+name+'_erc.json',base+name+'.kicad_sch',allowed=(0,5))
            cli('sch','export','svg','-o',base+'reports/',base+name+'.kicad_sch')
            svg=reports/(name+'.svg')
            svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
            data=json.loads((reports/(name+'_erc.json')).read_text())
            issues=[v for s in data['sheets'] for v in s['violations']]
            summary['stages'][stage.upper()]={'erc_exit_code':erc.returncode,'erc_violations':len(issues),'by_type':dict(Counter(i['type'] for i in issues)),'by_severity':dict(Counter(i['severity'] for i in issues))}
        summary['release_status']='BLOCKED'
        (reports/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
        handoff={'source_pcb':'GDI-4ch/GDI-4ch.kicad_pcb','excluded_source_references':sorted(c.attrib['ref'] for c in source.findall('.//components/comp') if c.attrib['ref'] not in selected),'stages':{}}
        for stage in 'AB':
            lookup=pin_nets(ET.parse(HERE/('stage_'+stage.lower()+'.xml')))
            refmap=mapping[stage]['reference_map'];netmap={}
            for name,nodes in fresh.items():
                values={lookup[(refmap[n['ref']],n['pin'])] for n in nodes}
                if len(values)!=1:raise SystemExit('Source net split during extraction')
                netmap[name]=next(iter(values))
            handoff['stages'][stage]={'reference_map':refmap,'net_map':netmap}
        (HERE/'pcb_handoff.json').write_text(json.dumps(handoff,indent=2)+'\n')
        summary['protection_sheets']={}
        for name in ['protection_a','protection_b','permission']:
            cli('sch','export','netlist','--format','kicadxml','-o',base+name+'.xml',base+name+'.kicad_sch')
            erc=cli('sch','erc','--exit-code-violations','--format','json','-o',base+'reports/'+name+'_erc.json',base+name+'.kicad_sch',allowed=(0,5))
            cli('sch','export','svg','-o',base+'reports/',base+name+'.kicad_sch')
            data=json.loads((reports/(name+'_erc.json')).read_text())
            issues=[v for s in data['sheets'] for v in s['violations']]
            summary['protection_sheets'][name]={'erc_exit_code':erc.returncode,'erc_violations':len(issues),'by_type':dict(Counter(i['type'] for i in issues))}
        (reports/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    for script in ['test_schematic.py','test_protection.py']:
        result=subprocess.run([sys.executable,str(HERE/script)],cwd=HERE)
        if result.returncode:return result.returncode
    print('Topology/part/pad checks PASS; ERC and manufacturing release remain BLOCKED.')
    return 2 if args.require_ready else 0


if __name__=='__main__':raise SystemExit(main())
