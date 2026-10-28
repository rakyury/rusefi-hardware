"""Guarded VIO bypass link and two local ground returns for U5605.

Only existing reviewed pads are connected; no placement or net changes.
"""
from pathlib import Path
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature

PLANS=(
 ('vio','WBO1_3V3',(('U5605','5',(161.37795,67.055558)),('C5618','1',(161.37795,69.055558))),
  ((161.37795,67.055558),(161.37795,69.055558)),None),
 ('cap_ground','GND',(('C5618','2',(162.92795,69.055558)),),
  ((162.92795,69.055558),(162.17795,69.805558)),(162.17795,69.805558)),
 ('ic_ground','GND',(('U5605','2',(166.32795,64.515558)),),
  ((166.32795,64.515558),(164.82795,64.515558),(164.82795,62.765558)),(164.82795,62.765558)),
)

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 if fps['U5605'].GetValue()!='TJA1051T/3/1J' or fps['C5618'].GetValue()!='100n':raise ValueError('VIO parts changed')
 existing=list(board.GetTracks());existing_signatures={signature(t) for t in existing};plans=[]
 for label,name,endpoints,points,via in PLANS:
  for ref,pin,position in endpoints:
   pad=next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
   if pad.GetNetname()!=name or not pad.IsOnLayer(p.B_Cu) or math.dist(xy(pad),position)>1e-5:raise ValueError('VIO endpoint contract changed')
  net=pad.GetNet();items=[]
  for a,b in zip(points,points[1:]):
   t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetLayer(p.B_Cu);t.SetWidth(p.FromMM(.25));t.SetNet(net);items.append(t)
  if via:
   v=p.PCB_VIA(board);v.SetPosition(vec(*via));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(net);items.append(v)
  present=[signature(t) in existing_signatures for t in items]
  if all(present):continue
  if any(present):raise ValueError('Partial VIO branch exists; review before routing')
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
    if any(math.dist(center,h)<.15+r+.26 for h,r in holes):raise ValueError('VIO via drill clearance blocked')
    for q in pads:
     for layer,mask in ((p.F_Cu,p.F_Mask),(p.B_Cu,p.B_Mask)):
      if q.IsOnLayer(mask) and q.GetEffectiveShape(layer).Collide(shape,p.FromMM(.1)+max(0,q.GetSolderMaskExpansion(mask))):raise ValueError('VIO via mask clearance blocked')
   else:
    shape=item.GetEffectiveShape();layers=(p.B_Cu,)
    if any(shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)) for h,r in holes):raise ValueError('VIO track hole clearance blocked')
   if not all(copper.clear(shape,bounds(item,.01),layer,name) for layer in layers):raise ValueError('VIO copper clearance blocked: '+label)
  for item in items:
   for layer in LAYERS:copper.add(item,layer)
  if via:holes.append((via,.15))
 result=[]
 for label,name,points,via,items in plans:
  for item in items:board.Add(item)
  result.append({'branch':label,'net':name,'points_mm':points,'via_mm':via,'width_mm':.25,
                 'added_uuids':[t.m_Uuid.AsString() for t in items],
                 'length_mm':round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),6)})
 return result
