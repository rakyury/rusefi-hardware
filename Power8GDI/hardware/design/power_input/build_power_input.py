"""Generate the logic supply candidate. Run after core_schlib is installed.

This is an original 5 V adaptation of TI's public LM5164-Q1 design procedure;
it is not a validated TI reference design or a load-dump qualification.
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--helper', type=Path, default=HERE.parent)
args = parser.parse_args()
sys.path.insert(0, str(args.helper))
from core_schlib import Sheet, Symbol, Quoted, parse, dump, children, child, uid

symbols = {}
standalone_library=[]
for expr in children(parse((HERE/'power_symbols.kicad_sym').read_text()), 'symbol'):
    name = str(expr[1]).split(':')[-1]
    fp = next((str(p[2]) for p in children(expr, 'property') if p[1] == 'Footprint'), '')
    symbols[name] = Symbol(name, dump(expr), fp)
    library_expr=copy.deepcopy(expr)
    library_expr[1]=Quoted(name)
    standalone_library.append(dump(library_expr))
(HERE/'power_input.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(standalone_library)+'\n)\n',encoding='utf-8')
(HERE/'sym-lib-table').write_text('(sym_lib_table (lib (name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/power_input.kicad_sym")(options "")(descr "Selected official KiCad supply symbols")))\n',encoding='utf-8')
(HERE/'power_input.kicad_pro').write_text('{"meta":{"filename":"power_input.kicad_pro","version":1}}\n',encoding='utf-8')

s = Sheet('power_input/power_input', '12 V logic input and 5 V buck', root=uid('Power8GDI_Core'))
s.text('LOGIC SUPPLY ONLY - actuator power uses independent feeds', 12.7, 17.78, 2.0)
s.text('Prototype calculation: nominal 12 V, logic output target 5 V / 0.8 A. Total load and thermals remain open.',12.7,24.13)
s.text('External fuse required. No cold-crank or ISO pulse qualification. Do not connect GDI boost input to this diode.',12.7,29.21)

RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0603_1608Metric'
def part(kind, ref, value, x, y, nets, fp=None, note='', dnp=False):
    start=len(s.items)
    s.component(symbols[kind],ref,value,x,y,{str(k):v for k,v in nets.items()},footprint=fp,note=note,dnp=dnp)
    if kind == 'LM5164DDA':
        instance=parse(s.items[start])
        for prop in children(instance,'property'):
            if prop[1]=='Value':
                child(prop,'at')[1:3]=[str(x),str(y-20.32)]
        s.items[start]=dump(instance)
    elif kind in ('D_TVS','D_Schottky'):
        instance=parse(s.items[start])
        for prop in children(instance,'property'):
            if prop[1] in ('Reference','Value'):
                child(prop,'at')[1:3]=[str(x),str(y+7.62 if prop[1]=='Value' else y-5.08)]
                effects=child(prop,'effects')
                effects[:]=[v for v in effects if not (isinstance(v,list) and v[0]=='justify')]
        s.items[start]=dump(instance)

# Raw-side bidirectional TVS and diode polarity are explicit in the manifest.
part('D_TVS','D502','SMBJ24CA',50.8,50.8,{1:'VBAT_MAIN_FUSED',2:'GND'},'Diode_SMD:D_SMB',
     'Littelfuse bidirectional 24 V standoff TVS;38.9V rated clamp at25C; pulse energy/fuse coordination and manufacturer grade not frozen')
part('D_Schottky','D501','STPS2H100UY',127,50.8,{1:'VBAT_LOGIC_PROTECTED',2:'VBAT_MAIN_FUSED'},'Diode_SMD:D_SMB',
     '100 V 2 A automotive SMB: pin1 cathode to protected rail; pin2 anode to fused input')
part('C','C501','2.2u 100V X7R',50.8,101.6,{1:'VBAT_LOGIC_PROTECTED',2:'GND'},'Capacitor_SMD:C_1210_3225Metric',
     '2 parallel input ceramics; require total effective capacitance >=2.2uF across qualified input range')
part('C','C502','2.2u 100V X7R',101.6,101.6,{1:'VBAT_LOGIC_PROTECTED',2:'GND'},'Capacitor_SMD:C_1210_3225Metric')
part('C_Polarized','C503','47u 63V bulk',152.4,101.6,{1:'VBAT_LOGIC_PROTECTED',2:'GND'},'Capacitor_SMD:CP_Elec_8x10',
     'Provisional 8x10mm aluminum damping capacitor: MPN, ESR, ripple current and -40C impedance require selection')
part('LM5164DDA','U501','LM5164QDDARQ1',254,76.2,
     {1:'GND',2:'VBAT_LOGIC_PROTECTED',3:'BUCK_EN',4:'BUCK_RON',5:'BUCK_FB',6:'PGOOD_5V_CORE',7:'BUCK_BST',8:'BUCK_SW',9:'GND'},
     note='TI DDA8 + exposed thermal pad9. EP tied GND; use close input/boot loops, Kelvin feedback ground.')
part('C','C504','2.2n 50V X7R 5%',355.6,50.8,{1:'BUCK_BST',2:'BUCK_SW'},CFP,
     'TI allowable external bootstrap capacitance1.5..2.5nF;5% nominal chosen')
part('L','L501','MSS1246T-473MLC',355.6,101.6,{1:'BUCK_SW',2:'+5V_CORE'},'Inductor_SMD:L_Coilcraft_MSS1246T-XXX',
     '47uH20%;2.7A at10% inductance drop,1.5A Irms20C rise at25C per Coilcraft; hot derating pending')

part('R','R501','453k 1%',50.8,152.4,{1:'VBAT_LOGIC_PROTECTED',2:'BUCK_EN'},RFP)
part('R','R502','100k 1%',101.6,152.4,{1:'BUCK_EN',2:'GND'},RFP)
part('R','R503','41.2k 1%',152.4,152.4,{1:'BUCK_RON',2:'GND'},RFP)
part('R','R504','158k 0.1%',203.2,152.4,{1:'+5V_CORE',2:'BUCK_FB'},RFP)
part('R','R505','49.9k 0.1%',254,152.4,{1:'BUCK_FB',2:'GND'},RFP)
part('C','C505','22u 25V X7R',304.8,152.4,{1:'+5V_CORE',2:'GND'},'Capacitor_SMD:C_1210_3225Metric',
     'Output ceramic voltage derating/MPN must be verified; evaluate load transient with actual effective Cout')
part('C','C506','22u 25V X7R',355.6,152.4,{1:'+5V_CORE',2:'GND'},'Capacitor_SMD:C_1210_3225Metric')

s.text('Type-3 injection: RA from SW to RIPPLE; CA from RIPPLE to VOUT; CB from RIPPLE to FB.',12.7,174.0)
part('R','R506','110k 1%',50.8,203.2,{1:'BUCK_SW',2:'BUCK_RIPPLE'},RFP)
part('C','C507','3.3n 50V C0G 5%',127,203.2,{1:'BUCK_RIPPLE',2:'+5V_CORE'},CFP)
part('C','C508','220p 50V C0G 5%',203.2,203.2,{1:'BUCK_RIPPLE',2:'BUCK_FB'},CFP)
part('R','R507','47k 1%',304.8,203.2,{1:'+3V3',2:'PGOOD_5V_CORE'},RFP,
     'PGOOD open-drain pullup to3.3V; read only when3.3V valid; no automatic power-output enable')
s.text('UVLO rising nominal8.295V at protected rail. Diode drop adds battery voltage requirement.',12.7,236.22)
s.text('Feedback divider ideal4.9996V; Type-3 ripple adds regulation offset. Check voltage before MCU connection.',12.7,242.57)
s.text('PGOOD is diagnostic only. Dedicated hardware actuator inhibit/watchdog circuit is a separate unfinished domain.',12.7,248.92)
s.write(HERE.parent)

vout=1.2*(1+158000/49900)
freq_khz=vout*2500/41.2
freq=freq_khz*1000
ca=3.3e-9; ra=110e3; lind=47e-6
samples=[]
for vin in (7.344,8.295,12.0,16.0,24.0,53.3):
    delta=vout/(freq*lind)*(1-vout/vin)
    ripple=(vout/vin/freq)*(vin-vout)/(ra*ca)
    samples.append({'vin_protected_v':vin,'ripple_current_nominal_a':delta,
                    'peak_current_at_0p8a_nominal_a':.8+delta/2,
                    'peak_current_at_0p8a_lminus20pct_a':.8+delta/1.6,
                    'fb_injection_nominal_mv':ripple*1000})
manifest={'schema_version':1,'project':'Power8GDI_Core','root_uuid':s.root,
          'qualification':'BLOCKED_ENGINEERING_CANDIDATE','parts':s.parts,
          'electrical_assumptions':{'rail':'12 V nominal','output_target_a':0.8,
          'current_limit_min_peak_a':1.25,'actuator_feed_supported':False,
          'ideal_output_v':vout,'nominal_switching_khz':freq_khz,
          'uvlo_rising_nominal_protected_v':1.5*(1+453/100),
          'uvlo_rising_conservative_max_protected_v':1.55*(1+453*1.01/(100*.99)),
          'uvlo_falling_min_protected_v':1.35*(1+453*.99/(100*1.01)),
          'ca_min_pf':1e12*10/(freq*(158000*49900/(158000+49900))),
          'cb_min_pf_for_75us':1e12*75e-6/(3*158000),
          'samples':samples},
          'open_items':['source impedance and input bulk ESR','fuse and TVS energy coordination',
          'actual shared5V/3.3V load budget','thermal/EMC/line and load transients',
          'PGOOD supervisor integration','capacitor MPN/derating','no cold-crank qualification']}
(HERE/'power_input_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
with (HERE/'power_input_bom.csv').open('w',newline='',encoding='utf-8') as f:
    writer=csv.DictWriter(f,fieldnames=['ref','value','footprint','dnp','note'])
    writer.writeheader()
    for p in s.parts: writer.writerow({k:p[k] for k in writer.fieldnames})
print(f'Wrote {len(s.parts)} actual components; {freq_khz:.2f}kHz nominal; not qualified')
