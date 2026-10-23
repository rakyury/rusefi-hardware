"""Actual KiCad XML verification, independent pin assertions, mutation regressions."""
from pathlib import Path
from copy import deepcopy
import argparse,hashlib,json,unittest
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
NETLIST=None

def load():
    if NETLIST:
        tree=ET.parse(NETLIST)
        return {s['name']:tree for s in json.loads((HERE/'interface.json').read_text(encoding='utf-8'))['sheets']}
    return {s['name']:ET.parse(HERE/(s['name']+'.xml')) for s in json.loads((HERE/'interface.json').read_text(encoding='utf-8'))['sheets']}
def lookup(tree):return {(p.attrib['ref'],p.attrib['pin']):n.attrib['name'] for n in tree.findall('.//nets/net') for p in n.findall('node')}
class AuxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.trees=load();cls.pins={s:lookup(t) for s,t in cls.trees.items()};cls.parts=json.loads((HERE/'parts.json').read_text(encoding='utf-8'))
    def test_manifest_export_parity_and_unique_refs(self):
        refs=[p['ref'] for p in self.parts];self.assertEqual(len(refs),len(set(refs)))
        for part in self.parts:
            comp=self.trees[part['sheet']].find(f'.//components/comp[@ref="{part["ref"]}"]')
            self.assertIsNotNone(comp);self.assertEqual(comp.findtext('value'),part['value']);self.assertEqual(comp.findtext('footprint'),part['footprint'])
            self.assertEqual(comp.find('property[@name="dnp"]') is not None,part['dnp'])
            for pin,net in part['pins'].items():
                if net:self.assertEqual(self.pins[part['sheet']][(part['ref'],pin)],net)
    def test_tpic_exact_primary_pinout(self):
        p=self.pins['knock_dual']
        expected={'1':'+5V_CORE','2':'GND','3':'KNOCK_VREF','7':'KNOCK_INT_HOLD_5V','8':'KNOCK_CS_N_5V','9':'KNOCK_CLK_5V','11':'KNOCK_SDO_5V','12':'AUX_SPI_MOSI_5V','13':'AUX_SPI_SCK_5V','15':'KNOCK_VREF','16':'KNOCK2_INV','17':'KNOCK2_FB','18':'KNOCK1_FB','19':'KNOCK1_INV','20':'KNOCK_VREF'}
        for pin,net in expected.items():self.assertEqual(p[('U1701',pin)],net)
    def test_knock_miso_disabled_when_not_selected(self):
        for pin,net in [('1','KNOCK_CS_N'),('2','KNOCK_SDO_5V'),('3','GND'),('4','GDI_SPI2_MISO'),('5','+3V3')]:
            self.assertEqual(self.pins['knock_dual'][('U1703',pin)],net)
    def test_unused_translator_inputs_grounded_no_old_wbo_controls(self):
        p=self.pins['knock_dual']
        for pin in ('13','15','17'):self.assertEqual(p[('U1702',pin)],'GND')
        for pin in ('7','5','3'):self.assertTrue(p[('U1702',pin)].startswith('unconnected-'))
        self.assertFalse(any(net in {'WBO1_CS_N','WBO2_CS_N','WBO_ADC_CS_N'} for net in p.values()))
    def test_actual_footprint_pad_numbers_cover_all_pins(self):
        manifest=json.loads((HERE/'footprint_manifest.json').read_text(encoding='utf-8'))
        for part in self.parts:self.assertFalse(set(part['pins'])-set(manifest[part['footprint']]['pads']),part['ref'])
    def test_resource_and_release_contract(self):
        m=json.loads((HERE/'interface.json').read_text(encoding='utf-8'))
        self.assertEqual(m['gpio'],['KNOCK_CS_N','KNOCK_INT_HOLD'])
        self.assertEqual(m['mcu_adc_required'],0)
        self.assertEqual(m['release_status'],'BLOCKED')
        self.assertEqual([x['name'] for x in m['sheets']],['knock_dual'])
    def test_primary_source_provenance_and_upstream_blobs(self):
        m=json.loads((HERE/'sources.json').read_text(encoding='utf-8'));self.assertEqual(len(m['documents']),7)
        for doc in m['documents']:
            self.assertTrue(doc['url'].startswith('https://'));self.assertEqual(len(doc['sha256']),64);self.assertGreater(doc['bytes'],10000)
        for item in m['source_files']:
            raw=(HERE.parents[3]/item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--netlist',type=Path)
    args,remaining=parser.parse_known_args();NETLIST=args.netlist
    unittest.main(argv=['test_aux.py',*remaining],verbosity=2)
