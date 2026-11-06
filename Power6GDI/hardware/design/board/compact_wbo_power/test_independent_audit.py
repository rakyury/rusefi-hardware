"""Fault-injection checks; never mutate the saved candidate."""
import json,tempfile,unittest
from pathlib import Path
import pcbnew as p
from independent_audit import audit
HERE=Path(__file__).resolve().parent
NETLIST=HERE.parents[1]/'core.net'
KEEP=[]
class AuditFaults(unittest.TestCase):
 def run_case(self,mutation=None,pattern=None):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);source=HERE/'candidate/WBO_Power.kicad_pcb';board=p.LoadBoard(str(source));KEEP.append(board)
   manifest=json.loads((HERE/'candidate/manifest.json').read_text())
   if mutation:mutation(board,manifest)
   path=out/'case.kicad_pcb';p.SaveBoard(str(path),board);m=out/'manifest.json';m.write_text(json.dumps(manifest))
   if pattern:
    with self.assertRaisesRegex(AssertionError,pattern):audit(path,m,NETLIST)
   else:self.assertEqual(audit(path,m,NETLIST)['native_unconnected'],0)
 def pad(self,b,r,n):return next(q for f in b.GetFootprints() if f.GetReference()==r for q in f.Pads() if q.GetNumber()==n)
 def bridge(self,b,m,a,z,net):
  t=p.PCB_TRACK(b);t.SetStart(self.pad(b,*a).GetPosition());t.SetEnd(self.pad(b,*z).GetPosition());t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.2));t.SetNet(b.FindNet(net));b.Add(t);KEEP.append(t)
  m['groups'].append({'role':'other','added_uuids':[t.m_Uuid.AsString()]})
 def test_unmodified_candidate(self):self.run_case()
 def test_early_set_ground_merge(self):
  self.run_case(lambda b,m:self.bridge(b,m,('C5660','2'),('U5604','8'),'GND'),'early Kelvin merge')
 def test_out_outs_shortcut(self):
  self.run_case(lambda b,m:self.bridge(b,m,('U5604','9'),('U5604','10'),'WBO1_3V3'),'early Kelvin merge')
 def test_reference_ground_shortcut(self):
  self.run_case(lambda b,m:self.bridge(b,m,('U5603','3'),('U5604','8'),'GND'),'early Kelvin merge')
 def test_wrong_set_net(self):
  self.run_case(lambda b,m:self.pad(b,'R5660','1').SetNet(b.FindNet('GND')),'wrong net')
 def test_shrunk_land(self):
  self.run_case(lambda b,m:self.pad(b,'C5662','1').SetSize(p.VECTOR2I(p.FromMM(.3),p.FromMM(.3))),'changed land geometry')
 def test_disconnected_reference(self):
  def mutation(b,m):
   group=next(g for g in m['groups'] if g['name']=='ref_input');ids=set(group['added_uuids'])
   for t in list(b.GetTracks()):
    if t.m_Uuid.AsString() in ids:KEEP.append(t);b.Remove(t)
   m['groups'].remove(group)
  self.run_case(mutation,'disconnected net')
if __name__=='__main__':unittest.main()
