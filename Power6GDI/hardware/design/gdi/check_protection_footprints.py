"""Run inside pinned KiCad image; check exported pins against loaded real pads."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
import pcbnew

HERE=Path(__file__).resolve().parent
rows=[]
for name in ('protection_a','protection_b','permission'):
    tree=ET.parse(HERE/(name+'.xml'))
    for component in tree.findall('.//components/comp'):
        ref=component.get('ref');lib,fp=component.findtext('footprint').split(':')
        path=(HERE if lib.startswith('Power8GDI_') else Path('/usr/share/kicad/footprints'))/(lib+'.pretty')
        loaded=pcbnew.FootprintLoad(str(path),fp)
        assert loaded is not None,(ref,'missing footprint')
        pads={p.GetNumber() for p in loaded.Pads() if p.GetNumber()}
        pins={p.get('pin') for p in tree.findall('.//nets/net/node') if p.get('ref')==ref}
        assert not pins-pads,(ref,pins-pads)
        if fp=='LM74800_DRR0012E':
            ep=next(p for p in loaded.Pads() if p.GetNumber()=='13')
            assert abs(pcbnew.ToMM(ep.GetSizeX())-1.3)<1e-6
            assert abs(pcbnew.ToMM(ep.GetSizeY())-2.5)<1e-6
            assert len(pads)==13
            assert all(p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD for p in loaded.Pads())
        rows.append({'ref':ref,'footprint':lib+':'+fp,'pads':sorted(pads),
                     'sha256':hashlib.sha256((path/(fp+'.kicad_mod')).read_bytes()).hexdigest()})
report={'status':'PASS_REAL_KICAD_FOOTPRINTS','parts':len(rows),'rows':rows,
        'qualification':'Pad identity and LM74800 EP geometry only; assembly/thermal verification pending'}
(HERE/'protection_footprint_checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['status'],len(rows))
