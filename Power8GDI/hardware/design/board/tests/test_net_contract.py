import csv
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from net_contract import read_netlists,compare_pad_assignments


class NetContractTests(unittest.TestCase):
    def fixture(self,body):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        path=Path(folder.name)/'source.xml';path.write_text(body);return path

    def test_dnp_and_bom_flags_survive_xml(self):
        path=self.fixture('<export><components><comp ref="R299"><value>0R</value><footprint>Resistor_SMD:R_0603_1608Metric</footprint><property name="dnp"/><property name="exclude_from_bom"/></comp></components><nets><net name="INHIBIT"><node ref="R299" pin="1"/></net></nets></export>')
        parts,pins,_=read_netlists([path])
        self.assertTrue(parts['R299']['dnp']);self.assertTrue(parts['R299']['exclude_from_bom'])
        self.assertEqual(pins,{('R299','1'):'INHIBIT'})

    def test_duplicates_fail_instead_of_silently_overwrite(self):
        path=self.fixture('<export><components><comp ref="U1"><footprint>X:Y</footprint></comp></components></export>')
        with self.assertRaisesRegex(ValueError,'Duplicate'):read_netlists([path,path])

    def test_conflicting_pin_nets_fail(self):
        path=self.fixture('<export><components><comp ref="R1"><footprint>X:Y</footprint></comp></components><nets><net name="A"><node ref="R1" pin="1"/></net><net name="B"><node ref="R1" pin="1"/></net></nets></export>')
        with self.assertRaisesRegex(ValueError,'Conflicting'):read_netlists([path])

    def test_repeated_thermal_pads_must_all_match(self):
        self.assertEqual(compare_pad_assignments({('U1','9'):'GND'},{('U1','9'):['GND','GND']}),[])
        self.assertTrue(compare_pad_assignments({('U1','9'):'GND'},{('U1','9'):['GND','VBAT']}))

    def test_missing_and_unexpected_connections_are_detected(self):
        self.assertEqual(len(compare_pad_assignments({('U1','1'):'GND'},{('U2','2'):['VBAT']})),2)

    def test_connector_aliases_do_not_short_gpio_or_unreviewed_power(self):
        path=Path(__file__).resolve().parents[1]/'connector_aliases.csv'
        aliases={r['pinout_net']:r['board_net'] for r in csv.DictReader(path.read_text().splitlines())}
        for n in range(1,9):self.assertNotEqual(aliases.get(f'IGN{n}'),f'IGN{n}')
        for name in ['PGND_MAIN_4','DI1_HIGH']:
            self.assertNotIn(name,aliases)
        self.assertEqual(aliases['VBAT_MAIN_2'],'VBAT_DBW_FUSED')
        self.assertEqual(aliases['VBAT_MAIN_3'],'VBAT_EWG_FUSED')
        self.assertNotEqual(aliases['VBAT_MAIN_1'],aliases['VBAT_MAIN_2'])
        self.assertNotEqual(aliases['VBAT_MAIN_2'],aliases['VBAT_MAIN_3'])


if __name__=='__main__':unittest.main()
