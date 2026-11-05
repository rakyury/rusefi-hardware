"""Generate two current-limited motor-interface candidates; not load-qualified."""
from __future__ import annotations
import copy
import csv
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from core_schlib import Sheet, Symbol, Quoted, box_symbol, child, children, dump, parse, uid

libs={}
for item in children(parse((HERE.parent/'power_input/power_symbols.kicad_sym').read_text()),'symbol'):
    name=str(item[1]).split(':')[-1]
    if name in ('R','C','C_Polarized','D_Schottky','D_TVS'):
        libs[name]=Symbol(name,dump(item))
driver=box_symbol('Motor_DRV8871DDA',[
    ('1','GND','power_in',-5.08,-17.78,90),('7','PGND','power_in',0,-17.78,90),('9','EP','passive',5.08,-17.78,90),
    ('5','VM','power_in',0,17.78,270),('3','IN1','input',-17.78,7.62,0),('2','IN2','input',-17.78,0,0),
    ('4','ILIM','input',-17.78,-7.62,0),('6','OUT1','output',17.78,5.08,180),('8','OUT2','output',17.78,-5.08,180)],
    'Power8GDI_Board:HSOP8_EP_ThermalVia0p3',width=30.48,height=30.48)
gate=box_symbol('Motor_AND_LVC1G08_Q1',[
    ('1','A','input',-10.16,2.54,0),('2','B','input',-10.16,-2.54,0),('4','Y','output',10.16,0,180),
    ('3','GND','power_in',0,-10.16,90),('5','VCC','power_in',0,10.16,270)],'Package_TO_SOT_SMD:SOT-23-5',width=15.24,height=15.24)
inv=box_symbol('Motor_NOT_LVC1G04_Q1',[
    ('1','NC','no_connect',-10.16,5.08,0),('2','A','input',-10.16,0,0),('4','Y','output',10.16,0,180),
    ('3','GND','power_in',0,-10.16,90),('5','VCC','power_in',0,10.16,270)],'Package_TO_SOT_SMD:SOT-23-5',width=15.24,height=15.24)
libs.update({x.name:x for x in (driver,gate,inv)})
RFP='Resistor_SMD:R_0603_1608Metric'; CFP='Capacitor_SMD:C_0603_1608Metric'
parts=[]
for channel,base in [('DBW',900),('EWG',950)]:
    prefix=channel+'_'
    s=Sheet('motor/'+channel.lower()+'_driver',channel+' provisional H-bridge and hardware gating',root=uid('Power8GDI_Core'),paper='A2')
    s.text(channel+' MOTOR INTERFACE - LOAD MODEL NOT SELECTED',12.7,17.78,2.0)
    s.text('Current chop target1.75A; continuous thermal/current capability not established. Driver choice may change with actual motor.',12.7,25.4)
    def add(sym,ref,value,x,y,nets,fp=None,note='',dnp=False):
        start=len(s.items)
        s.component(libs.get(sym,sym) if isinstance(sym,str) else sym,ref,value,x,y,{str(k):v for k,v in nets.items()},footprint=fp,note=note,dnp=dnp)
        if isinstance(sym,str) and sym in ('D_TVS','D_Schottky'):
            item=parse(s.items[start])
            for prop in children(item,'property'):
                if prop[1] in ('Reference','Value'):
                    child(prop,'at')[1:3]=[str(x),str(y+7.62 if prop[1]=='Value' else y-5.08)]
                    effects=child(prop,'effects');effects[:]=[v for v in effects if not(isinstance(v,list) and v[0]=='justify')]
            s.items[start]=dump(item)
    def res(n,value,x,y,one,two,note=''):
        add('R','R'+str(base+n),value,x,y,{1:one,2:two},RFP,note)
    def cap(n,value,x,y,one,fp=CFP,note=''):
        add('C','C'+str(base+n),value,x,y,{1:one,2:'GND'},fp,note)
    raw='VBAT_'+channel+'_FUSED';vm=prefix+'VM'
    add('D_Schottky','D'+str(base+1),'STPS2H100UY',76.2,76.2,{1:vm,2:raw},'Diode_SMD:D_SMB',
        'Separate motor-feed reverse diode; cathode1 protected, anode2 fused raw. 2A rating requires thermal review.')
    add('D_TVS','D'+str(base+2),'SMBJ24CA',152.4,76.2,{1:vm,2:'GND'},'Diode_SMD:D_SMB',
        'Afterreverseblockingdiode so clampcanabsorbregeneration; energy/hotclamp/fusecoordinationnotqualified')
    cap(1,'100n 50V X7R',228.6,76.2,vm,note='At driverVM/PGND; short switching-current loop')
    cap(2,'2.2u 50V X7R',292.1,76.2,vm,'Capacitor_SMD:C_1210_3225Metric')
    add('C_Polarized','C'+str(base+3),'100u 50V bulk',355.6,76.2,{1:vm,2:'GND'},'Capacitor_SMD:CP_Elec_10x10',
        'Provisional footprint and capacitance; select MPN/ESR/ripple rating after motor inductance and regeneration analysis')
    add(driver,'U'+str(base+1),'DRV8871DDAR',482.6,88.9,
        {1:'GND',7:'GND',9:'GND',5:vm,3:prefix+'IN1_GATED',2:prefix+'IN2_GATED',4:prefix+'ILIM',6:prefix+'MOTOR_A',8:prefix+'MOTOR_B'},
        note='Industrial driver candidate, not AEC-Q100. Bothinputs0=>coast/sleep. Automaticfaultretry; nofaultoutput/currenttelemetry.')
    res(1,'36.5k 1%',482.6,152.4,prefix+'ILIM','GND','Nominal1.753A,currentconstant59..69kV gives1.600..1.909A with1%R; no short-circuit or thermal qualification')
    # Four AND gates encode PWM+direction, then two independent disable conditions.
    logic=[
        (inv,14,76.2,228.6,{2:prefix+'DISABLE',4:prefix+'NOT_DISABLED'},'Invert MCU active-high disable'),
        (gate,10,177.8,228.6,{1:'HW_ACTUATOR_ENABLE',2:prefix+'NOT_DISABLED',4:prefix+'ENABLE'},'Independent latched hardware permission AND MCU notdisabled'),
        (gate,11,292.1,228.6,{1:prefix+'PWM',2:prefix+'ENABLE',4:prefix+'PWM_ENABLED'},'PWM blocked by either disable source'),
        (inv,15,406.4,228.6,{2:prefix+'DIR',4:prefix+'DIR_N'},'Direction complement'),
        (gate,12,177.8,330.2,{1:prefix+'PWM_ENABLED',2:prefix+'DIR_N',4:prefix+'IN1_GATED'},'Forward PWM only'),
        (gate,13,330.2,330.2,{1:prefix+'PWM_ENABLED',2:prefix+'DIR',4:prefix+'IN2_GATED'},'Reverse PWM only'),
    ]
    for sym,n,x,y,nets,note in logic:
        nets.update({3:'GND',5:'+3V3'})
        add(sym,'U'+str(base+n),'SN74LVC1G04QDBVRQ1' if sym is inv else 'SN74LVC1G08QDBVRQ1',x,y,nets,note=note)
        cap(n,'100n 16V X7R',x+38.1,y+38.1,'+3V3',note='Locallogicdecoupling atVCC/GND')
    res(2,'100k',38.1,330.2,prefix+'PWM','GND','MCUresetdefaultnoPWM')
    res(3,'100k',76.2,330.2,prefix+'DIR','GND')
    res(4,'10k',482.6,228.6,'+3V3',prefix+'DISABLE','MCUresetdefaultdisabled')
    res(5,'100k',533.4,228.6,'HW_ACTUATOR_ENABLE','GND','HardwarepermissiondefaultsOFFifsourceopen')
    res(6,'10k',457.2,330.2,prefix+'IN1_GATED','GND','Steadypoweroffleakage11uA*10k<0.5VVIL; dynamicpowersequencingunqualified')
    res(7,'10k',520.7,330.2,prefix+'IN2_GATED','GND','Steadypoweroffleakage11uA*10k<0.5VVIL; dynamicpowersequencingunqualified')
    s.text('IN1 = PWM & HW_ENABLE & !DISABLE & !DIR; IN2 = PWM & HW_ENABLE & !DISABLE & DIR.',12.7,388.62)
    s.text('00 = coast; DIR changes sign. PWM-low uses fast decay; account sleep/restart latency. Gate faults are not single-fault tolerant.',12.7,396.24)
    s.write(HERE.parent);parts.extend(s.parts)
    (HERE/(channel.lower()+'_driver.kicad_pro')).write_text('{"meta":{"version":1}}\n')

defs=[]
for sym in libs.values():
    expr=parse(sym.body);expr[1]=Quoted(sym.name);defs.append(dump(expr))
(HERE/'motor.kicad_sym').write_text('(kicad_symbol_lib (version 20241209)(generator "kicad_symbol_editor")\n'+'\n'.join(defs)+'\n)\n')
(HERE/'sym-lib-table').write_text('(sym_lib_table(lib(name "Power8GDI_Core")(type "KiCad")(uri "${KIPRJMOD}/motor.kicad_sym")(options "")(descr "Motorcandidatesymbols")))\n')
manifest={'schema_version':1,'qualification':'BLOCKED_LOAD_SELECTION_AND_VALIDATION','root_uuid':uid('Power8GDI_Core'),'parts':parts,
          'control':'HW_ENABLE & !DISABLE gates encodedPWM/direction; noPTenableconnection',
          'current_limit_a':{'nominal':64/36.5,'calculated_min':59/(36.5*1.01),'calculated_max':69/(36.5*.99)},
          'motor_models':None,'continuous_current_rating_a':None,
          'limitations':['industrialDRV8871candidate','actualmotorcurrent/thermal/speedunknown','regeneration/fuse/TVSunqualified',
                         'noindependentmotorcurrentmeasurement','noHbridgedriverfaulttelemetry','not single-fault tolerant',
                         'closed-loopDBW/EWGsoftwareandfeedbackvalidationunfinished']}
(HERE/'motor_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
with (HERE/'motor_bom.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['ref','value','footprint','dnp','note']);w.writeheader()
    for p in parts:w.writerow({k:p[k] for k in w.fieldnames})
print(f'Generated two H-bridge candidate sheets: {len(parts)} parts; load qualification BLOCKED')
