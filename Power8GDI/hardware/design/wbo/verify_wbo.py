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
    omitted_refs={'M1','R630','C604','C606'}
    # Explicit adaptations: SOT223 extra drain pad removed for DPAK; heater
    # input resistor moved behind safety buffer; one ternary ID pin floats.
    omitted_pins={('Q600','4'),('R622','2'),('U602','18' if index==1 else '15')}
    source_groups={};target_groups={};errors=[]
    for net in ET.parse(HERE/'reference/hellen1-wbo.xml').findall('./nets/net'):
        name=net.get('name')
        if name.startswith('unconnected-'):continue
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

def verify():
    parts={p['ref']:p for p in json.loads((HERE/'parts.json').read_text())}
    observed={};errors=[];checks=[]
    for f in HERE.glob('wbo*.xml'):
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
    check('All148parts exported exactly once',set(observed)==set(parts) and len(parts)==148)
    for ref,p in parts.items():
        o=observed.get(ref,{})
        check(ref+' exported electrical pins match manifest',all(o.get('pins',{}).get(pin)==net for pin,net in p['pins'].items()))
        check(ref+' footprint preserved',o.get('footprint')==p['footprint'])
    for i,b in [(1,5600),(2,5800)]:
        p=lambda r,n:observed[f'{r}{b+n}']['pins']
        pre=f'WBO{i}_'
        check(pre+'CAN polarity datasheet6L7H',p('U',5)['6']=='CAN2_L' and p('U',5)['7']=='CAN2_H')
        check(pre+'F042 pins PA11RX PA12TX',p('U',2)['21']==p('U',5)['4'] and p('U',2)['22']==p('U',5)['1'])
        check(pre+'F042 ADC pump/Nernst/virtualground',p('U',2)['6']==pre+'Un_sense' and p('U',2)['8']==pre+'Ip_sense' and p('U',2)['9']==pre+'Vm')
        check(pre+'F042 heaterPA7',p('U',2)['13']==pre+'F042_HEATER_PWM')
        check(pre+'hardware inhibits heater directly',p('U',11)['1']=='HW_ACTUATOR_ENABLE_N' and p('U',11)['5']=='+5V_CORE')
        check(pre+'individualF7permission andF042PWM',p('U',10)['1']==pre+'F042_HEATER_PWM' and p('U',10)['2']==pre+'HEATER_PWM' and p('U',10)['4']==p('U',11)['2'])
        check(pre+'gate signal resistor and pulldown',p('R',22)['2']==p('U',11)['4'] and p('R',22)['1']==p('Q',0)['1'] and p('R',45)['1']==p('Q',0)['1'] and p('R',45)['2']=='GND')
        check(pre+'Hminus actual powerdrain pin2',p('Q',0)['2']==f'HARNESS_WBO{i}_CONTACT3' and p('Q',0)['3']=='GND')
        check(pre+'diode ST DPAK1NC2K3A',p('D',10).get('1') is None and p('D',10)['2']==f'HARNESS_WBO{i}_CONTACT4' and p('D',10)['3']=='VBAT_MAIN_FUSED')
        check(pre+'Bosch sensor1pump5trim shunt',set(p('R',9).values())=={f'HARNESS_WBO{i}_CONTACT1',f'HARNESS_WBO{i}_CONTACT5'})
        check(pre+'Bosch sensor2VM separate fromGND',f'HARNESS_WBO{i}_CONTACT2' in p('R',6).values() and 'GND' not in p('R',6).values())
        check(pre+'Bosch sensor6Nernst',p('U',0)['10']==f'HARNESS_WBO{i}_CONTACT6')
        check(pre+'local3V3 rail isolated',p('U',4)['2']==pre+'3V3' and p('U',2)['1']==pre+'3V3')
        check(pre+'reference3V3 distinct fromdigital3V3',p('U',3)['2']==pre+'VDDA' and p('U',2)['5']==pre+'VDDA')
        check(pre+'CAN termination DNP',parts[f'R{b+29}']['dnp'])
        check(pre+'WBO all functionalICs fitted',not any(x['dnp'] for ref,x in parts.items() if ref.startswith('U') and b<=int(ref[1:])<b+200))
    check('Index0 low/floating',parts['R5644']['pins']=={'1':'WBO1_SEL1','2':'GND'} and observed['U5602']['pins'].get('18') is None)
    check('Index1 floating/high',parts['R5844']['pins']=={'1':'WBO2_SEL2','2':'WBO2_3V3'} and observed['U5802']['pins'].get('15') is None)
    # Ensure semantic adaptation does not accidentally join the two sensor analog loops.
    check('No formerCJ125 paths',not any('CJ125' in p['value'] or 'VCCSS' in str(p['pins']) for p in parts.values()))
    topology=[]
    from copy import deepcopy
    for index,base in [(1,5600),(2,5800)]:
        problems,counts=source_partition_errors(observed,index)
        topology.append({'channel':index,**counts,'errors':problems})
        check(f'WBO{index} original source pinsets preserve every connectivity partition',not problems)
        errors.extend(problems)
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

