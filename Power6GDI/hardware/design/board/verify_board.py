"""Verify an actual saved PCB against current XML and source assembly flags."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import pcbnew as p
from net_contract import read_netlists,compare_pad_assignments


def verify(boardpath,netlists):
    parts,expected,_=read_netlists(netlists);board=p.LoadBoard(str(boardpath));actual=defaultdict(list)
    footprints={f.GetReference():f for f in board.GetFootprints()}
    errors=[]
    if set(footprints)!=set(parts):errors.append('Component references differ from authoritative source')
    for ref,fp in footprints.items():
        if ref not in parts:continue
        if fp.GetValue()!=parts[ref]['value']:errors.append(f'{ref}: value differs from source')
        if fp.IsDNP()!=parts[ref]['dnp']:errors.append(f'{ref}: DNP lost/changed')
        if fp.IsExcludedFromBOM()!=parts[ref]['exclude_from_bom']:errors.append(f'{ref}: BOM exclusion changed')
        if str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName())!=parts[ref]['footprint']:errors.append(f'{ref}: footprint changed')
        for pad in fp.Pads():
            if pad.GetNumber():actual[(ref,pad.GetNumber())].append(pad.GetNetname())
    errors+=compare_pad_assignments(expected,actual)
    # Physical pin orientation and grid checks, independent of generator loops.
    expected_xy={'1':(-12,-14.5),'9':(12,-14.5),'10':(-10.5,-12),'17':(10.5,-12),
                 '18':(-10.5,-9),'25':(10.5,-9),'26':(-12,-6.5),'34':(12,-6.5)}
    for ref in ['J601','J602','J603','J604']:
        fp=footprints[ref];pads={q.GetNumber():q for q in fp.Pads() if q.GetNumber()}
        if set(pads)!=set(map(str,range(1,35))):errors.append(f'{ref}: wrong pin set')
        for number,(x,y) in expected_xy.items():
            pos=pads[number].GetPosition()-fp.GetPosition()
            if abs(p.ToMM(pos.x)-x)>1e-5 or abs(p.ToMM(pos.y)-y)>1e-5:errors.append(f'{ref}.{number}: mirrored/incorrect land pattern')
    if board.GetCopperLayerCount()!=4:errors.append('Wrong layer count')
    if len(list(board.GetTracks()))<100:errors.append('No substantive copper routing')
    if len(list(board.Zones()))<1:errors.append('No ground zone')
    # Inspect the saved PCB through KiCad, not just the footprint libraries.
    shunts={f'R{base+n}' for base in (200,300) for n in (3,12,13,15,21)}
    aperture_count=0
    for ref in sorted(shunts):
        fp=footprints.get(ref)
        if fp is None:errors.append(ref+': missing shunt');continue
        pads=list(fp.Pads())
        if len(pads)!=4 or {q.GetNumber() for q in pads}!={'1','2','3','4'}:
            errors.append(ref+': unexpected shunt pads')
        for pad in pads:
            power=pad.GetNumber() in ('1','4')
            wanted={p.F_Cu,p.F_Paste,p.F_Mask} if power else {p.F_Cu}
            if set(pad.GetLayerSet().Seq())!=wanted:errors.append(ref+'.'+pad.GetNumber()+': stencil layers')
            if pad.IsOnLayer(p.F_Paste):
                aperture_count+=1
                if pad.GetSize().x<=0 or pad.GetSize().y<=0:errors.append(ref+': empty stencil aperture')
        if any(g.GetLayer() in (p.F_Paste,p.B_Paste) for g in fp.GraphicalItems()):
            errors.append(ref+': unexpected separate paste primitive')
    if aperture_count!=20:errors.append('Expected twenty actual shunt paste apertures')
    result={'components':len(parts),'component_pin_assignments':len(expected),'dnp_count':sum(c['dnp'] for c in parts.values()),
            'shunt_stencil':{'actual_references':sorted(shunts),'power_apertures':aperture_count,
                'power_pad_numbers':['1','4'],'sense_pads_copper_only':not any('stencil' in e or 'paste' in e for e in errors)},'errors':errors}
    print(json.dumps(result,indent=2))
    if errors:raise SystemExit(1)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('board',type=Path);parser.add_argument('netlists',type=Path,nargs='+')
    args=parser.parse_args();verify(args.board,args.netlists)
