"""Native regression guards for local VIO and GND branches."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_vio import route
from route_wbo_can import signature
class WboVio(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.board=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'));route(cls.board)
  cls.fps={f.GetReference():f for f in cls.board.GetFootprints()}
 def test_idempotent(self):
  before=sorted(map(signature,self.board.GetTracks()));self.assertEqual(route(self.board),[])
  self.assertEqual(before,sorted(map(signature,self.board.GetTracks())))
 def test_wrong_vio_net_is_rejected_without_mutation(self):
  q=next(q for q in self.fps['U5605'].Pads() if q.GetNumber()=='5');old=q.GetNet();count=len(list(self.board.GetTracks()))
  try:
   q.SetNet(self.board.FindNet('+5V_CORE'))
   with self.assertRaises(ValueError):route(self.board)
   self.assertEqual(count,len(list(self.board.GetTracks())))
  finally:q.SetNet(old)
 def test_changed_ground_pad_location_is_rejected(self):
  q=next(q for q in self.fps['U5605'].Pads() if q.GetNumber()=='2');old=q.GetPosition()
  try:
   q.SetPosition(old+p.VECTOR2I(p.FromMM(.01),0))
   with self.assertRaises(ValueError):route(self.board)
  finally:q.SetPosition(old)
 def test_changed_existing_branch_width_is_rejected(self):
  t=next(t for t in self.board.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='WBO1_3V3' and abs(p.ToMM(t.GetStart().x)-161.37795)<1e-5 and abs(p.ToMM(t.GetStart().y)-67.055558)<1e-5);old=t.GetWidth()
  try:
   t.SetWidth(p.FromMM(.3))
   with self.assertRaises(ValueError):route(self.board)
  finally:t.SetWidth(old)
if __name__=='__main__':unittest.main()
