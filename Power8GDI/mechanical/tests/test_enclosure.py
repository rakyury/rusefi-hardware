"""CAD envelope assertions, not an engineering tolerance or IP-rating test."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
M=json.loads((ROOT/'assembly_manifest.json').read_text())
P=M['parameters']

class AssemblyEnvelopeContract(unittest.TestCase):
    def test_dimensions(self):
        self.assertGreater(P['housing_x'],P['pcb_x'])
        self.assertGreater(P['housing_y'],P['pcb_y'])
        self.assertEqual(P['pcb_thickness'],1.6)
        self.assertEqual(len(P['connector_x']),4)

    def test_connector_clearance_on_face(self):
        sorted_x=sorted(P['connector_x'])
        for a,b in zip(sorted_x,sorted_x[1:]):
            self.assertGreaterEqual(b-a,P['connector_width']+4)
        self.assertLessEqual(max(abs(x) for x in sorted_x)+P['connector_width']/2,
                             P['housing_x']/2-P['wall'])

    def test_no_component_exceeds_base_height(self):
        self.assertLess(P['pcb_bottom_z']+P['pcb_thickness']+12,P['base_z'])
        self.assertLess(P['connector_bottom_z']+P['connector_height'],P['base_z'])

    def test_board_fits_interior(self):
        self.assertLessEqual(P['pcb_x'],P['housing_x']-2*P['wall'])
        self.assertLessEqual(P['pcb_y'],P['housing_y']-2*P['wall'])

    def test_cad_exports_exist(self):
        self.assertGreater((ROOT/'Power8GDI_Assembly_PRELIM.step').stat().st_size,100000)
        for name in M['solids']:
            self.assertGreater((ROOT/'stl'/f'{name}.stl').stat().st_size,100)

    def test_status_explicit(self):
        self.assertEqual(M['status'],'PRELIMINARY_CLEARANCE_ENVELOPE_ONLY')
        self.assertTrue(P['concept_only'])

if __name__=='__main__':unittest.main()
