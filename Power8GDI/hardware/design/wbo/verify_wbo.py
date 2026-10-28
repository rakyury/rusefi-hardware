"""Audit KiCad-exported WBO netlists and critical manufacturer pin contracts."""
from pathlib import Path
import argparse, hashlib, json, xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent

def source_partition_errors(observed,index):
    """Compare source and target connectivity partitions, ignoring net names.

    Read original KiCad XML directly. DO NOT use the generated parts manifest,
    reference_map, mapper or sanitized aliases to predict source connectivity.
    Component identity changes only by the documented numeric offset.
    """
    base=5600 if index==1 else 5800
    omitted_refs={'M1','R630','C604','C606','U604'} # XC6206 replaced by LT3042, audited independently below
    # Explicit adaptations: SOT223 extra drain pad removed for DPAK; heater
    # input resistor moved behind safety buffer; one ternary ID pin floats.
    omitted_pins={('Q600','4'),('R622','2'),('U603','2'),('U602','18' if index==1 else '15')}
    source_groups={};target_groups={};errors=[]
    for net in ET.parse(HERE/'reference/hellen1-wbo.xml').findall('./nets/net'):
        name=net.get('name')
        if name.startswith('unconnected-'):continue
        # Sole intentional source-net merge: common buffered supply eliminates
        # F042 VDDA/VDD sequencing violation. No signal-net exception is allowed.
        if name=='VDDA':name='+3V3'
        for node in net.findall('node'):
            old,pin=node.get('ref'),node.get('pin')
            if old in omitted_refs or (old,pin) in omitted_pins:continue
            ref=old[0]+str(base+int(old[1:])-600);key=(old,pin)
            source_groups.setdefault(name,set()).add(key)
            target=observed.get(ref,{}).get('pins',{}).get(pin)
            if target is None:errors.append(f'{ref}.{pin} unexpectedly absent/unconnected')
            target_groups.setdefault(target,set()).add(key)
    source_partition={frozenset(x) for x in source_groups.values()}
    target_partition={frozenset(x) for x in target_groups.values()}
    if source_partition!=target_partition:
        for name,pins in source_groups.items():
            if frozenset(pins) not in target_partition:errors.append(f'WBO{index} source net partition changed: {name}: {sorted(pins)}')
    return errors,{'source_partition_count':len(source_partition),'target_partition_count':len(target_partition),'retained_source_pin_count':sum(map(len,source_groups.values()))}


def supply_errors(observed,index):
    """Manufacturer pin contract independent of generated manifest/alias mapping."""
    b=5600 if index==1 else 5800;pre=f'WBO{index}_';out=pre+'3V3';ref=pre+'REF3V3'
    expected={
        f'U{b+3}':{'1':'+5V_CORE','2':ref,'3':'GND'},
        f'U{b+4}':{'1':'+5V_CORE','2':'+5V_CORE','3':'+5V_CORE','4':None,'5':'GND','6':'+5V_CORE','7':pre+'REF_SET','8':'GND','9':out,'10':out,'11':'GND'},
        f'U{b+2}':{'1':out,'5':out,'17':out,'4':pre+'nRESET'},
        f'U{b+12}':{'1':pre+'nRESET','2':'GND','3':out,'4':None,'5':out,'6':out},
        f'R{b+60}':{'1':pre+'REF_SET','2':'GND'},f'R{b+61}':{'1':out,'2':'GND'},f'R{b+62}':{'1':pre+'nRESET','2':out},f'R{b+63}':{'1':ref,'2':pre+'REF_SET'},
        f'C{b+60}':{'1':pre+'REF_SET','2':'GND'},f'C{b+61}':{'1':'+5V_CORE','2':'GND'},f'C{b+62}':{'1':out,'2':'GND'},f'C{b+63}':{'1':out,'2':'GND'},f'C{b+64}':{'1':ref,'2':'GND'},
    }
    errors=[]
    for r,pins in expected.items():
        for p,n in pins.items():
            if observed.get(r,{}).get('pins',{}).get(p)!=n:errors.append(f'{r}.{p} must be {n}')
    for r,value in [(f'U{b+4}','LT3042IMSE#WTRPBF'),(f'U{b+12}','TPS3808G33QDBVRQ1'),(f'R{b+60}','30k 0.1%'),(f'R{b+61}','2.2k 1%'),(f'R{b+63}','220R 0.1%')]:
        if observed.get(r,{}).get('value')!=value:errors.append(f'{r} expected {value}')
    return errors


def inhibit_errors(observed,index):
    """Independent partial-power contract: OE pull-up lives with AHCT VCC."""
    b=5600 if index==1 else 5800;p=f'WBO{index}_';errors=[]
    expected={f'U{b+11}':{'1':p+'HEATER_OE_N','5':'+5V_CORE'},
              f'Q{b+20}':{'1':p+'HEATER_OE_BASE','2':'GND','3':p+'HEATER_OE_N'},
              f'R{b+42}':{'1':p+'HEATER_OE_N','2':'+5V_CORE'},
              f'R{b+64}':{'1':'HW_ACTUATOR_ENABLE','2':p+'HEATER_OE_BASE'},
              f'R{b+65}':{'1':p+'HEATER_OE_BASE','2':'GND'}}
    for r,pins in expected.items():
        for pin,net in pins.items():
            if observed.get(r,{}).get('pins',{}).get(pin)!=net:errors.append(f'{r}.{pin} must be {net}')
    for r,value in [(f'Q{b+20}','BC847B-QR'),(f'R{b+42}','2.2k 1%'),(f'R{b+64}','4.7k 1%'),(f'R{b+65}','10k 1%')]:
        if observed.get(r,{}).get('value')!=value:errors.append(f'{r} expected {value}')
    return errors


def partial_power_oe_bound(observed,index):
    """DC fault scenario, NOT device transient simulation or measured proof.

    Main3V3=0, local5V=4.5V, NPN base held low. Evaluate the actual pull-up
    destination; includes a6uA combined collector/input leakage budget.
    """
    b=5600 if index==1 else 5800;r=observed[f'R{b+42}'];oe=observed[f'U{b+11}']['pins']['1']
    ends=list(r['pins'].values())
    if oe not in ends:return None
    other=ends[1] if ends[0]==oe else ends[0]
    rail={'GND':0.0,'+3V3':0.0,'+5V_CORE':4.5}.get(other)
    if rail is None:return None
    return rail-2200*1.01*6e-6

def verify():
    parts={p['ref']:p for p in json.loads((HERE/'parts.json').read_text())}
    observed={};errors=[];checks=[]
    for sheet in json.loads((HERE/'interface.json').read_text())['sheets']:
        f=HERE/(Path(sheet['name']).name+'.xml')
        r=ET.parse(f).getroot()
        for c in r.findall('./components/comp'):
            ref=c.get('ref')
            if ref in observed:errors.append('Duplicate '+ref)
            observed[ref]={'value':c.findtext('value'),'pins':{},'footprint':c.findtext('footprint')}
        for net in r.findall('./nets/net'):
            for node in net.findall('node'):
                name=net.get('name'); observed[node.get('ref')]['pins'][node.get('pin')]=None if name.startswith('unconnected-') else name
    def check(label,condition):
        checks.append({'check':label,'passed':bool(condition)})
        if not condition:errors.append(label)
    check('All87parts exported exactly once',set(observed)==set(parts) and len(parts)==87)
    for ref,p in parts.items():
        o=observed.get(ref,{})
        check(ref+' exported electrical pins match manifest',all(o.get('pins',{}).get(pin)==net for pin,net in p['pins'].items()))
        check(ref+' footprint preserved',o.get('footprint')==p['footprint'])
    for i,b in [(1,5600)]:
        p=lambda r,n:observed[f'{r}{b+n}']['pins']
        pre=f'WBO{i}_'
        check(pre+'CAN polarity datasheet6L7H',p('U',5)['6']=='CAN2_L' and p('U',5)['7']=='CAN2_H')
        check(pre+'F042 pins PA11RX PA12TX',p('U',2)['21']==p('U',5)['4'] and p('U',2)['22']==p('U',5)['1'])
        check(pre+'F042 ADC pump/Nernst/virtualground',p('U',2)['6']==pre+'Un_sense' and p('U',2)['8']==pre+'Ip_sense' and p('U',2)['9']==pre+'Vm')
        check(pre+'F042 heaterPA7',p('U',2)['13']==pre+'F042_HEATER_PWM')
        check(pre+'hardware inhibit defaults disabled in5Vdomain',not inhibit_errors(observed,i))
        check(pre+'individualF7permission andF042PWM',p('U',10)['1']==pre+'F042_HEATER_PWM' and p('U',10)['2']==pre+'HEATER_PWM' and p('U',10)['4']==p('U',11)['2'])
        check(pre+'gate signal resistor and pulldown',p('R',22)['2']==p('U',11)['4'] and p('R',22)['1']==p('Q',0)['1'] and p('R',45)['1']==p('Q',0)['1'] and p('R',45)['2']=='GND')
        check(pre+'Hminus actual powerdrain pin2',p('Q',0)['2']==f'HARNESS_WBO{i}_CONTACT3' and p('Q',0)['3']=='GND')
        check(pre+'diode ST DPAK1NC2K3A',p('D',10).get('1') is None and p('D',10)['2']==f'HARNESS_WBO{i}_CONTACT4' and p('D',10)['3']=='VBAT_MAIN_FUSED')
        check(pre+'Bosch sensor1pump5trim shunt',set(p('R',9).values())=={f'HARNESS_WBO{i}_CONTACT1',f'HARNESS_WBO{i}_CONTACT5'})
        check(pre+'Bosch sensor2VM separate fromGND',f'HARNESS_WBO{i}_CONTACT2' in p('R',6).values() and 'GND' not in p('R',6).values())
        check(pre+'Bosch sensor6Nernst',p('U',0)['10']==f'HARNESS_WBO{i}_CONTACT6')
        check(pre+'local3V3 rail isolated frommain',p('U',4)['10']==pre+'3V3' and p('U',2)['1']==pre+'3V3')
        check(pre+'VDD VDDA common buffered precisionrail',p('U',2)['1']==p('U',2)['5']==p('U',2)['17']==p('U',4)['10'] and p('U',3)['2']==p('R',63)['1'] and p('R',63)['2']==p('U',4)['7']!=p('U',4)['10'])
        check(pre+'CAN termination DNP',parts[f'R{b+29}']['dnp'])
        check(pre+'WBO all functionalICs fitted',not any(x['dnp'] for ref,x in parts.items() if ref.startswith('U') and b<=int(ref[1:])<b+200))
    check('Index0 low/floating',parts['R5644']['pins']=={'1':'WBO1_SEL1','2':'GND'} and observed['U5602']['pins'].get('18') is None)
    check('No second WBO assembly', not any(r.startswith('U58') for r in observed))
    # Ensure semantic adaptation does not accidentally join the two sensor analog loops.
    check('No formerCJ125 paths',not any('CJ125' in p['value'] or 'VCCSS' in str(p['pins']) for p in parts.values()))
    topology=[]
    from copy import deepcopy
    for index,base in [(1,5600)]:
        problems,counts=source_partition_errors(observed,index)
        topology.append({'channel':index,**counts,'errors':problems})
        check(f'WBO{index} original source pinsets preserve every connectivity partition',not problems)
        errors.extend(problems)
        power_problems=supply_errors(observed,index)
        check(f'WBO{index} independent power/reset datasheet pin contract',not power_problems)
        errors.extend(power_problems)
        errors.extend(inhibit_errors(observed,index))
        bound=partial_power_oe_bound(observed,index)
        check(f'WBO{index} main3V3off 5Valive OE DC bound above2V',bound is not None and bound>2.0)
        bad=deepcopy(observed);bad[f'R{base+42}']['pins']['2']='+3V3'
        check(f'WBO{index} old3V3pullup fails partial-power DC scenario',partial_power_oe_bound(bad,index)<0.8)
        for ref,pin,wrong in [(f'R{base+42}','2','+3V3'),(f'U{base+11}','1','HW_ACTUATOR_ENABLE_N'),(f'R{base+64}','1','HW_ACTUATOR_ENABLE_N'),(f'R{base+65}','2',None)]:
            bad=deepcopy(observed);bad[ref]['pins'][pin]=wrong
            check(f'WBO{index} partial-power inhibit mutation caught {ref}.{pin}',bool(inhibit_errors(bad,index)))
        for ref,pin,wrong in [(f'U{base+2}','5',f'WBO{index}_OLD_VDDA'),(f'U{base+3}','2',f'WBO{index}_3V3'),(f'U{base+4}','6','GND'),(f'U{base+12}','5','+3V3')]:
            bad=deepcopy(observed);bad[ref]['pins'][pin]=wrong
            check(f'WBO{index} power fault mutation caught {ref}.{pin}',bool(supply_errors(bad,index)))
        # Simulate precisely the old sanitizer fault: merge each opamp +/- net.
        for source_ref,positive,negative in [('U600','3','2'),('U600','5','6'),('U601','3','4')]:
            ref=source_ref[0]+str(base+int(source_ref[1:])-600)
            bad=deepcopy(observed);a=bad[ref]['pins'][positive];b=bad[ref]['pins'][negative]
            check(f'WBO{index} {source_ref}.{positive}/{negative} physically distinct',a!=b)
            for c in bad.values():
                for pin,name in c['pins'].items():
                    if name==a:c['pins'][pin]=b
            check(f'WBO{index} collision mutation caught {source_ref}.{positive}/{negative}',bool(source_partition_errors(bad,index)[0]))
    footprints=[]
    try:
        import pcbnew as pcb
        for fp in sorted({p['footprint'] for p in parts.values()}):
            library,name=fp.split(':'); directory=Path('/usr/share/kicad/footprints')/(library+'.pretty')
            if library=='Power8GDI_Board':directory=HERE.parent/'board/Power8GDI_Board.pretty'
            f=pcb.FootprintLoad(str(directory),name)
            if f is None:errors.append('Missing footprint '+fp);continue
            pads={p.GetNumber() for p in f.Pads() if p.GetNumber()}
            for ref,p in parts.items():
                if p['footprint']==fp:
                    missing={n for n,v in p['pins'].items() if v is not None}-pads
                    if missing:errors.append(f'{ref} pads absent {missing}')
            footprints.append({'footprint':fp,'pads':sorted(pads)})
    except ImportError:
        errors.append('pcbnew not available: run in pinned KiCad9 image for footprint verification')
    report={'check_count':len(checks),'passed':not errors,'errors':errors,'checks':checks,'independent_source_topology':topology,'footprints':footprints,'schematic_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('wbo*.kicad_sch')},'qualification':'Connectivity and land-pattern pad audit only; integratedERC/DRC and hardware measurement pending'}
    (HERE/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'checks':len(checks),'passed':not errors,'errors':errors},indent=2))
    return 0 if not errors else 1

if __name__=='__main__':raise SystemExit(verify())

