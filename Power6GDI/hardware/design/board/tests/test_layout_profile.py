"""Layout profile contract; portable (no pcbnew)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import layout_profile


class LayoutProfileTests(unittest.TestCase):
    def tearDown(self):layout_profile.configure()

    def write(self,data):
        path=Path(tempfile.mkdtemp())/'profile.json';path.write_text(json.dumps(data));return path

    def base(self):return json.loads(layout_profile.DEFAULT.read_text())

    def test_default_reproduces_previous_constants(self):
        layout_profile.configure()
        self.assertEqual(layout_profile.outline(),(245,165))
        self.assertEqual(layout_profile.frame_shift(),(0,0))
        self.assertEqual(layout_profile.at(160.59045,73.2),(160.59045,73.2))
        # Former inline region() results.
        self.assertEqual(layout_profile.region('Ignition 5 IGBT stage'),((49,114,73,137),(61,125),0))
        self.assertEqual(layout_profile.region('wbo/wbo1 module'),((153,52,197,142),(175,108),5))
        self.assertEqual(layout_profile.region('wbo/common'),((198,52,242,142),(220,108),5))
        self.assertEqual(layout_profile.region('Ignition permission and three dual gate drivers'),((49,91,151,142),(99,113),1))
        self.assertEqual(layout_profile.region('anything else'),((156,5,239,142),(195,28),7))

    def test_stage_b_frame_moves_wbo_routes(self):
        data=self.base();data['outline_mm']=[300,200]
        data['stages']['B']['target_mm']=[160.5,10];data['wbo_regions_mm']['1']=[156.5,60,200.5,150]
        layout_profile.configure(self.write(data))
        self.assertEqual(layout_profile.frame_shift(),(3.5,8))
        self.assertEqual(layout_profile.shifted(('U1','2',(1.0,2.0),((3,4),(5.5,6)))),('U1','2',(4.5,10.0),((6.5,12),(9.0,14))))

    def test_wbo_must_follow_stage_b(self):
        data=self.base();data['stages']['B']['target_mm']=[160,2]
        with self.assertRaisesRegex(ValueError,'move with stage B'):layout_profile.configure(self.write(data))

    def test_stage_b_rotation_refused(self):
        data=self.base();data['stages']['B']['angle_deg']=0
        with self.assertRaisesRegex(ValueError,'rotation'):layout_profile.configure(self.write(data))

    def test_non_half_mm_shift_refused(self):
        data=self.base();data['stages']['B']['target_mm']=[157.2,2];data['wbo_regions_mm']['1']=[153.2,52,197.2,142]
        with self.assertRaisesRegex(ValueError,'0.5 mm'):layout_profile.configure(self.write(data))

    def test_region_outside_outline_refused(self):
        data=self.base();data['outline_mm']=[200,165]
        with self.assertRaisesRegex(ValueError,'outside outline'):layout_profile.configure(self.write(data))

    def test_all_committed_profiles_valid(self):
        for path in sorted((HERE/'layout_profiles').glob('*.json')):
            with self.subTest(path.name):layout_profile.configure(path)


if __name__=='__main__':
    unittest.main()
