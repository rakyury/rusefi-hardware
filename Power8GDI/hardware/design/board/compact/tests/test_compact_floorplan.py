import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
COMPACT = HERE.parent
sys.path.insert(0, str(COMPACT))
import pcb_sexpr  # noqa: E402
import compact_floorplan as cf  # noqa: E402

CANDIDATE = COMPACT.parent / 'gdi6_candidate' / 'Power8GDI_Review.kicad_pcb'
NETLIST = COMPACT.parents[1] / 'core.net'

SMALL_PCB = '''(kicad_pcb (version 20241229) (generator "test")
 (gr_rect (start 0 0) (end 50 40) (layer "Edge.Cuts"))
 (footprint "Lib:Pads2" (layer "F.Cu") (at 10 10 90)
  (property "Reference" "R1") (property "Value" "1k")
  (pad "1" smd rect (at -1 0 90) (size 1 2) (layers "F.Cu"))
  (pad "2" smd rect (at 1 0 90) (size 1 2) (layers "F.Cu")))
 (footprint "Lib:Court" (layer "B.Cu") (at 30 20)
  (property "Reference" "U1") (property "Value" "x")
  (attr smd dnp)
  (fp_rect (start -3 -2) (end 3 2) (layer "B.CrtYd"))
  (pad "1" smd rect (at 0 0) (size 1 1) (layers "B.Cu")))
)'''


class SexprTests(unittest.TestCase):
    def test_pad_box_rotation_and_courtyard(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 't.kicad_pcb'
            p.write_text(SMALL_PCB)
            b = pcb_sexpr.read_board(p)
        self.assertEqual(b['outline'], (0, 0, 50, 40))
        r1 = next(f for f in b['footprints'] if f.ref == 'R1')
        # pads span 3 x 2 locally; rotated 90 deg on the board -> 2 x 3
        self.assertEqual((r1.width, r1.height, r1.box_source), (2.0, 3.0, 'pads'))
        u1 = next(f for f in b['footprints'] if f.ref == 'U1')
        self.assertEqual((u1.width, u1.height, u1.side, u1.dnp, u1.box_source), (6.0, 4.0, 'B', True, 'courtyard'))

    def test_unbalanced_rejected(self):
        with self.assertRaises(ValueError):
            pcb_sexpr.parse('(a (b)')


class ZonePlanTests(unittest.TestCase):
    parts = [dict(ref='A', block='X', side='F', area=10.0, z=1.0),
             dict(ref='B', block='Y', side='B', area=10.0, z=1.0)]

    def test_overlap_and_containment_detected(self):
        plan = dict(board_w=20, board_d=20, density_target=0.5, zones=[
            dict(name='z1', side='F', rect=[0, 0, 10, 10], blocks=['X']),
            dict(name='z2', side='F', rect=[5, 5, 25, 15], blocks=[]),
            dict(name='z3', side='B', rect=[0, 0, 10, 10], blocks=['Y'])])
        r = cf.zone_plan(self.parts, plan)
        self.assertEqual(r['overlaps'], [('F', 'z1', 'z2')])
        self.assertFalse(next(z for z in r['zones'] if z['name'] == 'z2')['inside_board'])
        self.assertFalse(r['all_ok'])

    def test_uncovered_block_side_reported(self):
        plan = dict(board_w=20, board_d=20, density_target=0.5, zones=[
            dict(name='z1', side='F', rect=[0, 0, 10, 10], blocks=['X'])])
        r = cf.zone_plan(self.parts, plan)
        self.assertEqual(r['uncovered_block_sides'], [('Y', 'B')])

    def test_density_target_enforced(self):
        plan = dict(board_w=20, board_d=20, density_target=0.5, zones=[
            dict(name='z1', side='F', rect=[0, 0, 4, 4], blocks=['X']),
            dict(name='z2', side='B', rect=[0, 0, 10, 10], blocks=['Y'])])
        r = cf.zone_plan(self.parts, plan)
        self.assertFalse(next(z for z in r['zones'] if z['name'] == 'z1')['ok'])


@unittest.skipUnless(CANDIDATE.exists() and NETLIST.exists(), 'candidate PCB or netlist missing')
class CandidateStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parts, cls.board = cf.load_parts(CANDIDATE, NETLIST, COMPACT / 'body_overrides.json')

    def test_every_fitted_part_has_a_block(self):
        unassigned = sorted({p['block'] for p in self.parts if p['block'].startswith('unassigned')})
        self.assertEqual(unassigned, [])

    def test_gdi_capacitors_use_body_override(self):
        caps = [p for p in self.parts if p['ref'] in ('C205', 'C206', 'C305', 'C306', 'C207', 'C209', 'C307', 'C309')]
        self.assertEqual(len(caps), 8)
        for c in caps:
            self.assertEqual((c['width'], c['z']), (16.5, 25.0), c)

    def test_baseline_zone_plan_is_consistent(self):
        plan = json.loads((COMPACT / 'floorplan_190x160.json').read_text())
        r = cf.zone_plan(self.parts, plan)
        self.assertTrue(r['all_ok'], r)

    def test_pro8_depth_is_overfull_and_baseline_fits_at_50(self):
        envs = {k: cf.evaluate(self.parts, v) for k, v in cf.ENVELOPES.items()}
        self.assertEqual(envs['pro8_like_190x88']['verdict']['at_60pct'], 'overfull')
        self.assertEqual(envs['single_190x160']['verdict']['at_50pct'], 'fits')

    def test_height_budget_names_tall_back_parts(self):
        hb = cf.height_budget(self.parts)
        self.assertEqual(hb['front_max']['z'], 25.0)
        self.assertIn('C6054', [p['ref'] for p in hb['back_tall_parts']])


if __name__ == '__main__':
    unittest.main()
