"""Reviewed GDI source mapping; no hardware action. Readiness stays blocked."""
from pathlib import Path
import argparse,json,sys
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
def check(tree,bank):
    pins={(n.attrib['ref'],n.attrib['pin']):net.attrib['name'] for net in tree.findall('.//nets/net') for n in net.findall('node')}
    errors=[];ic=bank['ic_ref']
    def pin(ref,number,expected):
        got=pins.get((ref,number))
        if got!=expected:errors.append(f'{ref}.{number}: expected {expected}, got {got}')
    def fit(ref,dnp):
        comp=tree.find(f'.//components/comp[@ref="{ref}"]')
        if comp is None or (comp.find('property[@name="dnp"]') is not None)!=dnp:errors.append(f'{ref}: expected DNP={dnp}')
    for channel in bank['injectors']:
        for p,n in [('start_pin','start_net'),('positive_monitor_pin','positive_net'),('negative_monitor_pin','negative_net')]:pin(ic,channel[p],channel[n])
    p=bank['pump'];pin(ic,p['start_pin'],p['start_net']);pin(ic,p['positive_monitor_pin'],p['positive_net']);pin(p['negative_fet_ref'],p['negative_fet_drain_pin'],p['negative_net'])
    fit(p['drain_sense_link_ref'],False);fit(p['alternate_injector6_link_ref'],True)
    pin(p['drain_sense_link_ref'],'1',p['negative_net'])
    if pins.get((p['drain_sense_link_ref'],'2'))!=pins.get((ic,p['drain_sense_ic_pin'])):errors.append('pump drain sense link disconnected')
    pin(ic,bank['unused_start5_pin'],bank['unused_start5_net']);pin(ic,bank['enable_ic_pin'],bank['enable_ic_net']);fit(bank['enable_isolation_ref'],True)
    pin(ic,bank['battery_ic_pin'],bank['battery_net'])
    for control in bank['controls'].values():pin(ic,control['pin'],control['net'])
    return errors
def main():
    p=argparse.ArgumentParser();p.add_argument('--netlist',type=Path);p.add_argument('--require-ready',action='store_true');a=p.parse_args()
    contract=json.loads((HERE/'gdi_output_contract.json').read_text());errors=[]
    for bank in contract['banks']:
        path=a.netlist or HERE.parent/'gdi'/('stage_'+bank['stage'].lower()+'.xml')
        tree=ET.parse(path);errors.extend(check(tree,bank))
        mutated=ET.fromstring(ET.tostring(tree.getroot()))
        for n in mutated.findall('.//nets/net'):
            if any(x.attrib['ref']==bank['ic_ref'] and x.attrib['pin']=='9' for x in n.findall('node')):n.attrib['name']='WRONG_START5'
        if not check(ET.ElementTree(mutated),bank):errors.append('START swap mutation not rejected')
    if errors:print('\n'.join(errors),file=sys.stderr);return 1
    print('GDI mapping PASS:2 banks,8 DI start/output paths,2 pump source paths; START swap regressions rejected. Release BLOCKED.')
    return 2 if a.require_ready else 0
if __name__=='__main__':raise SystemExit(main())
