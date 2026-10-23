"""Deterministic real logic supply replacement. Manufacturer basis in README.md."""
from pathlib import Path
import json, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from core_schlib import Sheet, box_symbol, uid, parse, children, child, dump
LIB='Power8GDI_LogicPower'
ROOT=uid('Power8GDI_Core')
RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0805_2012Metric'
BIGC='Capacitor_SMD:C_1210_3225Metric'
LMFP='Package_DFN_QFN:Texas_RNP0030B_WQFN-30-1EP_4x6mm_P0.5mm_EP1.8x4.5mm'
TPSFP='Package_DFN_QFN:VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm'
def passive(name,fp,prefix):
    return box_symbol(name,[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],fp,width=5.08,height=2.54,prefix=prefix)
def ic(name,pins,fp):
    half=(len(pins)+1)//2; out=[]
    for i,(n,label,kind) in enumerate(pins):
        side=i//half; j=i%half
        out.append((str(n),label,kind,-25.4 if side==0 else 25.4,(half-1)*2.54-j*5.08,0 if side==0 else 180))
    return box_symbol(name,out,fp,width=45.72,height=(half+1)*5.08)
R=passive('PWR_R',RFP,'R'); C=passive('PWR_C',CFP,'C'); L=passive('PWR_L','Inductor_SMD:L_Coilcraft_XAL7070-XXX','L')
TVS=passive('PWR_TVS_BIDIR','Diode_SMD:D_SMB','D')
D=ic('STPS5H100BY',[(1,'NC','no_connect'),(2,'K_TAB','passive'),(3,'A','passive')],'Package_TO_SOT_SMD:TO-252-2')
LM=ic('LM76003QRNPRQ1',[(n,label,kind) for n,label,kind in [
(1,'SW1','power_out'),(2,'SW2','passive'),(3,'SW3','passive'),(4,'SW4','passive'),(5,'SW5','passive'),(6,'BOOT','passive'),(7,'NC_GND','passive'),(8,'VCC','power_out'),(9,'BIAS','power_in'),(10,'RT','passive'),(11,'SS','passive'),(12,'FB','input'),(13,'AGND1','power_in'),(14,'AGND2','passive'),(15,'AGND3','passive'),(16,'PGOOD','open_collector'),(17,'SYNC_MODE','input'),(18,'EN','input'),(19,'NC_GND','passive'),(20,'PVIN1','power_in'),(21,'PVIN2','passive'),(22,'PVIN3','passive'),(23,'NC_GND','passive'),(24,'PGND1','power_in'),(25,'PGND2','passive'),(26,'PGND3','passive'),(27,'NC_GND','passive'),(28,'NC_GND','passive'),(29,'NC_GND','passive'),(30,'NC_GND','passive'),(31,'DAP_GND','power_in')]],LMFP)
TPS=ic('TPS62130AQRGTRQ1',[(1,'SW1','power_out'),(2,'SW2','passive'),(3,'SW3','passive'),(4,'PG','open_collector'),(5,'FB','input'),(6,'AGND','power_in'),(7,'FSW','input'),(8,'DEF','input'),(9,'SS_TR','passive'),(10,'AVIN','power_in'),(11,'PVIN1','power_in'),(12,'PVIN2','passive'),(13,'EN','input'),(14,'VOS','input'),(15,'PGND1','power_in'),(16,'PGND2','passive'),(17,'EP_GND','power_in')],TPSFP)

def main():
    parts=[]; sheets=[]; symbols={}
    def finish(s):
        for index,item in enumerate(s.items):
            if not item.startswith('(symbol '): continue
            expr=parse(item); at=child(expr,'at'); x,y=float(at[1]),float(at[2])
            sym=s.symbols[str(child(expr,'lib_id')[1]).split(':')[-1]]
            offset=max(abs(p['y']) for p in sym.pins.values())+7.62
            for prop in children(expr,'property'):
                if prop[1] not in ('Reference','Value'): continue
                child(prop,'at')[1:3]=[str(x),str(y+(offset if prop[1]=='Value' else -offset))]
                effects=child(prop,'effects'); effects[:]=[v for v in effects if not(isinstance(v,list) and v[0]=='justify')]
            s.items[index]=dump(expr)
        s.write(HERE.parent)
        path=HERE.parent/(s.name+'.kicad_sch'); text=path.read_text(encoding='utf8').replace('Power8GDI_Core:',LIB+':')
        for p in s.parts:
            old=f'(project "Power8GDI_Core" (path "/{ROOT}/{s.sheet_id}" (reference "{p["ref"]}") (unit 1)))'
            extra=f'(project "{Path(s.name).name}" (path "/{s.uuid}" (reference "{p["ref"]}") (unit 1)))'
            text=text.replace(old,old+' '+extra)
        path.write_text(text,encoding='utf8',newline='\n'); path.with_suffix('.kicad_pro').write_text('{}\n')
        parts.extend(s.parts); symbols.update(s.symbols)
        sheets.append({'name':s.name,'sheet_uuid':s.uuid,'root_instance_uuid':s.sheet_id,'parts':len(s.parts)})
    def put(s,sym,ref,val,x,y,nets,note='',fp=None):
        s.component(sym,ref,val,x,y,{str(k):v for k,v in nets.items()},note=note,footprint=fp)
    s=Sheet('logic_power/logic_5v','Protected logic input and 5V / 2A design envelope',root=ROOT,paper='A2')
    s.text('LOGIC 5V: replaces the complete old power_input sheet. Keep externally fused main battery input.',20,15,2)
    s.text('Protected battery also feeds two sensor trackers and LIN VSUP. Their current bypasses the 5V buck.',20,25)
    put(s,D,'D5200','STPS5H100BY-TR',85,65,{1:None,2:'VBAT_LOGIC_PROTECTED',3:'VBAT_MAIN_FUSED'},'100V 5A DPAK automotive diode; pin1 NC, pin2/tab cathode, pin3 anode. 5A is not a PCB current rating.')
    put(s,TVS,'D5201','SMBJ24CA',290,65,{1:'VBAT_MAIN_FUSED',2:'GND'},'Inherited 24V standoff / 38.9V rated-clamp candidate. Dynamic clamp, pulse energy and fuse coordination remain unqualified.')
    nets={n:'GND' for n in range(1,32)}
    nets.update({n:'LP5_SW' for n in range(1,6)})
    nets.update({6:'LP5_BOOT',8:'LP5_VCC',9:'+5V_CORE',10:None,11:'LP5_SS',12:'LP5_FB',16:'LP5_PG_RAW',18:'LP5_EN',20:'VBAT_LOGIC_PROTECTED',21:'VBAT_LOGIC_PROTECTED',22:'VBAT_LOGIC_PROTECTED'})
    put(s,LM,'U5200','LM76003QRNPRQ1',170,165,nets,'TI SNVSAU3B pin table. RT open => 500kHz. MODE low => auto PFM/PWM. NC pads intentionally GND per datasheet. 3.5A silicon; 2A target load.')
    put(s,L,'L5200','XAL7070-682MEC 6.8uH',420,110,{1:'LP5_SW',2:'+5V_CORE'},'Coilcraft: 12.8A typical 30% Isat at25C, 19.62mOhm max DCR. Hot saturation/core loss require verification.')
    passives=[
      (C,'C5200','10u 100V X7R','VBAT_LOGIC_PROTECTED','GND',BIGC,'Input ceramics: combined effective >=10uF over qualified input range.'),
      (C,'C5201','10u 100V X7R','VBAT_LOGIC_PROTECTED','GND',BIGC,'Adjacent PVIN/PGND, compact hot loop.'),
      (C,'C5202','47n 100V X7R','VBAT_LOGIC_PROTECTED','GND',CFP,'High frequency bypass at PVIN/PGND.'),
      (C,'C5203','470n 25V X7R','LP5_BOOT','LP5_SW',CFP,'Bootstrap capacitor MUST connect BOOT to SW, not GND.'),
      (C,'C5204','2.2u 16V X7R','LP5_VCC','GND',CFP,'Internal VCC bypass; do not export VCC or parallel +3V3.'),
      (C,'C5205','1u 16V X7R','+5V_CORE','GND',CFP,'BIAS bypass adjacent pin9.'),
      (C,'C5206','22n 16V X7R','LP5_SS','GND',CFP,'Nominal 11ms external soft start at2uA; verify rise under full load.'),
      (R,'R5200','100k 0.1%','+5V_CORE','LP5_FB',RFP,'Top feedback. 1.006V typical reference =>5.03V nominal.'),
      (R,'R5201','25k 0.1%','LP5_FB','GND',RFP,'Bottom feedback; quiet Kelvin return to AGND.'),
      (C,'C5207','180p 50V C0G','+5V_CORE','LP5_FB',CFP,'Feedforward starting value for approx156uF effective load; loop validation required.'),
      (R,'R5202','470k 0.1%','VBAT_LOGIC_PROTECTED','LP5_EN','Resistor_SMD:R_0805_2012Metric','EN upper divider; voltage-rated resistor. Nominal rising6.86V atprotected input.'),
      (R,'R5203','100k 0.1%','LP5_EN','GND',RFP,'Default low enable; 150mV typical comparator hysteresis.'),
      (R,'R5204','100k 1%','+5V_CORE','LP5_PG_RAW',RFP,'PG pullup uses upstream5V, never3V3, avoiding sequencing deadlock. Sink <=51uA.'),
      (R,'R5205','1M 1%','LP5_PG_RAW','GND',RFP,'TPS enable fallback; allows nominal4.57V high. EN input <=1uA leakage.'),
    ]
    for i in range(4):
        passives.append((C,f'C{5208+i}','47u 25V X7R','+5V_CORE','GND',BIGC,'4 output ceramics nominal188uF. Require >=100uF effective locally including tolerance/DC bias/temperature.'))
    for i,(sym,ref,val,a,b,fp,note) in enumerate(passives):
        put(s,sym,ref,val,65+(i%4)*135,265+(i//4)*27,{1:a,2:b},note,fp)
    s.text('Input range is conditional: nominal EN rise6.86V atprotected rail; cold crank below this turns rails off.',20,395)
    s.text('No ISO7637/load dump qualification; no independent overvoltage disconnect on sensor/LIN battery rail.',20,404)
    finish(s)
    s=Sheet('logic_power/logic_3v3','Sequenced 3V3 / 1A design envelope',root=ROOT,paper='A3')
    s.text('3V3: REPLACE old core_power/TLV1117 sheet; never populate both sources in parallel.',20,15,2)
    s.text('5V PGOOD directly enables TPS62130A. 3V3 PG is optional diagnostic; existing supervisor remains authoritative.',20,25)
    nets={1:'LP33_SW',2:'LP33_SW',3:'LP33_SW',4:'PGOOD_3V3_CORE',5:'LP33_FB',6:'GND',7:'+5V_CORE',8:'GND',9:'LP33_SS',10:'+5V_CORE',11:'+5V_CORE',12:'+5V_CORE',13:'LP5_PG_RAW',14:'+3V3',15:'GND',16:'GND',17:'GND'}
    put(s,TPS,'U5300','TPS62130AQRGTRQ1',150,100,nets,'TI SLVSCC2E: adjustable variant; FSW HIGH selects1.25MHz, DEF LOW nominal voltage. VOS senses output directly; not FB.')
    put(s,L,'L5300','XAL5030-222MEC 2.2uH',330,75,{1:'LP33_SW',2:'+3V3'},'Coilcraft 9.2A typical30% Isat at25C,14.5mOhm maxDCR. Hot/coreloss validation remains.','Inductor_SMD:L_Coilcraft_XAL5030-XXX')
    passives=[
      (C,'C5300','10u 25V X7R','+5V_CORE','GND',CFP,'PVIN input bypass; require >=5uF effective at5V.'),
      (C,'C5301','100n 25V X7R','+5V_CORE','GND',CFP,'AVIN local bypass with quiet return.'),
      (C,'C5302','22u 16V X7R','+3V3','GND',BIGC,'Nominal22uF output; require >=10uF effective. Include core decoupling in loop review.'),
      (C,'C5303','3.3n 25V C0G','LP33_SS','GND',CFP,'Typical1.65ms soft start; actual ramp under load to verify.'),
      (R,'R5300','100k 0.1%','+3V3','LP33_FB',RFP,'Topfeedback. 0.8*(1+100/32)=3.300V nominal.'),
      (R,'R5301','32k 0.1%','LP33_FB','GND',RFP,'Bottomfeedback. Max100nA FB leakage contributes <=10mV output error.'),
      (R,'R5302','100k 1%','+3V3','PGOOD_3V3_CORE',RFP,'Diagnostic pullup only; not connected to safety fault bus without review.'),
      (R,'R5303','10k 1%','+3V3','GND',RFP,'Passive bleed; does not guarantee discharge time with external backfeed.'),
    ]
    for i,(sym,ref,val,a,b,fp,note) in enumerate(passives):
        put(s,sym,ref,val,65+(i%3)*135,180+(i//3)*32,{1:a,2:b},note,fp)
    s.text('Target1A is a design allocation, not thermal qualification. 3V3 short removes5V if buck protection propagates.',20,275)
    finish(s)
    (HERE/(LIB+'.kicad_sym')).write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(x.body.replace('Power8GDI_Core:','') for x in symbols.values())+'\n)\n',encoding='utf8')
    (HERE/'sym-lib-table').write_text(f'(sym_lib_table (version 7) (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.kicad_sym")(options "")(descr "Verified logic regulator pinmaps")))\n')
    (HERE/'parts.json').write_text(json.dumps(parts,indent=2)+'\n')
    contract={'schema_version':1,'root_uuid':ROOT,'qualification':'ENGINEERING_CANDIDATE_UNMEASURED','sheets':sheets,'remove_root_sheets':['power_input/power_input','core_power'],'required_absent_refs':['U102','C125','C126','U501','D501','D502'],'inputs':['VBAT_MAIN_FUSED','GND'],'outputs':['VBAT_LOGIC_PROTECTED','+5V_CORE','+3V3'],'internal_cross_sheet':['LP5_PG_RAW'],'optional_diagnostic':['PGOOD_3V3_CORE'],'removed_unused_diagnostic':['PGOOD_5V_CORE'],'rail_targets_A':{'+5V_CORE':2.0,'+3V3':1.0},'thermal_qualified':False}
    (HERE/'interface.json').write_text(json.dumps(contract,indent=2)+'\n')
    print(f'Generated {len(parts)} parts / {len(sheets)} sheets')
if __name__=='__main__': main()
