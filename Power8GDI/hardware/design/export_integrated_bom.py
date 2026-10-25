"""Export an assembly-review BOM only from the current KiCad XML netlist.

Reference MPNs are design candidates, not manufacturer-approved substitutions.
Generic passives deliberately have no invented order code. DNP is authoritative
from KiCad; excluded positions and required but unspecified parts remain visible.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent


def export(netlist=HERE/'core.net'):
    tree=ET.parse(netlist)
    digest=hashlib.sha256(netlist.read_bytes()).hexdigest()
    rows=[]
    for c in tree.findall('components/comp'):
        ref=c.get('ref'); value=c.findtext('value',''); fp=c.findtext('footprint','')
        props={p.get('name'):p.get('value','') for p in c.findall('property')}
        fields={p.get('name'):p.text or '' for p in c.findall('fields/field')}
        dnp='dnp' in props
        excluded='exclude_from_bom' in props
        explicit=next((fields[k] for k in ['MPN','Manufacturer Part Number','Mfr_PN','Part Number'] if fields.get(k)), '')
        # U/Q device names and certain discrete order codes are reference
        # design selections. Packaging suffix completeness still needs review.
        candidate=explicit
        if not candidate and re.match(r'^[UQ]',ref): candidate=value.split()[0]
        if not candidate and re.match(r'^(SMBJ|SMCJ|SMF|SDURB|ESD|BAV|BAT|BAS|STPS|SS[0-9]|PESD|USBLC|WSLP|ASEM|XAL[0-9]|TPS|TLV|TCAN)',value): candidate=value.split()[0]
        if value.startswith('Molex '):candidate=value.split()[1]
        if ref in {'J601','J602','J603','J604'}: candidate='6437288-1'
        bare=ref.startswith('TP') and value=='TestPoint' or 'Tag-Connect_' in fp
        tht=ref in {'J101','J601','J602','J603','J604'}
        quantity=0 if dnp or excluded or bare else 1
        rows.append({'Reference':ref,'Value':value,'Footprint':fp,'DNP':dnp,
                     'Assembly_Class':'BARE_PCB_FEATURE' if bare else ('THROUGH_HOLE' if tht else 'SURFACE_MOUNT'),
                     'Quantity_Per_Board':quantity,
                     'SMT_Placement_Quantity':quantity if not tht else 0,
                     'Exclude_From_BOM':excluded,'Reference_MPN':candidate,
                     'MPN_Status':'EXPLICIT_FIELD_CANDIDATE' if explicit else ('REFERENCE_VALUE_CANDIDATE' if candidate else 'ORDER_CODE_NOT_SELECTED'),
                     'Procurement_Status':'OBSOLETE_REFERENCE_REPLACEMENT_REVIEW_REQUIRED' if candidate.startswith('BUK9230-100B') else 'NOT_PURCHASE_QUALIFIED',
                     'Sheet':c.find('sheetpath').get('names'),
                     'Datasheet':c.findtext('datasheet',''),
                     'Source_LCSC':next((fields[k] for k in ['LCSC','LCSC Part','LCSC Part #'] if fields.get(k)),''),
                     'Source_Fields_JSON':json.dumps(fields,sort_keys=True),
                     'Source_Netlist_SHA256':digest})
    rows.sort(key=lambda r:(re.sub(r'\d','',r['Reference']),int(re.search(r'\d+',r['Reference'])[0])))
    with (HERE/'integrated_bom.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,list(rows[0]));writer.writeheader();writer.writerows(rows)
    counts=Counter(r['Reference_MPN'] for r in rows if r['Reference_MPN'] and r['Quantity_Per_Board'])
    report={'profile':'2026-10-25-sport-gdi6','source_netlist':str(netlist.name),'source_sha256':digest,
        'physical_positions':len(rows),'fitted_positions':sum(r['Quantity_Per_Board'] for r in rows),
        'bare_pcb_features':sum(r['Assembly_Class']=='BARE_PCB_FEATURE' for r in rows),
        'smt_placement_quantity':sum(r['SMT_Placement_Quantity'] for r in rows),
        'through_hole_placement_quantity':sum(r['Quantity_Per_Board'] for r in rows if r['Assembly_Class']=='THROUGH_HOLE'),
        'dnp_positions':sum(r['DNP'] for r in rows),'excluded_from_bom':sum(r['Exclude_From_BOM'] for r in rows),
        'fitted_positions_without_order_code':sum(not r['Reference_MPN'] and bool(r['Quantity_Per_Board']) for r in rows),
        'reference_mpn_counts':dict(sorted(counts.items())),
        'procurement_blockers':[{'reference_mpn':'BUK9230-100B','quantity':counts['BUK9230-100B'],
            'reason':'Obsolete reference MOSFET; no unreviewed clone or alternative selected'}],
        'status':'SCHEMATIC_DERIVED_CANDIDATE_BOM_NOT_PURCHASE_RELEASE',
        'limitations':['Generic passives and some source inductors lack selected manufacturer order codes',
          'Temperature grades, stock, tolerances, DC bias and thermal limits need part-specific review',
          'PT enable boundary DNP remains intentional until physical qualification',
          'PI is optional in application; shared quad ICs remain fitted in this assembly baseline']}
    (HERE/'integrated_bom_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__': print(json.dumps(export(),indent=2))
