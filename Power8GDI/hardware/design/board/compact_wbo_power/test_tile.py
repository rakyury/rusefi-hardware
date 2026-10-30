"""Native transform/integration contract tests; no hardware qualification."""
import hashlib,json,math,sys,tempfile,unittest,subprocess
from pathlib import Path
import pcbnew as p
from build_tile import build,BOARD,REFS
KEEP=[]
class Tile(unittest.TestCase):
 def test_rigid_transform_preserves_ports_and_every_route(self):
  source=BOARD/'gdi6_candidate/Power8GDI_Review.kicad_pcb';before=hashlib.sha256(source.read_bytes()).hexdigest()
  with tempfile.TemporaryDirectory() as temp:
   for rotation in (0,90,180,270):
    b,m,owners=build(Path(temp)/str(rotation),(31,42),rotation);KEEP.extend([b,owners]);tracks={t.m_Uuid.AsString():t for t in b.GetTracks()}
    self.assertEqual({f.GetReference() for f in b.GetFootprints()},REFS);self.assertEqual(m['native_unconnected'],0)
    self.assertFalse(m['full_board_source_connected'])
    for g in m['groups']:
     if 'world_points_mm' in g:
      for uid,a,z in zip(g['added_uuids'],g['world_points_mm'],g['world_points_mm'][1:]):
       t=tracks[uid]
       for actual,want in [(t.GetStart(),a),(t.GetEnd(),z)]:
        self.assertLess(math.dist((p.ToMM(actual.x),p.ToMM(actual.y)),want),2e-6)
     else:
      t=tracks[g['added_uuids'][0]];self.assertLess(math.dist((p.ToMM(t.GetPosition().x),p.ToMM(t.GetPosition().y)),g['world_position_mm']),2e-6)
    kos=[z for z in b.Zones() if z.GetIsRuleArea()];self.assertEqual(len(kos),1);self.assertTrue(kos[0].GetDoNotAllowCopperPour());self.assertEqual(kos[0].GetLayer(),p.B_Cu)
    c=b.GetConnectivity();epvia=next(tracks[g['added_uuids'][0]] for g in m['groups'] if g['name']=='thermal_ep');self.assertTrue(c.IsConnectedOnLayer(epvia,p.In1_Cu))
    out=Path(temp)/str(rotation);result=subprocess.run(['kicad-cli','pcb','drc','--format','json','--all-track-errors','--severity-all','--exit-code-violations','-o',str(out/'drc.json'),str(out/'WBO_Power.kicad_pcb')],capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr);report=json.loads((out/'drc.json').read_text());self.assertEqual(report['violations'],[]);self.assertEqual(report['unconnected_items'],[])
  self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
if __name__=='__main__':unittest.main()
