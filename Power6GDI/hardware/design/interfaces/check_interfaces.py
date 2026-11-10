"""Check exported KiCad connectivity and source-derived electrical invariants.

Exit0: structure only. --release always exits2 while explicit gates remain.
Does not claim circuit simulation, EMC qualification or successful root integration.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from core_schlib import parse,children,child


def read_netlists(directory=HERE):
    components={}; pins={}; source_pins={}
    for filename in ['comms2','usb_fs','sd_spi','sensor_power','digital_aux_1']:
        root=ET.parse(directory/(filename+'.xml')).getroot()
        libparts={p.get('part'):p for p in root.findall('./libparts/libpart')}
        for comp in root.findall('./components/comp'):
            ref=comp.get('ref')
            if ref in components: raise ValueError('Duplicate component '+ref)
            components[ref]={"value":comp.findtext('value'),"footprint":comp.findtext('footprint'),
                "dnp":any(p.get('name')=='dnp' for p in comp.findall('property'))}
            lib=libparts[comp.find('libsource').get('part')]
            source_pins[ref]={p.get('num'):p.get('name') for p in lib.findall('./pins/pin')}
        for net in root.findall('./nets/net'):
            for node in net.findall('node'):
                key=(node.get('ref'),node.get('pin'))
                if key in pins: raise ValueError('Pin in two nets: '+repr(key))
                pins[key]=net.get('name')
    return components,pins,source_pins


def electrical_checks(components,pins):
    errors=[]
    def expect(ref,pad,net):
        if pins.get((ref,str(pad)))!=net:
            errors.append(f'{ref}.{pad}: expected {net}, got {pins.get((ref,str(pad)))}')
    def dnp(ref,state=True):
        if components[ref]['dnp']!=state: errors.append(f'{ref}: required DNP={state}')
    # TI SLLSES9D Table6-1: HGV has VIO pad5, CANL6/CANH7.
    for pad,net in {1:'CAN2_TX',2:'GND',3:'+5V_CORE',4:'CAN2_RX',5:'+3V3',6:'CAN2_L',7:'CAN2_H',8:'CAN2_STB'}.items(): expect('U1501',pad,net)
    expect('R1501',1,'+3V3');expect('R1501',2,'CAN2_STB');dnp('R1502')
    # TI SLLSFK8A: RXD open-drain requires3V3 pullup, EN defaults low.
    for pad,net in {1:'LIN2_RX',2:'LIN2_EN',4:'LIN2_TX',5:'GND',6:'LIN2_BUS',7:'LIN2_VSUP'}.items():expect('U1502',pad,net)
    expect('R1503',1,'+3V3');expect('R1503',2,'LIN2_RX')
    expect('R1504',1,'LIN2_EN');expect('R1504',2,'GND')
    dnp('D1502',False);dnp('R1507',False)
    expect('D1502',1,'LIN2_VSUP');expect('D1502',3,'LIN2_COMMANDER_DIODE')
    expect('R1507',1,'LIN2_COMMANDER_DIODE');expect('R1507',2,'LIN2_BUS')
    if components['R1507']['footprint']!='Resistor_SMD:R_1206_3216Metric':errors.append('LIN commander pullup power footprint insufficient')
    # ST DS4260 diagram; the pairs1/6 and3/4 are feedthrough, not separate channels.
    for ref,a,b,vbus in [('D1510','USB_DP','USB_DM','USB_HOST_VBUS'),('D1520','SD_SCK_CARD','SD_MOSI_CARD','SD_3V3'),('D1521','SD_CS','SD_SPI3_MISO','SD_3V3')]:
        for pad,net in {1:a,6:a,3:b,4:b,2:'GND',5:vbus}.items():expect(ref,pad,net)
    for pad,net in {1:'USB_HOST_VBUS',2:'USB_DM',3:'USB_DP',5:'GND',6:'USB_SHIELD'}.items():expect('J1501',pad,net)
    # AN4879 MOSFET detector: no positive-rail link or divider directly into PA9.
    for pad,net in {1:'USB_VBUS_GATE',2:'GND',3:'USB_VBUS_PRESENT_N'}.items():expect('Q1510',pad,net)
    expect('R1512',1,'+3V3');expect('R1512',2,'USB_VBUS_PRESENT_N');dnp('R1513')
    if pins.get(('J1501','1')) in ('+3V3','+5V_CORE'): errors.append('USB host backfeeds ECU supply')
    # Molex SD-104031-001 pinmap + official footprint switch/shell numbering.
    for pad,net in {1:'SD_DAT2',2:'SD_CS',3:'SD_MOSI_CARD',4:'SD_3V3',5:'SD_SCK_CARD',6:'GND',7:'SD_SPI3_MISO',8:'SD_DAT1',9:'SD_CD',10:'GND',11:'GND'}.items():expect('J1502',pad,net)
    # TI SLVSCP3D DDA Table4-1 and Fig6-2. Input isolation cannot be reversed.
    for i,bank in enumerate('AB'):
        ref=f'U{1530+i}';rail='SENSOR_5V_'+bank;vin='SENSOR_'+bank+'_IN'
        for pad,net in {1:rail,3:'GND',4:rail,5:'+5V_CORE',6:'GND',8:vin,9:'GND'}.items():expect(ref,pad,net)
        expect(f'D{1530+i}',1,vin);expect(f'D{1530+i}',2,'VBAT_LOGIC_PROTECTED')
        if '22u 50V' not in components[f'C{1533+5*i}']['value']:errors.append('Tracker output capacitor must retain specified22u/50V candidate and effective-capacitance gate')
    for i,bank in enumerate('ABC'):
        expect(f'R{1530+i}',1,'HARNESS_SENSOR_GND_'+bank);expect(f'R{1530+i}',2,'GND');dnp(f'R{1530+i}',False)
    channels=['HALL1','HALL2','HALL3','HALL4','FLEX_FREQ']
    for i,name in enumerate(channels):
        ref=f'U{1600+i//6}';j=i%6
        expect(ref,[1,3,5,9,11,13][j],name+'_FILTERED');expect(ref,[2,4,6,8,10,12][j],name)
        expect(f'R{1600+3*i}',1,'HARNESS_'+name);expect(f'R{1600+3*i}',2,name+'_FILTERED')
        for pad,net in {1:'GND',2:'+5V_CORE',3:name+'_FILTERED'}.items():expect(f'D{1600+i}',pad,net)
        dnp(f'R{1602+3*i}')
    return errors


def check(directory=HERE,footprints=False):
    manifest=json.loads((directory/'interfaces_manifest.json').read_text())
    components,pins,source_pins=read_netlists(directory)
    errors=electrical_checks(components,pins)
    expected={p['ref']:p for p in manifest['parts']}
    if set(components)!=set(expected): errors.append('Export/manifest component set mismatch')
    for ref,part in expected.items():
        if components.get(ref,{}).get('footprint')!=part['footprint']:errors.append('Wrong footprint '+ref)
        if set(part['physical_pins'])!=set(source_pins[ref]):errors.append('Wrong physical pin set '+ref)
        if components[ref]['dnp']!=part['dnp']:errors.append('Export/manifest DNP differs '+ref)
        for pad,net in part['pins'].items():
            if pins.get((ref,pad))!=net:errors.append(f'Export/manifest mismatch {ref}.{pad}')
        for pad in set(source_pins[ref])-set(part['pins']):
            if not pins.get((ref,pad),'unconnected-').startswith('unconnected-'):errors.append(f'Intended NC is connected {ref}.{pad}')
    corelib=parse((directory.parent/'core_sources/core_selected.kicad_sym').read_text())
    mcusym=next(s for s in children(corelib,'symbol') if str(s[1]).split(':')[-1]=='STM32F767IIT6')
    pin_names={str(child(p,'number')[1]):str(child(p,'name')[1]) for unit in children(mcusym,'symbol') for p in children(unit,'pin')}
    seen=set()
    for row in manifest['gpio_contract']:
        pin=row['stm32_pin']
        if pin in seen:errors.append('Duplicate GPIO '+pin)
        seen.add(pin)
        if pin_names.get(str(row['package_pad']))!=pin:errors.append('Wrong package pad '+pin)
    contract={r['function']:r for r in manifest['gpio_contract']}
    if (contract['SENT3']['stm32_pin'],contract['SENT3']['package_pad'])!=('PE11',74):errors.append('SENT3 not safely remapped from CAN2_TX')
    if manifest['harness_aliases'].get('HARNESS_LIN2_BUS')!='LIN2_BUS':errors.append('LIN2 harness alias absent')
    if manifest['harness_aliases'].get('HARNESS_CHASSIS_GND')!='USB_SHIELD':errors.append('Chassis alias absent')
    erc=Counter()
    for info in manifest['sheets']:
        name=info['name'].split('/')[-1]
        data=json.loads((directory/(name+'_erc.json')).read_text())
        for sheet in data['sheets']:
            for v in sheet['violations']:erc[v['type']]+=1
    unexpected=set(erc)-{'power_pin_not_driven','pin_not_driven','global_label_dangling'}
    if unexpected:errors.append('Unexpected ERC types: '+','.join(sorted(unexpected)))
    fp_checked=0
    if footprints:
        import pcbnew
        for ref,p in expected.items():
            lib,name=p['footprint'].split(':')
            path=directory/'Power8GDI_Interfaces.pretty' if lib=='Power8GDI_Interfaces' else Path('/usr/share/kicad/footprints')/(lib+'.pretty')
            fp=pcbnew.FootprintLoad(str(path),name)
            if fp is None:errors.append('Footprint cannot load: '+p['footprint']);continue
            pads={pad.GetNumber() for pad in fp.Pads() if pad.GetNumber()}
            if pads!=set(p['physical_pins']):errors.append(f'{ref}: pad set {pads} != symbol {set(p["physical_pins"])}')
            if lib=='Power8GDI_Interfaces':
                # Independent source dimensions from TI4231348/A, not pad-count only.
                ep={tuple(round(v/1e6,3) for v in (pad.GetSize().x,pad.GetSize().y)) for pad in fp.Pads() if pad.GetNumber()=='9'}
                if ep!={(2.95,4.9),(2.6,3.2)}:errors.append(ref+': DDA central copper/mask dimensions differ from source')
                for pad in fp.Pads():
                    if pad.GetNumber() in {'1','2','3','4','5','6','7','8'}:
                        if tuple(round(v/1e6,3) for v in (pad.GetSize().x,pad.GetSize().y))!=(1.55,0.6):errors.append(ref+': DDA lead land size mismatch')
            fp_checked+=1
    return {'structural_status':'PASS' if not errors else 'FAIL','release_status':'BLOCKED','components':len(components),
        'exported_connected_pins':sum(len(p['pins']) for p in expected.values()),'footprints_checked':fp_checked,
        'erc_findings':dict(sorted(erc.items())),'errors':errors,'release_blockers':manifest['blockers']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');parser.add_argument('--footprints',action='store_true');parser.add_argument('--report',type=Path)
    args=parser.parse_args();report=check(footprints=args.footprints)
    if args.report:args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 1 if report['errors'] else 2 if args.release else 0


if __name__=='__main__':raise SystemExit(main())
