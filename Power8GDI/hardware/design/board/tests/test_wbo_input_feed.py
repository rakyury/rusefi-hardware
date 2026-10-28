"""Native checks for real-source input feed and its PGFB/reference branches."""
import sys,unittest
from pathlib import Path
import pcbnew as p
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE))
from route_wbo_input_feed import route,planned,connected,NET
from route_wbo_ref_input import route as reference_bypass
from route_wbo_can import signature
from route_wbo_local import vec,xy
KEEPALIVE=[]
class InputFeed(unittest.TestCase):
 def load(self):
  b=p.LoadBoard(str(HERE/'gdi6_candidate/Power8GDI_Review.kicad_pcb'));plans=planned(b);KEEPALIVE.extend([b,plans]);wanted={signature(t) for *_,ts in plans for t in ts}
  for t in list(b.GetTracks()):
   if signature(t) in wanted:KEEPALIVE.append(t);b.Remove(t)
  reference_bypass(b)
  return b
 def pad(self,b,ref,pin):return next(q for f in b.GetFootprints() if f.GetReference()==ref for q in f.Pads() if q.GetNumber()==pin)
 def test_real_source_connectivity_preservation_idempotence(self):
  b=self.load();b.BuildConnectivity();before=b.GetConnectivity().GetUnconnectedCount(False);source=self.pad(b,'L5200','2')
  targets=[self.pad(b,r,n) for r,n in [('C5661','1'),('U5604','1'),('U5604','2'),('U5604','3'),('U5604','6'),('U5603','1'),('C5617','1')]]
  for q in targets:self.assertFalse(connected(b,source,q))
  old={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()};report=route(b);self.assertEqual(sum(len(r['added_uuids']) for r in report),26)
  b.BuildConnectivity();self.assertEqual(b.GetConnectivity().GetUnconnectedCount(False),before-3)
  for q in targets:self.assertTrue(connected(b,source,q))
  now={t.m_Uuid.AsString():signature(t) for t in b.GetTracks()}
  for uid,s in old.items():self.assertEqual(now[uid],s)
  snap=sorted(map(signature,b.GetTracks()));self.assertEqual(route(b),[]);self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_device_net_and_position_guards(self):
  b=self.load();self.pad(b,'L5200','2').SetNet(b.FindNet('LP5_SW'))
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'C5661','1').SetPosition(vec(158,88.078729))
  with self.assertRaises(ValueError):route(b)
  b=self.load();self.pad(b,'U5604','1').GetParentFootprint().SetValue('wrong')
  with self.assertRaises(ValueError):route(b)
 def test_source_bank_detachment_rejected(self):
  b=self.load()
  for t in list(b.GetTracks()):
   if t.GetNetname()==NET and 90<xy(t)[0]<104 and 17<xy(t)[1]<26:KEEPALIVE.append(t);b.Remove(t)
  snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'real source'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_partial_duplicate_and_modified(self):
  b=self.load();plans=planned(b);KEEPALIVE.append(plans);b.Add(plans[0][-1][0]);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'Partial'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
  b=self.load();route(b);plans=planned(b);KEEPALIVE.append(plans);b.Add(plans[0][-1][0])
  with self.assertRaisesRegex(ValueError,'Duplicate'):route(b)
  b=self.load();plans=planned(b);KEEPALIVE.append(plans);t=plans[0][-1][0];t.SetWidth(p.FromMM(.6));b.Add(t)
  with self.assertRaisesRegex(ValueError,'Altered'):route(b)
 def test_late_branch_obstacle_atomic(self):
  b=self.load();t=p.PCB_TRACK(b);t.SetStart(vec(165.2,75.3));t.SetEnd(vec(166.2,75.3));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.2));t.SetNet(b.FindNet('GND'));b.Add(t);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'copper/HV clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
 def test_same_net_drill_atomic(self):
  b=self.load();v=p.PCB_VIA(b);v.SetPosition(vec(108,43.975));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet(NET));b.Add(v);snap=sorted(map(signature,b.GetTracks()))
  with self.assertRaisesRegex(ValueError,'hole clearance'):route(b)
  self.assertEqual(snap,sorted(map(signature,b.GetTracks())))
if __name__=='__main__':unittest.main()
