"""Export source footprint positions without copying copper or placing target PCB.

Run under KiCad pcbnew. The proposed transform is a placement starting point only:
0603 enlargement, heater power changes and safety gates require new routing/DRC.
"""
from pathlib import Path
import hashlib,json
import pcbnew as pcb
HERE=Path(__file__).resolve().parent
source=HERE/'reference/hellen1-wbo.kicad_pcb'
board=pcb.LoadBoard(str(source));parts={p['ref']:p for p in json.loads((HERE/'parts.json').read_text())}
mapping=[p for p in json.loads((HERE/'reference_map.json').read_text()) if p['channel']==1]
reference_to_target={p['source_ref']:p['ref'] for p in mapping}
rows=[];groups={}
def bounds(boxes):
    return [round(min(x[0] for x in boxes),4),round(min(x[1] for x in boxes),4),round(max(x[2] for x in boxes),4),round(max(x[3] for x in boxes),4)]
for fp in board.GetFootprints():
    ref=fp.GetReference()
    if ref not in reference_to_target:continue
    target_ref=reference_to_target[ref];target=parts[target_ref]
    boxes=[]
    for pad in fp.Pads():
        box=pad.GetBoundingBox();boxes.append([pcb.ToMM(box.GetX()),pcb.ToMM(box.GetY()),pcb.ToMM(box.GetRight()),pcb.ToMM(box.GetBottom())])
    padbounds=bounds(boxes)
    layer=board.GetLayerName(fp.GetLayer());group=target['sheet'].split('/')[-1].replace('wbo1_','')
    row={'source_ref':ref,'target_ref_ch1':target_ref,'target_ref_ch2':target_ref[0]+str(int(target_ref[1:])+200),'source_position_mm':[pcb.ToMM(fp.GetPosition().x),pcb.ToMM(fp.GetPosition().y)],'source_rotation_degrees':fp.GetOrientationDegrees(),'source_layer':layer,'source_footprint':str(fp.GetFPID().GetLibItemName()),'target_footprint':target['footprint'],'source_pad_bounds_mm':padbounds,'group':group}
    rows.append(row);groups.setdefault(group,[]).append(padbounds);groups.setdefault(group+'_'+layer,[]).append(padbounds)
extents={g:{'bounds_mm':bounds(items)} for g,items in groups.items()}
for g,d in extents.items():
    x1,y1,x2,y2=d['bounds_mm'];d['size_mm']=[round(x2-x1,4),round(y2-y1,4)]
all_bounds=bounds([r['source_pad_bounds_mm'] for r in rows]);x0,y0=all_bounds[:2]
for r in rows:r['initial_scaled_position_relative_mm']=[round((r['source_position_mm'][0]-x0)*1.65+2,4),round((r['source_position_mm'][1]-y0)*1.65+2,4)]
report={'source_board_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'upstream_commit':(HERE/'reference/commit.txt').read_text().strip(),'source_pad_bounds_mm':all_bounds,'groups':extents,'footprints':sorted(rows,key=lambda r:r['source_ref']),'proposal':{'scale_for_initial_0603_placement':1.65,'relative_origin':'source all-component pad bbox minimum; plus2mm offset','estimated_source_core_scaled_pad_envelope_mm':[round((all_bounds[2]-x0)*1.65+4,2),round((all_bounds[3]-y0)*1.65+4,2)],'new_heater_power_area_extra_mm':[20,25],'new_heater_and_safety_parts':'Must be placed manually outside analog core; original Q600 placement is invalid after DPAK change','maintain_source_layers':True,'copper_imported':False,'qualification':'Coordinate reference only; no placement/clearance/electrical layout approval. Target footprints differ; recheck every courtyard and critical analog loop.'}}
(HERE/'layout_reference.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'bounds':all_bounds,'groups':extents,'proposed_core':report['proposal']['estimated_source_core_scaled_pad_envelope_mm']},indent=2))
