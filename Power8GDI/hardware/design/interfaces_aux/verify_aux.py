"""Offline export/connectivity checks; readiness is intentionally blocked."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,subprocess,sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BASE='/repo/Power8GDI/hardware/design/interfaces_aux/'

def docker(entry,*args,allowed=(0,)):
    cmd=['docker','run','--rm','--network','none','--mount',f'type=bind,source={ROOT},target=/repo','--entrypoint',entry,'kicad/kicad:9.0',*args]
    r=subprocess.run(cmd,text=True,capture_output=True)
    if r.stdout.strip():print(r.stdout.strip())
    if r.returncode not in allowed:print(r.stderr,file=sys.stderr);raise SystemExit(r.returncode)
    return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--kicad',action='store_true');p.add_argument('--require-ready',action='store_true');a=p.parse_args()
    data=json.loads((HERE/'interface.json').read_text());reports=HERE/'reports';reports.mkdir(exist_ok=True)
    if a.kicad:
        summary={'version':docker('kicad-cli','version').stdout.strip(),'sheets':{},'release_status':'BLOCKED','hardware_tests':'NOT RUN'}
        for s in data['sheets']:
            name=s['name'];src=BASE+name+'.kicad_sch'
            docker('kicad-cli','sch','export','netlist','--format','kicadxml','-o',BASE+name+'.xml',src)
            erc=docker('kicad-cli','sch','erc','--format','json','--exit-code-violations','-o',BASE+'reports/'+name+'_erc.json',src,allowed=(0,5))
            docker('kicad-cli','sch','export','svg','-o',BASE+'reports/',src)
            svg=reports/(name+'.svg');svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n',encoding='utf-8',newline='\n')
            findings=[v for sheet in json.loads((reports/(name+'_erc.json')).read_text())['sheets'] for v in sheet['violations']]
            summary['sheets'][name]={'erc_exit':erc.returncode,'violations':len(findings),'types':dict(Counter(v['type'] for v in findings)),'severities':dict(Counter(v['severity'] for v in findings))}
        docker('python3',BASE+'verify_aux.py','--footprints-internal')
        (reports/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
    r=subprocess.run([sys.executable,str(HERE/'test_aux.py')])
    if r.returncode:return r.returncode
    print('Aux source-level checks PASS. CJ125/heater/electrical release BLOCKED.')
    return 2 if a.require_ready else 0

def footprints():
    from schlib import parse,children
    result={}
    for part in json.loads((HERE/'parts.json').read_text()):
        fp=part['footprint']
        if fp in result:continue
        lib,name=fp.split(':')
        path=(HERE.parent/'Power8GDI_Core.pretty'/(name+'.kicad_mod')) if lib=='Power8GDI_Core' else Path('/usr/share/kicad/footprints')/(lib+'.pretty')/(name+'.kicad_mod')
        raw=path.read_bytes();pads=sorted(set(str(p[1]) for p in children(parse(raw.decode()),'pad')))
        result[fp]={'sha256':hashlib.sha256(raw).hexdigest(),'pads':pads,'path':str(path),'geometry_status':'CANDIDATE_UNVERIFIED_CJ125' if lib=='Package_QFP' else 'library_or_project_source; assembly qualification pending'}
    (HERE/'footprint_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'Footprint source hashes and pads: {len(result)} files')

if __name__=='__main__':
    if '--footprints-internal' in sys.argv:footprints()
    else:raise SystemExit(main())
