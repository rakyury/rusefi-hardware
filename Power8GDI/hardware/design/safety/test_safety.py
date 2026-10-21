"""Offline connectivity/logic regressions; not analog simulation or physical qualification."""
from copy import deepcopy
from pathlib import Path
import itertools
import json
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent

def lookup(tree):
    return {(node.attrib['ref'],node.attrib['pin']):n.attrib['name'] for n in tree.findall('.//nets/net') for node in n.findall('node')}

def gate_errors(tree):
    actual=lookup(tree);errors=[]
    for pin in ['1','19']:
        if actual.get(('U805',pin))!='HW_ACTUATOR_ENABLE_N':errors.append('unsafe_oe')
    for i,(a,y) in enumerate(zip([2,4,6,8,11,13,15,17],[18,16,14,12,9,7,5,3]),1):
        for pin,net in [(str(a),f'IGN{i}'),(str(y),f'IGN{i}_GATED')]:
            if actual.get(('U805',pin))!=net:errors.append('wrong_channel')
        if actual.get((f'R{820+i}','1'))!=f'IGN{i}_GATED' or actual.get((f'R{820+i}','2'))!='GND':errors.append('missing_pulldown')
    return errors

def step(q,previous_arm,arm,fault_n):
    # Datasheet D=1, /PRE=1 function table at valid supply and valid timings.
    return 0 if not fault_n else (1 if arm and not previous_arm else q)

class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree=ET.parse(HERE/'safety_gate.xml');cls.pins=lookup(cls.tree)

    def test_all_intended_nets_survive_export(self):
        parts=json.loads((HERE/'parts.json').read_text())
        self.assertEqual(len(self.tree.findall('.//components/comp')),33)
        for p in parts:
            comp=self.tree.find(f'.//components/comp[@ref="{p["ref"]}"]')
            self.assertEqual(comp.findtext('value'),p['value'])
            self.assertEqual(comp.findtext('footprint'),p['footprint'])
            for pin,net in p['pins'].items():
                if net:self.assertEqual(self.pins[(p['ref'],pin)],net)

    def test_supervisor_and_watchdog_fault_wired_or(self):
        for ref,pin in [('U801','7'),('U801','8'),('U802','1'),('U803','2'),('R801','1')]:
            self.assertEqual(self.pins[(ref,pin)],'SAFETY_FAULT_N')
        for pin in ['3','5']:self.assertEqual(self.pins[('U801',pin)],'+3V3')
        for ref,pin in [('U801','7'),('U801','8'),('U802','1')]:
            node=self.tree.find(f'.//nets/net/node[@ref="{ref}"][@pin="{pin}"]')
            self.assertEqual(node.attrib['pintype'],'open_collector')

    def test_latch_datasheet_pin_polarity(self):
        expected={'1':'SAFETY_ARM_REQUEST','2':'+3V3','3':'HW_ACTUATOR_ENABLE_N','4':'GND','5':'HW_ACTUATOR_ENABLE','6':'SAFETY_CLEAR_N','7':'+3V3','8':'+3V3'}
        for pin,net in expected.items():self.assertEqual(self.pins[('U804',pin)],net)
        self.assertEqual(self.pins[('U803','4')],'SAFETY_CLEAR_N')

    def test_eight_gate_channels_and_default_disable(self):
        self.assertEqual(gate_errors(self.tree),[])
        self.assertEqual(self.pins[('R805','1')],'HW_ACTUATOR_ENABLE_N')
        self.assertEqual(self.pins[('R805','2')],'+3V3')
        self.assertEqual(self.tree.find('.//components/comp[@ref="U805"]/value').text,'SN74LVC244AQPWRQ1')

    def test_regression_catches_oe_polarity_swap_and_missing_pd(self):
        tree=deepcopy(self.tree)
        n=tree.find('.//nets/net/node[@ref="U805"][@pin="1"]')
        parent=next(x for x in tree.findall('.//nets/net') if n in list(x));parent.remove(n)
        tree.find('.//nets/net[@name="HW_ACTUATOR_ENABLE"]').append(n)
        self.assertIn('unsafe_oe',gate_errors(tree))
        tree=deepcopy(self.tree)
        n=tree.find('.//nets/net/node[@ref="R821"][@pin="2"]')
        next(x for x in tree.findall('.//nets/net') if n in list(x)).remove(n)
        self.assertIn('missing_pulldown',gate_errors(tree))

    def test_every_electrical_pin_exists_in_footprint(self):
        manifest=json.loads((HERE/'footprint_manifest.json').read_text())
        for p in json.loads((HERE/'parts.json').read_text()):
            self.assertFalse(set(p['pins'])-set(manifest[p['footprint']]['pads']),p['ref'])
        self.assertIn('9',manifest['Package_SON:VSON-8-1EP_3x3mm_P0.65mm_EP1.6x2.4mm']['pads'])

    def test_fault_clear_without_new_arm_does_not_reenable(self):
        q=step(0,0,1,True);self.assertEqual(q,1)
        q=step(q,1,1,False);self.assertEqual(q,0)
        q=step(q,1,1,True);self.assertEqual(q,0)
        q=step(q,1,0,True);self.assertEqual(q,0)
        q=step(q,0,1,True);self.assertEqual(q,1)

    def test_async_clear_dominates_and_rejected_arm_not_queued(self):
        for q,old,arm in itertools.product([0,1],repeat=3):self.assertEqual(step(q,old,arm,False),0)
        self.assertEqual(step(step(0,0,1,False),1,1,True),0)
        # Both banks suppress all 256 raw combinations while disabled.
        for raw in range(256):self.assertEqual(raw if step(1,1,1,False) else 0,0)

    def test_watchdog_cap_margin_and_timing(self):
        data=json.loads((HERE/'interface.json').read_text())['watchdog_ms']
        self.assertGreaterEqual(data['capacitor_pf']*.99,100)
        self.assertAlmostEqual(data['nominal'],64.288)
        self.assertLess(data['with_cap_tolerance_min'],data['nominal'])
        self.assertGreater(data['with_cap_tolerance_max'],data['nominal'])

    def test_no_pt_enable_or_unqualified_rail_connection(self):
        self.assertFalse(any('DRVEN' in x or 'VBAT' in x or '5V' in x for x in self.pins.values()))
        self.assertEqual(json.loads((HERE/'interface.json').read_text())['release_status'],'BLOCKED')

if __name__=='__main__':unittest.main(verbosity=2)
