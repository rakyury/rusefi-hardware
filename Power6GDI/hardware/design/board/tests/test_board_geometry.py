"""Run with the pinned KiCad9 image: python3 -m unittest discover ..."""
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
import pcbnew as p

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from build_board import project_file
from build_connector import make_footprint
from build_thermal_footprint import SOURCE,SOURCE_NAME,NAME


class BoardGeometryTests(unittest.TestCase):
    def test_thermal_changes_only_six_ep_holes(self):
        plugin=p.PCB_IO_MGR.PluginFind(p.PCB_IO_MGR.KICAD_SEXP)
        source=plugin.FootprintLoad(str(SOURCE),SOURCE_NAME)
        target=plugin.FootprintLoad(str(HERE/'Power8GDI_Board.pretty'),NAME)
        def lands(fp):
            return sorted((q.GetNumber(),q.GetPosition().x,q.GetPosition().y,q.GetSize().x,q.GetSize().y)
                          for q in fp.Pads() if q.GetAttribute()!=p.PAD_ATTRIB_PTH)
        self.assertEqual(lands(source),lands(target))
        holes=[q for q in target.Pads() if q.GetAttribute()==p.PAD_ATTRIB_PTH]
        self.assertEqual(len(holes),6)
        for q in holes:
            self.assertEqual(q.GetNumber(),'9')
            self.assertEqual(q.GetDrillSize().x,p.FromMM(.3))
            self.assertEqual(q.GetSize().x,p.FromMM(.6))

    def test_connector_silk_stays_inside_edge(self):
        fp=make_footprint()
        silk=[g for g in fp.GraphicalItems() if g.GetLayer()==p.F_SilkS]
        self.assertTrue(silk)
        self.assertLessEqual(max(p.ToMM(g.GetBoundingBox().GetBottom()) for g in silk),3.3)
        self.assertEqual(len([q for q in fp.Pads() if q.GetNumber()]),34)

    def test_rules_survive_kicad_roundtrip(self):
        with tempfile.TemporaryDirectory() as temporary:
            board_path=Path(temporary)/'test.kicad_pcb'
            p.SaveBoard(str(board_path),p.BOARD())
            project=board_path.with_suffix('.kicad_pro');project_file(project)
            subprocess.run([sys.executable,'-c',
                'import pcbnew as p,sys; b=p.LoadBoard(sys.argv[1]); p.SaveBoard(sys.argv[1],b)',str(board_path)],check=True)
            data=json.loads(project.read_text())
            self.assertEqual(data['board']['design_settings']['rules']['min_track_width'],.2)
            self.assertEqual(data['board']['design_settings']['rules']['min_through_hole_diameter'],.3)
            self.assertEqual(data['board']['design_settings']['drc_exclusions'],[])
            self.assertEqual(data['net_settings']['meta']['version'],4)
            self.assertTrue(all('priority' in c for c in data['net_settings']['classes']))
            rules=project.with_suffix('.kicad_dru').read_text()
            self.assertIn('(min 0.6mm)',rules);self.assertIn('PTA_VBOOST',rules)


if __name__=='__main__':unittest.main()
