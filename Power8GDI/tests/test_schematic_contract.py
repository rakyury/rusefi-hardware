"""Static consistency checks for the interface-only KiCad starter.

These tests are NOT KiCad ERC/DRC and do not validate an electrical circuit.
"""
import csv
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMATIC = ROOT / "hardware/Power8GDI_RevA.kicad_sch"
PCB = ROOT / "hardware/Power8GDI_RevA.kicad_pcb"
PINOUT = ROOT / "pinout/power8gdi_revA_pinout.csv"


class SchematicContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sch = SCHEMATIC.read_text(encoding="utf-8")
        cls.pcb = PCB.read_text(encoding="utf-8")
        with PINOUT.open(encoding="utf-8", newline="") as fp:
            cls.rows = list(csv.DictReader(fp))

    def test_csv_columns(self):
        self.assertEqual(
            ["connector", "pin", "position", "net", "group", "notes"],
            list(self.rows[0]),
        )

    def test_schematic_labels_exactly_match_pinout(self):
        labels = re.findall(r'\(label "([^"]+)"', self.sch)
        csv_names = [row["net"] for row in self.rows]
        self.assertCountEqual(labels, csv_names)
        self.assertEqual(136, len(labels))

    def test_four_interface_connectors(self):
        self.assertEqual(
            4, self.sch.count('(symbol (lib_id "Power8GDI:SS34_INTERFACE")')
        )
        self.assertEqual(4, self.sch.count('(pin "34" (uuid'))

    def test_all_cylinders_have_dedicated_injector_pairs(self):
        maps = {(row["connector"], row["position"]): row["net"] for row in self.rows}
        for i in range(1, 9):
            self.assertEqual(maps["A", str(2 * i - 1)], f"DI{i}_HIGH")
            self.assertEqual(maps["A", str(2 * i)], f"DI{i}_LOW")

    def test_hpfp_pairs_are_separate(self):
        nets = {r["net"] for r in self.rows}
        self.assertTrue({"HPFP1_HIGH", "HPFP1_LOW", "HPFP2_HIGH", "HPFP2_LOW"} <= nets)

    def test_pcb_remains_nonproduction_placeholder(self):
        self.assertIn('(layer "Edge.Cuts")', self.pcb)
        self.assertNotIn("(footprint ", self.pcb)
        self.assertNotIn("(segment ", self.pcb)
        self.assertNotIn("(via ", self.pcb)


if __name__ == "__main__":
    unittest.main()
