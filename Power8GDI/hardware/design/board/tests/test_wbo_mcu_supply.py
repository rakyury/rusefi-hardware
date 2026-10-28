"""Native checks for the single digital VDD bypass connection."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_mcu_supply import route,PLANS
from route_wbo_local import vec,xy
from route_wbo_can import signature
class McuSupply(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
  for t in list(b.GetTracks()):
   if not isinstance(t,p.PCB_VIA) and t.GetNetname()=='WBO1_3V3' and t.GetLayer()==p.F_Cu and t.GetWidth()==p.FromMM(.25) and {tuple(p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y)),tuple(p.ToMM(v) for v in (t.GetEnd().x,t.GetEnd().y))}==set(PLANS[0][3]):b.Remove(t)
  return b
 def pad(self,b,ref,pin):return next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
 def bfs(self,b,a,z):
  c=b.GetConnectivity();todo=[a];seen={a.m_Uuid.AsString()}
  while todo:
   item=todo.pop()
   for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
    if q.GetNetname()==a.GetNetname() and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
  return z.m_Uuid.AsString() in seen
 def test_connectivity_preservation_and_idempotence(self):
  b=self.load();b.BuildConnectivity();before=b.GetConnectivity().GetUnconnectedCount(False);a=self.pad(b,'U5602','1');z=self.pad(b,'C5612','1');self.assertFalse(self.bfs(b,a,z))
  old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};r=route(b);self.assertEqual(len(r),1);self.assertEqual(len(r[0]['added_uuids']),1)
  b.BuildConnectivity();self.assertTrue(self.bfs(b,a,z));self.assertEqual(b.GetConnectivity().GetUnconnectedCount(False),before-1)
  for t in b.GetTracks():
   if t.m_Uuid.AsString() in old:self.assertEqual(signature(t),old[t.m_Uuid.AsString()])
  via=next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and xy(t)==(180.15295,67.975))
  self.assertTrue(self.bfs(b,self.pad(b,'C5612','2'),via));self.assertTrue(b.GetConnectivity().IsConnectedOnLayer(via,p.In1_Cu))
  snap=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_device_supply_ground_and_placement_guards(self):
  for ref,pin in [('U5602','1'),('C5612','2')]:
   b=self.load();self.pad(b,ref,pin).SetNet(b.FindNet('+5V_CORE'))
   with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'U5602','1').GetParentFootprint().SetValue('wrong')
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'C5612','1').SetPosition(vec(178.61,66.975))
  with self.assertRaises(ValueError):route(b)
 def test_altered_existing_route_rejected(self):
  b=self.load();r=route(b);t=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==r[0]['added_uuids'][0]);t.SetWidth(p.FromMM(.3))
  with self.assertRaises(ValueError):route(b)
 def test_truncated_branch_rejected(self):
  b=self.load();r=route(b);t=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==r[0]['added_uuids'][0]);t.SetEnd(vec(177.5,66.975));snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'Partial collinear'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_copper_obstacle_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetNet(b.FindNet('GND'));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.2));t.SetStart(vec(177.5,66.5));t.SetEnd(vec(177.5,67.5));b.Add(t);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_same_net_hole_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetNet(b.FindNet('WBO1_3V3'));v.SetPosition(vec(177.5,66.975));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);b.Add(v);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
if __name__=='__main__':unittest.main()
