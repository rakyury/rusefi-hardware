"""Connect REF3033 input bypass locally; upstream +5V feed is separate."""
from pathlib import Path
from collections import Counter
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature
VIA=(168.,79.0625)
PLANS=(('ref_input','+5V_CORE',((165.95,77.9375),(167.95,77.9375))),('ref_input_ground','GND',((169.5,77.9375),VIA)))

def planned(board):
 result=[]
 for name,net,points in PLANS:
  t=p.PCB_TRACK(board);t.SetStart(vec(*points[0]));t.SetEnd(vec(*points[1]));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.25));t.SetNet(board.FindNet(net));result.append((name,net,points,t))
 return result

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 if fps['U5603'].GetValue()!='REF3033AIDBZR':raise ValueError('REF device changed')
 for ref,pin,net,pos in [('U5603','1','+5V_CORE',PLANS[0][2][0]),('C5617','1','+5V_CORE',PLANS[0][2][1]),('C5617','2','GND',PLANS[1][2][0])]:
  q=next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
  if q.GetNetname()!=net or not q.IsOnLayer(p.B_Cu) or math.dist(xy(q),pos)>1e-5:raise ValueError('REF pad contract changed')
 existing=list(board.GetTracks());vias=[t for t in existing if isinstance(t,p.PCB_VIA) and xy(t)==VIA]
 if len(vias)!=1:raise ValueError('REF ground via missing or duplicate')
 via=vias[0]
 if via.GetNetname()!='GND' or via.GetViaType()!=p.VIATYPE_THROUGH or via.GetWidth(p.B_Cu)!=p.FromMM(.65) or via.GetDrillValue()!=p.FromMM(.3):raise ValueError('REF ground via changed')
 plans=planned(board);counts=Counter(signature(t) for t in existing);wanted=[signature(t) for *_,t in plans]
 if any(counts[s]>1 for s in wanted):raise ValueError('Duplicate REF route')
 present=[counts[s]==1 for s in wanted]
 if all(present):return []
 if any(present):raise ValueError('Partial REF route')
 for *_,t in plans:
  for old in existing:
   if signature(t)[:4]==signature(old)[:4]:raise ValueError('Altered REF route')
 pads=[q for f in board.GetFootprints() for q in f.Pads()];copper=Copper()
 for obj in pads+existing+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
  for layer in LAYERS:copper.add(obj,layer)
 holes=[(xy(t),p.ToMM(t.GetDrillValue())/2,t.m_Uuid.AsString()) for t in existing if isinstance(t,p.PCB_VIA)]
 holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2,q.m_Uuid.AsString()) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
 for name,net,points,t in plans:
  shape=t.GetEffectiveShape()
  for h,r,uid in holes:
   if net=='GND' and uid==via.m_Uuid.AsString():continue
   if shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)):raise ValueError('REF hole clearance blocked')
  if not copper.clear(shape,bounds(t,.01),p.B_Cu,net):raise ValueError('REF copper clearance blocked')
 result=[]
 for name,net,points,t in plans:
  board.Add(t);result.append(dict(branch=name,net=net,layer='B.Cu',points_mm=points,width_mm=.25,length_mm=math.dist(*points),added_uuids=[t.m_Uuid.AsString()]))
 return result
