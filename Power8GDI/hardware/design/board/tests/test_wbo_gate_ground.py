"""Native checks for a bounded logic-ground drop, including plane contact."""
import sys
import unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from route_wbo_gate_ground import route, PLANS
from route_wbo_local import vec, xy
from route_wbo_can import signature

class GateGround(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
  # Exercise the baseline even after the reviewed addition is checked in.
  for t in list(b.GetTracks()):
   if t.GetNetname()!='GND':continue
   if isinstance(t,p.PCB_VIA):
    if xy(t)==(178.8625,81.8) and t.GetWidth()==p.FromMM(.65) and t.GetDrillValue()==p.FromMM(.3):b.Remove(t)
   elif t.GetLayer()==p.B_Cu and t.GetWidth()==p.FromMM(.25) and {tuple(p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y)),tuple(p.ToMM(v) for v in (t.GetEnd().x,t.GetEnd().y))}=={(178.8625,82.55),(178.8625,81.8)}:b.Remove(t)
  return b
 def pad(self,b,pin='3'):
  return next(q for f in b.GetFootprints() if f.GetReference()=='U5610' for q in f.Pads() if q.GetNumber()==pin)
 def test_native_contact_and_idempotence(self):
  b=self.load(); old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()}
  b.BuildConnectivity(); before=b.GetConnectivity().GetUnconnectedCount(False)
  report=route(b); b.BuildConnectivity(); c=b.GetConnectivity()
  self.assertEqual(len(report),1)
  self.assertEqual(c.GetUnconnectedCount(False),before-1)
  for t in b.GetTracks():
   if t.m_Uuid.AsString() in old:self.assertEqual(signature(t),old[t.m_Uuid.AsString()])
  via=next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and xy(t)==(178.8625,81.8))
  seen={self.pad(b).m_Uuid.AsString()}; todo=[self.pad(b)]
  while todo:
   item=todo.pop()
   for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
    if q.GetNetname()=='GND' and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
  self.assertIn(via.m_Uuid.AsString(),seen)
  self.assertTrue(c.IsConnectedOnLayer(via,p.In1_Cu))
  zones=[z for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(p.In1_Cu) and z.GetFilledPolysList(p.In1_Cu).Contains(via.GetPosition(),0)]
  self.assertEqual(len(zones),1)
  self.assertEqual(zones[0].GetFilledPolysList(p.In1_Cu).OutlineCount(),1)
  snapshot=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snapshot,sorted(map(signature,b.GetTracks())))
  b.Remove(zones[0]);b.BuildConnectivity()
  self.assertFalse(b.GetConnectivity().IsConnectedOnLayer(via,p.In1_Cu))
 def test_wrong_supply_and_device(self):
  b=self.load(); q=self.pad(b,'5');q.SetNet(b.FindNet('+5V_CORE'))
  with self.assertRaisesRegex(ValueError,'supply'):route(b)
  b=self.load();self.pad(b).GetParentFootprint().SetValue('wrong')
  with self.assertRaisesRegex(ValueError,'device'):route(b)
 def test_moved_endpoint(self):
  b=self.load();self.pad(b).SetPosition(vec(178.87,82.55))
  with self.assertRaisesRegex(ValueError,'endpoint'):route(b)
 def test_partial_and_changed_width(self):
  b=self.load();report=route(b);ids=report[0]['added_uuids']
  track=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==ids[0]);track.SetWidth(p.FromMM(.3))
  with self.assertRaises(ValueError):route(b)
  b.Remove(track)
  with self.assertRaises(ValueError):route(b)
 def test_all_layer_obstacle_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetNet(b.FindNet('+5V_CORE'));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.2));t.SetStart(vec(178.4,81.8));t.SetEnd(vec(179.2,81.8));b.Add(t)
  before=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper clearance'):route(b)
  self.assertEqual(before,sorted(map(signature,b.GetTracks())))
 def test_same_net_hole_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetNet(b.FindNet('GND'));v.SetPosition(vec(178.8625,81.4));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);b.Add(v)
  before=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance|drill clearance'):route(b)
  self.assertEqual(before,sorted(map(signature,b.GetTracks())))
if __name__=='__main__':unittest.main()
