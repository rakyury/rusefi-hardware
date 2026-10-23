import json
from pathlib import Path
import pcbnew
HERE=Path(__file__).resolve().parent
parts=json.loads((HERE/'parts.json').read_text());records=[];errors=[]
for p in parts:
    lib,name=p['footprint'].split(':');fp=pcbnew.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',name)
    if fp is None:errors.append(p['ref']+': missing footprint');continue
    pads={pad.GetNumber():{'x':pcbnew.ToMM(pad.GetPosition().x),'y':pcbnew.ToMM(pad.GetPosition().y),'w':pcbnew.ToMM(pad.GetSize().x),'h':pcbnew.ToMM(pad.GetSize().y)} for pad in fp.Pads() if pad.GetNumber()}
    missing=set(p['pins'])-set(pads)
    if missing:errors.append(p['ref']+': missing pads '+str(sorted(missing)))
    if p['ref']=='U5200':
        if pads['31']['w']!=1.8 or pads['31']['h']!=4.5:errors.append('LM EP geometry')
    if p['ref']=='U5300':
        if pads['17']['w']!=1.68 or pads['17']['h']!=1.68:errors.append('TPS EP geometry')
    records.append({'ref':p['ref'],'footprint':p['footprint'],'pads':pads})
report={'kicad':pcbnew.GetBuildVersion(),'count':len(records),'errors':errors,'records':records}
(HERE/'footprint_check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'count':len(records),'errors':errors}));assert not errors
