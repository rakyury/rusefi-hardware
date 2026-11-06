"""Count physical solder lands, not BOM placements or Kelvin/paste subpads.

Estimate for assembly quoting; a contractor must confirm thermal-pad and
connector handling. Run inside pinned KiCad Python.
"""
from pathlib import Path
import csv
import hashlib
import json
import sys
import pcbnew as p

HERE=Path(__file__).resolve().parent

def count(board_path, bom_path):
    rows={r['Reference']:r for r in csv.DictReader(bom_path.open(encoding='utf8',newline=''))}
    board=p.LoadBoard(str(board_path)); records=[]
    for fp in board.GetFootprints():
        ref=fp.GetReference(); row=rows[ref]
        if int(row['Quantity_Per_Board'])==0:continue
        smt=[];tht=[]
        for pad in fp.Pads():
            if not pad.GetNumber():continue
            # Copper-only Kelvin taps and paste-only stencil subdivisions
            # are not separate assembled terminals. Mask-opening electrical
            # pad is the solder land, even when paste is separate primitives.
            if not (pad.IsOnLayer(p.F_Mask) or pad.IsOnLayer(p.B_Mask)):continue
            if not (pad.IsOnLayer(p.F_Cu) or pad.IsOnLayer(p.B_Cu)):continue
            if pad.GetAttribute()==p.PAD_ATTRIB_SMD:smt.append(pad.GetNumber())
            elif pad.GetAttribute()==p.PAD_ATTRIB_PTH and row['Assembly_Class']=='THROUGH_HOLE':tht.append(pad.GetNumber())
        name=row['Footprint'].lower()
        leadless=ref.startswith('U') and (any(s in name for s in ('qfn','son','lga','bga','dfn','vqfn','vson','1ep','thermalvias'))
          or row['Value'].startswith(('MC33PT2001','TLE9104SH','TPS7B4253','LM74800')))
        records.append({'reference':ref,'assembly_class':row['Assembly_Class'],
          'smt_solder_lands':len(smt),'tht_solder_lands':len(tht),
          'smt_land_numbers':smt,'tht_land_numbers':tht,
          'hidden_pad_xray_candidate':leadless,'footprint':row['Footprint']})
    return {'status':'PHYSICAL_LAND_COUNT_FOR_QUOTE_NOT_CONTRACTOR_CONFIRMATION',
      'hash_normalization':'CRLF_TO_LF_TEXT_ONLY',
      'board_sha256':hashlib.sha256(board_path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
      'bom_sha256':hashlib.sha256(bom_path.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
      'fitted_positions':len(records),'smt_solder_lands':sum(r['smt_solder_lands'] for r in records),
      'tht_solder_lands':sum(r['tht_solder_lands'] for r in records),
      'hidden_pad_xray_candidates':[r['reference'] for r in records if r['hidden_pad_xray_candidate']],
      'limitations':['X-ray classification uses footprint and reviewed package families, including leaded IC exposed pads; assembler review required',
        'Exposed pads count as one land unless physically separated mask lands; paste subdivisions and Kelvin copper-only taps excluded',
        'DNP, bare test pads, Tag-Connect PCB features and SMT thermal-via holes excluded'],
      'records':sorted(records,key=lambda r:r['reference'])}

if __name__=='__main__':
    board=Path(sys.argv[1]) if len(sys.argv)>1 else HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'
    result=count(board,HERE.parent/'integrated_bom.csv')
    target=board.parent/'assembly_joints.json';target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
