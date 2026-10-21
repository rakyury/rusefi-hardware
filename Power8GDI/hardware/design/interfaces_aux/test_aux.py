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
        return {s['name']:tree for s in json.loads((HERE/'interface.json').read_text())['sheets']}
    return {s['name']:ET.parse(HERE/(s['name']+'.xml')) for s in json.loads((HERE/'interface.json').read_text())['sheets']}
def lookup(tree):return {(p.attrib['ref'],p.attrib['pin']):n.attrib['name'] for n in tree.findall('.//nets/net') for p in n.findall('node')}
def isolation_errors(pinmaps):
    errors=[]
    for i in (1,2):
        p=pinmaps[f'wbo{i}_analog'];ref=f'U{1701+i*100}'
        if p.get((ref,'18'))!=f'WBO{i}_VCCSS_UNRESOLVED':errors.append('unreviewed_vccss')
        if p.get((ref,'20'))!=f'WBO{i}_VM':errors.append('virtual_ground_short')
        if p.get((ref,'32'))!=f'WBO{i}_IP':errors.append('pump_pin_mismatch')
    return errors

class AuxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.trees=load();cls.pins={s:lookup(t) for s,t in cls.trees.items()};cls.parts=json.loads((HERE/'parts.json').read_text())
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
    def test_three_spi_miso_returns_disable_on_their_cs(self):
        for sheet,ref,cs,source in [('knock_dual','U1703','KNOCK_CS_N','KNOCK_SDO_5V'),('wbo1_analog','U1802','WBO1_CS_N','WBO1_SO_5V'),('wbo2_analog','U1902','WBO2_CS_N','WBO2_SO_5V')]:
            for pin,net in [('1',cs),('2',source),('3','GND'),('4','GDI_SPI2_MISO'),('5','+3V3')]:self.assertEqual(self.pins[sheet][(ref,pin)],net)
    def test_cj125_virtual_grounds_and_unknown_pin_not_shortened(self):
        self.assertEqual(isolation_errors(self.pins),[])
        for i in (1,2):
            p=self.pins[f'wbo{i}_analog'];b=1700+100*i
            self.assertEqual(p[(f'R{b+22}','1')],f'HARNESS_WBO{i}_CONTACT2')
            self.assertEqual(p[(f'R{b+22}','2')],f'WBO{i}_VM')
            for ref in [f'U{b+1}',f'R{b+23}',f'R{b+24}']:
                self.assertIsNotNone(self.trees[f'wbo{i}_analog'].find(f'.//components/comp[@ref="{ref}"]/property[@name="dnp"]'))
    def test_unknown_supply_and_vm_short_regressions(self):
        p=deepcopy(self.pins);p['wbo1_analog'][('U1801','18')]='+5V_CORE';self.assertIn('unreviewed_vccss',isolation_errors(p))
        p=deepcopy(self.pins);p['wbo2_analog'][('U1901','20')]='GND';self.assertIn('virtual_ground_short',isolation_errors(p))
    def test_sensor_pin_roles_and_ri_resistors(self):
        for i in (1,2):
            p=self.pins[f'wbo{i}_analog'];b=1700+100*i
            for pin,target in enumerate(['IP','VM','HEATER_NEG','HEATER_POS','IA','UN_RAW'],1):self.assertEqual(p[(f'R{b+20+pin}','2')],f'WBO{i}_{target}')
            self.assertEqual(self.trees[f'wbo{i}_analog'].findtext(f'.//components/comp[@ref="R{b+4}"]/value'),'301R 0.1%')
            self.assertEqual(self.trees[f'wbo{i}_analog'].findtext(f'.//components/comp[@ref="R{b+6}"]/value'),'31.6k 1%')
            self.assertEqual((p[(f'R{b+11}','1')],p[(f'R{b+11}','2')]),(f'WBO{i}_UN_RAW',f'WBO{i}_UP'))
            self.assertEqual(p[(f'C{b+2}','2')],'GND')
            self.assertEqual(self.trees[f'wbo{i}_analog'].findtext(f'.//components/comp[@ref="C{b+2}"]/value'),'2.2nF 25V C0G')
    def test_four_analog_outputs_reach_four_adc_inputs(self):
        p=self.pins['wbo_adc_control']
        for pin,net in [('1','WBO1_UA_ADC'),('2','WBO1_UR_ADC'),('3','WBO2_UA_ADC'),('4','WBO2_UR_ADC'),('8','WBO_ADC_CS_N'),('9','GDI_SPI2_MOSI'),('10','GDI_SPI2_MISO'),('11','GDI_SPI2_SCK'),('12','GND'),('13','+3V3'),('14','+3V3')]:self.assertEqual(p[('U2001',pin)],net)
        ratio_max=15000*1.001/(10000*.999+15000*1.001)
        self.assertLess(5.25*ratio_max,3.3)
    def test_heater_logic_inhibit_and_no_claimed_powerstage(self):
        p=self.pins['wbo_adc_control']
        for pin in ('1','19'):self.assertEqual(p[('U2002',pin)],'HW_ACTUATOR_ENABLE_N')
        for i,ref in [(1,'R2005'),(2,'R2006')]:self.assertEqual((p[(ref,'1')],p[(ref,'2')]),(f'WBO{i}_HEATER_GATE_DRIVE','GND'))
        self.assertFalse(any(x['ref'].startswith('Q') for x in self.parts))
    def test_cj_outputs_are_buffered_before_loading_dividers(self):
        p=self.pins['wbo_adc_control']
        self.assertEqual(p[('U2003','4')],'+5V_CORE');self.assertEqual(p[('U2003','11')],'GND')
        for i,(raw,positive,negative,output) in enumerate(zip(['WBO1_UA','WBO1_UR','WBO2_UA','WBO2_UR'],[3,5,10,12],[2,6,9,13],[1,7,8,14])):
            self.assertEqual(p[('U2003',str(positive))],raw)
            self.assertEqual(p[('U2003',str(negative))],raw+'_BUFFERED')
            self.assertEqual(p[('U2003',str(output))],raw+'_BUFFERED')
            self.assertEqual(p[(f'R{2010+2*i}','1')],raw+'_BUFFERED')
    def test_actual_footprint_pad_numbers_cover_all_pins(self):
        manifest=json.loads((HERE/'footprint_manifest.json').read_text())
        for part in self.parts:self.assertFalse(set(part['pins'])-set(manifest[part['footprint']]['pads']),part['ref'])
    def test_resource_and_release_contract(self):
        m=json.loads((HERE/'interface.json').read_text());self.assertEqual(len(m['gpio']),7);self.assertEqual(m['mcu_adc_required'],0);self.assertEqual(m['release_status'],'BLOCKED');self.assertGreaterEqual(len(m['blockers']),7)
    def test_primary_source_provenance_and_upstream_blobs(self):
        m=json.loads((HERE/'sources.json').read_text());self.assertEqual(len(m['documents']),7)
        for doc in m['documents']:
            self.assertTrue(doc['url'].startswith('https://'));self.assertEqual(len(doc['sha256']),64);self.assertGreater(doc['bytes'],10000)
        for item in m['source_files']:
            raw=(HERE.parents[3]/item['path']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),item['sha256'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--netlist',type=Path)
    args,remaining=parser.parse_known_args();NETLIST=args.netlist
    unittest.main(argv=['test_aux.py',*remaining],verbosity=2)
