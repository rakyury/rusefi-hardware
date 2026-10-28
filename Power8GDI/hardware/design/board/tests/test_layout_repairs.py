"""Native KiCad guards for the narrowly scoped GDI6 layout repairs."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from layout_repairs import repair_returns,repair_silk,point,same,xy

class Repairs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
        cls.fps={f.GetReference():f for f in cls.board.GetFootprints()}
    def test_existing_repair_is_idempotent(self):
        count=len(list(self.board.GetTracks()))
        self.assertEqual(repair_returns(self.board),[])
        self.assertEqual(repair_silk(self.board),[])
        self.assertEqual(len(list(self.board.GetTracks())),count)
    def test_wrong_return_net_fails_without_adding_copper(self):
        expected=point(self.fps['R315'],(.8,-1.1))
        via=next(t for t in self.board.GetTracks() if isinstance(t,p.PCB_VIA) and same(xy(t.GetPosition()),expected))
        before=len(list(self.board.GetTracks()));old=via.GetNet()
        try:
            via.SetNet(self.board.FindNet('+3V3'))
            with self.assertRaises(ValueError):repair_returns(self.board)
            self.assertEqual(len(list(self.board.GetTracks())),before)
        finally:via.SetNet(old)
    def test_wrong_shunt_land_size_is_rejected(self):
        pad=next(q for q in self.fps['R215'].Pads() if q.GetNumber()=='4');size=pad.GetSize()
        try:
            pad.SetSize(p.VECTOR2I(p.FromMM(2.0),p.FromMM(1.65)))
            with self.assertRaises(ValueError):repair_returns(self.board)
        finally:pad.SetSize(size)
    def test_unknown_silk_is_not_silently_overwritten(self):
        shape=next(g for g in self.fps['Y301'].GraphicalItems() if isinstance(g,p.PCB_SHAPE) and g.GetLayer()==p.F_SilkS)
        start=shape.GetStart()
        try:
            shape.SetStart(start+p.VECTOR2I(p.FromMM(.01),0))
            with self.assertRaises(ValueError):repair_silk(self.board)
        finally:shape.SetStart(start)

if __name__=='__main__':unittest.main()
