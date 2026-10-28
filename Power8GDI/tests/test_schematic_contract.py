"""Active six-cylinder connector contract from the real KiCad XML export.

The old Power8GDI_RevA interface-only starter is historical, not a circuit.
"""
import csv
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "hardware/Power8GDI_RevA.kicad_sch"
PCB = ROOT / "hardware/Power8GDI_RevA.kicad_pcb"
NETLIST = ROOT / 'hardware/design/core.net'
PINOUT = ROOT / "pinout/power8gdi_revA_pinout.csv"


class SchematicContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = ET.parse(NETLIST)
        cls.pins = {(p.get('ref'),p.get('pin')):n.get('name') for n in cls.doc.findall('nets/net') for p in n.findall('node')}
        cls.aliases = {r['pinout_net']:r['board_net'] for r in csv.DictReader((ROOT/'hardware/design/board/connector_aliases.csv').read_text().splitlines())}
        with PINOUT.open(encoding="utf-8", newline="") as fp:
            cls.rows = list(csv.DictReader(fp))

    def test_csv_columns(self):
        self.assertEqual(
            ["connector", "pin", "position", "net", "group", "notes"],
            list(self.rows[0]),
        )

    def test_schematic_labels_exactly_match_pinout(self):
        self.assertEqual(len(self.rows),136)
        for row in self.rows:
            actual=self.pins[('J60'+str('ABCD'.index(row['connector'])+1),row['position'])]
            if row['net'].startswith('UNUSED_'): self.assertTrue(actual.startswith('unconnected-'))
            else: self.assertEqual(actual,self.aliases.get(row['net'],'HARNESS_'+row['net']))

    def test_four_interface_connectors(self):
        for ref in ['J601','J602','J603','J604']:
            self.assertEqual(len([p for r,p in self.pins if r==ref]),34)

    def test_all_cylinders_have_dedicated_injector_pairs(self):
        nets = [r['net'] for r in self.rows]
        for i in range(1, 7):
            self.assertEqual(nets.count(f'DI{i}_HIGH'),1)
            self.assertEqual(nets.count(f'DI{i}_LOW'),1)
        for prefix in ('DI7','DI8','PI7','PI8','IGN7','IGN8','MOTOR3','MOTOR4','WBO2'):
            self.assertFalse(any(n.startswith(prefix) for n in nets))

    def test_hpfp_pairs_are_separate(self):
        nets = {r["net"] for r in self.rows}
        self.assertTrue({"HPFP1_HIGH", "HPFP1_LOW", "HPFP2_HIGH", "HPFP2_LOW"} <= nets)

    def test_physical_removed_assemblies_do_not_reappear(self):
        refs={c.get('ref') for c in self.doc.findall('components/comp')}
        self.assertTrue({'U201','U301','U6000','U6050','U5602'} <= refs)
        self.assertFalse({'Q210','Q310','U6100','U6150','U5802','Q5540','Q5560','U5405'} & refs)


if __name__ == "__main__":
    unittest.main()
