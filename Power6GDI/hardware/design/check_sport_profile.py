"""Independent scope audit of real KiCad-exported connectivity for Power6GDI."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent


def check(path=HERE/'core.net'):
    root=ET.parse(path); parts={c.get('ref'):c.findtext('value') for c in root.findall('components/comp')}
    pins={(p.get('ref'),p.get('pin')):n.get('name') for n in root.findall('nets/net') for p in n.findall('node')}
    errors=[]
    def require(ok,message):
        if not ok: errors.append(message)
    counts=Counter(parts.values())
    for value,count in {'MC33PT2001AE':2,'STM32F767IIT6':1,'STGB18N40LZT4':6,
                        'TLE9201SG':2,'TLE9104SHXUMA1':6,'STM32F042K6T6':1,
                        'TPIC8101DWR':1,'TCAN1042HGVDRQ1':2,'TLIN1029ADRQ1':2}.items():
        require(counts[value]==count,f'{value}: expected {count}, found {counts[value]}')
    forbidden=re.compile(r'^(?:HARNESS_)?(?:DI[78](?:_|$)|PI[78](?:_|$)|IGN[78](?:_|$)|WBO2_|MOTOR[34]_)')
    require(not any(forbidden.match(n) for n in pins.values()),'Removed channel net still exists')
    for bank,first,ref,pump in [('A',1,'U201','HPFP1'),('B',4,'U301','HPFP2')]:
        for i in range(3): require(pins.get((ref,str(4+i)))==f'DI{first+i}',f'{ref} START{i+1} map')
        bias='R297' if bank=='A' else 'R397'
        require(pins.get((ref,'7'))==f'PT{bank}_UNUSED_START4',f'{ref} unused START4 net')
        require(pins.get((bias,'1'))==f'PT{bank}_UNUSED_START4' and pins.get((bias,'2'))=='GND',f'{ref} START4 external pull-down')
        require(parts.get(bias)=='10k 1%',f'{bias} pull-down value')
        require(pins.get((ref,'9'))==pump,f'{ref} START6 pump map')
        for pin in ['35','44']:require(pins.get((ref,pin),'').startswith('unconnected-'),f'{ref}.{pin} unused channel must be NC')
    require(pins.get(('U6190','2'))=='EWG_SPI_SO','Two-device motor diagnostic chain must end at EWG')
    for ref in ['U6100','U6150','U5802','Q210','Q310','Q5540','Q5560']: require(ref not in parts,f'Removed physical part {ref} remains')
    for pin in ['4','17']:require(pins.get(('U1106',pin))=='+3V3','Unused active-low TLE9104 inputs must be held OFF')
    for pin in ['10','11']:require(pins.get(('U1106',pin),'').startswith('unconnected-'),'Unused TLE9104 power outputs must not reach harness')
    connector_nc=sum(n.startswith('unconnected-') for (ref,_),n in pins.items() if ref in ['J601','J602','J603','J604'])
    require(connector_nc==18,f'Expected 18 unconnected harness contacts, found {connector_nc}')
    return {'profile':'2026-10-25-sport-gdi6','status':'FAIL' if errors else 'PASS_STATIC_SCOPE',
        'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'components':len(parts),
        'counts':{'DI':6,'PI':6,'HPFP':2,'IGN':6,'DBW':1,'EWG':1,'onboard_lambda':1,
                  'knock_inputs':2,'external_CAN_buses':2,'LIN_buses':2,'SENT_inputs':4,
                  'low_side_outputs':22,'unused_internal_low_side_outputs':2,'unused_harness_contacts':connector_nc},
        'errors':errors,'hardware_qualified':False,'manufacturing_release':'BLOCKED'}


if __name__=='__main__':
    result=check();(HERE/'sport_profile_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2));raise SystemExit(bool(result['errors']))
