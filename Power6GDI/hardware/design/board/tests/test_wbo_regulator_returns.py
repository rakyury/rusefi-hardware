"""Native tests for two LDO returns to an existing EP/plane connection."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_regulator_returns import route,planned,VIA
from route_wbo_can import signature
from route_wbo_local import vec,xy
KEEPALIVE=[]
class RegulatorReturns(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'));plans=planned(b);KEEPALIVE.extend([b,plans]);wanted={signature(t) for *_,t in plans}
  for t in list(b.GetTracks()):
   if signature(t) in wanted:KEEPALIVE.append(t);b.Remove(t)
  return b
 def pad(self,b,ref,pin):return next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
 def bfs(self,b,a,z):
  todo=[a];seen={a.m_Uuid.AsString()};c=b.GetConnectivity()
  while todo:
   item=todo.pop()
   for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
    if q.GetNetname()==a.GetNetname() and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
  return z.m_Uuid.AsString() in seen
 def via(self,b):return next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and xy(t)==VIA)
 def test_native_ground_and_power_preservation(self):
  b=self.load();b.BuildConnectivity();c=b.GetConnectivity();before=c.GetUnconnectedCount(False);via=self.via(b);ep=self.pad(b,'U5604','11');cout=self.pad(b,'C5662','2');ic=self.pad(b,'U5604','8')
  self.assertTrue(self.bfs(b,ep,via));self.assertFalse(self.bfs(b,cout,via));self.assertFalse(self.bfs(b,ic,via));self.assertTrue(c.IsConnectedOnLayer(via,p.In1_Cu))
  old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};r=route(b);self.assertEqual(len(r),2);b.BuildConnectivity();self.assertEqual(b.GetConnectivity().GetUnconnectedCount(False),before-2)
  now={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};self.assertEqual(len(now),len(old)+2)
  for k,v in old.items():self.assertEqual(now[k],v)
  for a in [ep,cout,ic]:self.assertTrue(self.bfs(b,a,via))
  self.assertTrue(b.GetConnectivity().IsConnectedOnLayer(via,p.In1_Cu));self.assertTrue(self.bfs(b,self.pad(b,'U5604','10'),self.pad(b,'U5602','1')))
  snap=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_device_net_position_guards(self):
  b=self.load();self.pad(b,'U5604','8').SetNet(b.FindNet('+5V_CORE'))
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'C5662','2').SetPosition(vec(164.02,91.028729))
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'U5604','8').GetParentFootprint().SetValue('wrong')
  with self.assertRaises(ValueError):route(b)
 def test_existing_via_and_ep_trace_guards(self):
  b=self.load();self.via(b).SetDrill(p.FromMM(.35))
  with self.assertRaisesRegex(ValueError,'via'):route(b)
  b=self.load();t=next(t for t in b.GetTracks() if not isinstance(t,p.PCB_VIA) and t.GetStart()==vec(161,85) and t.GetEnd()==vec(*VIA));t.SetWidth(p.FromMM(.3));snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'EP to via'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_partial_duplicate_modified_rejected(self):
  b=self.load();plans=planned(b);KEEPALIVE.append(plans);b.Add(plans[0][-1]);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'Partial'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  b=self.load();route(b);plans=planned(b);KEEPALIVE.append(plans);b.Add(plans[0][-1])
  with self.assertRaisesRegex(ValueError,'Duplicate'):route(b)
  b=self.load();plans=planned(b);KEEPALIVE.append(plans);t=plans[0][-1];t.SetWidth(p.FromMM(.3));b.Add(t)
  with self.assertRaisesRegex(ValueError,'Altered'):route(b)
 def test_obstacle_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetStart(vec(162,84.7));t.SetEnd(vec(162,85.3));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.2));t.SetNet(b.FindNet('+5V_CORE'));b.Add(t);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_same_net_hole_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetPosition(vec(162,85));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet('GND'));b.Add(v);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
if __name__=='__main__':unittest.main()
