"""Run inside KiCad 9 Python; extract source-embedded footprints, not new land patterns."""
from pathlib import Path
import json
import hashlib
import tempfile
import pcbnew

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
    if not target.exists() or target.read_bytes()!=content:
        target.write_bytes(content)
    manifest[ref] = {'source_footprint':source_id,'derived_footprint':'Power8GDI_GDI:'+name,
                     'pad_numbers': sorted({pad.GetNumber() for pad in fp.Pads()}),
                     'qualification':'SOURCE_GEOMETRY_ONLY_NOT_LAND_PATTERN_APPROVAL',
                     'derived_footprint_sha256':hashlib.sha256(content).hexdigest()}
if set(manifest)!=set(refs):
    raise RuntimeError('Missing reference footprints: '+str(set(refs)-set(manifest)))
(HERE/'footprint_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
scratch.cleanup()
print('Extracted',len(manifest),'embedded footprints; no reference board edits.')
