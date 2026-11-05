"""Native regression checks for the single bounded reset branch."""
import sys
import unittest
from pathlib import Path
import pcbnew as p

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from route_wbo_reset import route, POINTS, NET
from route_wbo_can import signature


class WboReset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
        cls.report = route(cls.board)
        cls.fps = {f.GetReference():f for f in cls.board.GetFootprints()}

    def test_idempotent_and_connected(self):
        before = sorted(map(signature,self.board.GetTracks()))
        self.assertEqual(route(self.board),[])
        self.assertEqual(before,sorted(map(signature,self.board.GetTracks())))
        self.board.BuildConnectivity(); c = self.board.GetConnectivity()
        a = next(q for q in self.fps['U5612'].Pads() if q.GetNumber()=='1')
        b = next(q for q in self.fps['R5662'].Pads() if q.GetNumber()=='1')
        seen = {a.m_Uuid.AsString()}; todo = [a]
        while todo:
            item = todo.pop()
            for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
                uid = q.m_Uuid.AsString()
                if q.GetNetname()==NET and uid not in seen:
                    seen.add(uid); todo.append(q)
        self.assertIn(b.m_Uuid.AsString(),seen)

    def test_wrong_pullup_net_rejected(self):
        q = next(q for q in self.fps['R5662'].Pads() if q.GetNumber()=='2')
        old = q.GetNet(); before = sorted(map(signature,self.board.GetTracks()))
        try:
            q.SetNet(self.board.FindNet('+5V_CORE'))
            with self.assertRaises(ValueError): route(self.board)
            self.assertEqual(before,sorted(map(signature,self.board.GetTracks())))
        finally: q.SetNet(old)

    def test_wrong_device_rejected(self):
        f = self.fps['U5612']; old = f.GetValue()
        try:
            f.SetValue('wrong supervisor')
            with self.assertRaises(ValueError): route(self.board)
        finally: f.SetValue(old)

    def test_endpoint_motion_rejected(self):
        q = next(q for q in self.fps['U5612'].Pads() if q.GetNumber()=='1')
        old = q.GetPosition()
        try:
            q.SetPosition(old+p.VECTOR2I(p.FromMM(.01),0))
            with self.assertRaises(ValueError): route(self.board)
        finally: q.SetPosition(old)

    def test_modified_existing_width_rejected(self):
        t = next(t for t in self.board.GetTracks() if t.GetNetname()==NET
                 and not isinstance(t,p.PCB_VIA) and t.GetStart()==p.VECTOR2I(p.FromMM(POINTS[0][0]),p.FromMM(POINTS[0][1])))
        old = t.GetWidth()
        try:
            t.SetWidth(p.FromMM(.25))
            with self.assertRaises(ValueError): route(self.board)
        finally: t.SetWidth(old)

    def test_late_obstacle_rejects_whole_plan(self):
        board = p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
        wanted = set()
        for a,b in zip(POINTS,POINTS[1:]):
            t = p.PCB_TRACK(board); t.SetLayer(p.B_Cu); t.SetNet(board.FindNet(NET)); t.SetWidth(p.FromMM(.2))
            t.SetStart(p.VECTOR2I(p.FromMM(a[0]),p.FromMM(a[1]))); t.SetEnd(p.VECTOR2I(p.FromMM(b[0]),p.FromMM(b[1])))
            wanted.add(signature(t))
        # Permit running against a later checked-in candidate with this route present.
        for t in list(board.GetTracks()):
            if signature(t) in wanted: board.Remove(t)
        block = p.PCB_TRACK(board); block.SetLayer(p.B_Cu); block.SetNet(board.FindNet('GND')); block.SetWidth(p.FromMM(.2))
        block.SetStart(p.VECTOR2I(p.FromMM(175.6),p.FromMM(84.1)))
        block.SetEnd(p.VECTOR2I(p.FromMM(175.6),p.FromMM(84.8))); board.Add(block)
        before = sorted(map(signature,board.GetTracks()))
        with self.assertRaisesRegex(ValueError,'copper clearance'): route(board)
        self.assertEqual(before,sorted(map(signature,board.GetTracks())))


if __name__=='__main__': unittest.main()
