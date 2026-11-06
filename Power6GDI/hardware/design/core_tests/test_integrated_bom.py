"""Assembly costing must count actual packages and exclude PCB-only features."""
from pathlib import Path
import csv
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export_integrated_bom import assembly_class, export


class IntegratedBomTests(unittest.TestCase):
    def test_radial_capacitor_is_not_smt(self):
        self.assertEqual(assembly_class('Power8GDI_GDI:REF_C14'), 'THROUGH_HOLE')

    def test_smt_ic_with_thermal_holes_remains_smt(self):
        self.assertEqual(assembly_class('Power8GDI_GDI:REF_U1'), 'SURFACE_MOUNT')

    def test_unrecognized_package_is_not_silently_counted_as_smt(self):
        self.assertEqual(assembly_class('NewLibrary:UnreviewedPackage'), 'UNCLASSIFIED')

    def test_physical_assembly_totals(self):
        with tempfile.TemporaryDirectory() as folder:
            report = export(output_dir=Path(folder))
            with (Path(folder)/'integrated_bom.csv').open(newline='', encoding='utf8') as source:
                rows = list(csv.DictReader(source))
        self.assertEqual(report['physical_positions'], 1092)
        self.assertEqual(report['fitted_positions'], 1047)
        self.assertEqual(report['smt_placement_quantity'], 1034)
        self.assertEqual(report['through_hole_placement_quantity'], 13)
        self.assertEqual(report['unclassified_placement_quantity'], 0)
        tht_caps = [r for r in rows if r['Reference'].startswith('C') and r['Assembly_Class']=='THROUGH_HOLE']
        self.assertEqual(len(tht_caps), 8)
        for row in rows:
            if row['Assembly_Class']=='BARE_PCB_FEATURE' or row['DNP']=='True':
                self.assertEqual(row['Quantity_Per_Board'], '0')
                self.assertEqual(row['SMT_Placement_Quantity'], '0')


if __name__ == '__main__': unittest.main()
