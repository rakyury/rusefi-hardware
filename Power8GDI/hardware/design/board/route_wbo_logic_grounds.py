"""Guarded local ground returns for the WBO MCU and nearby C5612 3V3 bypass.

Only existing reviewed pads are connected; no placement or net changes.
"""
from pathlib import Path
import math
from collections import Counter
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature

PLANS=(
 ('bypass_ground','GND',(('C5612','2',(180.15295,66.975)),),
  ((180.15295,66.975),(180.15295,67.975)),(180.15295,67.975)),
 ('mcu_vss16','GND',(('U5602','16',(169.37795,60.0)),),
  ((169.37795,60.0),(169.37795,61.25)),(169.37795,61.25)),
 ('mcu_vss32','GND',(('U5602','32',(174.97795,68.35)),),
  ((174.97795,68.35),(176.22795,68.85)),(176.22795,68.85)),
)

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 if 'U5602' not in fps or fps['U5602'].GetValue()!='STM32F042K6T6' or fps['C5612'].GetValue()!='100n':raise ValueError('MCU ground devices changed')
 for ref,pin,position in (('U5602','1',(176.35295,66.975)),('C5612','1',(178.60295,66.975))):
  supply=next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
  if supply.GetNetname()!='WBO1_3V3' or not supply.IsOnLayer(p.F_Cu) or math.dist(xy(supply),position)>1e-5:raise ValueError('MCU supply contract changed')
 existing=list(board.GetTracks());existing_signatures=Counter(signature(t) for t in existing);plans=[]
 for label,name,endpoints,points,via in PLANS:
  for ref,pin,position in endpoints:
   pad=next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
   if pad.GetNetname()!=name or not pad.IsOnLayer(p.F_Cu) or math.dist(xy(pad),position)>1e-5:raise ValueError('logic ground endpoint contract changed')
  net=pad.GetNet();items=[]
  for a,b in zip(points,points[1:]):
   t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetLayer(p.F_Cu);t.SetWidth(p.FromMM(.25));t.SetNet(net);items.append(t)
  if via:
   v=p.PCB_VIA(board);v.SetPosition(vec(*via));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(net);items.append(v)
  if any(existing_signatures[signature(t)]>1 for t in items):raise ValueError('Duplicate logic ground geometry')
  present=[signature(t) in existing_signatures for t in items]
  if all(present):continue
  if any(present):raise ValueError('Partial logic ground branch exists; review before routing')
  # Reject an altered coincident branch rather than covering it with new copper.
  for candidate in items:
   wanted=signature(candidate)
   for old in existing:
    actual=signature(old)
    if wanted[0:3]==actual[0:3] and (wanted[0]=='via' or wanted[3]==actual[3]):raise ValueError('Existing branch geometry differs')
  plans.append((label,name,points,via,items))
 if not plans:return []
 pads=[q for f in board.GetFootprints() for q in f.Pads()];copper=Copper()
 for item in pads+existing+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
  for layer in LAYERS:copper.add(item,layer)
 holes=[(xy(t),p.ToMM(t.GetDrillValue())/2) for t in existing if isinstance(t,p.PCB_VIA)]
 holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
 for label,name,points,via,items in plans:
  for item in items:
   if isinstance(item,p.PCB_VIA):
    center=xy(item);shape=p.SHAPE_CIRCLE(vec(*center),p.FromMM(.325));layers=LAYERS
    if any(math.dist(center,h)<.15+r+.26 for h,r in holes):raise ValueError('logic ground via drill clearance blocked')
    for q in pads:
     for layer,mask in ((p.F_Cu,p.F_Mask),(p.B_Cu,p.B_Mask)):
      if q.IsOnLayer(mask) and q.GetEffectiveShape(layer).Collide(shape,p.FromMM(.1)+max(0,q.GetSolderMaskExpansion(mask))):raise ValueError('logic ground via mask clearance blocked')
   else:
    shape=item.GetEffectiveShape();layers=(p.F_Cu,)
    if any(shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)) for h,r in holes):raise ValueError('logic ground track hole clearance blocked')
   if not all(copper.clear(shape,bounds(item,.01),layer,name) for layer in layers):raise ValueError('logic ground copper clearance blocked: '+label)
  for item in items:
   for layer in LAYERS:copper.add(item,layer)
  if via:holes.append((via,.15))
 result=[]
 for label,name,points,via,items in plans:
  for item in items:board.Add(item)
  result.append({'branch':label,'net':name,'ref':next(plan[2][0][0] for plan in PLANS if plan[0]==label),'pin':next(plan[2][0][1] for plan in PLANS if plan[0]==label),'layer':'F.Cu','points_mm':points,'via_mm':via,'width_mm':.25,
                 'added_uuids':[t.m_Uuid.AsString() for t in items],
                 'length_mm':round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),6)})
 return result
