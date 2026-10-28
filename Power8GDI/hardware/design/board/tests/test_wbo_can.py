"""Native guards for the two WBO digital nets; no placement changes allowed."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_can import route,signature
class WboCan(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.board=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'));route(cls.board)
  cls.fps={f.GetReference():f for f in cls.board.GetFootprints()}
 def test_idempotent(self):
  before=sorted(map(signature,self.board.GetTracks()));self.assertEqual(route(self.board),[])
  self.assertEqual(before,sorted(map(signature,self.board.GetTracks())))
 def test_changed_supply_is_rejected(self):
  q=next(q for q in self.fps['U5605'].Pads() if q.GetNumber()=='5');old=q.GetNet();count=len(list(self.board.GetTracks()))
  try:
   q.SetNet(self.board.FindNet('+5V_CORE'))
   with self.assertRaises(ValueError):route(self.board)
   self.assertEqual(len(list(self.board.GetTracks())),count)
  finally:q.SetNet(old)
 def test_changed_endpoint_is_rejected(self):
  q=next(q for q in self.fps['U5602'].Pads() if q.GetNumber()=='21');old=q.GetPosition()
  try:
   q.SetPosition(old+p.VECTOR2I(p.FromMM(.01),0))
   with self.assertRaises(ValueError):route(self.board)
  finally:q.SetPosition(old)
 def test_unreviewed_existing_route_is_rejected(self):
  t=next(t for t in self.board.GetTracks() if t.GetNetname()=='WBO1_CAN_TX' and not isinstance(t,p.PCB_VIA));old=t.GetWidth()
  try:
   t.SetWidth(p.FromMM(.25))
   with self.assertRaises(ValueError):route(self.board)
  finally:t.SetWidth(old)
if __name__=='__main__':unittest.main()
