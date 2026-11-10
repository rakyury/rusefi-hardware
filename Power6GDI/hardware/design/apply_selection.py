"""Bind conditional sourcing to actual generated symbols, with no silent values.

The procurement map is evidence, not authority to alter circuit values/packages.
Only local, reviewed deviations below may differ from its baseline snapshot.
"""
from pathlib import Path
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from gdi.sexpr import parse,dump,child,children,prop,Quoted as Q

HERE=Path(__file__).resolve().parent
SELECTION=HERE.parents[1]/'procurement/selection/bom_selection.json'
DEVIATIONS={'C114':('10u 16V X7R','Capacitor_SMD:C_1206_3216Metric')}
# D5604: same SOT-23 pads/mask/paste; local silk clears J5600, pin-1 marker unchanged.
DEVIATIONS['D5604']=('PESD1CAN','Power8GDI_Board:SOT-23_D5604_J5600_Clearance')
DEVIATIONS['C1511']=('1n 2kV C0G','Capacitor_SMD:C_1812_4532Metric')
for ref in ('C1533','C1538'):DEVIATIONS[ref]=('22u 50V X7R','Power8GDI_Interfaces:CGA9P3_2220')
for n in range(5208,5212):DEVIATIONS[f'C{n}']=('47u 16V X7R','Capacitor_SMD:C_1210_3225Metric')
for base in (200,300):
    for n,src in ((5,14),(6,15)):DEVIATIONS[f'C{base+n}']=('1300uF 50V',f'Power8GDI_GDI:REF_C{src}')
    for n,src in ((1,1),(2,2),(3,3),(4,4),(5,5),(6,6),(7,7),(8,8),(9,9),(11,11),(12,12),(13,16)):
        DEVIATIONS[f'Q{base+n}']=('IPD60N10S4L12ATMA1',f'Power8GDI_GDI:REF_Q{src}')

def specifications(row,value,footprint):
    errors=[];ref=row['reference'];actual=(value,footprint)
    source=(row['source_value'],row['footprint'])
    if actual!=source and actual!=DEVIATIONS.get(ref):errors.append(f'{ref}: value/footprint differs without hardware-approved deviation: {actual}')
    ratings=row.get('ratings',{})
    if ref.startswith('C'):
        match=re.match(r'([0-9.]+)\s*([pnu])',value.replace('µ','u'),re.I)
        if match and ratings.get('capacitance_pf') is not None:
            expected=float(match[1])*{'p':1,'n':1000,'u':1000000}[match[2].lower()]
            if abs(expected-ratings['capacitance_pf'])>max(1,expected*1e-9):errors.append(f'{ref}: capacitor rating disagrees with schematic')
        match=re.search(r'(\d+(?:\.\d+)?)\s*(k?)V\b',value,re.I)
        if match and ratings.get('rated_voltage_v') is not None and ratings['rated_voltage_v']<float(match[1])*(1000 if match[2] else 1):errors.append(f'{ref}: selected voltage below schematic requirement')
        for dielectric in ('C0G','X7R','X5R'):
            if dielectric in value and ratings.get('dielectric') not in (None,dielectric):errors.append(f'{ref}: dielectric substitution')
    if ref.startswith('R') and ratings.get('resistance_ohm') is not None:
        match=re.match(r'([0-9.]+)\s*([kKmMrR]?)(?:\b|\s|$)',value)
        if match:
            expected=float(match[1])*{'':1,'r':1,'R':1,'k':1000,'K':1000,'M':1e6,'m':.001}[match[2]]
            if abs(expected-ratings['resistance_ohm'])>max(1e-9,expected*1e-9):errors.append(f'{ref}: resistor rating disagrees with schematic')
    return errors

def selected_fields(row):
    return {'MPN':row.get('orderable_mpn') or '', 'Manufacturer':row.get('manufacturer') or '',
      'Selection_ID':row['selection_id'],'Procurement_Status':row['status'],
      'Hardware_Qualification':row['qualification'],
      'Selection_Gaps':json.dumps(row.get('gaps',[]),ensure_ascii=True),
      'Selection_Ratings':json.dumps(row.get('ratings',{}),sort_keys=True),
      'Selection_Source_URLs':' '.join(row.get('source_urls',[])),
      'Purchase_Released':'false'}

def hierarchy(path):
    yield path
    doc=parse(path.read_text(encoding='utf8'))
    for sheet in children(doc,'sheet'):
        filename=prop(sheet,'Sheetfile') or prop(sheet,'Sheet file')
        if filename is None:raise ValueError('Missing child sheet path')
        yield from hierarchy(path.parent/str(filename[2]))

def apply(selection=SELECTION):
    data=json.loads(selection.read_text(encoding='utf8'));assert data['schema_version']==1
    rows={r['reference']:r for r in data['references']};assert len(rows)==len(data['references'])
    seen=set();documents=[];errors=[]
    for path in hierarchy(HERE/'Power8GDI_Core.kicad_sch'):
        doc=parse(path.read_text(encoding='utf8'));changed=False
        for symbol in children(doc,'symbol'):
            ref=str(prop(symbol,'Reference')[2])
            if ref not in rows:
                fp=prop(symbol,'Footprint');value=prop(symbol,'Value')
                nonpart=ref.startswith('#') or not fp or not str(fp[2]) or 'Tag-Connect_' in str(fp[2]) or (ref.startswith('TP') and str(value[2])=='TestPoint')
                omitted=any(child(symbol,key) and child(symbol,key)[1]=='yes' for key in ('dnp','exclude_from_bom'))
                if not nonpart and not omitted:errors.append(ref+': fitted physical part missing from selection')
                continue
            if child(symbol,'dnp') and child(symbol,'dnp')[1]=='yes':errors.append(ref+': selection attempts to fit DNP')
            if ref in seen:errors.append(ref+': duplicate physical ref')
            seen.add(ref);row=rows[ref]
            errors+=specifications(row,str(prop(symbol,'Value')[2]),str(prop(symbol,'Footprint')[2]))
            at=child(symbol,'at')
            # Legacy vendor fields must not look like current sourcing after
            # a selected part changes. Keep them as explicit source provenance.
            for field in children(symbol,'property'):
                if field[1] in ('LCSC','MFG,MFG#','VEND1,VEND1#','VEND2,VEND2#'):
                    field[1]=Q('Source_'+str(field[1]))
            for key,value in selected_fields(row).items():
                field=prop(symbol,key)
                if field is not None:field[2]=Q(value)
                else:symbol.append(['property',Q(key),Q(value),['at',*at[1:]],['effects',['font',['size','1','1']],['hide','yes']]])
            changed=True
        if changed:documents.append((path,doc))
    errors += [r+': selected ref absent from hierarchy' for r in sorted(rows.keys()-seen)]
    if errors:raise ValueError('\n'.join(errors))
    # Validate the complete hierarchy before making any edits.
    for path,doc in documents:path.write_text(dump(doc)+'\n',encoding='utf8')
    return {'selected_positions':len(seen),'schematic_files':len(documents),'map_sha256':hashlib.sha256(selection.read_bytes().replace(b'\r\n',b'\n')).hexdigest()}

def verify(netlist=HERE/'core.net',selection=SELECTION):
    data=json.loads(selection.read_text(encoding='utf8'));root=ET.parse(netlist).getroot()
    parts={c.get('ref'):c for c in root.findall('components/comp')}
    pins={(n.get('ref'),n.get('pin')):net.get('name') for net in root.findall('nets/net') for n in net.findall('node')}
    errors=[];records=[]
    for row in data['references']:
        ref=row['reference'];c=parts.get(ref)
        if c is None:errors.append(ref+': absent');continue
        before=len(errors)
        errors+=specifications(row,c.findtext('value'),c.findtext('footprint'))
        actual={f.get('name'):f.text or '' for f in c.findall('fields/field')}
        for key,value in selected_fields(row).items():
            if actual.get(key)!=value:errors.append(f'{ref}: exported {key} mismatch')
        for pin in row['nets']:
            if pins.get((ref,str(pin['pin'])))!=pin['net']:errors.append(f'{ref}: sourcing snapshot pin connection mismatch {pin}')
        records.append({'reference':ref,'result':'PASS' if len(errors)==before else 'FAIL',
          'selection_id':row['selection_id'],'orderable_mpn':row.get('orderable_mpn'),
          'current_value':c.findtext('value'),'current_footprint':c.findtext('footprint'),
          'source_value':row['source_value'],'source_footprint':row['footprint'],
          'hardware_deviation_applied':(c.findtext('value'),c.findtext('footprint'))!=(row['source_value'],row['footprint']),
          'pins_checked':len(row['nets']),'qualification':row['qualification']})
    report={'status':'PASS' if not errors else 'FAIL','purchase_released':False,'errors':errors,
      'hash_normalization':'CRLF_TO_LF_TEXT_ONLY',
      'map_sha256':hashlib.sha256(selection.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'netlist_sha256':hashlib.sha256(netlist.read_bytes().replace(b'\r\n',b'\n')).hexdigest(),
      'selected_positions':len(data['references']),'unresolved_order_codes':sum(not r.get('orderable_mpn') for r in data['references']),
      'per_reference':records}
    (HERE/'selection_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if errors:raise ValueError('\n'.join(errors))
    return report

if __name__=='__main__':
    import sys
    print(json.dumps(verify() if '--verify' in sys.argv else apply(),indent=2))
