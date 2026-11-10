"""Independent BOM consistency checks. Not electrical/physical qualification."""
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

HERE=Path(__file__).resolve().parent
HW=HERE/'source_snapshot'

def nominal(v):
    m=re.match(r'^(\d+(?:\.\d+)?)\s*([pnumkKMµR]?)',v)
    return None if not m else float(m[1])*{'p':1e-12,'n':1e-9,'u':1e-6,'µ':1e-6,'m':1e-3,'k':1e3,'K':1e3,'M':1e6,'R':1,'':1}[m[2]]

class SelectionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc=json.loads((HERE/'bom_selection.json').read_text(encoding='utf-8'))
        cls.refs={r['reference']:r for r in cls.doc['references']}
        with (HW/'integrated_bom.csv').open(encoding='utf-8-sig') as f:
            cls.source={r['Reference']:r for r in csv.DictReader(f)}
        cls.fitted={r for r,s in cls.source.items() if s['DNP']=='False' and s['Exclude_From_BOM']=='False' and s['Assembly_Class'] in ('SURFACE_MOUNT','THROUGH_HOLE')}

    def test_exact_reference_coverage(self):
        self.assertEqual(set(self.refs),self.fitted)
        self.assertEqual(len(self.refs),1047)
        self.assertEqual(len(self.doc['references']),1047)
        self.assertEqual(collections.Counter(r['assembly_class'] for r in self.refs.values()),{'SURFACE_MOUNT':1034,'THROUGH_HOLE':13})
        self.assertEqual(set(self.source)-self.fitted,{r['reference'] for r in self.doc['exclusions']})

    def test_snapshot_and_source_traceability(self):
        for file,key in [('integrated_bom.csv','sha256'),('core.net','netlist_sha256')]:
            self.assertEqual(hashlib.sha256((HW/file).read_bytes()).hexdigest(),self.doc['bom_snapshot'][key])
        for ref,r in self.refs.items():
            self.assertEqual(r['source_value'],self.source[ref]['Value'],ref)
            self.assertEqual(r['footprint'],self.source[ref]['Footprint'],ref)
            self.assertEqual(r['source_reference_mpn'],self.source[ref]['Reference_MPN'],ref)

    def test_groups_partition_and_batch_quantities(self):
        seen=[]
        for g in self.doc['groups']:
            seen+=g['refs']
            self.assertEqual(g['quantity_per_board'],len(g['refs']))
            self.assertEqual(g['quantity_10_boards'],10*len(g['refs']))
            for ref in g['refs']:
                self.assertEqual(self.refs[ref]['selection_id'],g['selection_id'])
                for key in ('orderable_mpn','manufacturer','package','ratings','gaps'):
                    self.assertEqual(self.refs[ref][key],g[key],(ref,key))
        self.assertEqual(collections.Counter(seen),collections.Counter(self.fitted))

    def test_csv_preserves_json_and_gaps(self):
        with (HERE/'bom_selection.csv').open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),len(self.refs))
        for r in rows:
            target=self.refs[r['reference']]
            self.assertEqual(r['orderable_mpn'],target['orderable_mpn'] or '')
            for key in ('ratings','source_urls','gaps','nets','source_fields','approved_deviation','requirements'):
                self.assertEqual(json.loads(r[key+'_json']),target[key])

    def test_values_require_explicit_approved_changes(self):
        for ref,r in self.refs.items():
            value=nominal(r['source_value'])
            key='resistance_ohm' if ref.startswith('R') else 'capacitance_pf' if ref.startswith('C') else None
            if value is None or key not in r['ratings']:continue
            expected=value*(1e12 if key=='capacitance_pf' else 1)
            actual=r['ratings'][key]
            if abs(actual-expected)>max(abs(expected),1)*1e-8:
                d=r['approved_deviation']
                self.assertIsNotNone(d,ref)
                self.assertEqual(d['approved_by'],'gdi6_hardware',ref)
                self.assertEqual(d['new_pf'],actual,ref)
                self.assertEqual(d['old_pf'],round(expected),ref)

    def test_cap_voltage_dielectric_and_package(self):
        for ref,r in self.refs.items():
            if not ref.startswith('C') or not r['orderable_mpn']:continue
            m=re.search(r'(\d+(?:\.\d+)?)\s*(k?)V',r['source_value'])
            if m:
                minimum=float(m[1])*(1000 if m[2] else 1)
                if r['ratings']['rated_voltage_v']<minimum:
                    self.assertEqual(r['approved_deviation']['old_voltage_v'],minimum,ref)
                    self.assertEqual(r['approved_deviation']['new_voltage_v'],r['ratings']['rated_voltage_v'],ref)
                else:self.assertGreaterEqual(r['ratings']['rated_voltage_v'],minimum,ref)
            d=re.search(r'(C0G|X[578][RST])',r['source_value'])
            if d:self.assertEqual(r['ratings']['dielectric'],d[1],ref)
            size=re.search(r'(?<!\d)(0603|0805|1206|1210|1812|2220)(?!\d)',r['normalized_footprint'])
            if size and r['package']!=size[1]:
                self.assertEqual(r['approved_deviation']['new_package'],r['package'],ref)

    def test_c114_effective_capacitance_not_nominal(self):
        r=self.refs['C114']
        self.assertEqual(r['orderable_mpn'],'C1206C106K4RACTU')
        self.assertEqual(r['package'],'1206')
        self.assertEqual(r['ratings']['capacitance_pf'],10000000)
        self.assertEqual(r['ratings']['required_effective_capacitance_min_pf'],4700000)
        self.assertIsNone(r['ratings']['effective_capacitance_min_pf'])
        self.assertEqual(r['qualification'],'EFFECTIVE_CAPACITANCE_VALIDATION_REQUIRED')
        self.assertTrue(any('effective' in g.lower() for g in r['gaps']))

    def test_shunts_are_metal_strip_with_pulse_gate(self):
        for ref in ('R203','R212','R213','R215','R221','R303','R312','R313','R315','R321'):
            r=self.refs[ref]
            self.assertEqual(r['orderable_mpn'],'WSLP1206R0100FEA')
            self.assertEqual(r['ratings']['technology'],'metal strip')
            self.assertEqual(r['ratings']['resistance_ohm'],.01)
            self.assertEqual(r['ratings']['terminals'],2)
            self.assertEqual(r['ratings']['pcb_sense_pads'],4)
            self.assertIn('PULSE',r['qualification'])
            self.assertIn('1206',r['normalized_footprint'])

    def test_high_voltage_and_power_packages(self):
        for ref in ('C207','C209','C307','C309'):
            self.assertEqual(self.refs[ref]['ratings']['rated_voltage_v'],80)
            self.assertIn('BOOST',self.refs[ref]['qualification'])
        mos=[r for r in self.refs.values() if r['source_reference_mpn']=='BUK9230-100B']
        self.assertEqual(len(mos),24)
        for r in mos:
            self.assertEqual(r['orderable_mpn'],'IPD60N10S4L12ATMA1')
            self.assertEqual(r['ratings']['vds_max_v'],100)
            self.assertEqual(r['package'],'TO-252-2')
        self.assertEqual(self.refs['D212']['package'],'TO-263-2')
        self.assertEqual(self.refs['C1511']['requirements']['rated_voltage_min_v'],2000)

    def test_current_design_binding_when_export_has_changed(self):
        actual_hw=HERE.parents[1]/'hardware/design'
        net=actual_hw/'core.net'
        digest=hashlib.sha256(net.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        baseline_digest=hashlib.sha256((HW/'core.net').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        report_path=actual_hw/'selection_validation.json'
        if digest==baseline_digest and not report_path.exists() and os.environ.get('REQUIRE_BOM_BINDING')!='1':
            self.skipTest('Original baseline: selection not yet applied; set REQUIRE_BOM_BINDING=1 for integration')
        self.assertTrue(report_path.exists(),'Changed hardware must have current selection validation')
        report=json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['status'],'PASS')
        self.assertEqual(report['netlist_sha256'],digest,'Stale actual-netlist report')
        self.assertEqual(report['map_sha256'],hashlib.sha256((HERE/'bom_selection.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'Stale selection report')
        parts={c.get('ref'):c for c in ET.parse(net).findall('./components/comp')}
        checked={r['reference']:r for r in report['per_reference']}
        self.assertEqual(set(checked),set(self.refs))
        for ref,row in self.refs.items():
            actual=parts[ref]
            fields={f.get('name'):f.text or '' for f in actual.findall('fields/field')}
            self.assertEqual(fields['MPN'],row['orderable_mpn'],ref)
            self.assertEqual(fields['Selection_ID'],row['selection_id'],ref)
            self.assertEqual(fields['Purchase_Released'],'false',ref)
            self.assertEqual(checked[ref]['current_footprint'],actual.findtext('footprint'),ref)
            self.assertEqual(checked[ref]['current_value'],actual.findtext('value'),ref)
            self.assertEqual(checked[ref]['result'],'PASS',ref)

    def test_no_implicit_purchasing_or_zero_prices(self):
        self.assertFalse(self.doc['purchase_released'])
        unresolved=0
        for r in self.refs.values():
            self.assertFalse(r['purchase_released'])
            self.assertTrue(r['qualification'])
            self.assertNotIn('unit_price',r)
            if r['orderable_mpn']:
                self.assertTrue(r['manufacturer'],r['reference'])
                self.assertTrue(r['source_urls'],r['reference'])
                for url in r['source_urls']:
                    self.assertIn(urlparse(url).scheme,('http','https'))
                    self.assertTrue(urlparse(url).netloc)
            else:
                unresolved+=1
                self.assertTrue(r['status'].startswith('UNRESOLVED'))
                self.assertTrue(r['gaps'])
        self.assertEqual(unresolved,self.doc['counts']['unresolved_mpn_refs'])

if __name__=='__main__':unittest.main()
