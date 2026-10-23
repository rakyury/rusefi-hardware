"""Measure real package and donor copper geometry before assigning regions."""
from collections import defaultdict
import json
from pathlib import Path
import pcbnew as p
from build_board import load_footprint, mm
from net_contract import read_netlists
from copper_transfer import audited_copper

HERE=Path(__file__).resolve().parent

def bounds(items):
    boxes=[x.GetBoundingBox(False,False) if isinstance(x,p.FOOTPRINT) else x.GetBoundingBox() for x in items]
    return [p.ToMM(min(b.GetX() for b in boxes)),p.ToMM(min(b.GetY() for b in boxes)),p.ToMM(max(b.GetRight() for b in boxes)),p.ToMM(max(b.GetBottom() for b in boxes))]

def audit():
    design=HERE.parent
    components,assignments,sources=read_netlists([design/'core.net'])
    manifest=json.loads((design/'core_manifest.json').read_text())
    byref={x['ref']:x for x in manifest['parts']}
    mapping=json.loads((design/'gdi/reference_mapping.json').read_text())
    donor=p.LoadBoard(str(HERE.parents[3]/'GDI-4ch/GDI-4ch.kicad_pcb'))
    donorparts={x.GetReference():x for x in donor.GetFootprints()}
    stages={};imported=set();groupmap={}
    for stage in ('A','B'):
        refmap=mapping[stage]['reference_map']; imported.update(refmap.values())
        netmap,copper,report=audited_copper(donor,refmap,assignments)
        fps=[donorparts[ref] for ref in refmap]
        stages[stage]={'footprint_count':len(fps),'copper_items':len(copper),'footprint_bounds_mm':bounds(fps),'copper_bounds_mm':bounds(copper),'front_parts':sum(f.GetLayer()==p.F_Cu for f in fps),'back_parts':sum(f.GetLayer()==p.B_Cu for f in fps)}
        for old,new in refmap.items():groupmap[new]=donorparts[old]
    groups=defaultdict(list)
    details={}
    for ref,comp in components.items():
        if ref in imported:continue
        fp=load_footprint(comp['footprint'],design);b=fp.GetBoundingBox(False,False)
        w,h=p.ToMM(b.GetWidth()),p.ToMM(b.GetHeight())
        sheet=byref.get(ref,{}).get('sheet','connector' if ref.startswith('J60') else 'unknown')
        groups[sheet].append({'reference':ref,'width_mm':w,'height_mm':h,'area_mm2':w*h})
        details[ref]={'footprint':comp['footprint'],'sheet':sheet,'size_mm':[w,h]}
    result={'input_netlist':sources,'outline_mm':[245,165],'donor':stages,'groups':{s:{'count':len(items),'body_area_mm2':sum(x['area_mm2'] for x in items),'largest':sorted(items,key=lambda x:-x['area_mm2'])[:4]} for s,items in groups.items()},'parts':details,'warning':'Body areas exclude routing channels, electrical clearance and thermal copper; not a packing proof.'}
    destination=HERE/'layout_candidate';destination.mkdir(exist_ok=True)
    (destination/'area_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='parts'},indent=2))

if __name__=='__main__':audit()
