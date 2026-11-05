"""Build a traceable per-reference engineering selection, without editing hardware."""
from __future__ import annotations
import collections, copy, csv, hashlib, json, re
from pathlib import Path
import xml.etree.ElementTree as ET
from catalog import CAPS, SPECIAL, SHUNT, PRECISION

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HW = HERE / 'source_snapshot'
DATE = '2026-10-28'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def natural(x): return (re.sub(r'\d+', '', x), int(re.search(r'\d+', x)[0]))
def number(value):
    m = re.match(r'([\d.]+)\s*([pnumkKMR\u00b5]?)', value)
    if not m: return None
    return float(m[1]) * {'p':1e-12,'n':1e-9,'u':1e-6,'\u00b5':1e-6,'m':1e-3,'k':1e3,'K':1e3,'M':1e6,'R':1,'':1}[m[2]]

def normalized_footprint(row, manifest):
    fp = row['Footprint']
    if fp.startswith('Power8GDI_GDI:REF_'):
        return manifest[fp.split('REF_')[1]]['source_footprint']
    return fp

def size_from_fp(fp):
    if 'Shunt_1206' in fp: return '1206'
    if 'PAD-0805-PAD' in fp: return '0805'
    m = re.search(r'(0603|0805|1206|1210|2512)',fp)
    return m[1] if m else fp.split(':')[-1]

def resistor_code(ohms):
    if ohms == 0: return '0000'
    if ohms >= 1e6: v,unit=ohms/1e6,'M'
    elif ohms >= 1e3: v,unit=ohms/1e3,'K'
    else: v,unit=ohms,'R'
    t = format(v,'.6g')
    if '.' in t: a,b=t.split('.');return (a+unit+b).ljust(4,'0')
    return (t+unit).ljust(4,'0')

def resistor(row, package):
    ohms=number(row['Value'])
    if row['Value']=='Jumper-Pad-Pad':ohms=0
    if ohms==0.01:return copy.deepcopy(SHUNT)
    if row['Reference'] in SPECIAL:return copy.deepcopy(SPECIAL[row['Reference']])
    precision = '0.1%' in row['Value'] or '25ppm' in row['Value']
    if precision:
        if (package,ohms) not in PRECISION:
            raise ValueError(f'No reviewed precision resistor: {row}')
        result=copy.deepcopy(PRECISION[(package,ohms)])
    else:
        mpn=f'CRCW{package}{resistor_code(ohms)}'+('Z0EA' if ohms==0 else 'FKEA')
        power={'0603':0.1,'0805':0.125,'1206':0.25}[package]
        if '0.5W' in row['Value']:mpn+='HP';power=0.75
        result=dict(manufacturer='Vishay',orderable_mpn=mpn,package=package,
            ratings=dict(resistance_ohm=ohms,tolerance_pct=None if ohms==0 else 1,
                tcr_ppm_c=None if ohms==0 else 100,power_w=power,
                working_voltage_v={'0603':75,'0805':150,'1206':200}[package],
                power_reference_temperature_c=70,temperature_min_c=-55,temperature_max_c=155,
                technology='jumper' if ohms==0 else 'thick film',aec_q200=True),
            source_urls=['https://www.vishay.com/docs/20035/dcrcwe3.pdf'],
            confidence='MANUFACTURER_ORDERING_TABLE',status='SELECTED_FAMILY_CODE')
        if ohms==0:result['ratings']['current_a']={'0603':2,'0805':2.5,'1206':3.5}[package]
        if 'HP' in mpn:
            result['source_urls']=['https://www.vishay.com/docs/20043/crcwhpe3.pdf']
            result['source_urls'].append('https://www.newark.com/vishay/crcw12061k00fkeahp/surface-mount-thick-film-resistor/dp/41R4820')
            result['confidence']='CATALOG_IDENTITY_AND_NOMINALS';result['status']='SELECTED_CATALOG_ITEM'
    result['qualification']='BOARD_QUALIFICATION_PENDING'
    return result

def cap_select(row, package):
    pf=round(number(row['Value'])*1e12)
    vm=re.search(r'(\d+(?:\.\d+)?)\s*(k?)V',row['Value'])
    volts=float(vm[1]) * (1000 if vm[2] else 1) if vm else None
    dm=re.search(r'(X[578][RST]|C0G)',row['Value']);diel=dm[1] if dm else None
    lcsc=row['Source_LCSC']
    # Original reference manufacturer ID and traced node pairs establish minima.
    original={'C342873':(100,'X7R'),'C1615':(25,'X7R'),'C14663':(50,'X7R'),
        'C15849':(16,'X7R'),'C19666':(16,'X7R'),'C106247':(50,'C0G'),
        'C576850':(100,'C0G'),'C342899':(50,'C0G'),'C525649':(100,'C0G')}
    if volts is None:
        volts,source_diel=original.get(lcsc,(50 if pf<1e6 else 16,'X7R'))
        diel=diel or source_diel
    elif diel is None:diel='X7R'
    choices=[v for (s,c,vol,d),v in CAPS.items() if s==package and c==pf and vol>=volts and d==diel]
    if choices:return copy.deepcopy(sorted(choices,key=lambda x:x['ratings']['rated_voltage_v'])[0])
    return dict(manufacturer='',orderable_mpn=None,package=package,ratings={},
        source_urls=[],confidence='UNRESOLVED',status='UNRESOLVED_SPECIFICATION',
        qualification='NO_SUITABLE_EXACT_PART_CONFIRMED',gaps=[f'No verified exact match for {row["Value"]} in {package}; do not lower voltage or substitute dielectric.'])

def maker(mpn):
    if mpn.startswith(('SN74','CLVC','TPS','LM','INA','TPIC','TCAN','TLIN','TLV','REF30','UCC')):return 'Texas Instruments'
    if mpn.startswith(('IPD','TLE')):return 'Infineon Technologies'
    if mpn.startswith(('STM','STGB','STPS','VND','USBLC')):return 'STMicroelectronics'
    if mpn.startswith(('LTC','LT30','AD8','MAX')):return 'Analog Devices'
    if mpn.startswith(('BUK','BAT','BAS','BC8','2N7','PESD')):return 'Nexperia'
    if mpn.startswith(('MC33','TJA')):return 'NXP Semiconductors'
    if mpn.startswith('MCP'):return 'Microchip Technology'
    if mpn.startswith('NCV'):return 'onsemi'
    if mpn.startswith('XAL'):return 'Coilcraft'
    if mpn.startswith('WSLP'):return 'Vishay'
    if mpn.startswith(('10403','10501')):return 'Molex'
    if mpn.startswith('6437'):return 'TE Connectivity'
    if mpn.startswith('ASEM'):return 'Abracon'
    if mpn.startswith(('SMBJ','SMCJ')):return 'Littelfuse'
    if mpn.startswith('SDURB'):return 'SMC Diode Solutions'
    return ''

def existing(row,package):
    mpn=row['Reference_MPN'];mf=maker(mpn)
    rename={'IPD90N10S4-06':'IPD90N10S406ATMA1','TLE9201SG':'TLE9201SGAUMA1',
        'MAX9924UAUB/V+':'MAX9924UAUB/V+T','PESD1CAN':'PESD1CAN,215','PESD2CAN':'PESD2CAN,215'}
    selected=rename.get(mpn,mpn)
    ti_families={
        'TCAN1042HGVDRQ1':'TCAN1042H-Q1','TLIN1029ADRQ1':'TLIN1029A-Q1',
        'TLV9004QPWRQ1':'TLV9004-Q1','SN74LVC14AQPWRQ1':'SN74LVC14A-Q1',
        'TPS3431SQDRBRQ1':'TPS3431-Q1','TPS3808G33QDBVRQ1':'TPS3808-Q1','TPS3808G01QDBVRQ1':'TPS3808-Q1',
        'TPS7B4253QDDARQ1':'TPS7B4253-Q1','TPIC8101DWR':'TPIC8101',
        'LM74800QDRRRQ1':'LM7480-Q1','LM76003QRNPRQ1':'LM76003-Q1','TPS62130AQRGTRQ1':'TPS62130A-Q1',
        'UCC27524AQDRQ1':'UCC27524A-Q1','INA300AQDGSRQ1':'INA300-Q1','REF3033AIDBZR':'REF3033',
        'CLVC1G125QDBVRQ1':'SN74LVC1G125-Q1'}
    if mpn.startswith('SN74') and mpn not in ti_families:
        ti_families[mpn]=re.sub(r'(Q(?:DBVR|PWR|DCUR)|DCKR)Q1$','-Q1',mpn)
    urls={'Texas Instruments':'https://www.ti.com/product/'+ti_families.get(mpn,mpn)+'/part-details/'+mpn,
        'Nexperia':'https://www.nexperia.com/product/'+mpn.split(',')[0],
        'Infineon Technologies':'https://www.infineon.com/part/'+mpn,
        'STMicroelectronics':'https://www.st.com/en/search.html#q='+mpn,
        'Analog Devices':'https://www.analog.com/en/search.html?q='+mpn,
        'Molex':'https://www.molex.com/en-us/products/part-detail/'+mpn,
        'TE Connectivity':'https://www.te.com/en/product-'+mpn+'.html',
        'Coilcraft':'https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xal/xal'+('5030' if '5030' in mpn else '7070')+'/',
        'Abracon':'https://abracon.com/Oscillators/ASEM.pdf',
        'Littelfuse':'https://www.littelfuse.com/products/tvs-diodes/surface-mount/'+mpn[:4].lower(),
        'Vishay':'https://www.vishay.com/docs/30122/wslp.pdf',
        'Microchip Technology':'https://www.microchip.com/en-us/product/MCP6004',
        'NXP Semiconductors':('https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf' if mpn.startswith('MC33') else 'https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf')}
    url=row['Datasheet'] if row['Datasheet'].startswith('http') else urls.get(mf,'')
    return dict(manufacturer=mf,orderable_mpn=selected,package=package,ratings={},
        source_urls=[url] if url else [],confidence='EXISTING_REFERENCE_MPN_NOT_REQUALIFIED',
        gaps=['Existing schematic MPN retained. Complete circuit rating/temperature and package signoff is still required.'],
        status='REFERENCE_MPN_RETAINED',qualification='PINOUT_RATINGS_AND_DELIVERY_SUFFIX_REVIEW_PENDING')

def build():
    bom=HW/'integrated_bom.csv';net=HW/'core.net'
    rows=list(csv.DictReader(bom.open(encoding='utf-8-sig')))
    manifest=json.loads((HW/'gdi/footprint_manifest.json').read_text(encoding='utf-8'))
    nets=collections.defaultdict(list)
    for n in ET.parse(net).findall('./nets/net'):
        for node in n.findall('node'):nets[node.get('ref')].append({'pin':node.get('pin'),'net':n.get('name')})
    fitted=[r for r in rows if r['DNP']=='False' and r['Exclude_From_BOM']=='False' and r['Assembly_Class'] in ('SURFACE_MOUNT','THROUGH_HOLE')]
    overrides=json.loads((HERE/'overrides.json').read_text(encoding='utf-8')) if (HERE/'overrides.json').exists() else {}
    selected=[]
    for row in fitted:
        ref=row['Reference'];fp=normalized_footprint(row,manifest);package=size_from_fp(fp)
        if row['Reference_MPN']:s=existing(row,package)
        elif ref.startswith('R'):s=resistor(row,package)
        elif ref.startswith('C'):s=cap_select(row,package)
        else:s=dict(manufacturer='',orderable_mpn=None,package=package,ratings={},source_urls=[],confidence='UNRESOLVED',status='UNRESOLVED_PART',qualification='REVIEW_REQUIRED',gaps=['Exact manufacturer/orderable part not selected'])
        override=overrides.get(ref) or overrides.get('MPN:'+row['Reference_MPN']) or overrides.get('LCSC:'+row['Source_LCSC'])
        if override:s.update(copy.deepcopy(override))
        s.setdefault('gaps',[]);s.setdefault('qualification','BOARD_QUALIFICATION_PENDING')
        s.setdefault('approved_deviation',None)
        s['requirements']={'source_value':row['Value'],'source_package':package,'rating_basis':'Explicit schematic fields; absent ratings are not inferred as proven circuit margins.'}
        if ref.startswith('C'):
            vm=re.search(r'(\d+(?:\.\d+)?)\s*(k?)V',row['Value'])
            s['requirements']['rated_voltage_min_v']=float(vm[1])*(1000 if vm[2] else 1) if vm else None
            dm=re.search(r'(X[578][RST]|C0G)',row['Value'])
            s['requirements']['dielectric']=dm[1] if dm else None
        if row['Reference_MPN']=='BUK9230-100B' and not override:
            s.update(orderable_mpn=None,status='RESERVED_HARDWARE_REVIEW',confidence='REPLACEMENT_PENDING',qualification='PT2001_GATE_DRIVE_AND_THERMAL_REVIEW')
            s['gaps']=['Hardware engineer owns replacement for obsolete BUK9230-100B; not an order instruction.']
        if ref=='C114':
            s['status']='SELECTED_CONDITIONAL';s['gaps'].append('C114 must provide >=4.7uF effective at actual 3.3V, temperature, negative tolerance and aging. 10uF nominal is not proof; supplier envelope and board validation pending.')
            s['ratings']['required_effective_capacitance_min_pf']=4700000
        fields=json.loads(row['Source_Fields_JSON'])
        note=fields.get('Design note','')
        if ('effective' in note.lower() or 'effective' in row['Value'].lower()):
            s['gaps'].append('Required effective capacitance not yet verified with supplier bias, temperature, tolerance and aging envelope.')
        if row['Source_LCSC']=='C309628':s['gaps'].append('Original C309628 thick-film1500ppm/K rejected for precision current sensing; proposed metal strip needs repetitive pulse, hot derating and Kelvin pad review.')
        if s['ratings'].get('capacitance_pf',0)>=1e6 and s['ratings'].get('dielectric') in ('X7R','X7S','X5R'):
            s['ratings'].setdefault('effective_capacitance_min_pf',None)
            s['ratings'].setdefault('dc_bias_qualification','PENDING_AT_ACTUAL_NODE_VOLTAGE')
        if s['ratings'].get('technology') in ('thick film','thin film','metal strip'):
            s['ratings']['derating']='Use manufacturer power versus ambient/terminal temperature curve; PCB thermal and fault pulse envelope not qualified.'
        s.update(reference=ref,source_value=row['Value'],source_reference_mpn=row['Reference_MPN'],
            footprint=row['Footprint'],normalized_footprint=fp,source_fields=fields,
            source_lcsc=row['Source_LCSC'],nets=nets[ref],sheet=row['Sheet'],
            assembly_class=row['Assembly_Class'],quantity_per_board=1,quantity_10_boards=10,
            purchase_released=False,observed_date=DATE)
        selected.append(s)
    # Group only rows whose selection and ratings match; original values/notes remain per ref.
    groups={}
    keys=('manufacturer','orderable_mpn','package','ratings','source_urls','confidence','qualification','status','gaps')
    for s in selected:
        record={k:s[k] for k in keys};key=json.dumps(record,sort_keys=True)
        if key not in groups:
            groups[key]=dict(record,selection_id='SEL-'+hashlib.sha256(key.encode()).hexdigest()[:12],refs=[],purchase_released=False)
        g=groups[key];g['refs'].append(s['reference']);s['selection_id']=g['selection_id']
    for g in groups.values():g.update(quantity_per_board=len(g['refs']),quantity_10_boards=10*len(g['refs']))
    counts=collections.Counter(s['status'] for s in selected)
    doc=dict(schema_version=1,generated_date=DATE,scope='sport-gdi6; B58 Gen2 DI / ID1050x-family PI project; external injectors excluded from PCBA BOM',
        purchase_released=False,bom_snapshot=dict(path='procurement/selection/source_snapshot/integrated_bom.csv',original_path='hardware/design/integrated_bom.csv',netlist_path='procurement/selection/source_snapshot/core.net',sha256=sha(bom),netlist_sha256=sha(net),base_git_revision='013f467'),
        counts=dict(source_rows=len(rows),fitted_refs=len(selected),smt=sum(s['assembly_class']=='SURFACE_MOUNT' for s in selected),tht=sum(s['assembly_class']=='THROUGH_HOLE' for s in selected),
            source_missing_mpn=sum(not s['source_reference_mpn'] for s in selected),selected_orderable_mpn_refs=sum(bool(s['orderable_mpn']) for s in selected),
            unresolved_mpn_refs=sum(not s['orderable_mpn'] for s in selected),refs_with_explicit_gaps=sum(bool(s['gaps']) for s in selected),groups=len(groups),statuses=dict(counts)),
        exclusions=[dict(reference=r['Reference'],value=r['Value'],dnp=r['DNP'],assembly_class=r['Assembly_Class']) for r in rows if r not in fitted],
        global_qualification_gates=['No purchasing release. A populated MPN is an engineering selection only.',
            'Exact landed footprint, polarity, pinout, pad dimensions and component height require hardware signoff.',
            'Temperature, fault pulses, ripple, EMI and mounted thermal qualification remain required.',
            'No stock or price is inferred by this file. Costing uses separate dated evidence/allowances.',
            'Manufacturer catalog rating is not the same as verified circuit stress margin.'],
        groups=sorted(groups.values(),key=lambda g:(g['manufacturer'],g['orderable_mpn'] or '',g['selection_id'])),references=sorted(selected,key=lambda s:natural(s['reference'])))
    (HERE/'bom_selection.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    columns=['reference','selection_id','quantity_per_board','quantity_10_boards','source_value','source_reference_mpn','manufacturer','orderable_mpn','package','footprint','normalized_footprint','assembly_class','status','confidence','qualification','purchase_released','ratings_json','source_urls_json','gaps_json','nets_json','source_fields_json','approved_deviation_json','requirements_json']
    with (HERE/'bom_selection.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=columns);w.writeheader()
        for s in doc['references']:
            out={k:s.get(k,'') for k in columns if not k.endswith('_json')}
            for k in ('ratings','source_urls','gaps','nets','source_fields','approved_deviation','requirements'):out[k+'_json']=json.dumps(s[k],ensure_ascii=False,sort_keys=True)
            w.writerow(out)
    print(json.dumps(doc['counts'],indent=2))
    return doc

if __name__=='__main__':build()
