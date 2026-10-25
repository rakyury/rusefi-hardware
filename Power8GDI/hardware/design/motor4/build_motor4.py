"""Four TLE9201 channels and two protected feeds; manufacturer evidence in README.

Uses the repository's deterministic drawing helper, but a separate symbol library.
No ERC exclusions or fictitious power flags. This is an engineering candidate.
"""
from pathlib import Path
import csv, json, sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'interfaces_aux'))
from schlib import Sheet, Symbol, box_symbol, parse, dump, child, children
ROOT='f4d21065-0a5b-5086-a08e-1af9469f04bd'
LIB='Power8GDI_Motor4'
RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0805_2012Metric'
TLEFP='Package_SO:Infineon_PG-DSO-12-11_ThermalVias'

def ic(name,left,right,fp,prefix='U'):
    n=max(len(left),len(right));pins=[]
    for items,x,a in [(left,-20.32,0),(right,20.32,180)]:
        pins += [(str(p),label,t,x,(n-1)*2.54-i*5.08,a) for i,(p,label,t) in enumerate(items)]
    return box_symbol(name,pins,fp,width=35.56,height=(n+1)*5.08,prefix=prefix)

R=box_symbol('Motor_R',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],RFP,width=5.08,height=2.54,prefix='R')
C=box_symbol('Motor_C',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],CFP,width=5.08,height=2.54,prefix='C')
C=Symbol(C.name,C.body.replace('(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0.254) (type default)) (fill (type background)))','(polyline (pts (xy -1.27 2.54) (xy -1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy 1.27 2.54) (xy 1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none)))').replace('(length 2.54)','(length 3.81)'),CFP)
TVS=box_symbol('Motor_TVS_BIDIR',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],'Diode_SMD:D_SMC',width=5.08,height=5.08,prefix='D')

def build():
    sheets=[];parts=[];symbols={}
    def finish(s):
        for i,item in enumerate(s.items):
            if not item.startswith('(symbol '):continue
            e=parse(item);at=child(e,'at');x,y=map(float,at[1:3]);sym=s.symbols[str(child(e,'lib_id')[1]).split(':')[-1]]
            offset=max(abs(p['y']) for p in sym.pins.values())+7.62
            for p in children(e,'property'):
                if p[1] not in ('Reference','Value'):continue
                child(p,'at')[1:3]=[str(x),str(y+(offset if p[1]=='Value' else -offset))]
                ef=child(p,'effects');ef[:]=[v for v in ef if not(isinstance(v,list) and v[0]=='justify')]
            s.items[i]=dump(e)
        s.write(HERE.parent);path=HERE.parent/(s.name+'.kicad_sch')
        txt=path.read_text().replace('Power8GDI_Aux:',LIB+':')
        for p in s.parts:
            old=f'(project "Power8GDI_Core" (path "/{ROOT}/{s.sheet_id}" (reference "{p["ref"]}") (unit 1)))'
            txt=txt.replace(old,old+f' (project "{Path(s.name).name}" (path "/{s.uuid}" (reference "{p["ref"]}") (unit 1)))')
        path.write_text(txt,encoding='utf-8',newline='\n');path.with_suffix('.kicad_pro').write_text('{}\n')
        sheets.append({'name':s.name,'uuid':s.uuid,'sheet_id':s.sheet_id,'components':len(s.parts)})
        parts.extend(s.parts);symbols.update(s.symbols)

    tle=ic('TLE9201SG',[(1,'DIR','input'),(12,'PWM','input'),(11,'DIS','input'),(9,'CSN','input'),(10,'SCK','input'),(8,'SI','input'),(2,'VSO','power_in')],[(5,'OUT1','passive'),(7,'OUT2','passive'),(4,'VS','power_in'),(3,'SO','tri_state'),(6,'GND','power_in'),(13,'EP_GND','power_in')],TLEFP)
    orgate=ic('SN74LVC1G32_Q1',[(1,'A','input'),(2,'B','input'),(3,'GND','power_in')],[(5,'VCC','power_in'),(4,'Y','output')],'Package_TO_SOT_SMD:SOT-23-5')
    buf=ic('SN74LVC1G125_Q1',[(1,'~{OE}','input'),(2,'A','input'),(3,'GND','power_in')],[(5,'VCC','power_in'),(4,'Y','tri_state')],'Package_TO_SOT_SMD:SOT-23-5')
    channels=[('DBW',6000,'MOTOR13','PC6','PI2','PD13'),('EWG',6050,'MOTOR24','PC8','PD14','PD15')]
    for index,(ch,base,feed,pwm,dr,dis) in enumerate(channels):
        s=Sheet('motor4/'+ch.lower(),ch+': TLE9201 motor bridge',root=ROOT,paper='A2')
        pre=ch+'_'; rail=feed+'_VS'; inp='MOTOR_SPI_SI' if index==0 else channels[index-1][0]+'_SPI_SO'
        s.text(ch+': direct timer PWM / DIR / default-off DIS; 2A continuous DESIGN TARGET ONLY',20,15,2)
        s.text('VS from dedicated protected motor feed; VSO=+3V3 logic. PWM=0 does not disconnect both motor terminals.',20,24)
        s.component(tle,f'U{base}', 'TLE9201SG',280,93,{'1':pre+'DIR_FILTERED','2':'+3V3','3':pre+'SPI_SO','4':rail,'5':pre+'MOTOR_A','6':'GND','7':pre+'MOTOR_B','8':inp,'9':'MOTOR_CS_N','10':'MOTOR_SPI_SCK','11':pre+'DIS_GATED','12':pre+'PWM_FILTERED','13':'GND'},note='Infineon Rev1.0 p4: pin13 here denotes exposed ground slug. PG-DSO-12-17 dimensions checked against KiCad PG-DSO-12-11 land pattern; see checks.')
        s.component(orgate,f'U{base+1}','SN74LVC1G32QDBVRQ1',90,93,{'1':'HW_ACTUATOR_ENABLE_N','2':pre+'DISABLE','3':'GND','4':pre+'DIS_GATED','5':'+3V3'},note='High means DISABLE. Either global latch or per-channel command forces both bridge outputs off; reset defaults are high.')
        entries=[('R',0,'100R',pre+'PWM',pre+'PWM_FILTERED',None),('R',1,'100R',pre+'DIR',pre+'DIR_FILTERED',None),('R',2,'10k',pre+'PWM_FILTERED','GND',None),('R',3,'10k',pre+'DIR_FILTERED','GND',None),('R',4,'10k',pre+'DISABLE','+3V3',None),('R',5,'10k',pre+'DIS_GATED','+3V3',None),('C',0,'100n 25V X7R','+3V3','GND',None),('C',1,'100n 25V X7R','+3V3','GND',None),('C',2,'100n 50V X7R',rail,'GND',None),('C',3,'1u 50V X7R',rail,'GND','Capacitor_SMD:C_1206_3216Metric'),('C',4,'100u 50V low ESR',rail,'GND','Capacitor_SMD:CP_Elec_10x10.5'),('C',5,'1n 100V C0G',pre+'MOTOR_A','GND',None),('C',6,'1n 100V C0G',pre+'MOTOR_B','GND',None)]
        for k,(kind,n,val,a,b,fp) in enumerate(entries):
            note='Bulk capacitor exact MPN, cold ESR/ripple and height not qualified.' if kind=='C' and n==4 else 'Place output EMI capacitor at IC; Infineon application limit <33nF.' if kind=='C' and n in(5,6) else ''
            s.component(R if kind=='R' else C,f'{kind}{base+n}',val,80+135*(k%4),185+38*(k//4),{'1':a,'2':b},footprint=fp,note=note)
        s.component(TVS,f'D{base}','SMCJ18CA',485,93,{'1':rail,'2':'GND'},note='18V standoff, 29.2V rated pulse clamp; input OV disconnect limits normal supply. Local regeneration/overshoot may exceed28V operating limit but must stay below40V ABSMAX. Energy/hot clamp not qualified.')
        s.text('Place VS bypass and TVS close to pins4/6; EP13 solid GND with thermal vias. Power returns avoid sensor ground necks.',20,355)
        s.text('Current chopping6..10A is NOT a precise operating current limit; no current ADC. Stall timeout and position plausibility required.',20,364)
        s.text('Both PWM pins share TIM3 frequency. Use <=20kHz; begin bench bring-up at2kHz and validate final switching/EMI losses.',20,373)
        finish(s)

    s=Sheet('motor4/spi', 'Motor daisy chain and shared SPI isolation',root=ROOT,paper='A3')
    s.text('Shared SPI2: MOSI -> DBW -> EWG -> gated MISO',20,15,1.5)
    s.component(buf,'U6190','SN74LVC1G125QDBVRQ1',200,70,{'1':'MOTOR_CS_N','2':'EWG_SPI_SO','3':'GND','4':'MOTOR_MISO_BUFFERED','5':'+3V3'},note='Extra explicit MISO isolation. TLE SO is tri-state at CSN high; asynchronous fault flag exists while CSN low before first clock, per Infineon4.12.1.')
    entries=[('R6190','47R','GDI_SPI2_MOSI','MOTOR_SPI_SI'),('R6191','47R','GDI_SPI2_SCK','MOTOR_SPI_SCK'),('R6192','47R','MOTOR_MISO_BUFFERED','GDI_SPI2_MISO'),('R6193','10k','MOTOR_CS_N','+3V3'),('R6194','10k','HW_ACTUATOR_ENABLE_N','+3V3'),('R6195','100k','EWG_SPI_SO','GND'),('C6190','100n 25V X7R','+3V3','GND')]
    for k,(ref,val,a,b) in enumerate(entries):s.component(R if ref[0]=='R' else C,ref,val,75+130*(k%3),140+30*(k//3),{'1':a,'2':b})
    s.text('Mode1, MSB-first, <=1MHz initial configuration, 16 clocks per CS pulse; hold CS high >=2us between frames.',20,250)
    s.text('Send bytes EWG,DBW. Receive previous-frame replies in the same order. SIN bit must remain0.',20,258)
    s.text('Serialize with PT2001 transactions. Keep all other CS high; change SPI mode/rate only with every CS high.',20,266)
    finish(s)

    controller=ic('LM74800QDRRRQ1',[(1,'DGATE','output'),(2,'A','input'),(3,'VSNS','input'),(4,'SW','passive'),(5,'OV','input'),(6,'EN/UVLO','input')],[(12,'C','input'),(11,'CAP','output'),(10,'VS','power_in'),(9,'OUT','input'),(8,'HGATE','output'),(7,'GND','power_in'),(13,'EP_FLOAT','no_connect')],LIB+':LM74800_DRR0012E')
    fet=ic('IPD90N10S4_06',[(1,'G','input')],[(2,'D_TAB','passive'),(3,'S','passive')],'Package_TO_SOT_SMD:TO-252-2','Q')
    for feed,base,raw in [('MOTOR13',6200,'VBAT_DBW_FUSED'),('MOTOR24',6250,'VBAT_EWG_FUSED')]:
        s=Sheet('motor4/'+feed.lower()+'_power',feed+': independent protected feed',root=ROOT,paper='A2')
        p=feed+'_';mid=p+'MID';rail=p+'VS';dg=p+'DGATE';hg=p+'HGATE';cap=p+'CAP';ov=p+'OV';sw=p+'SW';en=p+'POWER_EN'
        s.text(feed+': one motor channel per externally fused connector feed; 2A continuous DESIGN TARGET',20,15,2)
        s.text('Input OV disconnect nominal18.465V; static maximum19.075V. No precision current limit in this supply stage.',20,24)
        s.text('LM74800 EP13 MUST FLOAT: no GND plane connection / no thermal vias. Input FET source faces battery.',20,33)
        s.component(fet,f'Q{base}', 'IPD90N10S4-06',85,80,{'1':dg,'2':mid,'3':raw},note='Common drain reverse blocking FET, source=input. Exact 100V variant as existing GDI protection.')
        s.component(fet,f'Q{base+1}', 'IPD90N10S4-06',365,80,{'1':hg,'2':mid,'3':rail},note='Common drain output disconnect FET. Startup hot SOA and total motor bulk must be checked.')
        s.component(controller,f'U{base}','LM74800QDRRRQ1',225,155,{'1':dg,'2':raw,'3':raw,'4':sw,'5':ov,'6':en,'7':'GND','8':hg,'9':rail,'10':mid,'11':cap,'12':mid,'13':None},note='TI SNOSD95C common-drain reference; mirrored existing GDI protection22d5fff. EP is electrically floating.')
        s.component(TVS,f'D{base}','SMCJ33CA',80,155,{'1':raw,'2':'GND'},note='Input surge clamp53.3V at ratedpulse current, undercontroller65V limit. Hot clamp/pulseenergy/fuse coordination pending.')
        s.component(C,f'C{base}','100n 100V X7R',370,155,{'1':mid,'2':'GND'})
        entries=[('R',0,'140k 0.1%',sw,ov,'Resistor_SMD:R_0805_2012Metric'),('R',1,'10k 0.1%',ov,'GND',None),('R',2,'1k','HW_ACTUATOR_ENABLE',en,None),('R',3,'10k',en,'GND',None),('R',4,'1M',dg,raw,None),('R',5,'1M',hg,rail,None),('C',1,'100n 25V X7R',cap,mid,None),('C',2,'100n 100V X7R',raw,'GND',None),('C',3,'100n 50V X7R',rail,'GND',None),('R',6,'1k',hg,p+'SLEW',None),('C',4,'22n 100V X7R',p+'SLEW','GND',None),('R',7,'10k',rail,'GND',None)]
        for k,(kind,n,val,a,b,fp) in enumerate(entries):s.component(R if kind=='R' else C,f'{kind}{base+n}',val,80+135*(k%4),240+38*(k//4),{'1':a,'2':b},footprint=fp)
        s.text('Ideal-diode input blocks regeneration to battery: 2x100uF plus local18V TVS absorb transient energy; load energy still UNKNOWN.',20,355)
        s.text('Global hardware latch removes supply AND forces DIS high; default-off EN10k. Residual bulk voltage is not immediate safe discharge.',20,364)
        s.text('No 24V jump-start operating claim. Verify OV turnoff overshoot, loss-of-battery braking, hot short and external fuse/contact budget.',20,373)
        finish(s)

    (HERE/(LIB+'.kicad_sym')).write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(s.body.replace('Power8GDI_Aux:','') for s in symbols.values())+'\n)\n')
    (HERE/'sym-lib-table').write_text(f'(sym_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.kicad_sym") (options "") (descr "Four motor bridges")))\n')
    (HERE/'fp-lib-table').write_text(f'(fp_lib_table (version 7) (lib (name "{LIB}") (type "KiCad") (uri "${{KIPRJMOD}}/{LIB}.pretty") (options "") (descr "LM74800 floatingEP")))\n')
    (HERE/'parts.json').write_text(json.dumps(parts,indent=2)+'\n')
    interface={'schema_version':1,'root_uuid':ROOT,'symbol_library':LIB,'footprint_library':LIB,'sheets':sheets,'parts':len(parts),'channels':[{'name':ch,'ref':f'U{base}','protected_feed':feed+'_VS','pwm':pwm,'dir':dr,'disable':dis,'output_nets':[ch+'_MOTOR_A',ch+'_MOTOR_B']} for ch,base,feed,pwm,dr,dis in channels], 'feed_input_nets':['VBAT_DBW_FUSED','VBAT_EWG_FUSED'],'shared_nets':['+3V3','GND','HW_ACTUATOR_ENABLE','HW_ACTUATOR_ENABLE_N','MOTOR_CS_N','GDI_SPI2_SCK','GDI_SPI2_MOSI','GDI_SPI2_MISO'],'pwm_frequency_max_hz':20000,'pwm_timer':'TIM3 shared DBW/EWG','spi':{'cs':'PB4','mode':1,'max_initial_hz':1000000,'frame_bits':16,'minimum_cs_high_us':2,'physical_order':['DBW','EWG'],'wire_byte_order':['EWG','DBW'],'response_latency_frames':1,'MISO_buffer_OE':'MOTOR_CS_N'},'disable_equation':'HW_ACTUATOR_ENABLE_N OR CHANNEL_DISABLE','normal_supply_ov_v':{'nominal':18.465,'static_min':1.195*(1+140000*.999/(10000*1.001))-.0000002*(140000*1.001+46),'static_max':1.267*(1+(140000*1.001+46)/(10000*.999))+.0000002*(140000*1.001+46)},'continuous_current_A_design_target_only':{'each_channel':2,'each_feed_sum':2,'all_channels_sum':4},'remove_old_sheets':['motor/dbw_driver','motor/ewg_driver'],'release_status':'NOT_HARDWARE_QUALIFIED','remaining_gates':['Load/stall and regenerative energy unknown','Thermal and simultaneous-current contact/fuse budget','Protection dynamicovershoot/EMC and MOSFET startupSOA','Bulk MPN/ripple/coldESR/height final selection','Root ERC/PCB layout/DRC','Real firmware SPI diagnostics / position safety / fault injection']}
    (HERE/'interface.json').write_text(json.dumps(interface,indent=2)+'\n')
    with (HERE/'bom.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['ref','value','footprint','sheet','dnp','note']);w.writeheader();w.writerows({k:p[k] for k in w.fieldnames} for p in parts)
    print(json.dumps({'sheets':len(sheets),'parts':len(parts)}))

if __name__=='__main__':build()
