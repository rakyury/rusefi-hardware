"""Audit cross-sheet boundaries in a real KiCad XML export, not drawing labels."""
from pathlib import Path
import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE/'board'))
from net_contract import read_netlists
from interfaces.check_interfaces import electrical_checks as interface_electrical_checks
from gdi.test_protection import protection_errors, gate_errors


def verify(path):
    parts,pins,_=read_netlists([path]);errors=[]
    def expect(ref,pin,net):
        if net is None and pins.get((ref,str(pin)),'').startswith('unconnected-'):return
        if pins.get((ref,str(pin)))!=net:errors.append(f'{ref}.{pin}: expected {net}; got {pins.get((ref,str(pin)))}')
    expected_refs=set()
    for rel in ['core_manifest.json','power_input/power_input_manifest.json','motor/motor_manifest.json','safety/parts.json','board/connector_manifest.json','interfaces/interfaces_manifest.json','interfaces_aux/parts.json','gdi/protection_manifest.json','wbo/parts.json']:
        manifest=json.loads((HERE/rel).read_text())
        entries=manifest if isinstance(manifest,list) else manifest['parts']
        for part in entries:
            ref=part['ref'];expected_refs.add(ref)
            if ref not in parts:errors.append('Missing '+ref);continue
            if parts[ref]['dnp']!=part['dnp']:errors.append(ref+': assembly DNP flag changed')
            if parts[ref]['value']!=part['value']:errors.append(ref+': value changed')
            for pin,net in part['pins'].items():expect(ref,pin,net)
    for stage in ['a','b']:
        local,connections,_=read_netlists([HERE/f'gdi/stage_{stage}.xml'])
        expected_refs.update(local)
        for ref,comp in local.items():
            if ref not in parts:errors.append('Missing '+ref);continue
            if parts[ref]['dnp']!=comp['dnp']:errors.append(ref+': GDI DNP flag changed')
            if parts[ref]['value']!=comp['value']:errors.append(ref+': GDI value changed')
        for (ref,pin),net in connections.items():
            if not net.startswith('unconnected-'):expect(ref,pin,net)
    if set(parts)!=expected_refs:errors.append('Integrated component set differs from leaf manifests')
    errors.extend(interface_electrical_checks(parts,pins))
    tree=ET.parse(path)
    for stage in 'AB':errors.extend(protection_errors(tree,stage))
    errors.extend(gate_errors(tree))
    for ref,net in [('U201','HPFP1'),('U301','HPFP2')]:expect(ref,9,net)
    # CAN WBO MCU permissions must be distinct from local heater PWM.
    for net in ['WBO1_CS_N','WBO2_CS_N','WBO_ADC_CS_N','WBO_RESET_N_5V']:
        if net in pins.values():errors.append('Obsolete WBO SPI control remains: '+net)
    for route in json.loads((HERE/'interfaces/interfaces_manifest.json').read_text())['gpio_contract']:
        expect('U101',route['package_pad'],route['function'])
    # Independent pin facts: TI SN74LVC244A-Q1 and MIC4427, plus STM32 DS11532.
    gate_inputs=[2,4,6,8,11,13,15,17];gate_outputs=[18,16,14,12,9,7,5,3]
    for i,(inp,out) in enumerate(zip(gate_inputs,gate_outputs),1):
        expect('U805',inp,f'IGN{i}');expect('U805',out,f'IGN{i}_GATED')
        expect('U'+str(110+(i-1)//2),2 if i%2 else 4,f'IGN{i}_GATED')
        if not parts[f'R{127+i}']['dnp']:errors.append(f'IGN{i} output link must remain DNP')
    for pad,net in [(45,'SAFETY_HEARTBEAT'),(46,'SAFETY_ARM_REQUEST'),(83,'SAFETY_FAULT_N')]:expect('U101',pad,net)
    for base,channel in [(900,'DBW'),(950,'EWG')]:
        expect(f'U{base+10}',1,'HW_ACTUATOR_ENABLE')
        expect(f'U{base+1}',3,channel+'_IN1_GATED');expect(f'U{base+1}',2,channel+'_IN2_GATED')
    # MAX9924 Rev5 Mode A2 and 3V3 open-drain pull-up.
    for pad in [4,5,6,9]:expect('U731',pad,'GND')
    expect('U731',10,'+5V_CORE');expect('U731',7,'CRANK');expect('R792',1,'+3V3')
    # No vehicle-side harness may bypass its frontend directly to MCU.
    for (ref,pin),net in pins.items():
        if ref=='U101' and net.startswith('HARNESS_'):errors.append('Harness directly on MCU pad '+pin)
    connector_rows=list(csv.DictReader((HERE.parents[1]/'pinout/power8gdi_revA_pinout.csv').read_text(encoding='utf-8').splitlines()))
    aliases={r['pinout_net']:r['board_net'] for r in csv.DictReader((HERE/'board/connector_aliases.csv').read_text(encoding='utf-8').splitlines())}
    for row in connector_rows:expect('J60'+str('ABCD'.index(row['connector'])+1),row['position'],aliases.get(row['net'],'HARNESS_'+row['net']))
    counts={}
    for net in pins.values():counts[net]=counts.get(net,0)+1
    return {'status':'FAIL' if errors else 'PASS_STATIC_INTEGRATION','components':len(parts),'exported_pins':len(pins),
            'dnp_components':sum(p['dnp'] for p in parts.values()),'errors':errors,
            'unimplemented_harness_nets':sorted(n for n,c in counts.items() if n.startswith('HARNESS_') and c==1),
            'release_status':'BLOCKED','hardware_tested':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--netlist',type=Path,default=HERE/'core.net');parser.add_argument('--release',action='store_true')
    a=parser.parse_args();result=verify(a.netlist)
    (HERE/'integration_checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
    raise SystemExit(2 if a.release else bool(result['errors']))
