"""Two on-board Hellen-derived WBO channels, with explicit adaptation evidence.

Source XML is exported by KiCad from the pinned schematic. Electrical nets are
transferred, never inferred from PDF layout. Deliberate changes are recorded.
"""
from pathlib import Path
import csv, hashlib, json, re, sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'interfaces_aux'))
from schlib import Sheet, Symbol, box_symbol, parse, dump, children, child
ROOT='f4d21065-0a5b-5086-a08e-1af9469f04bd'
RFP='Resistor_SMD:R_0603_1608Metric'
CFP='Capacitor_SMD:C_0603_1608Metric'

def encode_auto_net(net):
    """Reversible byte encoding: '+' and '-' and '_' can never collapse.

    All source-generated Net-* names use a reserved AUTO_ namespace. Escape
    underscores too, so a literal source `_2B_` cannot mimic an encoded plus.
    """
    return 'AUTO_'+''.join(chr(b) if 48<=b<=57 or 65<=b<=90 or 97<=b<=122 else f'_{b:02X}_' for b in net.encode('utf-8'))

def symbol(name,pins,fp,prefix='U'):
    n=(len(pins)+1)//2; coords=[]
    for i,(number,label,kind) in enumerate(pins):
        side=i//n; k=i%n
        coords.append((number,label,kind,-17.78 if not side else 17.78,(n-1)*1.27-k*2.54,0 if not side else 180))
    return box_symbol('WBO_'+name,coords,fp,width=30.48,height=max(10.16,(n+1)*2.54),prefix=prefix)

R=box_symbol('WBO_R',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],RFP,width=5.08,height=2.54,prefix='R')
C=box_symbol('WBO_C',[('1','1','passive',-5.08,0,0),('2','2','passive',5.08,0,180)],CFP,width=5.08,height=2.54,prefix='C')
C=Symbol('WBO_C',C.body.replace('(rectangle (start -2.54 1.27) (end 2.54 -1.27) (stroke (width 0.254) (type default)) (fill (type background)))','(polyline (pts (xy -1.27 2.54) (xy -1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none))) (polyline (pts (xy 1.27 2.54) (xy 1.27 -2.54)) (stroke (width 0.254) (type default)) (fill (type none)))').replace('(length 2.54)','(length 3.81)'),CFP)

def build():
    source=ET.parse(HERE/'reference/hellen1-wbo.xml').getroot()
    nets={}
    for net in source.findall('./nets/net'):
        for p in net.findall('node'): nets.setdefault(p.get('ref'),{})[p.get('pin')]=net.get('name')
    pin_defs={(p.get('lib'),p.get('part')):[(x.get('num'),x.get('name') or x.get('num'),x.get('type')) for x in p.findall('./pins/pin')] for p in source.findall('./libparts/libpart')}
    sheets=[]; reference_maps=[]
    for index,base in [(1,5600)]:
        pre=f'WBO{index}_'
        def mapnet(net):
            if net.startswith('unconnected-'): return None
            if net=='+5V': return '+5V_CORE'
            if net=='GND': return 'GND'
            if net=='+3V3': return pre+'3V3'
            if net=='VDDA': return pre+'3V3' # approved supply-only merge; F042 requires VDDA>=VDD
            if net=='/CANH': return 'CAN2_H'
            if net=='/CANL': return 'CAN2_L'
            if net=='/heater_pwm':return pre+'F042_HEATER_PWM'
            if net=='/LSU_H+': return f'HARNESS_WBO{index}_CONTACT3'
            sensor={'/LSU_Ip':1,'/LSU_Vm':2,'/LSU_Rtrim':5,'/LSU_Un':6}
            if net in sensor: return f'HARNESS_WBO{index}_CONTACT{sensor[net]}'
            if net in ('/SEL1','/SEL2'):
                # f0_module port.cpp: low/floating -> index0, floating/high -> index1.
                if index==1 and net=='/SEL2' or index==2 and net=='/SEL1': return None
            return pre+(encode_auto_net(net) if net.startswith('Net-') else net.lstrip('/'))
        # Explicit aliases above are one-to-one within each channel. Reject
        # any future source name that collides with them before writing files.
        reverse={}
        for original in sorted({n for pins in nets.values() for n in pins.values()}):
            mapped=mapnet(original)
            if mapped is None:continue
            if mapped in reverse and {reverse[mapped],original}!={'+3V3','VDDA'}:
                raise ValueError(f'Net alias collision: {reverse[mapped]} and {original} -> {mapped}')
            reverse[mapped]=original
        def refmap(ref):return re.sub(r'\d+',lambda m:str(base+int(m[0])-600),ref)
        analog=Sheet(f'wbo/wbo{index}_analog',f'WBO{index}: LSU4.9 pump and Nernst analog loop',root=ROOT,paper='A2')
        control=Sheet(f'wbo/wbo{index}_control',f'WBO{index}: F042, CAN and hardware-inhibited heater',root=ROOT,paper='A2')
        for s in [analog,control]:
            s.text('Hellen WBO 0.6 derived candidate; no engine / thermal / EMC approval',20,15,2)
            s.text('Pinned source f8be5db671b7a2739d0c5c2ee7c9a80c3022aa76. Design changes and remaining checks in README.',20,24)
        main_positions={'U600':(analog,90,85),'U601':(analog,275,85),'U602':(control,90,95),'U603':(analog,450,85),'U604':(control,275,65),'U605':(control,450,65),'Q600':(control,275,130),'J600':(control,450,130),'D604':(control,450,200)}
        analog_refs={f'R{x}' for x in [600,601,602,603,604,605,606,607,608,609,610,611,612,613,614,615,618,619,620,621,623,624]}|{f'C{x}' for x in [600,601,603,605,607,608,611,612]}|{'U600','U601','U603'}
        counts={analog.name:0,control.name:0}
        for comp in source.findall('./components/comp'):
            old=comp.get('ref')
            if old in ('M1','R630','C604','C606'):continue # frame interface and unpopulated redundant capacitors
            value=comp.findtext('value');fp=comp.findtext('footprint'); lib=comp.find('libsource')
            pins=pin_defs[(lib.get('lib'),lib.get('part'))]
            mapped={p:mapnet(n) for p,n in nets[old].items()}
            note=f'Pinned Hellen 0.6 source {old}; netlist-derived.'
            if old=='Q600':
                value='VND7NV04TR-E';fp='Package_TO_SOT_SMD:TO-252-2';mapped.pop('4',None)
                pins=[('1','INPUT','input'),('2','DRAIN','passive'),('3','SOURCE','passive')]
                note+=' Active DPAK variant replaces obsolete SOT223. Drain is HEATER NEGATIVE despite source net LSU_H+.'
            if old=='R622': mapped['2']=pre+'HEATER_DRIVE_5V'
            if old=='U603':
                mapped['2']=pre+'REF3V3'
                note+=' Precision setpoint only; LT3042 buffers the common VDD/VDDA rail.'
            if old=='U604':
                fp='Package_SO:MSOP-10-1EP_3x3mm_P0.5mm_EP1.68x1.88mm'
                pins=[('1','IN','power_in'),('2','IN','power_in'),('3','EN_UV','input'),('4','PG','open_collector'),('5','ILIM','passive'),('6','PGFB','input'),('7','SET','passive'),('8','GND','power_in'),('9','OUTS','input'),('10','OUT','power_out'),('11','EP_GND','power_in')]
                mapped={'1':'+5V_CORE','2':'+5V_CORE','3':'+5V_CORE','4':None,'5':'GND','6':'+5V_CORE','7':pre+'REF_SET','8':'GND','9':pre+'3V3','10':pre+'3V3','11':'GND'}
                note='LT3042 RevC p15 external reference buffer; replaces XC6206. PGFB=IN disables fast start. OUTS Kelvin to output capacitor. EP grounded.'
            if old=='R629':value='120R DNP';note+=' Do not fit: node on shared CAN2 bus, termination only at physical ends.'
            if old=='U605':
                pins=[(p,n,'bidirectional' if p in ('6','7') else t) for p,n,t in pins]
                fp='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
            if old=='D604':
                pins=[('1','CANH','passive'),('2','CANL','passive'),('3','GND','passive')]
                fp='Power8GDI_Board:SOT-23_D5604_J5600_Clearance'
            exact={'U600':'MCP6004T-E/ST','U601':'AD8628ARTZ-REEL7','U602':'STM32F042K6T6','U603':'REF3033AIDBZR','U604':'LT3042IMSE#WTRPBF'}
            value=exact.get(old,value)
            if old in main_positions:s,x,y=main_positions[old]
            else:
                s=analog if old in analog_refs else control
                k=counts[s.name];counts[s.name]+=1
                x=65+135*(k%4);y=(165+22*(k//4) if s is analog else 230+15.5*(k//4))
            # Passive 0402 parts enlarged to0603; same net topology and nominal values.
            if old.startswith('R'): fp=RFP;sym=R
            elif old.startswith('C'):fp=CFP;sym=C
            else:sym=symbol(old+'_mapped',pins,fp,old[0])
            start=len(s.items)
            s.component(sym,refmap(old),value,x,y,mapped,footprint=fp,note=note,dnp='DNP' in value)
            if old[0] not in 'RCU':
                inst=parse(s.items[start]);at=child(inst,'at');sx,sy=float(at[1]),float(at[2])
                extent=max(7.62,max(abs(p['y']) for p in sym.pins.values())+5.08)
                for prop in children(inst,'property'):
                    if prop[1] in ('Reference','Value'):
                        child(prop,'at')[1:3]=[str(sx),str(sy+(-extent if prop[1]=='Reference' else extent))]
                        effects=child(prop,'effects');effects[:]=[v for v in effects if not (isinstance(v,list) and v[0]=='justify')]
                s.items[start]=dump(inst)
            reference_maps.append({'channel':index,'source_ref':old,'ref':refmap(old),'source_pins':nets[old],'mapped_pins':mapped})
        # Peripheral controls use separate local supply; never tie WBO3V3 to main3V3.
        andsym=symbol('SN74LVC1G08', [('1','A','input'),('2','B','input'),('3','GND','power_in'),('4','Y','output'),('5','VCC','power_in')],'Package_TO_SOT_SMD:SOT-23-5')
        bufsym=symbol('SN74AHCT1G125',[('1','~{OE}','input'),('2','A','input'),('3','GND','power_in'),('4','Y','tri_state'),('5','VCC','power_in')],'Package_TO_SOT_SMD:SOT-23-5')
        control.component(andsym,f'U{base+10}','SN74LVC1G08QDBVRQ1',90,190,{'1':pre+'F042_HEATER_PWM','2':pre+'HEATER_PWM','3':'GND','4':pre+'HEATER_ALLOWED_3V3','5':pre+'3V3'},note='Main F7 permission uses legacy WBOx_HEATER_PWM net name; static enable, not a second PWM.')
        control.component(bufsym,f'U{base+11}','SN74AHCT1G125QDBVRQ1',275,200,{'1':pre+'HEATER_OE_N','2':pre+'HEATER_ALLOWED_3V3','3':'GND','4':pre+'HEATER_DRIVE_5V','5':'+5V_CORE'},note='OE local5V pull-up defaults disabled; NPN level shift enables only when positive global HW enable is present. No5V pull-up on main3V3 output.')
        extras=[('R',40,'10k',pre+'HEATER_PWM','GND'),('R',41,'10k',pre+'HEATER_DRIVE_5V','GND'),('C',40,'100n 16V X7R',pre+'3V3','GND'),('C',41,'100n 16V X7R','+5V_CORE','GND'),('R',42,'2.2k 1%',pre+'HEATER_OE_N','+5V_CORE'),('R',43,'10k',pre+'HEATER_ALLOWED_3V3','GND'),('R',44,'0R',pre+('SEL1' if index==1 else 'SEL2'),'GND' if index==1 else pre+'3V3'),('R',45,'10k',pre+'HEATER_GATE','GND')]
        # Gate discharge resistor at actual FET input (after1k), not before it.
        extras[-1]=('R',45,'100k',mapnet('Net-(Q600-G)'),'GND')
        for kind,num,val,a,b in extras:
            k=counts[control.name];counts[control.name]+=1
            control.component(R if kind=='R' else C,f'{kind}{base+num}',val,65+135*(k%4),230+15.5*(k//4),{'1':a,'2':b})
        reset=symbol('TPS3808G33',[('1','~{RESET}','open_collector'),('2','GND','power_in'),('3','~{MR}','input'),('4','CT','passive'),('5','SENSE','input'),('6','VDD','power_in')],'Package_TO_SOT_SMD:SOT-23-6')
        control.component(reset,f'U{base+12}','TPS3808G33QDBVRQ1',90,145,{'1':pre+'nRESET','2':'GND','3':pre+'3V3','4':None,'5':pre+'3V3','6':pre+'3V3'},note='Local rail monitor: ~3.07V threshold; CT open ~20ms recovery delay. NRST internal POR alone does not guarantee ADC supply validity.')
        for kind,num,val,a,b in [('R',60,'30k 0.1%',pre+'REF_SET','GND'),('R',61,'2.2k 1%',pre+'3V3','GND'),('R',62,'10k',pre+'nRESET',pre+'3V3'),('R',63,'220R 0.1%',pre+'REF3V3',pre+'REF_SET'),('C',60,'100n 16V X7R',pre+'REF_SET','GND'),('C',61,'10u 16V X7R effective>=4.7u','+5V_CORE','GND'),('C',62,'10u 16V X7R effective>=4.7u',pre+'3V3','GND'),('C',63,'100n 16V X7R',pre+'3V3','GND'),('C',64,'100n 16V X7R',pre+'REF3V3','GND')]:
            k=counts[control.name];counts[control.name]+=1
            control.component(R if kind=='R' else C,f'{kind}{base+num}',val,65+135*(k%4),230+15.5*(k//4),{'1':a,'2':b},footprint='Capacitor_SMD:C_1206_3216Metric' if kind=='C' and num in (61,62) else None,note='SET bleed sinks >102uA at nominal rail; 220R limits SET clamp fault current. Nominal buffered rail3.2978V.' if num==60 and kind=='R' else ('LT3042 CIN/COUT effective capacitance and ESR/ESL must meet datasheet at bias/temp; exact MPN release gate.' if kind=='C' and num in (61,62) else ''))
        oe=symbol('BC847B_Q',[('1','BASE','input'),('2','EMITTER','passive'),('3','COLLECTOR','open_collector')],'Package_TO_SOT_SMD:SOT-23','Q')
        control.component(oe,f'Q{base+20}','BC847B-QR',275,165,{'1':pre+'HEATER_OE_BASE','2':'GND','3':pre+'HEATER_OE_N'},note='NexperiaBC847x-Q Rev2:1B2E3C. Main3V3 absent -> base10k pull-down -> OE rises to5V independent of main permission.')
        for num,val,a,b in [(64,'4.7k 1%','HW_ACTUATOR_ENABLE',pre+'HEATER_OE_BASE'),(65,'10k 1%',pre+'HEATER_OE_BASE','GND')]:
            k=counts[control.name];counts[control.name]+=1
            control.component(R,f'R{base+num}',val,65+135*(k%4),230+15.5*(k//4),{'1':a,'2':b})
        # Heater supply is not routed through the logic supply diode.
        feed=Sheet(f'wbo/wbo{index}_heater_feed',f'WBO{index}: reverse protected heater supply',root=ROOT,paper='A3')
        feed.text('Heater current uses VBAT_MAIN_FUSED and dedicated power return; never +5V_CORE or VBAT_LOGIC_PROTECTED.',20,20,1.5)
        diode=symbol('STPS5H100BY',[('1','NC','no_connect'),('2','CATHODE_TAB','passive'),('3','ANODE','passive')],'Package_TO_SOT_SMD:TO-252-2','D')
        feed.component(diode,f'D{base+10}','STPS5H100BY-TR',90,75,{'1':None,'2':f'HARNESS_WBO{index}_CONTACT4','3':'VBAT_MAIN_FUSED'},note='ST DS6906 page1 package: leftlead1 NC, tab2 K, rightlead3 A. External branch fuse coordination and diode thermal validation required.')
        tvs=symbol('SMBJ24CA',[('1','1','passive'),('2','2','passive')],'Diode_SMD:D_SMB','D')
        feed.component(tvs,f'D{base+11}','SMBJ24CA',245,75,{'1':f'HARNESS_WBO{index}_CONTACT4','2':'GND'},note='38.9V ratedclamp nominal <40V switch minimumclamp; overshoot/pulse energy still unqualified.')
        for n,val,fp in [(50,'100n 100V X7R','Capacitor_SMD:C_0805_2012Metric'),(51,'47u 63V lowESR','Capacitor_SMD:CP_Elec_8x10')]:
            feed.component(C,f'C{base+n}',val,90+(n-50)*155,145,{'1':f'HARNESS_WBO{index}_CONTACT4','2':'GND'},footprint=fp,note='Provisional bulk MPN/ripple and cold ESR pending.' if n==51 else '')
        feed.text('Normal sensor supply10.8..16.5V after diode. Control receives measured voltage over CAN.\nDiode drop must be compensated in reported heater supply; current implementation has no local supply ADC.\nBosch LSU4.9 steady heater power7.5W/channel; cold start, fuse coordination and thermal tests pending.',20,200)
        sheets += [analog,control,feed]
    parts=[];symbols={}
    for s in sheets:
        for n,item in enumerate(s.items):
            if not item.startswith('(symbol '):continue
            inst=parse(item); props=children(inst,'property')
            ref=next(str(p[2]) for p in props if p[1]=='Reference')
            if ref[0] not in 'DQJ':continue
            at=child(inst,'at');sx,sy=float(at[1]),float(at[2])
            sym=s.symbols[str(child(inst,'lib_id')[1]).split(':')[-1]]
            extent=max(7.62,max(abs(p['y']) for p in sym.pins.values())+5.08)
            for prop in props:
                if prop[1] in ('Reference','Value'):
                    child(prop,'at')[1:3]=[str(sx),str(sy+(-extent if prop[1]=='Reference' else extent))]
                    effects=child(prop,'effects');effects[:]=[v for v in effects if not (isinstance(v,list) and v[0]=='justify')]
            s.items[n]=dump(inst)
        s.write(HERE.parent)
        p=HERE.parent/(s.name+'.kicad_sch');t=p.read_text(encoding='utf-8')
        for part in s.parts:
            old=f'(project "Power8GDI_Core" (path "/{ROOT}/{s.sheet_id}" (reference "{part["ref"]}") (unit 1)))'
            t=t.replace(old,old+f' (project "{Path(s.name).name}" (path "/{s.uuid}" (reference "{part["ref"]}") (unit 1)))')
        p.write_text(t.replace('Power8GDI_Aux:','Power8GDI_WBO:'),encoding='utf-8',newline='\n');parts+=s.parts;symbols.update(s.symbols)
        p.with_suffix('.kicad_pro').write_text('{}\n')
    (HERE/'parts.json').write_text(json.dumps(parts,indent=2)+'\n')
    (HERE/'reference_map.json').write_text(json.dumps(reference_maps,indent=2)+'\n')
    (HERE/'Power8GDI_WBO.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n'+'\n'.join(s.body.replace('Power8GDI_Aux:','') for s in symbols.values())+'\n)\n')
    (HERE/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Power8GDI_WBO") (type "KiCad") (uri "${KIPRJMOD}/Power8GDI_WBO.kicad_sym") (options "") (descr "WBO derived candidate")))\n')
    contract={'schema_version':1,'project':'Power8GDI_Core','root_uuid':ROOT,'sheets':[{'name':s.name,'uuid':s.uuid,'sheet_id':s.sheet_id,'components':len(s.parts)} for s in sheets],'parts':len(parts),'local_supply':{'architecture':'REF3033 + current-limited SET + LT3042 common VDD/VDDA','nominal_volts':3.297816,'reset_supervisor':'TPS3808G33QDBVRQ1','reset_threshold_nominal_volts':3.07,'power_qa':'ELECTRICAL_QA.md'},'references':{'hardware_commit':(HERE/'reference/commit.txt').read_text().strip(),'firmware_commit':(HERE/'reference/firmware_commit.txt').read_text().strip()},'upstream_license':'NO LICENSE FOUND IN HELLEN-ONE; redistribution review pending','channel_count':1,'sensor':'Bosch LSU4.9 automotive6pin','main_mcu_signals':['WBO1_HEATER_PWM'],'shared_nets':['CAN2_H','CAN2_L','+5V_CORE','GND','HW_ACTUATOR_ENABLE','VBAT_MAIN_FUSED'],'can':{'bitrate':500000,'standard_data_ids':[400],'diagnostic_ids':[401],'local_termination_fitted':False},'heater_equation':'F042_PWM AND MAIN_PERMISSION AND HW_ACTUATOR_ENABLE; local5V OE default disabled','remove_old_sheets':['interfaces_aux/wbo1_analog','interfaces_aux/wbo2_analog','interfaces_aux/wbo_adc_control'],'external_egt':{'onboard_channels':0,'bus':'CAN2','rate_and_protocol':'TBD; target500kbit/s compatible with WBO'},'remaining_gates':['Main firmware stale/invalid CAN must clear individual permissions; no separate F042 hardware heartbeat','Heater supply voltage compensation after diode, fuse/cold-current/thermal and load dump validation','WBO source license/redistribution review','Exact assembly MPN grades and passives selection; source MCU85C ceiling; LT3042 effectiveCout/stability and ADC calibration','Integrated ERC, PCB layout/DRC, bench calibration and hardware fault testing']}
    (HERE/'interface.json').write_text(json.dumps(contract,indent=2)+'\n')
    with (HERE/'bom.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['ref','value','footprint','dnp','sheet','note']);w.writeheader();w.writerows({k:p[k] for k in w.fieldnames} for p in parts)
    print(json.dumps({'sheets':len(sheets),'parts':len(parts)}))

if __name__=='__main__':build()
