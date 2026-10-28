"""Seal already generated candidate artifacts; does not run or waive checks."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
DESIGN=HERE.parent
OUT=HERE/'gdi6_candidate'

def digest(path):
    data=path.read_bytes()
    if path.suffix not in ('.pdf','.png'):data=data.replace(b'\r\n',b'\n')
    return hashlib.sha256(data).hexdigest()

def main():
    # KiCad emits trailing spaces in SVG markup; canonicalize without changing geometry.
    for name in ('front.svg', 'back.svg'):
        path = OUT / name
        text = '\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n'
        path.write_bytes(text.encode('utf-8'))
    net=digest(DESIGN/'core.net')
    selection=json.loads((DESIGN/'selection_validation.json').read_text())
    review=json.loads((DESIGN/'review_validation.json').read_text())
    coverage=json.loads((OUT/'net_coverage.json').read_text())
    bom=json.loads((DESIGN/'integrated_bom_manifest.json').read_text())
    joints=json.loads((OUT/'assembly_joints.json').read_text())
    drc=json.loads((OUT/'drc.provenance.json').read_text())
    pads=json.loads((OUT/'pad_validation.json').read_text())
    assert selection['status']=='PASS' and selection['netlist_sha256']==net
    assert review['structural_checks']=='PASS' and review['source_sha256']['core.net']==net
    assert joints['board_sha256']==digest(OUT/'Power8GDI_Review.kicad_pcb')==drc['board_sha256']
    assert joints['bom_sha256']==digest(DESIGN/'integrated_bom.csv')
    assert not pads['errors']
    paths=[DESIGN/p for p in ['core.net','sport_gdi6_schematic.pdf','integrated_bom.csv','integrated_bom_manifest.json','selection_validation.json','gdi/load_review.json']]
    paths += [OUT/p for p in ['Power8GDI_Review.kicad_pcb','Power8GDI_Review.kicad_pro','Power8GDI_Review.kicad_dru','board_report.json','pad_validation.json','drc.json','drc.provenance.json','net_coverage.json','assembly_joints.json','front.svg','back.svg','front.png','back.png']]
    result={'profile':'2026-10-25-sport-gdi6','updated':'2026-10-28',
      'qualification':'INCOMPLETE_ENGINEERING_REVIEW_DO_NOT_FABRICATE',
      'source_base_commit':'013f467','selection_source_commit':'deb0afa',
      'hardware_revision':'same Git revision as this manifest; exact file hashes below',
      'hash_normalization':'CRLF_TO_LF_TEXT_ONLY; PDF/PNG raw bytes',
      'kicad_version':'9.0.9','kicad_image':review['image'],
      'source_netlist_sha256':net,'selection_map_sha256':selection['map_sha256'],
      'schematic_pdf_pages':49,'pdf_visual_review':{'all_pages_contact_sheet':True,'larger_scale_pages':[27]},
      'pad_comparison':'PASS','physical_positions':pads['components'],
      'pad_net_assignments':pads['component_pin_assignments'],
      'manufacturing_gate':'BLOCKED','erc_counts':review['erc_counts'],
      'connectivity_unconnected_count':coverage['connectivity_unconnected_count'],
      'reported_drc_violations':coverage['total_violations'],
      'drc_report_may_be_truncated':coverage['drc_report_may_be_truncated'],
      'drc_categories':coverage['violations'],'design_rule_exclusions_added':False,
      'assembly_bom_after_classification_fix':{'installed':bom['fitted_positions'],'smt':bom['smt_placement_quantity'],
        'through_hole':bom['through_hole_placement_quantity'],'bare_pcb_features':bom['bare_pcb_features'],'dnp':bom['dnp_positions'],
        'unclassified':bom['unclassified_placement_quantity'],'smt_solder_lands':joints['smt_solder_lands'],'tht_solder_lands':joints['tht_solder_lands']},
      'selection_binding':{'status':selection['status'],'actual_references':selection['selected_positions'],'missing_order_codes':selection['unresolved_order_codes']},
      'files':{p.relative_to(DESIGN).as_posix():{'sha256':digest(p),'bytes':p.stat().st_size} for p in paths}}
    (OUT/'artifact_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))

if __name__=='__main__':main()
