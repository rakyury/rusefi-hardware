"""Actual KiCad netlist checks for power direction and independent permission.

Mutation tests cover reversed FET, grounded thermal pad and an ungated enable.
No simulation or physical qualification is implied.
"""
from copy import deepcopy
from pathlib import Path
import json
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def pins(tree):
    return {(n.get('ref'), n.get('pin')): net.get('name')
            for net in tree.findall('.//nets/net') for n in net.findall('node')}


def protection_errors(tree, stage):
    base = 5000 if stage == 'A' else 5050
    pin = pins(tree); errors = []
    p = f'GDI_{stage}_'; raw=f'VBAT_GDI_{stage}_FUSED'; rail=f'VBAT_GDI_{stage}'
    expected = {
        'U'+str(base+1): {1:p+'DGATE',2:raw,3:raw,4:p+'SW',5:p+'OV',6:p+'POWER_EN',
                          7:'GND',8:p+'HGATE',9:rail,10:p+'MID',11:p+'CAP',12:p+'MID'},
        'Q'+str(base+1): {1:p+'DGATE',2:p+'MID',3:raw},
        'Q'+str(base+2): {1:p+'HGATE',2:p+'MID',3:rail},
        'C'+str(base+1): {1:p+'MID',2:'GND'},
        'C'+str(base+2): {1:p+'CAP',2:p+'MID'},
        'R'+str(base+1): {1:p+'SW',2:p+'OV'},
        'R'+str(base+2): {1:p+'OV',2:'GND'},
        'R'+str(base+3): {1:'HW_ACTUATOR_ENABLE',2:p+'POWER_EN'},
        'R'+str(base+4): {1:p+'POWER_EN',2:'GND'},
    }
    for ref, nets in expected.items():
        for number, net in nets.items():
            if pin.get((ref,str(number))) != net:
                errors.append(f'{ref}.{number} expected {net}')
    ep=pin.get(('U'+str(base+1),'13'), '')
    if not ep.startswith('unconnected-'):
        errors.append('LM74800 exposed pad must be electrically floating')
    ep_nodes = [n for n in tree.findall('.//nets/net') if n.get('name')==ep]
    if len(ep_nodes)!=1 or len(ep_nodes[0].findall('node'))!=1:
        errors.append('Floating pad has another circuit connection')
    if raw == rail or p+'MID' in (raw,rail):
        errors.append('Protection power path bypass')
    return errors


def gate_errors(tree):
    lookup=pins(tree); errors=[]
    expected={1:'PTA_DRVEN',2:'HW_ACTUATOR_ENABLE',7:'PTA_DRVEN_GATED',
              5:'PTB_DRVEN',6:'HW_ACTUATOR_ENABLE',3:'PTB_DRVEN_GATED',8:'+3V3',4:'GND'}
    for number, net in expected.items():
        if lookup.get(('U5101',str(number)))!=net:
            errors.append(f'Gate pin{number} mismatch')
    for i,net in enumerate(['PTA_DRVEN','PTB_DRVEN','PTA_DRVEN_GATED','PTB_DRVEN_GATED',
                            'PTA_DEVICE_DRVEN','PTB_DEVICE_DRVEN'],1):
        if [lookup.get((f'R510{i}',str(p))) for p in (1,2)] != [net,'GND']:
            errors.append(f'{net} missing default-off resistor')
    return errors


def move_pin(tree, ref, number, dest):
    node=tree.find(f'.//nets/net/node[@ref="{ref}"][@pin="{number}"]')
    parent=next(n for n in tree.findall('.//nets/net') if node in list(n))
    parent.remove(node)
    next(n for n in tree.findall('.//nets/net') if n.get('name')==dest).append(node)


class ProtectionTests(unittest.TestCase):
    def test_banks_match_manufacturer_pin_map(self):
        for stage in 'AB':
            self.assertEqual(protection_errors(ET.parse(HERE/f'protection_{stage.lower()}.xml'),stage),[])

    def test_faults_rejected(self):
        original=ET.parse(HERE/'protection_a.xml')
        for ref,pin,dest in [('Q5001','3','GDI_A_MID'),('U5001','13','GND'),
                              ('C5002','2','GND'),('U5001','6','VBAT_GDI_A_FUSED')]:
            with self.subTest(ref=ref,pin=pin):
                bad=deepcopy(original); move_pin(bad,ref,pin,dest)
                self.assertTrue(protection_errors(bad,'A'))

    def test_no_shared_power_nodes_between_banks(self):
        a,b=(pins(ET.parse(HERE/f'protection_{s}.xml')) for s in 'ab')
        self.assertEqual(set(a.values()) & set(b.values()),{'GND','HW_ACTUATOR_ENABLE'})

    def test_gate_and_device_pulldowns(self):
        tree=ET.parse(HERE/'permission.xml')
        self.assertEqual(gate_errors(tree),[])
        move_pin(tree,'U5101','2','+3V3')
        self.assertTrue(gate_errors(tree))

    def test_static_ov_bounds_below_regulator_normal_max(self):
        data=json.loads((HERE/'protection_manifest.json').read_text())
        bounds=data['ov_rising_v']
        low=1.195*(1+140000*.999/(10000*1.001))-200e-9*(140000*1.001+46)
        high=1.267*(1+(140000*1.001+46)/(10000*.999))+200e-9*(140000*1.001+46)
        self.assertAlmostEqual(bounds['min_static'],low)
        self.assertAlmostEqual(bounds['max_static'],high)
        self.assertLess(high,20.0)
        self.assertGreater(low,17.0)
        self.assertFalse(data['hardware_tested'])

    def test_manifest_exports_no_missing_parts_or_dnp_additions(self):
        manifest=json.loads((HERE/'protection_manifest.json').read_text())
        self.assertEqual(len(manifest['parts']),42)
        for sheet in manifest['sheets']:
            tree=ET.parse(HERE/(Path(sheet['name']).name+'.xml'))
            actual={c.get('ref'):c for c in tree.findall('.//components/comp')}
            rows=[p for p in manifest['parts'] if p['sheet']==sheet['name']]
            self.assertEqual(set(actual),{p['ref'] for p in rows})
            for p in rows:
                self.assertIsNone(actual[p['ref']].find('property[@name="dnp"]'))
                self.assertEqual(actual[p['ref']].findtext('footprint'),p['footprint'])


if __name__=='__main__':
    unittest.main(verbosity=2)
