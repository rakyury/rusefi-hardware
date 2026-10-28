"""Two bounded LT3042 ground returns; SET/Cset Kelvin return remains pending."""
from pathlib import Path
from collections import Counter
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature
VIA=(159.,83.)
PLANS=(('cout_return',((164.011038,91.028729),(161.,85.)),.25),('ic_ground',((163.15,85.),(161.,85.)),.25))
def planned(board):
 result=[]
 for name,points,width in PLANS:
  t=p.PCB_TRACK(board);t.SetStart(vec(*points[0]));t.SetEnd(vec(*points[1]));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(width));t.SetNet(board.FindNet('GND'));result.append((name,points,width,t))
 return result

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 if fps['U5604'].GetValue()!='LT3042IMSE#WTRPBF' or fps['C5662'].GetValue()!='10u 16V X7R effective>=4.7u':raise ValueError('LDO return device contract changed')
 for ref,pin,net,pos in [('U5604','8','GND',(163.15,85.)),('U5604','11','GND',(161.,85.)),('C5662','2','GND',(164.011038,91.028729)),('C5662','1','WBO1_3V3',(164.011038,88.078729))]:
  q=next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
  if q.GetNetname()!=net or not q.IsOnLayer(p.B_Cu) or math.dist(xy(q),pos)>1e-5:raise ValueError('LDO return pad contract changed')
 existing=list(board.GetTracks());vias=[t for t in existing if isinstance(t,p.PCB_VIA) and xy(t)==VIA]
 if len(vias)!=1:raise ValueError('Expected unique existing GND via')
 via=vias[0]
 if via.GetViaType()!=p.VIATYPE_THROUGH:raise ValueError('Existing GND via type changed')
 if via.GetNetname()!='GND' or via.GetWidth(p.B_Cu)!=p.FromMM(.65) or via.GetDrillValue()!=p.FromMM(.3) or via.TopLayer()!=p.F_Cu or via.BottomLayer()!=p.B_Cu:raise ValueError('Existing GND via contract changed')
 ep=p.PCB_TRACK(board);ep.SetStart(vec(161.,85.));ep.SetEnd(vec(*VIA));ep.SetLayer(p.B_Cu);ep.SetWidth(p.FromMM(.2));ep.SetNet(board.FindNet('GND'))
 if sum(signature(t)==signature(ep) for t in existing)!=1:raise ValueError('Existing EP to via trace changed')
 plans=planned(board);counts=Counter(signature(t) for t in existing);wanted=[signature(t) for *_,t in plans]
 if any(counts[s]>1 for s in wanted):raise ValueError('Duplicate LDO return')
 present=[counts[s]==1 for s in wanted]
 if all(present):return []
 if any(present):raise ValueError('Partial LDO return exists')
 for *_,t in plans:
  want=signature(t)
  for old in existing:
   actual=signature(old)
   if want[:4]==actual[:4]:raise ValueError('Altered LDO return exists')
 pads=[q for f in board.GetFootprints() for q in f.Pads()];copper=Copper()
 for obj in pads+existing+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
  for layer in LAYERS:copper.add(obj,layer)
 holes=[(xy(t),p.ToMM(t.GetDrillValue())/2,t.m_Uuid.AsString()) for t in existing if isinstance(t,p.PCB_VIA)]
 holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2,q.m_Uuid.AsString()) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
 for name,points,width,t in plans:
  shape=t.GetEffectiveShape()
  for h,r,uid in holes:
   if shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)):raise ValueError('LDO return hole clearance blocked')
  if not copper.clear(shape,bounds(t,.01),p.B_Cu,'GND'):raise ValueError('LDO return copper clearance blocked')
 result=[]
 for name,points,width,t in plans:
  board.Add(t);result.append({'branch':name,'net':'GND','layer':'B.Cu','points_mm':points,'width_mm':width,'length_mm':round(math.dist(*points),6),'added_uuids':[t.m_Uuid.AsString()],'existing_via_uuid':via.m_Uuid.AsString()})
 return result
