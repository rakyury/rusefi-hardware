"""Native, generator-independent checks of the standalone WBO power tile."""
import argparse,json,hashlib
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET
import pcbnew as p
REFS={'U5603','U5604','R5660','R5661','R5663','C5617','C5660','C5661','C5662','C5664'}
def audit(path,manifest,netlist):
 b=p.LoadBoard(str(path));b.BuildConnectivity();c=b.GetConnectivity()
 fps={f.GetReference():f for f in b.GetFootprints()};assert set(fps)==REFS
 root=ET.parse(netlist).getroot();expected={}
 for net in root.findall('./nets/net'):
  for n in net.findall('node'):
   if n.get('ref') in REFS:expected[n.get('ref'),n.get('pin')]=net.get('name')
 unnumbered=[q for f in fps.values() for q in f.Pads() if not q.GetNumber()]
 assert all(not any(q.IsOnLayer(layer) for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)) for q in unnumbered),'Unnumbered copper land'
 pads={(r,q.GetNumber()):q for r,f in fps.items() for q in f.Pads() if q.GetNumber()}
 assert set(pads)==set(expected),('Pad population differs from netlist',set(pads)-set(expected),set(expected)-set(pads))
 for key,net in expected.items():assert pads[key].GetNetname()==net,('wrong net',key)
 # Placement may change; the approved land geometry must not be shrunk to fit.
 source=Path(netlist).parent/'board/gdi6_candidate/Power8GDI_Review.kicad_pcb'
 original=p.LoadBoard(str(source));original_pads={(f.GetReference(),q.GetNumber()):q for f in original.GetFootprints() if f.GetReference() in REFS for q in f.Pads()}
 def land(q):return (q.GetShape(),q.GetSize().x,q.GetSize().y,q.GetDrillSize().x,q.GetDrillSize().y,q.GetAttribute(),round(q.GetRoundRectRadiusRatio(),8))
 for key,q in pads.items():assert land(q)==land(original_pads[key]),('changed land geometry',key)
 for comp in root.findall('./components/comp'):
  if comp.get('ref') in REFS:
   f=fps[comp.get('ref')];assert f.GetValue()==comp.findtext('value')
   assert f.GetFPID().GetLibItemName()==comp.findtext('footprint').split(':')[-1]
 def island(seed):
  todo=[seed];seen={seed.m_Uuid.AsString()}
  while todo:
   item=todo.pop()
   for q in list(c.GetConnectedPads(item))+list(c.GetConnectedTracks(item)):
    uid=q.m_Uuid.AsString()
    if q.GetNetname()==seed.GetNetname() and uid not in seen:seen.add(uid);todo.append(q)
  return seen
 nets=defaultdict(list)
 for q in pads.values():nets[q.GetNetname()].append(q)
 for net,ps in nets.items():
  reached=island(ps[0]);assert all(q.m_Uuid.AsString() in reached for q in ps),('disconnected net',net)
 tracks={t.m_Uuid.AsString():t for t in b.GetTracks()};groups=json.loads(Path(manifest).read_text(encoding='utf-8-sig'))['groups']
 ids=[uid for g in groups for uid in g['added_uuids']]
 assert len(ids)==len(set(ids)) and set(ids)==set(tracks),'Unclassified or duplicated copper'
 for g in groups:
  if g.get('name') in ('reference_ground','reference_input_ground'):g['role']='kelvin_reference'
 def polygon(obj,layer,error):
  poly=p.SHAPE_POLY_SET();obj.TransformShapeToPolygon(poly,layer,0,1,error);return poly
 def kelvin(role,net,capkey,quietkeys):
  quietids={uid for g in groups if g['role']==role for uid in g['added_uuids']};assert quietids
  quiet=[tracks[uid] for uid in quietids];assert all(not isinstance(t,p.PCB_VIA) for t in quiet)
  layer=quiet[0].GetLayer();assert all(t.GetLayer()==layer and t.GetNetname()==net for t in quiet)
  cp=polygon(pads[capkey],layer,p.ERROR_INSIDE)
  others=[t for uid,t in tracks.items() if uid not in quietids and t.GetNetname()==net and t.IsOnLayer(layer)]
  others += [q for key,q in pads.items() if key not in quietkeys and key!=capkey and q.GetNetname()==net and q.IsOnLayer(layer)]
  for q in quiet+[pads[key] for key in quietkeys]:
   qp=polygon(q,layer,p.ERROR_OUTSIDE)
   for other in others:
    op=polygon(other,layer,p.ERROR_OUTSIDE);inter=p.SHAPE_POLY_SET();inter.BooleanIntersection(qp,op);inter.BooleanSubtract(cp)
    assert inter.OutlineCount()==0,('early Kelvin merge',role,q.m_Uuid.AsString(),other.m_Uuid.AsString())
   for zone in b.Zones():
    if zone.GetNetname()==net and zone.IsOnLayer(layer) and not zone.GetIsRuleArea():
     inter=p.SHAPE_POLY_SET();inter.BooleanIntersection(qp,zone.GetFilledPolysList(layer));inter.BooleanSubtract(cp)
     assert inter.OutlineCount()==0,('Kelvin plane shortcut',role)
  touched=False
  for t in quiet:
   inter=p.SHAPE_POLY_SET();inter.BooleanIntersection(polygon(t,layer,p.ERROR_INSIDE),cp)
   touched=touched or inter.Area()>0
  assert touched,'Kelvin misses Cout'
  return {'role':role,'tracks':len(quiet),'early_merge':False}
 result=[kelvin('kelvin_ground','GND',('C5662','2'),{('C5660','2'),('R5660','2')}),kelvin('kelvin_sense','WBO1_3V3',('C5662','1'),{('U5604','9')}),kelvin('kelvin_reference','GND',('C5662','2'),{('U5603','3'),('C5617','2'),('C5664','2')})]
 return {'board_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'components':len(fps),'pads':len(pads),'netlist_contract':'PASS','all_tile_nets_copper_connected':True,'kelvin':result,'native_unconnected':c.GetUnconnectedCount(False),'full_board_5v_source_connected':False,'full_compact_board_qualified':False}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('board',type=Path);ap.add_argument('manifest',type=Path);ap.add_argument('netlist',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
 result=audit(a.board,a.manifest,a.netlist);text=json.dumps(result,indent=2)+'\n'
 if a.output:a.output.write_text(text,encoding='utf-8')
 print(text)
