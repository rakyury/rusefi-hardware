"""Compact LT3042/REF3033 candidate; never edits the full-board source."""
from pathlib import Path
import argparse,json,math,shutil,os
import pcbnew as p
HERE=Path(__file__).resolve().parent
BOARD=HERE.parent
REFS={'U5603','U5604','R5660','R5661','R5663','C5617','C5660','C5661','C5662','C5664'}
PLACEMENT={'U5604':(10,10,0),'C5661':(5,13.5,-90),'C5662':(15,13,-90),'C5660':(16,9,0),'R5660':(16,7,0),'R5661':(12.5,13,-90),'U5603':(6,4,90),'C5617':(9.5,4.9375,0),'C5664':(3,2.5,90),'R5663':(12.7,5,0)}
def vec(q):return p.VECTOR2I(round(q[0]*1e6),round(q[1]*1e6))
def build(output,origin=(0,0),rotation=0):
 source=BOARD/'gdi6_candidate/Power8GDI_Review.kicad_pcb'
 b=p.LoadBoard(str(source));keep=[b]
 for obj in list(b.GetFootprints())+list(b.GetTracks())+list(b.Zones())+list(b.GetDrawings()):
  if isinstance(obj,p.FOOTPRINT) and obj.GetReference() in REFS:continue
  keep.append(obj);b.Remove(obj)
 fps={f.GetReference():f for f in b.GetFootprints()}
 for ref,(x,y,a) in PLACEMENT.items():
  f=fps[ref];f.SetOrientationDegrees(a);f.SetPosition(vec((x,y)));f.Reference().SetVisible(False);f.Value().SetVisible(False)
 groups=[]
 def track(name,net,points,width=.25,layer=p.B_Cu,role='other'):
  ids=[]
  for a,z in zip(points,points[1:]):
   t=p.PCB_TRACK(b);t.SetStart(vec(a));t.SetEnd(vec(z));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(b.FindNet(net));b.Add(t);ids.append(t.m_Uuid.AsString())
  groups.append(dict(name=name,role=role,net=net,points_mm=points,width_mm=width,layer=b.GetLayerName(layer),added_uuids=ids))
 def via(name,net,xy):
  v=p.PCB_VIA(b);v.SetPosition(vec(xy));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(b.FindNet(net));b.Add(v);groups.append(dict(name=name,role='other',net=net,position_mm=xy,added_uuids=[v.m_Uuid.AsString()]))
 track('out_power','WBO1_3V3',[(12.15,11),(13.3,11),(14.4,11.9),(15,11.9)],.3)
 track('out_sense','WBO1_3V3',[(12.15,10.5),(15,10.5),(15,11.525)],.2,role='kelvin_sense')
 track('output_bleed','WBO1_3V3',[(12.5,11),(12.5,12.175)],.25)
 track('cset_return','GND',[(16.775,9),(17.5,9),(17.5,14.475),(15,14.475)],.25,role='kelvin_ground')
 track('rset_return','GND',[(16.825,7),(17.5,7),(17.5,9)],.25,role='kelvin_ground')
 track('set','WBO1_REF_SET',[(12.15,9.5),(13.5,9.5),(14,9),(15.225,9)],.2)
 track('rset','WBO1_REF_SET',[(15.175,7),(15.175,9)],.2)
 track('series_set','WBO1_REF_SET',[(13.525,5),(14,5),(15.175,7)],.2)
 track('ground_pin','GND',[(12.15,10),(10,10)],.2)
 track('ground_ep','GND',[(10,10),(10,14.475),(15,14.475)],.4)
 track('ground_ilim','GND',[(7.85,9),(9.2,9),(10,10)],.25)
 track('ground_bleed','GND',[(12.5,13.825),(12.5,14.475)],.25)
 track('cin_return','GND',[(5,14.975),(10,14.475)],.5)
 track('input_pins','+5V_CORE',[(7.85,10),(7.85,10.5),(7.85,11),(5,12.025)],.25)
 track('input_via_exit','+5V_CORE',[(5,12.025),(5,10.5)],.4)
 via('input_via','+5V_CORE',(5,10.5))
 track('input_distribution','+5V_CORE',[(5,10.5),(5,5.75),(8.725,5.75),(13.5,5.75),(13.5,8.3)],.4,p.F_Cu)
 via('pgfb_via','+5V_CORE',(13.5,8.3))
 track('pgfb','+5V_CORE',[(13.5,8.3),(12.15,9)],.2)
 via('ref_input_via','+5V_CORE',(8.725,5.75))
 track('ref_input','+5V_CORE',[(8.725,5.75),(8.725,4.9375),(6.95,4.9375)],.25)
 track('reference','WBO1_REF3V3',[(5.05,4.9375),(3,4.9375),(3,6.5),(11.875,6.5),(11.875,5)],.25)
 track('reference_cap','WBO1_REF3V3',[(3,4.9375),(3,3.275)],.25)
 track('reference_ground','GND',[(6,3.0625),(6,1.725),(3,1.725),(2,1.725),(2,16.5),(15,16.5),(15,14.475)],.3)
 track('reference_input_ground','GND',[(10.275,4.9375),(10.275,2),(6,2)],.25)
 via('thermal_ep','GND',(10,10))
 zone=p.ZONE(b);zone.SetLayer(p.In1_Cu);zone.SetNet(b.FindNet('GND'));zone.SetLocalClearance(p.FromMM(.2));zone.SetThermalReliefGap(p.FromMM(.25));zone.SetThermalReliefSpokeWidth(p.FromMM(.3));zone.SetPadConnection(p.ZONE_CONNECTION_FULL);poly=zone.Outline();poly.NewOutline()
 for q in [(1,1),(19,1),(19,17),(1,17)]:poly.Append(int(q[0]*1e6),int(q[1]*1e6))
 b.Add(zone)
 # Prevent a later same-net B.Cu pour from silently bypassing the Kelvin star.
 ko=p.ZONE(b);ko.SetLayer(p.B_Cu);ko.SetIsRuleArea(True);ko.SetDoNotAllowCopperPour(True);ko.SetDoNotAllowTracks(False);ko.SetDoNotAllowVias(False);ko.SetDoNotAllowPads(False);ko.SetDoNotAllowFootprints(False);poly=ko.Outline();poly.NewOutline()
 for q in [(0,0),(20,0),(20,18),(0,18)]:poly.Append(int(q[0]*1e6),int(q[1]*1e6))
 b.Add(ko)
 # A candidate tile outline is not a proposed full ECU outline.
 for a,z in zip([(0,0),(20,0),(20,18),(0,18)],[(20,0),(20,18),(0,18),(0,0)]):
  s=p.PCB_SHAPE();s.SetShape(p.SHAPE_T_SEGMENT);s.SetStart(vec(a));s.SetEnd(vec(z));s.SetLayer(p.Edge_Cuts);s.SetWidth(p.FromMM(.05));b.Add(s)
 if rotation:
  for obj in list(b.GetFootprints())+list(b.GetTracks())+list(b.GetDrawings())+list(b.Zones()):obj.Rotate(vec((0,0)),p.EDA_ANGLE(rotation,p.DEGREES_T))
 if origin!=(0,0):
  for obj in list(b.GetFootprints())+list(b.GetTracks())+list(b.GetDrawings())+list(b.Zones()):obj.Move(vec(origin))
 p.ZONE_FILLER(b).Fill(b.Zones());output.mkdir(parents=True,exist_ok=True);p.SaveBoard(str(output/'WBO_Power.kicad_pcb'),b)
 for ext in ('.kicad_pro','.kicad_dru'):shutil.copyfile(source.with_suffix(ext),output/('WBO_Power'+ext))
 relative=Path(os.path.relpath(source.parent.resolve(),output.resolve())).as_posix()
 table=(source.parent/'fp-lib-table').read_text();table=table.replace('${KIPRJMOD}','${KIPRJMOD}/'+relative);(output/'fp-lib-table').write_text(table)
 b.BuildConnectivity();report={'source_board':str(source),'groups':groups,'placement':PLACEMENT,'origin_mm':origin,'rotation_degrees':rotation,'tile_size_mm':[20,18],'native_unconnected':b.GetConnectivity().GetUnconnectedCount(False),'ports':{'+5V_CORE':['C5661','1'],'GND':['C5662','2'],'WBO1_3V3':['C5662','1']},'full_board_source_connected':False}
 angle=math.radians(rotation)
 def world(q):return [round(origin[0]+q[0]*math.cos(angle)+q[1]*math.sin(angle),6),round(origin[1]-q[0]*math.sin(angle)+q[1]*math.cos(angle),6)]
 for g in groups:
  if 'points_mm' in g:g['world_points_mm']=[world(q) for q in g['points_mm']]
  if 'position_mm' in g:g['world_position_mm']=world(g['position_mm'])
 report['world_placement']={ref:{'position_mm':[p.ToMM(f.GetPosition().x),p.ToMM(f.GetPosition().y)],'angle_degrees':f.GetOrientationDegrees()} for ref,f in fps.items()}
 report['world_ports']={name:{'ref':ref,'pin':pin,'position_mm':[p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y)]} for name,(ref,pin) in report['ports'].items() for q in fps[ref].Pads() if q.GetNumber()==pin}
 report['constraints']={'reserved_outline_world_mm':[world(q) for q in [(0,0),(20,0),(20,18),(0,18)]],'foreign_copper_inside_reserved_area':'forbidden until integration DRC and Kelvin proof rerun','B_Cu_zone_fill':'prohibited by actual rule-area; preserve it on integration','kelvin_ground_star':'C5662.2 only; no extra via/plane/same-net shortcut on C5660.2 or R5660.2 branches','kelvin_sense_star':'C5662.1 only; OUTS9 must not join OUT10 earlier','thermal':'In1 GND contact through EP via present; thermal dissipation, via construction and case heat path unqualified','EMI':'Do not place boost/ignition/motor switching copper inside or across this quiet module; final spacing/return partition requires full-board review','source':'External +5V_CORE source not connected in this standalone tile','load':'External WBO load distribution not connected; take power and ground at Cout pads'}
 (output/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'tracks':len(b.GetTracks()),'unconnected':report['native_unconnected']}))
 return b,report,keep
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=HERE/'candidate');ap.add_argument('--origin',nargs=2,type=float,default=[0,0]);ap.add_argument('--rotation',type=float,default=0);a=ap.parse_args();build(a.output,tuple(a.origin),a.rotation)
