"""Check actual KiCad exports against independent critical pin/safety contracts."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent

def electrical_errors(nets):
    errors=[]
    def need(ref,pin,net):
        if nets.get((ref,str(pin)))!=net:errors.append(f'{ref}.{pin} expected {net}')
    channels=[('DBW',6000,'MOTOR13','MOTOR_SPI_SI'),('EWG',6050,'MOTOR24','DBW_SPI_SO'),('MOTOR3',6100,'MOTOR13','EWG_SPI_SO'),('MOTOR4',6150,'MOTOR24','MOTOR3_SPI_SO')]
    for ch,b,feed,si in channels:
        # Infineon p4 physical pin map, not extracted from generator manifest.
        expected={1:ch+'_DIR_FILTERED',2:'+3V3',3:ch+'_SPI_SO',4:feed+'_VS',5:ch+'_MOTOR_A',6:'GND',7:ch+'_MOTOR_B',8:si,9:'MOTOR_CS_N',10:'MOTOR_SPI_SCK',11:ch+'_DIS_GATED',12:ch+'_PWM_FILTERED',13:'GND'}
        for pin,net in expected.items():need(f'U{b}',pin,net)
        for pin,net in {1:'HW_ACTUATOR_ENABLE_N',2:ch+'_DISABLE',3:'GND',4:ch+'_DIS_GATED',5:'+3V3'}.items():need(f'U{b+1}',pin,net)
        for offset,net,other in [(2,ch+'_PWM_FILTERED','GND'),(3,ch+'_DIR_FILTERED','GND'),(4,ch+'_DISABLE','+3V3'),(5,ch+'_DIS_GATED','+3V3')]:
            need(f'R{b+offset}',1,net);need(f'R{b+offset}',2,other)
        need(f'C{b+4}',1,feed+'_VS');need(f'C{b+4}',2,'GND')
        need(f'D{b}',1,feed+'_VS');need(f'D{b}',2,'GND')
    for pin,net in {1:'MOTOR_CS_N',2:'MOTOR4_SPI_SO',3:'GND',4:'MOTOR_MISO_BUFFERED',5:'+3V3'}.items():need('U6190',pin,net)
    need('R6192',1,'MOTOR_MISO_BUFFERED');need('R6192',2,'GDI_SPI2_MISO')
    need('R6193',1,'MOTOR_CS_N');need('R6193',2,'+3V3')
    for feed,b,raw in [('MOTOR13',6200,'VBAT_DBW_FUSED'),('MOTOR24',6250,'VBAT_EWG_FUSED')]:
        p=feed+'_';rail=p+'VS';mid=p+'MID'
        for pin,net in {1:p+'DGATE',2:raw,3:raw,4:p+'SW',5:p+'OV',6:p+'POWER_EN',7:'GND',8:p+'HGATE',9:rail,10:mid,11:p+'CAP',12:mid,13:None}.items():need(f'U{b}',pin,net)
        for ref,mapping in [(f'Q{b}',{1:p+'DGATE',2:mid,3:raw}),(f'Q{b+1}',{1:p+'HGATE',2:mid,3:rail}),(f'C{b+1}',{1:p+'CAP',2:mid}),(f'R{b}',{1:p+'SW',2:p+'OV'}),(f'R{b+1}',{1:p+'OV',2:'GND'}),(f'R{b+2}',{1:'HW_ACTUATOR_ENABLE',2:p+'POWER_EN'}),(f'R{b+3}',{1:p+'POWER_EN',2:'GND'})]:
            for pin,net in mapping.items():need(ref,pin,net)
    return errors

def main():
    manifest={p['ref']:p for p in json.loads((HERE/'parts.json').read_text())};nets={};exported={};checks=[];errors=[]
    def check(name,ok):
        checks.append({'check':name,'passed':bool(ok)})
        if not ok:errors.append(name)
    for path in sorted(HERE.glob('*.xml')):
        root=ET.parse(path).getroot()
        for c in root.findall('./components/comp'):
            ref=c.get('ref');check(ref+' unique export',ref not in exported);exported[ref]=c
        for n in root.findall('./nets/net'):
            name=n.get('name');name=None if name.startswith('unconnected-') else name
            for pin in n.findall('node'):nets[(pin.get('ref'),pin.get('pin'))]=name
    check('Exactly106 expected parts in exports',len(exported)==106 and set(exported)==set(manifest))
    for ref,p in manifest.items():
        check(ref+' every exported net matches',all(nets.get((ref,pin))==net for pin,net in p['pins'].items()))
        c=exported[ref];check(ref+' footprint matches',c.findtext('footprint')==p['footprint'])
        check(ref+' dedicated symbol namespace',c.find('libsource').get('lib')=='Power8GDI_Motor4')
    critical=electrical_errors(nets);check('Independent critical manufacturer/safety contracts',not critical);errors.extend(critical)
    # These mutations must be detected by the independently specified contract.
    for ref,pin,badnet in [('U6000','2','MOTOR13_VS'),('U6000','11','DBW_DISABLE'),('U6190','1','GND'),('U6100','8','MOTOR_SPI_SI'),('Q6200','3','MOTOR13_MID'),('U6200','13','GND'),('C6201','2','GND'),('R6253','2','+3V3')]:
        changed=dict(nets);changed[(ref,pin)]=badnet
        check(f'Fault mutation caught {ref}.{pin}->{badnet}',bool(electrical_errors(changed)))
    check('All functional components fitted',not any(p['dnp'] for p in manifest.values()))
    checks_erc={}
    for p in HERE.glob('*.erc.json'):
        r=json.loads(p.read_text());types={}
        for sheet in r['sheets']:
            for violation in sheet['violations']:
                k=violation['type'];types[k]=types.get(k,0)+1
        checks_erc[p.name]=types
        check(p.name+' only external-driver/global-label findings',set(types)<= {'global_label_dangling','power_pin_not_driven','pin_not_driven'})
    import pcbnew as pcb
    footprints=[];tle=None
    for name in sorted({p['footprint'] for p in manifest.values()}):
        lib,item=name.split(':');folder=HERE/(lib+'.pretty') if lib=='Power8GDI_Motor4' else Path('/usr/share/kicad/footprints')/(lib+'.pretty')
        fp=pcb.FootprintLoad(str(folder),item);check('Footprint exists '+name,fp is not None)
        if fp is None:continue
        pads={p.GetNumber() for p in fp.Pads() if p.GetNumber()};footprints.append({'name':name,'pads':sorted(pads)})
        for ref,p in manifest.items():
            if p['footprint']==name:check(ref+' all connected pads present',not({n for n,v in p['pins'].items() if v is not None}-pads))
        if item=='Infineon_PG-DSO-12-11_ThermalVias':tle=fp
        if item=='LM74800_DRR0012E':
            ep=[p for p in fp.Pads() if p.GetNumber()=='13'];check('LM74800 exposedpad single isolated SMD land',len(ep)==1 and ep[0].GetDrillSize().x==0)
            check('LM74800 EP1.3x2.5 perDRR0012E',len(ep)==1 and tuple(round(pcb.ToMM(v),3) for v in (ep[0].GetSize().x,ep[0].GetSize().y))==(1.3,2.5))
    if tle:
        pads={p.GetNumber():p for p in tle.Pads() if p.GetNumber() in [str(i) for i in range(1,13)]}
        for n in range(1,13):
            pad=pads[str(n)];x,y=(pcb.ToMM(v) for v in (pad.GetPosition().x,pad.GetPosition().y));expected=(-4.8,-2.5+(n-1)) if n<=6 else (4.8,2.5-(n-7))
            check(f'TLE physical lead{n} matches1mm pitch andpin1corner',abs(x-expected[0])<.001 and abs(y-expected[1])<.001)
            check(f'TLE lead{n} land2x0.65 overlaps10.3mm bodyspan',tuple(round(pcb.ToMM(v),3) for v in (pad.GetSize().x,pad.GetSize().y))==(2,0.65))
        ep=[p for p in tle.Pads() if p.GetNumber()=='13' and p.GetDrillSize().x==0 and p.IsOnLayer(pcb.F_Cu)]
        check('TLE EPland4.5x8.1 covers slug4.2x7.8',len(ep)==1 and tuple(round(pcb.ToMM(v),3) for v in (ep[0].GetSize().x,ep[0].GetSize().y))==(4.5,8.1))
        check('TLE18 ground thermal vias present',sum(1 for p in tle.Pads() if p.GetNumber()=='13' and p.GetDrillSize().x>0)==18)
    interface=json.loads((HERE/'interface.json').read_text());check('Static max OV disconnect below28V normal limit',interface['normal_supply_ov_v']['static_max']<28)
    power={'continuous_target_A_per_channel':2,'TLE_path_R_ohm_max_at150C':.4,'conduction_W_each_at2A':2**2*.4,'conduction_W_four_at2A':4*2**2*.4,'conduction_W_each_at6A_notcontinuous':6**2*.4,'reference_JEDEC_RthetaJA_CperW':30,'illustrative_rise_C_at2A_excluding_switching':2**2*.4*30,'feed_pair_bulk_F':200e-6,'bulk_energy_margin_J_14V_to28V':.5*200e-6*(28**2-14**2),'qualification':'Illustrative budgets; actual PCB thermal impedance, load regen, dynamic overshoot and fuse coordination unknown'}
    report={'passed':not errors,'check_count':len(checks),'errors':errors,'checks':checks,'erc_leaf_counts':checks_erc,'footprints':footprints,'power_budget':power,'schematic_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.kicad_sch')},'scope':'Electrical export and footprint checks, not integrated ERC/DRC or hardware certification'}
    (HERE/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'checks':len(checks),'passed':not errors,'errors':errors},indent=2))
    raise SystemExit(0 if not errors else 1)

if __name__=='__main__':main()
