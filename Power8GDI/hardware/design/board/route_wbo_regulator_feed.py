"""Guarded LT3042 OUT10 power feed and OUTS9 Kelvin repair.

Cout and SET ground completion remains a separate prerequisite to a working LDO.
"""
from pathlib import Path
from collections import Counter
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper,LAYERS,vec,xy,bounds
from route_wbo_can import signature
FEED=((164.011038,88.078729),(166.511038,85.578729),(167.511038,85.328729),(168.011038,84.828729),(168.011038,82.578729),(169.261038,81.078729),(169.261038,79.828729),(170.511038,78.328729),(170.511038,76.078729),(173.011038,73.578729),(173.761038,73.578729),(176.011038,72.578729),(177.10295,68.975))
FRONT=(FEED[-1],(178.60295,66.975))
SENSE=((163.15,85.5),(164.2,85.5),(164.2,88.078729),(164.011038,88.078729))
SHORTCUT=((163.15,85.5),(163.15,86.0))
POWER=((163.15,86.0),FEED[0])
NET='WBO1_3V3'

def track(board,a,b,width,layer):
 t=p.PCB_TRACK(board);t.SetStart(vec(*a));t.SetEnd(vec(*b));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(board.FindNet(NET));return t

def planned(board):
 groups=[]
 for name,points,width,layer in (('power_feed',FEED,.4,p.B_Cu),('digital_vdd',FRONT,.25,p.F_Cu),('kelvin_sense',SENSE,.2,p.B_Cu)):
  items=[track(board,a,b,width,layer) for a,b in zip(points,points[1:])]
  if name=='power_feed':
   v=p.PCB_VIA(board);v.SetPosition(vec(*FEED[-1]));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(board.FindNet(NET));items.append(v)
  groups.append((name,points,width,layer,items))
 return groups

def kelvin_guard(cap,sense,power):
 """Conservative 1 nm polygon test: no common power/sense copper outside Cout."""
 cp=p.SHAPE_POLY_SET();cap.TransformShapeToPolygon(cp,p.B_Cu,0,1,p.ERROR_INSIDE)
 for st in sense:
  sp=p.SHAPE_POLY_SET();st.TransformShapeToPolygon(sp,p.B_Cu,0,1,p.ERROR_OUTSIDE)
  for pt in power:
   pp=p.SHAPE_POLY_SET();pt.TransformShapeToPolygon(pp,p.B_Cu,0,1,p.ERROR_OUTSIDE)
   overlap=p.SHAPE_POLY_SET();overlap.BooleanIntersection(sp,pp);overlap.BooleanSubtract(cp)
   if overlap.OutlineCount():raise ValueError('Kelvin copper joins power outside Cout pad')

def route(board,netlist=None):
 voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
 fps={f.GetReference():f for f in board.GetFootprints()}
 if fps['U5604'].GetValue()!='LT3042IMSE#WTRPBF' or fps['U5602'].GetValue()!='STM32F042K6T6' or fps['C5612'].GetValue()!='100n':raise ValueError('Regulator feed device contract changed')
 # Effective-capacitance-qualified replacement is an independent design review.
 if fps['C5662'].GetValue()!='10u 16V X7R effective>=4.7u':raise ValueError('Cout contract changed')
 contracts=(('U5604','10',NET,POWER[0],p.B_Cu),('U5604','9',NET,SENSE[0],p.B_Cu),('C5662','1',NET,FEED[0],p.B_Cu),('C5662','2','GND',(164.011038,91.028729),p.B_Cu),('U5602','1',NET,(176.35295,66.975),p.F_Cu),('C5612','1',NET,FRONT[-1],p.F_Cu),('C5612','2','GND',(180.15295,66.975),p.F_Cu))
 pads_by_key={}
 for ref,pin,net,pos,layer in contracts:
  q=next(q for q in fps[ref].Pads() if q.GetNumber()==pin);pads_by_key[ref,pin]=q
  if q.GetNetname()!=net or not q.IsOnLayer(layer) or math.dist(xy(q),pos)>1e-5:raise ValueError('Regulator feed endpoint contract changed')
 existing=list(board.GetTracks());counts=Counter(signature(t) for t in existing)
 shortcut_sig=signature(track(board,*SHORTCUT,.2,p.B_Cu));power_sig=signature(track(board,*POWER,.2,p.B_Cu))
 if counts[power_sig]!=1:raise ValueError('Existing OUT10 to Cout power trace changed')
 groups=planned(board);items=[t for *_,ts in groups for t in ts];wanted=[signature(t) for t in items]
 if any(counts[s]>1 for s in wanted):raise ValueError('Duplicate regulator feed geometry')
 present=[counts[s]==1 for s in wanted]
 if all(present):
  if counts[shortcut_sig]:raise ValueError('Kelvin shortcut still exists')
  return []
 if any(present):raise ValueError('Partial regulator feed exists')
 if counts[shortcut_sig]!=1:raise ValueError('Expected unique Kelvin shortcut changed or missing')
 shortcut=next(t for t in existing if signature(t)==shortcut_sig)
 for candidate in items:
  wanted_sig=signature(candidate)
  for old in existing:
   actual=signature(old)
   if wanted_sig[:3]==actual[:3] and (wanted_sig[0]=='via' or wanted_sig[3]==actual[3]):raise ValueError('Altered regulator feed geometry exists')
 pads=[q for f in board.GetFootprints() for q in f.Pads()];copper=Copper()
 for obj in pads+existing+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
  for layer in LAYERS:copper.add(obj,layer)
 holes=[(xy(t),p.ToMM(t.GetDrillValue())/2) for t in existing if isinstance(t,p.PCB_VIA)]
 holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
 for item in items:
  if isinstance(item,p.PCB_VIA):
   center=xy(item);shape=p.SHAPE_CIRCLE(vec(*center),p.FromMM(.325));layers=LAYERS
   if any(math.dist(center,h)<.15+r+.26 for h,r in holes):raise ValueError('Feed via drill clearance blocked')
   for q in pads:
    for layer,mask in ((p.F_Cu,p.F_Mask),(p.B_Cu,p.B_Mask)):
     if q.IsOnLayer(mask) and q.GetEffectiveShape(layer).Collide(shape,p.FromMM(.1)+max(0,q.GetSolderMaskExpansion(mask))):raise ValueError('Feed via mask clearance blocked')
  else:
   shape=item.GetEffectiveShape();layers=(item.GetLayer(),)
   if any(shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)) for h,r in holes):raise ValueError('Feed track hole clearance blocked')
   if item.GetStart()!=vec(*FEED[-1]) and item.GetEnd()!=vec(*FEED[-1]) and shape.Collide(p.SHAPE_CIRCLE(vec(*FEED[-1]),p.FromMM(.15)),p.FromMM(.26)):raise ValueError('Feed track conflicts with planned drill')
  if not all(copper.clear(shape,bounds(item,.01),layer,NET) for layer in layers):raise ValueError('Feed copper clearance blocked')
 sense=groups[-1][-1]
 power=[t for t in existing if t.GetNetname()==NET and t.GetLayer()==p.B_Cu and t.m_Uuid.AsString()!=shortcut.m_Uuid.AsString() and not isinstance(t,p.PCB_VIA)]+groups[0][-1][:-1]+[q for q in pads if q.GetNetname()==NET and q.IsOnLayer(p.B_Cu) and q.m_Uuid.AsString() not in {pads_by_key['U5604','9'].m_Uuid.AsString(),pads_by_key['C5662','1'].m_Uuid.AsString()}]
 kelvin_guard(pads_by_key['C5662','1'],sense,power)
 # No board mutation until every addition and the replacement topology passed.
 removed={'removed_uuids':[shortcut.m_Uuid.AsString()],'removed_signatures':[shortcut_sig]}
 board.Remove(shortcut)
 result=[]
 for name,points,width,layer,ts in groups:
  for item in ts:board.Add(item)
  report={'branch':name,'net':NET,'points_mm':points,'width_mm':width,'layer':board.GetLayerName(layer),'length_mm':round(sum(math.dist(a,b) for a,b in zip(points,points[1:])),6),'added_uuids':[t.m_Uuid.AsString() for t in ts]}
  if name=='power_feed':report['via_mm']=FEED[-1]
  if name=='kelvin_sense':report.update(removed)
  result.append(report)
 return result
