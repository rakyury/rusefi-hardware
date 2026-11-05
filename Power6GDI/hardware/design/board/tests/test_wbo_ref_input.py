"""Native REF input connectivity and failure atomicity."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_ref_input import route,planned,VIA
from route_wbo_can import signature
from route_wbo_local import vec,xy
KEEPALIVE=[]
class RefInput(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'));plans=planned(b);KEEPALIVE.extend([b,plans]);wanted={signature(t) for *_,t in plans}
  for t in list(b.GetTracks()):
   if signature(t) in wanted:KEEPALIVE.append(t);b.Remove(t)
  return b
 def pad(self,b,r,n):return next(q for f in b.GetFootprints() if f.GetReference()==r for q in f.Pads() if q.GetNumber()==n)
 def test_connectivity_and_idempotence(self):
  b=self.load();b.BuildConnectivity();before=b.GetConnectivity().GetUnconnectedCount(False);old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};self.assertEqual(len(route(b)),2);b.BuildConnectivity();self.assertEqual(b.GetConnectivity().GetUnconnectedCount(False),before-2)
  c=b.GetConnectivity();q=self.pad(b,'U5603','1');todo=[q];seen={q.m_Uuid.AsString()}
  while todo:
   q=todo.pop()
   for n in list(c.GetConnectedPads(q))+list(c.GetConnectedTracks(q)):
    if n.GetNetname()=='+5V_CORE' and n.m_Uuid.AsString() not in seen:seen.add(n.m_Uuid.AsString());todo.append(n)
  self.assertIn(self.pad(b,'C5617','1').m_Uuid.AsString(),seen)
  now={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()}
  for uid,sig in old.items():self.assertEqual(now[uid],sig)
  self.assertEqual(route(b),[])
 def test_wrong_endpoint_rejected(self):
  b=self.load();self.pad(b,'U5603','1').SetNet(b.FindNet('GND'));before=len(b.GetTracks())
  with self.assertRaises(ValueError):route(b)
  self.assertEqual(len(b.GetTracks()),before)
 def test_partial_rejected(self):
  b=self.load();plans=planned(b);KEEPALIVE.append(plans);b.Add(plans[0][-1]);before=len(b.GetTracks())
  with self.assertRaisesRegex(ValueError,'Partial'):route(b)
  self.assertEqual(len(b.GetTracks()),before)
 def test_obstacle_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetStart(vec(166.95,77.5));t.SetEnd(vec(166.95,78.5));t.SetWidth(p.FromMM(.2));t.SetLayer(p.B_Cu);t.SetNet(b.FindNet('GND'));b.Add(t);before=len(b.GetTracks())
  with self.assertRaisesRegex(ValueError,'clearance'):route(b)
  self.assertEqual(len(b.GetTracks()),before)
if __name__=='__main__':unittest.main()
