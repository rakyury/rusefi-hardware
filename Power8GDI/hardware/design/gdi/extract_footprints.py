"""Run inside KiCad 9 Python; extract source-embedded footprints, not new land patterns."""
from pathlib import Path
import json
import hashlib
import tempfile
import pcbnew
from sexpr import parse, dump, child, children, Quoted as Q
from oscillator_silk import SILK_EDITS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
library = HERE / 'Power8GDI_GDI.pretty'
library.mkdir(exist_ok=True)
refs = json.loads((HERE/'reference_mapping.json').read_text())['A']['reference_map']
refs = set(refs) | {'U3'}
board = pcbnew.LoadBoard(str(ROOT/'GDI-4ch/GDI-4ch.kicad_pcb'))
plugin = pcbnew.PCB_IO_MGR.PluginFind(pcbnew.PCB_IO_MGR.KICAD_SEXP)
scratch = tempfile.TemporaryDirectory(suffix='.pretty')
manifest = {}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref not in refs:
        continue
    source_id = fp.GetFPID().GetUniStringLibId()
    fp.SetPosition(pcbnew.VECTOR2I(0,0))
    fp.SetOrientationDegrees(0)
    fp.SetReference('REF**')
    name = 'REF_' + ref
    fp.SetFPID(pcbnew.LIB_ID('Power8GDI_GDI',name))
    for pad in fp.Pads():
        pad.SetNetCode(0)
    plugin.FootprintSave(scratch.name,fp)
    content=(Path(scratch.name)/(name+'.kicad_mod')).read_bytes()
    target=library/(name+'.kicad_mod')
    # KiCad synthesizes UUIDs for legacy custom fields when loading the
    # source PCB. Keep the established derived identities on regeneration.
    if target.exists():
        previous={str(v[1]):child(v,'uuid')[1] for v in children(parse(target.read_text()),'property') if child(v,'uuid')}
        for field in children(parse(content.decode('utf8')),'property'):
            identifier=child(field,'uuid')
            if identifier and str(field[1]) in previous:
                content=content.replace(str(identifier[1]).encode(),str(previous[str(field[1])]).encode())
    changes=[]
    if ref in {'R12','R21','R22','R26','R45'}:
        # The two resistor terminals are NOT a net tie. Only the Kelvin tap
        # and power pad of the SAME terminal may share copper.
        data=parse(content.decode('utf8'))
        groups=child(data,'net_tie_pad_groups')
        assert groups is not None, ref
        groups[1:]=[Q('1,2'),Q('3,4')]
        # Vishay WSLP1206 10mohm, DS30122 rev09-Sep-2024 p2:
        # land 1.65 x1.93, terminal gap1.80; preserve inner Kelvin taps.
        for pad in children(data,'pad'):
            if pad[1] in ('1','4'):
                child(pad,'at')[1:]=[str(-1.725 if pad[1]=='1' else 1.725),'0','90']
                child(pad,'size')[1:]=['1.93','1.65']
                child(pad,'layers')[1:]=[Q('F.Cu'),Q('F.Paste'),Q('F.Mask')]
            elif pad[1] in ('2','3'):
                child(pad,'layers')[1:]=[Q('F.Cu')]
        for line in children(data,'fp_line'):
            if child(line,'layer')[1]=='F.CrtYd':
                for key in ('start','end'):
                    point=child(line,key)
                    point[1:]=[str(2.8 if float(point[1])>0 else -2.8),str(1.215 if float(point[2])>0 else -1.215)]
        content=(dump(data)+'\n').encode('utf8')
        changes.append('Restrict Kelvin net ties to same-terminal pairs 1/2 and 3/4')
        changes.append('WSLP1206 10mohm manufacturer land pattern1.65x1.93mm gap1.80mm; thermal qualification pending')
        changes.append('Stencil openings on power lands1/4 only; Kelvin taps2/3 remain copper-only')
    if ref=='Y2':
        data=parse(content.decode('utf8'))
        # SiT8924B rev1.72 p12 rotated land pattern. Pin ordering retained;
        # electrical use of OE floating and PT clock load remain conditional.
        for pad in children(data,'pad'):
            at=child(pad,'at');at[1]=str(-1.905 if float(at[1])<0 else 1.905)
            child(pad,'size')[1:]=['2.0','2.2']
        content=(dump(data)+'\n').encode('utf8')
        changes.append('SiT8924B7x5mm manufacturer land pattern span3.81x5.08mm, pads2.0x2.2mm')
        silk=[line for line in children(data,'fp_line') if child(line,'layer')[1]=='F.SilkS']
        if len(silk)!=5:raise ValueError('Unexpected REF_Y2 silk geometry')
        for old,new in SILK_EDITS:
            line=next(line for line in silk if tuple(map(float,child(line,'start')[1:]+child(line,'end')[1:]))==old)
            child(line,'start')[1:]=list(map(str,new[:2]));child(line,'end')[1:]=list(map(str,new[2:]))
        content=(dump(data)+'\n').encode('utf8')
        changes.append('Silk clears enlarged oscillator mask and R223/R323; pin1 stub retained')
    if not target.exists() or target.read_bytes()!=content:
        target.write_bytes(content)
    manifest[ref] = {'source_footprint':source_id,'derived_footprint':'Power8GDI_GDI:'+name,
                     'pad_numbers': sorted({pad.GetNumber() for pad in fp.Pads()}),
                     'qualification':'SOURCE_GEOMETRY_WITH_EXPLICIT_REVIEW_CORRECTIONS_NOT_LOAD_APPROVAL',
                     'review_changes':changes,
                     'derived_footprint_sha256':hashlib.sha256(content).hexdigest()}
if set(manifest)!=set(refs):
    raise RuntimeError('Missing reference footprints: '+str(set(refs)-set(manifest)))
(HERE/'footprint_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
scratch.cleanup()
print('Extracted',len(manifest),'embedded footprints; no reference board edits.')
