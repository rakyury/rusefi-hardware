"""22 direct, active-high MCU commands into six TLE9104SH low-side ICs.

Pin facts: Infineon TLE9104SH Rev1.31, Tables3-1/5-1/5-2 and p24.
Board-level current, repeated avalanche and timing qualification remains open.
"""
from pathlib import Path
import hashlib
import json
from core_schlib import Sheet, box_symbol

HERE=Path(__file__).resolve().parent
CHANNELS=[*[f'PI{i}' for i in range(1,7)],*[f'VVT{i}' for i in range(1,5)],
          *[f'AUX_PWM{i}' for i in range(1,9)],*[f'LS_AUX{i}' for i in range(1,5)]]
FP_R='Resistor_SMD:R_0603_1608Metric'
FP_C='Capacitor_SMD:C_0603_1608Metric'


def footprint():
    """Infineon package page FPD: top-view pin1 at lower left.

    9.55mm row centers, .5mm pitch, .25x1.55 copper, cross-shaped EP.
    No numbered mounting pads or guessed SOIC equivalent. 0.3mm thermal drills.
    """
    dest=HERE.parent/'Power8GDI_Core.pretty/TLE9104SH_PG-DSO-20-88.kicad_mod'
    dest.parent.mkdir(exist_ok=True)
    rows=['(footprint "TLE9104SH_PG-DSO-20-88" (version 20241229) (generator "pcbnew") (layer "F.Cu")',
          '(descr "Infineon PG-DSO-20-88 FPD copper dimensions; 0.3mm filled/capped thermal via candidate; assembly review required") (attr smd)',
          '(fp_text reference "REF**" (at 0 -6.1) (layer "F.SilkS") (effects(font(size 1 1)(thickness .15))))',
          '(fp_text value "TLE9104SH" (at 0 6.1) (layer "F.Fab") (effects(font(size 1 1)(thickness .15))))',
          '(fp_rect(start -3.2 -3.75)(end 3.2 3.75)(stroke(width .1)(type default))(fill none)(layer "F.Fab"))',
          '(fp_rect(start -4.15 -5.8)(end 4.15 5.8)(stroke(width .05)(type default))(fill none)(layer "F.CrtYd"))',
          '(fp_circle(center -3 5.5)(end -2.85 5.5)(stroke(width .15)(type default))(fill none)(layer "F.SilkS"))']
    for i in range(10):
        for number,x,y in [(i+1,-2.25+.5*i,4.775),(i+11,2.25-.5*i,-4.775)]:
            rows.append(f'(pad "{number}" smd rect(at {x} {y})(size .25 1.55)(layers "F.Cu" "F.Mask")(solder_mask_margin .025))')
            rows.append(f'(pad "" smd rect(at {x} {y})(size .25 1.51)(layers "F.Paste"))')
    for w,h in [(5.1,4.23),(7.8,1.6)]:
        rows.append(f'(pad "21" smd rect(at 0 0)(size {w} {h})(layers "F.Cu" "F.Mask"))')
    for x,y in [(-1.3,-1.4),(1.3,-1.4),(-2.6,0),(0,0),(2.6,0),(-1.3,1.4),(1.3,1.4)]:
        rows.append(f'(pad "" smd rect(at {x} {y})(size 2.3 1.1)(layers "F.Paste"))')
    for x in [-2.2,-1.1,0,1.1,2.2]:
        for y in [-1.2,0,1.2]:
            rows.append(f'(pad "21" thru_hole circle(at {x} {y})(size .6 .6)(drill .3)(layers "*.Cu"))')
    dest.write_text('\n'.join(rows)+')\n',encoding='utf8')
    return str(dest.relative_to(HERE.parent)), hashlib.sha256(dest.read_bytes()).hexdigest()


def make_outputs(syms,root_id):
    r,c=syms['R'],syms['C']; sheets=[]
    def res(s,ref,value,x,y,a,b,note=''):
        s.component(r,ref,value,x,y,{'1':a,'2':b},footprint=FP_R,note=note)
    def cap(s,ref,value,x,y,rail):
        s.component(c,ref,value,x,y,{'1':rail,'2':'GND'},footprint=FP_C)
    in_pads=[1,3,5,9,11,13]; out_pads=[2,4,6,8,10,12]
    pins=[('14','VCC','power_in',0,25.4,270),('7','GND','power_in',0,-25.4,90)]
    for j in range(6):
        pins += [(str(in_pads[j]),f'{j+1}A','input',-15.24,19.05-j*7.62,0),
                 (str(out_pads[j]),f'{j+1}Y_INV','output',15.24,19.05-j*7.62,180)]
    inv=box_symbol('SN74LVC14A_Q1',pins,'Package_SO:TSSOP-14_4.4x5mm_P0.65mm',width=25.4,height=45.72)
    # Deliberately explicit physical pin numbers, including floating heat slug21.
    pins=[]
    left=[(3,'IN1_N'),(18,'IN2_N'),(4,'IN3_N'),(17,'IN4_N'),(6,'SI'),(8,'SCK'),(7,'CSN'),(13,'RESN'),(14,'EN')]
    for i,(n,name) in enumerate(left):pins.append((str(n),name,'input',-25.4,30.48-i*7.62,0))
    for i,(n,name,kind) in enumerate([(1,'OUT1','open_collector'),(20,'OUT2','open_collector'),(10,'OUT3','open_collector'),(11,'OUT4','open_collector'),(5,'SO','tri_state')]):
        pins.append((str(n),name,kind,25.4,30.48-i*10.16,180))
    for n,x in [(15,-10.16),(16,10.16)]:pins.append((str(n),'VIO' if n==15 else 'VDD','power_in',x,43.18,270))
    for i,n in enumerate([2,9,12,19,21]):pins.append((str(n),'EP_GND' if n==21 else 'GND','power_in',-20.32+i*10.16,-43.18,90))
    driver=box_symbol('TLE9104SH',pins,'Power8GDI_Core:TLE9104SH_PG-DSO-20-88',width=45.72,height=81.28)
    for bank in range(6):
        names=CHANNELS[4*bank:4*bank+4]; b=1100+bank*20
        sheet=Sheet(f'outputs/ls_bank_{bank+1}',f'Direct protected low-side {", ".join(names)}',root=root_id,paper='A2');sheets.append(sheet)
        dn={str(n):'GND' for n in [2,9,12,19,21]}
        dn.update({'15':'+3V3','16':'+5V_CORE','5':f'LS{bank+1}_SO','6':'LS_SPI_MOSI','8':'LS_SPI_SCK',
                   '7':f'LS{bank+1}_CS_N','13':'LS_RESET_N','14':f'LS{bank+1}_ENABLE'})
        gn={'14':'+3V3','7':'GND', **{str(p):'GND' for p in in_pads}}
        for pad in [3,18,4,17]: dn[str(pad)]='+3V3'  # unused active-low inputs held OFF
        for i,name in enumerate(names):
            dn[str([3,18,4,17][i])]=name+'_IN_N'
            dn[str([1,20,10,11][i])]='HARNESS_'+name
            gn[str(in_pads[i])]=name;gn[str(out_pads[i])]=name+'_INV'
            y=90+i*65
            res(sheet,f'R{b+i*3+1}','100k',55,y,name,'GND','MCU high-Z/reset command OFF; high command turns load ON through inverter')
            res(sheet,f'R{b+i*3+2}','100R',110,y,name+'_INV',name+'_IN_N','Input current/edge damping; direct timing path, not SPI control')
            res(sheet,f'R{b+i*3+3}','10k',165,y,'+3V3',name+'_IN_N','Default high is OFF at TLE input; essential active-low pin polarity')
        sheet.component(inv,f'U{1121+bank}','SN74LVC14AQPWRQ1',260,100,gn,
                        note='TI SCAS705B. Only assigned gates invert MCU commands; all unused inputs tied low and outputs no-connect.')
        sheet.component(driver,f'U{1101+bank}','TLE9104SHXUMA1',440,115,dn,
                        note='Infineon Rev1.31. INx ACTIVE LOW; EN high AND CTRL.OUT_EN=1 required. All4GNDs and floatingEP connected. No parallel channels.')
        res(sheet,f'R{b+13}','47R',260,220,f'LS_CS{bank+1}',f'LS{bank+1}_CS_N')
        res(sheet,f'R{b+14}','10k',315,220,'+3V3',f'LS{bank+1}_CS_N','Deselected during reset')
        res(sheet,f'R{b+15}','100R',370,220,f'LS{bank+1}_SO','GDI_SPI2_MISO','Shared SPI2; high-Z SO while CSN high, 8MHz device maximum')
        res(sheet,f'R{b+16}','100R',425,220,'HW_ACTUATOR_ENABLE',f'LS{bank+1}_ENABLE','Dedicated EN physical kill independent of direct IN commands')
        res(sheet,f'R{b+17}','10k',480,220,f'LS{bank+1}_ENABLE','GND','Default hardware inhibit')
        cap(sheet,f'C{b+1}','100n 16V X7R',260,275,'+3V3')
        cap(sheet,f'C{b+2}','100n 16V X7R',315,275,'+3V3')
        cap(sheet,f'C{b+3}','100n 16V X7R',370,275,'+5V_CORE')
        cap(sheet,f'C{b+4}','1u 16V X7R',425,275,'+5V_CORE')
        sheet.text('LOW-SIDE ONLY: external loads connect to separately fused +12V; return current through all driver GND/EP pads.\n3V3 MCU high -> inverter low -> load ON, only with hardware EN and SPI OUT_EN. MCU reset -> OFF.\nCandidate envelope for initial calculation: <=1.4A turn-off; repeated clamp energy <=7mJ, NOT an approved rating.\nNo low-impedance peak/hold injector support. VVT/AUX frequencies require scheduled GPIO implementation.\nDriver fault thresholds, load L/R, simultaneous dissipation, harness fuses and board heat sinking remain unqualified.',25.4,335)
    ctrl=Sheet('outputs/ls_control','Low-side shared SPI and reset',root=root_id,paper='A3');sheets.append(ctrl)
    reset=box_symbol('SN74LVC1G17_Q1',[('1','NC','no_connect',-10.16,7.62,0),('2','A','input',-10.16,0,0),('4','Y','output',10.16,0,180),('5','VCC','power_in',0,12.7,270),('3','GND','power_in',0,-12.7,90)],'Package_TO_SOT_SMD:SOT-23-5',width=15.24,height=20.32)
    ctrl.component(reset,'U1140','SN74LVC1G17QDBVRQ1',100,90,{'2':'LS_RESET_RELEASE','4':'LS_RESET_N','5':'+3V3','3':'GND'},
                   note='Noninverting reset buffer; active-high MCU release. Keep low >=10us after VDD5V stable. Firmware must restart reset after either rail fault.')
    res(ctrl,'R1241','100k',50,150,'LS_RESET_RELEASE','GND')
    res(ctrl,'R1242','1k 1%',150,150,'LS_RESET_N','GND','6x100uA internal pullups +10uA Ioff =>0.6161V worst-case, below 1V reset-low limit')
    cap(ctrl,'C1241','100n 16V X7R',200,90,'+3V3')
    res(ctrl,'R1243','33R',260,90,'GDI_SPI2_SCK','LS_SPI_SCK','Branch damping; validate signal integrity across6drivers and2PT chips')
    res(ctrl,'R1244','33R',260,150,'GDI_SPI2_MOSI','LS_SPI_MOSI')
    ctrl.text('Startup: all22 commands low, sixCS high, reset-release low. Stabilize 3V3/5V; hold RESN low >=10us.\nRelease reset; verify POR, keep outputs disabled, set direct-drive/no-parallel CFG bits.\nSet OUT_EN only after configuration readback and healthy watchdog; then arm hardware permission.\nMaintain communication watchdog (default50ms); 16-bit odd-parity frames; bus mode/clock changed only with allCS high.\nNo automatic fault clearing/re-enable. External watchdog is not a per-injector maximum pulse timer.\nSPI scheduling, rail sequencing, current/flyback/thermal and engine timing need hardware verification.',25.4,200)
    fp,sha=footprint()
    result={'schema_version':1,'channels':CHANNELS,'bank_channels':[CHANNELS[4*i:4*i+4] for i in range(6)],
            'parts':[part for s in sheets for part in s.parts],'footprint':fp,'footprint_sha256':sha,
            'source':'https://www.infineon.com/assets/row/public/documents/10/49/infineon-tle9104sh-datasheet-en.pdf',
            'source_revision':'1.31 2020-09-30','qualification':'BLOCKED_PENDING_LOADS_AND_PHYSICAL_VALIDATION'}
    (HERE/'outputs_manifest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    return sheets
