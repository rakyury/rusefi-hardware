"""Structural checks and explicit arithmetic bounds, never a current calibration."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET
from sexpr import parse, child, children

HERE=Path(__file__).resolve().parent
MOSFET='IPD60N10S4L12ATMA1'
SHUNT_SOURCE_REFS={'R12','R21','R22','R26','R45'}

def validate(root, contract):
    errors=[]
    pins={(n.get('ref'),n.get('pin')):net.get('name') for net in root.findall('./nets/net') for n in net.findall('node')}
    parts={c.get('ref'):c for c in root.findall('./components/comp')}
    if contract['engine_permission'] is not False:errors.append('Unqualified engine permission')
    if contract['qualified_demagnetization_guard_us'] is not None or not contract['deny_when_guard_is_unqualified']:errors.append('Unqualified demagnetization must deny admission')
    if contract['phases_owning_shared_current_path']!=['boost','pickup','hold','demagnetization']:errors.append('Missing ownership phase')
    expected=[([1,2],'A',212,[26,25],[208,207],204),([3],'A',213,[28,27],[209],206),([4,5],'B',312,[26,25],[308,307],304),([6],'B',313,[28,27],[309],306)]
    if len(contract['shared_current_paths'])!=4:errors.append('Resource count')
    for group,(channels,bank,res,sense,low,high) in zip(contract['shared_current_paths'],expected):
        u='U201' if bank=='A' else 'U301';r=f'R{res}'
        if (group['channels'],group['sense_resistor'],group['pt_device'],group['sense_pins'],group['low_side_devices'],group['max_simultaneously_active'])!=(channels,r,u,sense,[f'Q{x}' for x in low],1):errors.append('Wrong shared-path mapping')
        for q in low:
            if pins.get((f'Q{q}','3'))!=pins.get((r,'1')):errors.append(f'LS source not on shunt {q}')
        if pins.get((u,str(sense[0])))!=pins.get((r,'2')):errors.append(f'{r} Kelvin+')
        if pins.get((u,str(sense[1])))!=pins.get((r,'3')):errors.append(f'{r} Kelvin-')
        if pins.get((r,'4'))!='GND':errors.append(f'{r} return')
        if pins.get((f'Q{high}','3'))!=group['high_side_net']:errors.append(f'{bank} high-side mismatch')
    expected_boost=[('PTA_VBOOST',[1,2,3]),('PTB_VBOOST',[4,5,6])]
    if [(b['resource'],b['channels']) for b in contract['boost_supplies']]!=expected_boost or any(b['max_simultaneous_boost_phases']!=1 for b in contract['boost_supplies']):errors.append('Boost admission mismatch')
    mosfets=[c for r,c in parts.items() if r in {f'Q{base+n}' for base in (200,300) for n in (1,2,3,4,5,6,7,8,9,11,12,13)}]
    if len(mosfets)!=24 or any(c.findtext('value')!=MOSFET for c in mosfets):errors.append('MOSFET selection not in actual netlist')
    for c in mosfets:
        if c.find("fields/field[@name='LCSC']") is not None:errors.append('Obsolete LCSC retained as current device')
    for base in (200,300):
        if parts[f'R{base+99}'].find("property[@name='dnp']") is None:errors.append('PT enable fitted before qualification')
        bank='A' if base==200 else 'B';prefix='PT'+bank+'_'
        for number in (7,9):
            if [pins.get((f'C{base+number}',p)) for p in ('1','2')]!=[prefix+'VBOOST',prefix+'Vdrive_shunt']:errors.append('Boost capacitor polarity/return')
        if [pins.get((f'L{base+2}',p)) for p in ('1','2')]!=[prefix+'+Batt_filtered',prefix+'Vdrive_coil']:errors.append('Wrong boost inductor path')
        if [pins.get((f'D{base+12}',p)) for p in ('1','2','3')]!=[prefix+'Vdrive_coil',prefix+'VBOOST',prefix+'Vdrive_coil']:errors.append('Boost diode pinout')
    return errors

def footprint_errors(fp, kelvin=False):
    if kelvin:
        groups=child(fp,'net_tie_pad_groups')
        actual={frozenset(s.strip() for s in g.split(',')) for g in groups[1:]} if groups else set()
        errors=[] if actual=={frozenset(('1','2')),frozenset(('3','4'))} else ['Kelvin pad groups bridge resistor terminals']
        pads={str(p[1]):p for p in children(fp,'pad')}
        for num,x in [('1',-1.725),('4',1.725)]:
            pad=pads[num]
            if child(pad,'at')[1:]!=[str(x),'0','90'] or child(pad,'size')[1:]!=['1.93','1.65']:errors.append('Shunt manufacturer land pattern '+num)
        return errors
    # Infineon PG-TO252-3-313 recommended land pattern, rotated 90deg.
    pads={str(p[1]):p for p in children(fp,'pad') if p[1] and 'F.Cu' in child(p,'layers') and 'F.Mask' in child(p,'layers')}
    errors=[]
    for number,xy,size in [('1',(-5.04,-2.28),(2.2,1.2)),('2',(1.26,0),(6.4,5.8)),('3',(-5.04,2.28),(2.2,1.2))]:
        pad=pads.get(number)
        if pad is None:errors.append('Missing package pad '+number);continue
        if any(abs(float(a)-b)>.011 for a,b in zip(child(pad,'at')[1:3],xy)):errors.append('Pad location '+number)
        if any(abs(float(a)-b)>.011 for a,b in zip(child(pad,'size')[1:3],size)):errors.append('Pad size '+number)
    return errors

def report():
    net=HERE.parent/'core.net';contract=json.loads((HERE/'scheduling_contract.json').read_text())
    errors=validate(ET.parse(net).getroot(),contract)
    manifest=json.loads((HERE/'reference_mapping.json').read_text())['A']['reference_map']
    for ref in manifest:
        if ref in SHUNT_SOURCE_REFS or ref.startswith('Q'):
            errors += [f'{ref}: {e}' for e in footprint_errors(parse((HERE/'Power8GDI_GDI.pretty'/f'REF_{ref}.kicad_mod').read_text()), ref in SHUNT_SOURCE_REFS)]
    result={'status':'STRUCTURE_PASS_LOAD_QUALIFICATION_BLOCKED' if not errors else 'FAIL','errors':errors,
      'netlist_sha256':hashlib.sha256(net.read_bytes()).hexdigest(),
      'requested_loads':{'DI':'B58B30 Gen2','PI':'IDX1050'},
      'family_reference_only':{'family':'Bosch HDEV6 solenoid','boost_V':65,'boost_A_range':[12,13],'pickup_A':5.3,'pickup_duration_us':600,'hold_A_range':[2.6,3.6],'coil_ohm_ambient':1.83,'boost_duration_us':None,'injector_inductance_H':None,'exact_OEM_current_profile_verified':False},
      'pt2001':{'device':'MC33PT2001AE','nominal_gate_V':7,'ordering_table_VBOOST_max_V':72,'recommended_operating_VBOOST_max_V':None,'absolute_max_VBOOST_V':None,'HAE_ordering_table_max_V':80,'HAE_drop_in_qualification':False},
      'arithmetic_examples_not_operating_limits':{'nominal_bank_Cboost_F':940e-6,'stored_energy_65V_J':.5*940e-6*65**2,'Cboost_energy_65_to_60V_J':.5*940e-6*(65**2-60**2),'13A_no_recharge_droop_V_per_100us':13*100e-6/940e-6,'shunt_10mohm_13A_instantaneous_W':13**2*.010,'selected_mosfet_15mohm_13A_25C_instantaneous_W':13**2*.015,'boost_12V_to_65V_ideal_duty':1-12/65,'boost_10uH_100kHz_12V_ideal_ripple_A':12*(1-12/65)/(10e-6*100e3),'all_12_gates_per_bank_49nC_100kHz_charge_current_A':12*49e-9*100e3},
      'blocked':['Exact OEM injector identity/current waveform/inductance and pump load','Full PT electrical data and approved 65V regulation/transient margin','Independent hardware VBOOST overvoltage/shutdown and returned-energy clamp','Boost L202/L302 saturation/RMS and diode dynamic/thermal qualification','Capacitor voltage/ripple/lifetime and pulse shunt temperature qualification','Gate drive/switching/SOA/avalanche and PCB heat-spreading bench evidence','Qualified demagnetization guard and real scheduler integration']}
    (HERE/'load_review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    result=report();print(json.dumps(result,indent=2));raise SystemExit(bool(result['errors']))
