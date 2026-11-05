"""Guarded +5V_CORE source feed from the LM76003 output bank to WBO inputs."""
from pathlib import Path
from collections import Counter
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature
NET='+5V_CORE'
PLANS=(
 ('source_to_cin',((102.,24.475),(107.5,33.475),(108.,43.975),(113.5,48.475),(114.,51.475),(116.5,52.475),(117.,52.475),(118.,53.475),(118.,54.475),(125.,60.475),(126.,61.975),(128.5,61.975),(130.,63.475),(130.,64.975),(133.,67.475),(135.5,67.475),(142.5,69.475),(156.5,85.475),(157.988962,88.078729)),.5),
 ('pgfb_supply',((163.15,84.),(159.15,82.25),(158.4,82.5),(156.5,85.475)),.25),
 ('reference_supply',((165.95,77.9375),(165.7,75.1875),(165.2,74.9375),(158.2,75.6875),(157.45,76.4375),(150.,78.046429)),.25),
)
def planned(board):
 result=[]
 for name,points,width in PLANS:
  items=[]
  for a,b in zip(points,points[1:]):
   t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetWidth(p.FromMM(width));t.SetLayer(p.B_Cu);t.SetNet(board.FindNet(NET));items.append(t)
  result.append((name,points,width,items))
 return result

def connected(board,a,z):
 c=board.GetConnectivity();todo=[a];seen={a.m_Uuid.AsString()}
 while todo:
  item=todo.pop()
  for q in list(c.GetConnectedTracks(item))+list(c.GetConnectedPads(item)):
   if q.GetNetname()==NET and q.m_Uuid.AsString() not in seen:seen.add(q.m_Uuid.AsString());todo.append(q)
 return z.m_Uuid.AsString() in seen

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 for ref,value in [('L5200','XAL7070-682MEC 6.8uH'),('C5211','47u 16V X7R'),('U5604','LT3042IMSE#WTRPBF'),('C5661','10u 16V X7R effective>=4.7u'),('U5603','REF3033AIDBZR')]:
  if fps[ref].GetValue()!=value:raise ValueError('Input feed device contract changed: '+ref)
 contracts=(('L5200','2',NET,(94.41,19.5)),('L5200','1','LP5_SW',(89.59,19.5)),('C5211','1',NET,(102.,24.475)),('C5211','2','GND',(102.,21.525)),('C5661','1',NET,(157.988962,88.078729)),('C5661','2','GND',(157.988962,91.028729)),('U5604','1',NET,(158.85,86.)),('U5604','2',NET,(158.85,85.5)),('U5604','3',NET,(158.85,85.)),('U5604','6',NET,(163.15,84.)),('U5603','1',NET,(165.95,77.9375)))
 keyed={}
 for ref,pin,net,pos in contracts:
  q=next(q for q in fps[ref].Pads() if q.GetNumber()==pin);keyed[ref,pin]=q
  if q.GetNetname()!=net or not q.IsOnLayer(p.B_Cu) or math.dist(xy(q),pos)>1e-5:raise ValueError('Input feed endpoint contract changed')
 board.BuildConnectivity()
 if not connected(board,keyed['L5200','2'],keyed['C5211','1']):raise ValueError('Output capacitor bank detached from real source')
 for pin in ['1','2','3']:
  if not connected(board,keyed['C5661','1'],keyed['U5604',pin]):raise ValueError('Local regulator input island changed')
 existing=list(board.GetTracks());counts=Counter(signature(t) for t in existing);plans=planned(board);items=[t for *_,ts in plans for t in ts];wanted=[signature(t) for t in items]
 if any(counts[s]>1 for s in wanted):raise ValueError('Duplicate input feed geometry')
 present=[counts[s]==1 for s in wanted]
 if all(present):return []
 if any(present):raise ValueError('Partial input feed exists')
 for t in items:
  want=signature(t)
  for old in existing:
   if want[:4]==signature(old)[:4]:raise ValueError('Altered input feed geometry exists')
 pads=[q for f in board.GetFootprints() for q in f.Pads()];copper=Copper()
 for obj in pads+existing+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
  for layer in LAYERS:copper.add(obj,layer)
 holes=[(xy(t),p.ToMM(t.GetDrillValue())/2) for t in existing if isinstance(t,p.PCB_VIA)]
 holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
 hole_shapes=[p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)) for h,r in holes]
 for t in items:
  shape=t.GetEffectiveShape()
  if any(shape.Collide(h,p.FromMM(.26)) for h in hole_shapes):raise ValueError('Input feed hole clearance blocked')
  if not copper.clear(shape,bounds(t,.01),p.B_Cu,NET):raise ValueError('Input feed copper/HV clearance blocked')
 result=[]
 for name,points,width,ts in plans:
  for t in ts:board.Add(t)
  result.append({'branch':name,'net':NET,'layer':'B.Cu','width_mm':width,'points_mm':points,'length_mm':round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),6),'added_uuids':[t.m_Uuid.AsString() for t in ts]})
 return result
