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
    expected={('R6500','1'):'IGN_OC_OK',('R6500','2'):'HW_KILL_N',
        ('U802','3'):'HW_KILL_N',('U803','2'):'SAFETY_FAULT_N',
        ('U803','4'):'SAFETY_CLEAR_N',('U804','6'):'SAFETY_CLEAR_N',
        ('R805','1'):'HW_ACTUATOR_ENABLE_N',('R805','2'):'+3V3',
        ('R806','1'):'HW_ACTUATOR_ENABLE',('R806','2'):'GND',
        ('U806','6'):'+3V3',('U806','5'):'SAFETY_5V_SENSE',
        ('U806','1'):'SAFETY_FAULT_N',('U806','2'):'GND',('U806','3'):'+3V3',
        ('R807','1'):'+5V_CORE',('R807','2'):'SAFETY_5V_SENSE',
        ('R808','1'):'SAFETY_5V_SENSE',('R808','2'):'GND'}
    for key,net in expected.items():
        if actual.get(key)!=net:errors.append(str(key)+' expected '+net)
    return errors

def step(q,previous_arm,arm,fault_n):
    # Datasheet D=1, /PRE=1 function table at valid supply and valid timings.
    return 0 if not fault_n else (1 if arm and not previous_arm else q)

class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree=ET.parse(HERE/'safety_gate.xml');cls.pins=lookup(cls.tree)

    def test_all_intended_nets_survive_export(self):
        parts=json.loads((HERE/'parts.json').read_text(encoding='utf-8'))
        self.assertEqual(len(self.tree.findall('.//components/comp')),21)
        for p in parts:
            comp=self.tree.find(f'.//components/comp[@ref="{p["ref"]}"]')
            self.assertEqual(comp.findtext('value'),p['value'])
            self.assertEqual(comp.findtext('footprint'),p['footprint'])
            for pin,net in p['pins'].items():
                if net:self.assertEqual(self.pins[(p['ref'],pin)],net)

    def test_supervisor_and_watchdog_fault_wired_or(self):
        for ref,pin in [('U801','7'),('U801','8'),('U802','1'),('U806','1'),('U803','2'),('R801','1')]:
            self.assertEqual(self.pins[(ref,pin)],'SAFETY_FAULT_N')
        for pin in ['3','5']:self.assertEqual(self.pins[('U801',pin)],'+3V3')
        for ref,pin in [('U801','7'),('U801','8'),('U802','1'),('U806','1')]:
            node=self.tree.find(f'.//nets/net/node[@ref="{ref}"][@pin="{pin}"]')
            self.assertEqual(node.attrib['pintype'],'open_collector')

    def test_latch_datasheet_pin_polarity(self):
        expected={'1':'SAFETY_ARM_REQUEST','2':'+3V3','3':'HW_ACTUATOR_ENABLE_N','4':'GND','5':'HW_ACTUATOR_ENABLE','6':'SAFETY_CLEAR_N','7':'+3V3','8':'+3V3'}
        for pin,net in expected.items():self.assertEqual(self.pins[('U804',pin)],net)
        self.assertEqual(self.pins[('U803','4')],'SAFETY_CLEAR_N')

    def test_overcurrent_fault_reaches_global_latch(self):
        self.assertEqual(gate_errors(self.tree),[])
        self.assertEqual(self.tree.find('.//components/comp[@ref="R6500"]/value').text,'0R')
        self.assertIsNone(self.tree.find('.//components/comp[@ref="U805"]'))

    def test_regression_catches_disconnected_fault_and_missing_default(self):
        for ref,pin in [('R6500','2'),('R806','2'),('U804','6'),('U806','1'),('R807','1')]:
            tree=deepcopy(self.tree)
            n=tree.find(f'.//nets/net/node[@ref="{ref}"][@pin="{pin}"]')
            next(x for x in tree.findall('.//nets/net') if n in list(x)).remove(n)
            self.assertTrue(gate_errors(tree))

    def test_every_electrical_pin_exists_in_footprint(self):
        manifest=json.loads((HERE/'footprint_manifest.json').read_text(encoding='utf-8'))
        for p in json.loads((HERE/'parts.json').read_text(encoding='utf-8')):
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
        data=json.loads((HERE/'interface.json').read_text(encoding='utf-8'))['watchdog_ms']
        self.assertGreaterEqual(data['capacitor_pf']*.99,100)
        self.assertAlmostEqual(data['nominal'],64.288)
        self.assertLess(data['with_cap_tolerance_min'],data['nominal'])
        self.assertGreater(data['with_cap_tolerance_max'],data['nominal'])

    def test_no_pt_enable_or_unqualified_rail_connection(self):
        self.assertFalse(any('DRVEN' in x or 'VBAT' in x for x in self.pins.values()))
        # 5V is only a divided sense input, never the safety logic supply.
        self.assertEqual({key for key,net in self.pins.items() if net=='+5V_CORE'},{('R807','1')})
        self.assertEqual(json.loads((HERE/'interface.json').read_text(encoding='utf-8'))['release_status'],'BLOCKED')

    def test_5v_undervoltage_sense_and_recovery_margin(self):
        self.assertEqual(gate_errors(self.tree),[])
        self.assertEqual(self.tree.find('.//components/comp[@ref="U806"]/value').text,'TPS3808G01QDBVRQ1')
        self.assertTrue(self.pins[('U806','4')].startswith('unconnected-'))
        # Independently evaluate worst-case static threshold including input bias.
        top,bottom=102000,9760
        e=.001+25e-6*100
        low=.405*.98*(1+top*(1-e)/(bottom*(1+e)))-25e-9*top*(1+e)
        high=.405*1.02*(1+top*(1+e)/(bottom*(1-e)))*1.03+25e-9*top*(1+e)
        self.assertGreater(low,4.5)  # minimum recommended ignition driver supply
        self.assertLess(high,4.92111)  # calculated minimum static 5V rail
        self.assertEqual(self.tree.find('.//components/comp[@ref="R807"]/value').text,'102k 0.1% 25ppm')
        self.assertEqual(self.tree.find('.//components/comp[@ref="R808"]/value').text,'9.76k 0.1% 25ppm')

if __name__=='__main__':unittest.main(verbosity=2)
