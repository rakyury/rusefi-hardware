"""Evidence-based aux circuits. CJ125/heater/package uncertainty stays explicit."""
from pathlib import Path
import csv,json
from schlib import Sheet,Symbol,box_symbol,uid

HERE=Path(__file__).resolve().parent
ROOT_UUID='f4d21065-0a5b-5086-a08e-1af9469f04bd'
PWR='+5V_CORE';IO='+3V3';GND='GND'
BUFFER_FP='Package_SO:TSSOP-14_4.4x5mm_P0.65mm'
FP={'R':'Resistor_SMD:R_0603_1608Metric','C':'Capacitor_SMD:C_0603_1608Metric','AHCT':'Package_SO:Texas_PW0020A_TSSOP-20_4.4x6.5mm_P0.65mm','LVC':'Package_TO_SOT_SMD:SOT-23-5','TPIC':'Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm','CJ':'Package_QFP:LQFP-32_7x7mm_P0.8mm','ADC':'Package_SO:SOIC-14_3.9x8.7mm_P1.27mm','OSC':'Power8GDI_Core:ASEM_3225'}

def ic(name,left,right,fp,prefix='U'):
    count=max(len(left),len(right));pins=[]
    for values,x,angle in [(left,-17.78,0),(right,17.78,180)]:
        pins += [(str(n),label,kind,x,(count-1)*1.27-i*2.54,angle) for i,(n,label,kind) in enumerate(values)]
    return box_symbol(name,pins,FP[fp],width=30.48,height=(count+1)*2.54,prefix=prefix)

R=box_symbol('R',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],FP['R'],width=5.08,height=2.54,prefix='R')
C=box_symbol('C',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],FP['C'],width=5.08,height=2.54,prefix='C')
C=Symbol('C',C.body.replace('(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0.254) (type default)) (fill (type background)))','(polyline (pts (xy -1.27 2.54) (xy -1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy 1.27 2.54) (xy 1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none)))').replace('(length 2.54)','(length 3.81)'),FP['C'])
AHCT=ic('SN74AHCT244QPWRQ1',[(20,'VCC','power_in'),(1,'~{1OE}','input'),(19,'~{2OE}','input')]+[(n,f'A{i+1}','input') for i,n in enumerate([2,4,6,8,11,13,15,17])],[(n,f'Y{i+1}','tri_state') for i,n in enumerate([18,16,14,12,9,7,5,3])]+[(10,'GND','power_in')],'AHCT')
LVC=ic('CLVC1G125QDBVRQ1',[(5,'VCC','power_in'),(1,'~{OE}','input'),(2,'A','input')],[(4,'Y','tri_state'),(3,'GND','power_in')],'LVC')

def passives(s,items,y=175):
    for i,item in enumerate(items):
        ref,value,a,b,*more=item
        s.component(R if ref.startswith('R') else C,ref,value,70+135*(i%4),y+22*(i//4),{'1':a,'2':b},note=more[0] if more else '',dnp=more[1] if len(more)>1 else False)

def sheet(name,title):
    s=Sheet(name,title,root=ROOT_UUID,paper='A2');s.text('ENGINEERING CANDIDATE — NOT MANUFACTURING OR ENGINE APPROVED',20,15,2);return s

def ahct_nets(channels,oe=GND):
    n={'20':PWR,'10':GND,'1':oe,'19':oe}
    for (a,y),(source,dest) in zip(zip([2,4,6,8,11,13,15,17],[18,16,14,12,9,7,5,3]),channels):n[str(a)]=source;n[str(y)]=dest
    return n

def knock():
    s=sheet('knock_dual','Two-input TPIC8101 and 3.3/5 V serial interface')
    s.text('SPI digital readout: multiplexed dual sensors, not simultaneous acquisition. MCU ADC pins are not used.\nOwn 8 MHz oscillator; no added load on MCU oscillator. Sensor gain/window/filter/calibration remain unqualified.',20,24)
    t=ic('TPIC8101DWR',[(1,'VDD','power_in'),(3,'Vref','power_out'),(20,'CH1P','input'),(19,'CH1N','input'),(18,'CH1FB','output'),(15,'CH2P','input'),(16,'CH2N','input'),(17,'CH2FB','output'),(9,'XIN','input')],[(2,'GND','power_in'),(4,'OUT','output'),(5,'NC','no_connect'),(6,'NC','no_connect'),(7,'INT/HOLD','input'),(8,'~{CS}','input'),(10,'XOUT','output'),(11,'SDO','tri_state'),(12,'SDI','input'),(13,'SCLK','input'),(14,'~{TEST}','input')],'TPIC')
    n={'1':PWR,'2':GND,'3':'KNOCK_VREF','4':None,'5':None,'6':None,'7':'KNOCK_INT_HOLD_5V','8':'KNOCK_CS_N_5V','9':'KNOCK_CLK_5V','10':None,'11':'KNOCK_SDO_5V','12':'AUX_SPI_MOSI_5V','13':'AUX_SPI_SCK_5V','14':None,'15':'KNOCK_VREF','16':'KNOCK2_INV','17':'KNOCK2_FB','18':'KNOCK1_FB','19':'KNOCK1_INV','20':'KNOCK_VREF'}
    s.component(t,'U1701','TPIC8101DWR',80,90,n,note='TI SLIS110C p3 exact pins; TEST open per datasheet, NC5/6 no traces; OUT unused digital-readout mode')
    channels=[('GDI_SPI2_MOSI','AUX_SPI_MOSI_5V'),('GDI_SPI2_SCK','AUX_SPI_SCK_5V'),('KNOCK_CS_N','KNOCK_CS_N_5V'),('KNOCK_INT_HOLD','KNOCK_INT_HOLD_5V'),('KNOCK_OSC_3V3','KNOCK_CLK_5V'),(GND,None),(GND,None),(GND,None)]
    s.component(AHCT,'U1702',AHCT.name,235,90,ahct_nets(channels),note='TTL VIH2V recognizes3.3V; five knock/SPI outputs used, unused inputs tied low. WBO now uses independent CAN nodes')
    s.component(LVC,'U1703',LVC.name,390,90,{'5':IO,'1':'KNOCK_CS_N','2':'KNOCK_SDO_5V','4':'GDI_SPI2_MISO','3':GND},note='CS disables return buffer; input5.5V tolerant; shared MISO arbitration required')
    osc=ic('ASEM1_8MHz',[(1,'EN','input'),(4,'VDD','power_in')],[(3,'OUT','output'),(2,'GND','power_in')],'OSC',prefix='Y')
    s.component(osc,'Y1701','ASEM1-8.000MHZ-LC-T',390,145,{'1':IO,'2':GND,'3':'KNOCK_OSC_3V3','4':IO},note='Own oscillator; manufacturer15pF load ceiling; temp−40..85C is a release constraint')
    items=[('C1701','4.7uF 16V X7R',PWR,GND),('C1702','100nF 25V X7R',PWR,GND),('C1703','100nF 25V X7R','KNOCK_VREF',GND),('C1704','100nF 25V X7R',PWR,GND),('C1705','100nF 25V X7R',IO,GND),('C1706','100nF 25V X7R',IO,GND)]
    for i in (1,2):
        b=1710+(i-1)*10
        items += [(f'C{b+1}','3.3nF 50V C0G',f'HARNESS_KNOCK{i}_SIG',f'KNOCK{i}_AC'),(f'R{b+1}','100k 1%',f'KNOCK{i}_AC',f'KNOCK{i}_INV'),(f'R{b+2}','100k 1%',f'KNOCK{i}_FB',f'KNOCK{i}_INV'),(f'R{b+3}','0R',f'HARNESS_KNOCK{i}_RETURN',GND,'Dedicated return routed to analogue ground entry; sensor cable/EMC review required')]
    items += [('R1701','10k 1%','KNOCK_CS_N',IO),('R1702','10k 1%','KNOCK_INT_HOLD',GND),('R1703','100k 1%','KNOCK_SDO_5V',GND)]
    passives(s,items,205)
    return s

def wideband(index):
    b=1700+index*100;prefix=f'WBO{index}_';net=lambda name:prefix+name
    s=sheet(f'wbo{index}_analog',f'LSU4.9 / CJ125 channel {index}: verified analogue subcircuits')
    s.text('CJ125 LQFP32 from Bosch public2019 product info; NOT historical SOIC24. IC DNP while VCCSS pin18 is unresolved.\nNo heater power MOSFET or supply protection is claimed here. H+/H− remain external power-stage boundaries.\nCJ125 VM is virtual ground; DO NOT join it to GND or to the other sensor VM.',20,24)
    pins=[(1,'NC','no_connect'),(2,'IA','bidirectional'),(3,'OSZ','passive'),(4,'DIAHG','input'),(5,'VCCS','power_in'),(6,'DIAHD','input'),(7,'~{RST}','input'),(8,'RS','bidirectional'),(9,'NC','no_connect'),(10,'RM','output'),(11,'CM','input'),(12,'UR','output'),(13,'SCK','input'),(14,'SO','tri_state'),(15,'SI','input'),(16,'NC','no_connect'),(17,'~{SS}','input'),(18,'VCCSS_UNRESOLVED','power_in'),(19,'VCC','power_in'),(20,'VM','output'),(21,'US','output'),(22,'UP','input'),(23,'UA','output'),(24,'NC','no_connect'),(25,'NC','no_connect'),(26,'CF','input'),(27,'RF','output'),(28,'GNDS','power_in'),(29,'GND','power_in'),(30,'UB','power_in'),(31,'UN','bidirectional'),(32,'IP','input')]
    sym=ic('CJ125_LQFP32_PUBLIC_MAP',pins[:16],pins[16:],'CJ')
    n={str(p):None for p in (1,9,16,24,25)}
    n.update({'2':net('IA'),'3':net('OSZ'),'4':net('HEATER_GATE_FEEDBACK'),'5':PWR,'6':net('DIAHD'),'7':'WBO_RESET_N_5V','8':net('RS'),'10':net('RM'),'11':net('CM'),'12':net('UR'),'13':'AUX_SPI_SCK_5V','14':net('SO_5V'),'15':'AUX_SPI_MOSI_5V','17':net('CS_N_5V'),'18':net('VCCSS_UNRESOLVED'),'19':PWR,'20':net('VM'),'21':net('US'),'22':net('UP'),'23':net('UA'),'26':net('CF'),'27':net('RF'),'28':GND,'29':GND,'30':net('UB_9V_TO_18V'),'31':net('UN_FILTERED'),'32':net('IP')})
    s.component(sym,f'U{b+1}','CJ125 LQFP32 (ordering code unresolved)',90,100,n,dnp=True,note='DNP until Bosch full datasheet VCCSS, ordering code, package land pattern and operating/SPI limits reviewed')
    s.component(LVC,f'U{b+2}',LVC.name,265,100,{'5':IO,'1':net('CS_N'),'2':net('SO_5V'),'4':'GDI_SPI2_MISO','3':GND},note='5V->3.3V return candidate; disabled on CS high; CJ125 output levels/timing still require full datasheet')
    # Bosch application network; UN series R/post-filter C are project candidates
    # because the public raster drawing does not specify their values.
    items=[(f'R{b+1}','61.9R 0.1%',net('IP'),net('IA'),'Pump current shunt from Bosch proposal; calibration/grade required'),(f'R{b+2}','470k 1%',net('IA'),net('UP')),(f'R{b+3}','4.7k 1%',net('US'),net('UP')),(f'R{b+4}','301R 0.1%',net('RS'),net('VM'),'LSU4.9 Ri calibration resistor, not LSU4.2 82.5R'),(f'R{b+5}','100R 1%',net('UN_RAW'),net('UN_FILTERED'),'Candidate value: public Bosch drawing shows series resistor without readable value'),(f'C{b+1}','100nF 25V X7R',net('UN_FILTERED'),GND,'Candidate value: public Bosch drawing shows post-filter capacitor without readable value'),(f'C{b+2}','2.2nF 25V C0G',net('UN_RAW'),GND,'Bosch raster label2,2n; return is GND, not VM'),(f'R{b+11}','100k 1%',net('UN_RAW'),net('UP'),'Bosch leakage-detection resistor'),(f'R{b+6}','31.6k 1%',net('RM'),net('RM_AC')),(f'C{b+3}','100nF 25V X7R',net('RM_AC'),net('CM')),(f'R{b+7}','100k 1%',net('RF'),net('CF')),(f'C{b+4}','100nF 25V X7R',net('CF'),GND),(f'C{b+5}','33nF 25V X7R',net('UA'),GND),(f'C{b+6}','33nF 25V X7R',net('UR'),GND),(f'R{b+8}','10k 1%',net('OSZ'),GND),(f'R{b+9}','6.8k 1%',net('DIAHD'),net('HEATER_NEG')),(f'C{b+7}','33nF 25V X7R',PWR,GND),(f'C{b+8}','33nF 50V X7R',net('UB_9V_TO_18V'),GND),(f'C{b+9}','1nF 25V C0G','WBO_RESET_N_5V',GND),(f'C{b+10}','100nF 25V X7R',IO,GND),(f'R{b+10}','100k 1%',net('SO_5V'),GND)]
    # Explicit zero-ohm harness adaptation, with sensor connector semantics from Bosch.
    for pin,target in enumerate(['IP','VM','HEATER_NEG','HEATER_POS','IA','UN_RAW'],1):
        items.append((f'R{b+20+pin}','0R',f'HARNESS_WBO{index}_CONTACT{pin}',net(target),'Bosch LSU4.9 automotive connector mapping; project harness pin numbering must be reviewed',pin in (3,4)))
    passives(s,items,190)
    s.text('VCCSS and heater feeds are deliberate unresolved nets. H+ and H− harness links R'+str(b+23)+'/'+str(b+24)+' remain DNP.\nPad numbers match the public drawing; the generic LQFP32 footprint geometry is only a candidate pending Bosch package detail.',20,365)
    return s

def adc_and_heater_logic():
    s=sheet('wbo_adc_control','Four-channel WBO ADC and inhibited heater control boundaries')
    s.text('MCP3204 reads UA1/UR1/UA2/UR2. No MCU analog pin required. Shared SPI requires per-device clock/mode arbitration.\nADC temperature grade−40..85C is an explicit release blocker. Heater DRIVE is logic only; power stages remain absent.',20,24)
    adc=ic('MCP3204T_BI_SL',[(1,'CH0','input'),(2,'CH1','input'),(3,'CH2','input'),(4,'CH3','input'),(5,'NC','no_connect'),(6,'NC','no_connect'),(7,'DGND','power_in')],[(14,'VDD','power_in'),(13,'VREF','power_in'),(12,'AGND','power_in'),(11,'CLK','input'),(10,'DOUT','tri_state'),(9,'DIN','input'),(8,'~{CS}','input')],'ADC')
    adc_nets={'1':'WBO1_UA_ADC','2':'WBO1_UR_ADC','3':'WBO2_UA_ADC','4':'WBO2_UR_ADC','5':None,'6':None,'7':GND,'8':'WBO_ADC_CS_N','9':'GDI_SPI2_MOSI','10':'GDI_SPI2_MISO','11':'GDI_SPI2_SCK','12':GND,'13':IO,'14':IO}
    s.component(adc,'U2001','MCP3204T-BI/SL',90,95,adc_nets,note='DS21298E pin map, four12-bit inputs; candidate ≤500kHz clock; SAR source settling/calibration must be measured')
    channels=[('WBO1_HEATER_PWM','WBO1_HEATER_GATE_DRIVE'),(GND,None),(GND,None),(GND,None),('WBO2_HEATER_PWM','WBO2_HEATER_GATE_DRIVE'),(GND,None),(GND,None),(GND,None)]
    s.component(AHCT,'U2002',AHCT.name,265,95,ahct_nets(channels,'HW_ACTUATOR_ENABLE_N'),note='Both banks disabled when hardware latch off; outputs have pull-down. No power MOSFET included')
    FP['BUFFER']=BUFFER_FP
    buf=ic('TLV9004QPWRQ1',[(4,'V+','power_in'),(3,'IN1+','input'),(2,'IN1-','input'),(5,'IN2+','input'),(6,'IN2-','input'),(10,'IN3+','input'),(9,'IN3-','input'),(12,'IN4+','input'),(13,'IN4-','input')],[(1,'OUT1','output'),(7,'OUT2','output'),(8,'OUT3','output'),(14,'OUT4','output'),(11,'V-','power_in')],'BUFFER')
    bn={'4':PWR,'11':GND}
    for raw,positive,negative,output in zip(['WBO1_UA','WBO1_UR','WBO2_UA','WBO2_UR'],[3,5,10,12],[2,6,9,13],[1,7,8,14]):
        bn[str(positive)]=raw;bn[str(negative)]=raw+'_BUFFERED';bn[str(output)]=raw+'_BUFFERED'
    s.component(buf,'U2003',buf.name,445,95,bn,note='Unity buffers: CJ125 UA specified at <10uA load; divider must not directly load CJ outputs. 10k isolates100nF load')
    items=[('C2001','100nF 25V X7R',IO,GND),('C2002','1uF 16V X7R',IO,GND),('C2003','100nF 25V X7R',PWR,GND),('R2001','10k 1%','WBO_ADC_CS_N',IO),('R2002','10k 1%','HW_ACTUATOR_ENABLE_N',IO),('R2003','10k 1%','WBO1_HEATER_PWM',GND),('R2004','10k 1%','WBO2_HEATER_PWM',GND),('R2005','10k 1%','WBO1_HEATER_GATE_DRIVE',GND),('R2006','10k 1%','WBO2_HEATER_GATE_DRIVE',GND)]
    items.append(('C2004','100nF 25V X7R',PWR,GND))
    for i,raw in enumerate(['WBO1_UA','WBO1_UR','WBO2_UA','WBO2_UR']):
        items += [(f'R{2010+2*i}','10k 0.1%',raw+'_BUFFERED',raw+'_ADC'),(f'R{2011+2*i}','15k 0.1%',raw+'_ADC',GND),(f'C{2010+i}','100nF 25V X7R',raw+'_ADC',GND)]
    passives(s,items,180)
    return s

def main():
    sheets=[knock()];parts=[];symbols={}
    for s in sheets:
        s.write(HERE);p=HERE/(s.name+'.kicad_sch');text=p.read_text()
        for part in s.parts:
            old=f'(project "Power8GDI_Core" (path "/{ROOT_UUID}/{s.sheet_id}" (reference "{part["ref"]}") (unit 1)))'
            text=text.replace(old,old+f' (project "{s.name}" (path "/{s.uuid}" (reference "{part["ref"]}") (unit 1)))')
        p.write_text(text,newline='\n');(HERE/(s.name+'.kicad_pro')).write_text('{}\n')
        parts.extend(s.parts);symbols.update(s.symbols)
    (HERE/'Power8GDI_Aux.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(x.body.replace('Power8GDI_Aux:','') for x in symbols.values())+'\n)\n',newline='\n')
    (HERE/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_Aux") (type "KiCad") (uri "${KIPRJMOD}/Power8GDI_Aux.kicad_sym") (options "") (descr "Primary-source aux candidate")))\n')
    (HERE/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "Power8GDI_Core") (type "KiCad") (uri "${KIPRJMOD}/../Power8GDI_Core.pretty") (options "") (descr "Project oscillator land pattern")))\n')
    (HERE/'parts.json').write_text(json.dumps(parts,indent=2)+'\n')
    with (HERE/'bom.csv').open('w',newline='',encoding='utf-8') as f:
        out=csv.DictWriter(f,fieldnames=['ref','value','footprint','dnp','note','sheet']);out.writeheader();out.writerows({k:p[k] for k in out.fieldnames} for p in parts)
    manifest={'schema_version':1,'root_uuid':ROOT_UUID,'project':'Power8GDI_Core',
        'release_status':'BLOCKED',
        'sheets':[{'name':s.name,'sheet_uuid':s.uuid,'root_instance_uuid':s.sheet_id,'components':len(s.parts)} for s in sheets],
        'gpio':['KNOCK_CS_N','KNOCK_INT_HOLD'],
        'shared_spi':['GDI_SPI2_SCK','GDI_SPI2_MOSI','GDI_SPI2_MISO'],
        'mcu_adc_required':0,'part_count':len(parts),
        'blockers':['Sensor calibration and SPI scheduling untested','Oscillator temperature ceiling85C','Physical and EMC qualification pending'],
        'superseded_sheets':['wbo1_analog','wbo2_analog','wbo_adc_control'],
        'replacement':'../wbo/interface.json'}
    (HERE/'interface.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
