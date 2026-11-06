"""Native guarded local-ground regression tests."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_logic_grounds import route,PLANS
from route_wbo_local import vec,xy
from route_wbo_can import signature
class LogicGrounds(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
  for t in list(b.GetTracks()):
   if t.GetNetname()!='GND':continue
   for _,_,_,points,via in PLANS:
    if isinstance(t,p.PCB_VIA):
     if xy(t)==via and t.GetWidth()==p.FromMM(.65) and t.GetDrillValue()==p.FromMM(.3):b.Remove(t);break
    elif t.GetLayer()==p.F_Cu and t.GetWidth()==p.FromMM(.25) and {tuple(p.ToMM(v) for v in (t.GetStart().x,t.GetStart().y)),tuple(p.ToMM(v) for v in (t.GetEnd().x,t.GetEnd().y))}==set(points):b.Remove(t);break
  return b
 def pad(self,b,ref,pin):return next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
 def test_native_contact_preservation_idempotence(self):
  b=self.load();b.BuildConnectivity();c=b.GetConnectivity();before=c.GetUnconnectedCount(False)
  for _,_,ep,_,_ in PLANS:
   a=self.pad(b,*ep[0][:2]);self.assertEqual(len(c.GetConnectedTracks(a)),0);self.assertEqual(len(c.GetConnectedPads(a)),0)
  old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};reports=route(b);self.assertEqual(len(reports),3)
  b.BuildConnectivity();c=b.GetConnectivity();self.assertEqual(c.GetUnconnectedCount(False),before-3)
  for t in b.GetTracks():
   if t.m_Uuid.AsString() in old:self.assertEqual(signature(t),old[t.m_Uuid.AsString()])
  vias=[];zones=set()
  for _,_,ep,_,pos in PLANS:
   via=next(t for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and xy(t)==pos);vias.append(via)
   a=self.pad(b,*ep[0][:2]);todo=[a];seen={a.m_Uuid.AsString()}
   while todo:
    item=todo.pop()
    for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
     if q.GetNetname()=='GND' and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
   self.assertIn(via.m_Uuid.AsString(),seen);self.assertTrue(c.IsConnectedOnLayer(via,p.In1_Cu))
   matches=[z for z in b.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(p.In1_Cu) and z.GetFilledPolysList(p.In1_Cu).Contains(via.GetPosition(),0)]
   self.assertEqual(len(matches),1);self.assertEqual(matches[0].GetFilledPolysList(p.In1_Cu).OutlineCount(),1);zones.add(matches[0].m_Uuid.AsString())
  self.assertEqual(len(zones),1);snap=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  z=next(z for z in b.Zones() if z.m_Uuid.AsString() in zones);b.Remove(z);b.BuildConnectivity()
  for v in vias:self.assertFalse(b.GetConnectivity().IsConnectedOnLayer(v,p.In1_Cu))
 def test_wrong_device_supply_and_position(self):
  b=self.load();self.pad(b,'U5602','16').GetParentFootprint().SetValue('wrong')
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'C5612','1').SetNet(b.FindNet('+5V_CORE'))
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'U5602','32').SetPosition(vec(174.98,68.35))
  with self.assertRaises(ValueError):route(b)
 def test_changed_and_partial_geometry(self):
  b=self.load();reports=route(b);uid=reports[-1]['added_uuids'][0];t=next(t for t in b.GetTracks() if t.m_Uuid.AsString()==uid);t.SetWidth(p.FromMM(.3))
  with self.assertRaises(ValueError):route(b)
  b.Remove(t)
  with self.assertRaises(ValueError):route(b)
 def test_last_branch_obstacle_is_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetNet(b.FindNet('+5V_CORE'));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.2));t.SetStart(vec(175.9,68.85));t.SetEnd(vec(176.5,68.85));b.Add(t);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_same_net_hole_is_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetNet(b.FindNet('GND'));v.SetPosition(vec(176.22795,69.25));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);b.Add(v);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance|drill clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
if __name__=='__main__':unittest.main()
