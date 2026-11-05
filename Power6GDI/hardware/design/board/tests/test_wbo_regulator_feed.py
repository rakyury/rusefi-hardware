"""Native tests for a regulator power feed with a separate Kelvin sense branch."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_regulator_feed import route,planned,track,SHORTCUT,FEED,SENSE,NET,kelvin_guard
from route_wbo_can import signature
from route_wbo_local import vec,xy
# Retain detached SWIG objects and their parent boards through test teardown.
KEEPALIVE=[]
class RegulatorFeed(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'))
  plans=planned(b);KEEPALIVE.extend([b,plans])
  wanted={signature(t) for *_,items in plans for t in items}
  for t in list(b.GetTracks()):
   if signature(t) in wanted:KEEPALIVE.append(t);b.Remove(t)
  old=track(b,*SHORTCUT,.2,p.B_Cu);KEEPALIVE.append(old)
  if not any(signature(t)==signature(old) for t in b.GetTracks()):b.Add(old)
  return b
 def pad(self,b,ref,pin):return next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
 def bfs(self,b,a,z):
  todo=[a];seen={a.m_Uuid.AsString()};c=b.GetConnectivity()
  while todo:
   item=todo.pop()
   for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
    if q.GetNetname()==a.GetNetname() and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
  return z.m_Uuid.AsString() in seen
 def test_power_kelvin_connectivity_old_preservation_and_idempotence(self):
  b=self.load();b.BuildConnectivity();before=b.GetConnectivity().GetUnconnectedCount(False);out=self.pad(b,'U5604','10');sense=self.pad(b,'U5604','9');cap=self.pad(b,'C5662','1');vdd=self.pad(b,'U5602','1');self.assertFalse(self.bfs(b,out,vdd))
  old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};r=route(b);self.assertEqual(sum(len(x['added_uuids']) for x in r),17);removed=r[-1]['removed_uuids'];self.assertEqual(len(removed),1)
  now={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()}
  for uid,s in old.items():
   if uid not in removed:self.assertEqual(now.get(uid),s)
  self.assertNotIn(removed[0],now);b.BuildConnectivity();self.assertEqual(b.GetConnectivity().GetUnconnectedCount(False),before-1);self.assertTrue(self.bfs(b,out,vdd));self.assertTrue(self.bfs(b,sense,cap))
  snap=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  sense_ids=set(r[-1]['added_uuids'])
  for t in list(b.GetTracks()):
   if t.m_Uuid.AsString() in sense_ids:KEEPALIVE.append(t);b.Remove(t)
  sense.SetNet(b.FindNet('GND'));b.BuildConnectivity();self.assertTrue(self.bfs(b,out,vdd))
 def test_device_ground_contracts(self):
  for ref,pin in [('U5604','10'),('C5662','2')]:
   b=self.load();self.pad(b,ref,pin).SetNet(b.FindNet('+5V_CORE'));snap=sorted(map(signature,b.GetTracks()))
   with self.assertRaises(ValueError):route(b)
   self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  b=self.load();self.pad(b,'U5604','10').GetParentFootprint().SetValue('wrong')
  with self.assertRaises(ValueError):route(b)
 def test_shortcut_modified_duplicate_missing(self):
  for mode in ['width','duplicate','missing']:
   b=self.load();wanted=signature(track(b,*SHORTCUT,.2,p.B_Cu));t=next(t for t in b.GetTracks() if signature(t)==wanted)
   if mode=='width':t.SetWidth(p.FromMM(.25))
   elif mode=='duplicate':b.Add(track(b,*SHORTCUT,.2,p.B_Cu))
   else:KEEPALIVE.append(t);b.Remove(t)
   snap=sorted(map(signature,b.GetTracks()))
   with self.assertRaises(ValueError):route(b)
   self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_partial_route_and_duplicate_rejected(self):
  b=self.load();b.Add(planned(b)[0][-1][0]);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'Partial'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  b=self.load();route(b);b.Add(planned(b)[0][-1][0]);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'Duplicate'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_last_branch_obstacle_preserves_shortcut(self):
  b=self.load();t=track(b,(164.2,86.3),(164.2,86.7),.2,p.B_Cu);t.SetNet(b.FindNet('GND'));b.Add(t);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_same_net_drill_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetPosition(vec(FEED[-1][0]+.4,FEED[-1][1]));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet(NET));b.Add(v);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance|drill clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_kelvin_join_outside_cap_rejected(self):
  b=self.load();cap=self.pad(b,'C5662','1');s=[track(b,(163.15,85.5),(163.15,86),.2,p.B_Cu)];power=[self.pad(b,'U5604','10')]
  with self.assertRaisesRegex(ValueError,'Kelvin'):kelvin_guard(cap,s,power)
if __name__=='__main__':unittest.main()
