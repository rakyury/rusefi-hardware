"""Generate connected, unqualified watchdog/latch/IGN gate candidate."""
from pathlib import Path
import csv
import json
from schlib import Sheet, Symbol, box_symbol, uid, q

HERE=Path(__file__).resolve().parent
ROOT_UUID='f4d21065-0a5b-5086-a08e-1af9469f04bd'
FP={
 'watchdog':'Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.6x2.4mm',
 'supervisor':'Package_TO_SOT_SMD:SOT-23-6',
 'schmitt':'Package_TO_SOT_SMD:SOT-23-5',
 'latch':'Package_SO:VSSOP-8_2.3x2mm_P0.5mm',
 'gate':'Package_SO:Texas_PW0020A_TSSOP-20_4.4x6.5mm_P0.65mm',
 'R':'Resistor_SMD:R_0603_1608Metric',
 'C':'Capacitor_SMD:C_0603_1608Metric',
}

def ic(name,left,right,fp):
    count=max(len(left),len(right));h=(count+1)*2.54
    pins=[]
    for values,x,angle in [(left,-15.24,0),(right,15.24,180)]:
        for i,(number,label,kind) in enumerate(values):
            pins.append((str(number),label,kind,x,(count-1)*1.27-i*2.54,angle))
    return box_symbol(name,pins,FP[fp],width=25.4,height=h)

def main():
    s=Sheet('safety_gate','Watchdog, latched inhibit and eight ignition gates',root=ROOT_UUID,paper='A2')
    s.text('ENGINEERING CANDIDATE — NOT QUALIFIED FOR ACTUATION',20,15,2)
    s.text('3.3 V logic only. Hardware faults asynchronously clear enable; recovery requires a fresh ARM rising edge.\nMIC output isolation remains DNP. No PT2001 DRVEN connection or assumed polarity.\n64.288 ms nominal watchdog is a backup CPU monitor, NOT a coil dwell/current limiter.',20,23)
    w=ic('TPS3431SQDRBRQ1',[(1,'VDD','power_in'),(2,'CWD','input'),(3,'EN','input'),(5,'SET1','input'),(6,'WDI','input')],[(7,'~{WDO}','open_collector'),(8,'ENOUT','open_collector'),(4,'GND','power_in'),(9,'EP','power_in')],'watchdog')
    p=ic('TPS3808G33QDBVRQ1',[(6,'VDD','power_in'),(5,'SENSE','input'),(3,'~{MR}','input'),(4,'CT','input')],[(1,'~{RESET}','open_collector'),(2,'GND','power_in')],'supervisor')
    h=ic('SN74LVC1G17QDBVRQ1',[(5,'VCC','power_in'),(2,'A','input'),(1,'NC','no_connect')],[(4,'Y','output'),(3,'GND','power_in')],'schmitt')
    f=ic('SN74LVC2G74QDCURQ1',[(8,'VCC','power_in'),(1,'CLK','input'),(2,'D','input'),(6,'~{CLR}','input'),(7,'~{PRE}','input')],[(5,'Q','output'),(3,'~{Q}','output'),(4,'GND','power_in')],'latch')
    g=ic('SN74LVC244AQPWRQ1',[(20,'VCC','power_in'),(1,'~{1OE}','input'),(19,'~{2OE}','input')]+[(n,f'{1 if i<4 else 2}A{i%4+1}','input') for i,n in enumerate([2,4,6,8,11,13,15,17])],[(n,f'{1 if i<4 else 2}Y{i%4+1}','tri_state') for i,n in enumerate([18,16,14,12,9,7,5,3])]+[(10,'GND','power_in')],'gate')
    r=box_symbol('R', [('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],FP['R'],width=5.08,height=2.54,prefix='R')
    c=box_symbol('C', [('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],FP['C'],width=5.08,height=2.54,prefix='C')
    c=Symbol('C',c.body.replace('(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0.254) (type default)) (fill (type background)))', '(polyline (pts (xy -1.27 2.54) (xy -1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy 1.27 2.54) (xy 1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none)))').replace('(length 2.54)','(length 3.81)'),FP['C'])
    s.component(w,'U801',w.name,80,65,{'1':'+3V3','2':'WD_CWD','3':'+3V3','5':'+3V3','6':'SAFETY_HEARTBEAT','7':'SAFETY_FAULT_N','8':'SAFETY_FAULT_N','4':'GND','9':'GND'},note='ENOUT tied to WDO as explicitly allowed by TI; SET1/EN hardwired enabled')
    s.component(p,'U802',p.name,220,65,{'6':'+3V3','5':'+3V3','3':'HW_KILL_N','4':None,'1':'SAFETY_FAULT_N','2':'GND'},note='CT intentionally open: 20 ms nominal reset delay; 3.07 V nominal monitor')
    s.component(h,'U803',h.name,360,65,{'5':'+3V3','2':'SAFETY_FAULT_N','1':None,'4':'SAFETY_CLEAR_N','3':'GND'},note='Schmitt edge conditioning for asynchronous clear')
    s.component(f,'U804',f.name,80,140,{'8':'+3V3','1':'SAFETY_ARM_REQUEST','2':'+3V3','6':'SAFETY_CLEAR_N','7':'+3V3','5':'HW_ACTUATOR_ENABLE','3':'HW_ACTUATOR_ENABLE_N','4':'GND'},note='Fresh rising edge after fault release; D=1, PRE inactive high')
    gate_nets={'20':'+3V3','1':'HW_ACTUATOR_ENABLE_N','19':'HW_ACTUATOR_ENABLE_N','10':'GND'}
    for i,(a,y) in enumerate(zip([2,4,6,8,11,13,15,17],[18,16,14,12,9,7,5,3]),1):
        gate_nets[str(a)]=f'IGN{i}';gate_nets[str(y)]=f'IGN{i}_GATED'
    s.component(g,'U805',g.name,220,140,gate_nets,note='Both OE default disabled; gated output pulldowns; source-level candidate')
    passive=[('R801','10k 1%','SAFETY_FAULT_N','+3V3'),('R802','10k 1%','HW_KILL_N','+3V3'),('R803','10k 1%','SAFETY_HEARTBEAT','GND'),('R804','10k 1%','SAFETY_ARM_REQUEST','GND'),('R805','10k 1%','HW_ACTUATOR_ENABLE_N','+3V3'),('R806','10k 1%','HW_ACTUATOR_ENABLE','GND')]
    passive += [(f'R{810+i}','10k 1%',f'IGN{i}','GND') for i in range(1,9)]
    passive += [(f'R{820+i}','10k 1%',f'IGN{i}_GATED','GND') for i in range(1,9)]
    passive += [(f'C{800+i}','100nF 25V X7R','+3V3','GND') for i in range(1,6)]
    passive += [('C806','120pF 50V C0G 1%','WD_CWD','GND')]
    for i,(ref,value,a,b) in enumerate(passive):
        x=75+(i%4)*135;y=205+(i//4)*20
        s.component(r if ref[0]=='R' else c,ref,value,x,y,{'1':a,'2':b})
    s.text('HW_KILL_N: local 3.3 V open-drain/contact-to-ground boundary only; no harness/12 V direct connection.\nNo independent max-dwell/current limiter exists yet. ARM timing and power-sequence fault injection remain required.\nIC decoupling capacitors C801..C805 must be placed at U801..U805 respectively.',20,370)
    s.write(HERE)
    # Standalone and integrated reference paths are both retained by KiCad.
    path=HERE/'safety_gate.kicad_sch';text=path.read_text()
    for part in s.parts:
        old=f'(project "Power8GDI_Core" (path "/{ROOT_UUID}/{s.sheet_id}" (reference "{part["ref"]}") (unit 1)))'
        extra=f'(project "safety_gate" (path "/{s.uuid}" (reference "{part["ref"]}") (unit 1)))'
        text=text.replace(old,old+' '+extra)
    path.write_text(text,newline='\n')
    (HERE/'safety_gate.kicad_pro').write_text('{}\n')
    lib='(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(x.body.replace('Power8GDI_Safety:','') for x in s.symbols.values())+'\n)\n'
    (HERE/'Power8GDI_Safety.kicad_sym').write_text(lib,newline='\n')
    (HERE/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Safety") (type "KiCad") (uri "${KIPRJMOD}/Power8GDI_Safety.kicad_sym") (options "") (descr "Project-authored safety candidate")))\n')
    (HERE/'parts.json').write_text(json.dumps(s.parts,indent=2)+'\n')
    with (HERE/'bom.csv').open('w',newline='') as stream:
        out=csv.DictWriter(stream,fieldnames=['ref','value','footprint','dnp','note']);out.writeheader()
        out.writerows({k:p[k] for k in out.fieldnames} for p in s.parts)
    nominal=77.4*.120+55
    contract={'schema_version':1,'release_status':'BLOCKED','sheet_file':'safety_gate.kicad_sch','sheet_uuid':s.uuid,'root_instance_uuid':s.sheet_id,'root_uuid':ROOT_UUID,'project':'Power8GDI_Core','power':'+3V3','ground':'GND','inputs':['SAFETY_HEARTBEAT','SAFETY_ARM_REQUEST','HW_KILL_N']+[f'IGN{i}' for i in range(1,9)],'outputs':['SAFETY_FAULT_N','HW_ACTUATOR_ENABLE','HW_ACTUATOR_ENABLE_N']+[f'IGN{i}_GATED' for i in range(1,9)],'pt_drven_connected':False,'watchdog_ms':{'nominal':nominal,'ideal_cap_min':nominal*.905,'ideal_cap_max':nominal*1.095,'with_cap_tolerance_min':(77.4*.120*.99+55)*.905,'with_cap_tolerance_max':(77.4*.120*1.01+55)*1.095,'capacitor_pf':120,'capacitor_tolerance_percent':1},'part_count':len(s.parts)}
    (HERE/'interface.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(json.dumps(contract,indent=2))

if __name__=='__main__':main()
