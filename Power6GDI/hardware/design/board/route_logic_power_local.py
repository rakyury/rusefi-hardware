"""Local logic-power placement/route module; only refs5200..5399 may move.

Runs in pinned KiCad9 Python. Input is never overwritten. Existing copper is
preserved. A rigid local power cell must clear every foreign pad/track/via and
same-side component before being accepted. No global auto-router or DRC-rule
modification is performed. Partial routes and rejected paths are reported.
"""
from __future__ import annotations
import argparse, json, math, hashlib
from pathlib import Path
import pcbnew as p
import voltage_domains
import lm_boot_escape

REGION=(5.,5.,151.,55.)
# x,y,angle in B.Cu local coordinates. Dense supply/BOOT/FB placement has a
# deliberate side: switching right, low-level feedback/soft start left.
CELLS={
 '5v':{
 'U5200':(0,0,90),'L5200':(8,2,0),
 'C5200':(0,-8,90),'C5201':(-4,-8,90),'C5202':(1.5,-4,0),
 'C5203':(2,5,0),'C5204':(-1,5.5,270),'C5205':(-4.5,5.5,270),
 'C5206':(-8.5,4.7,180),'C5207':(-9,-.5,90),
 'C5208':(14,0,90),'C5209':(18,0,90),'C5210':(14,5.5,90),'C5211':(18,5.5,90),
 'R5200':(-5.7,.8,0),'R5201':(-5.7,-1.7,0),
 'R5202':(-4.5,-4,0),'R5203':(-8.5,-3.8,0),
 'R5204':(-4,10,0),'R5205':(-.5,10,0)},
 '3v3':{
 'U5300':(0,0,0),'L5300':(-6,.5,180),
 'C5300':(4.5,1.3,90),'C5301':(6,-2.5,90),
 'C5302':(-10.8,.5,90),'C5303':(3,-3.5,0),
 'R5300':(-3.2,-5.5,0),'R5301':(0,-5.5,0),'R5302':(-6,-5.5,90),
 'R5303':(-10.8,5,0)},
}

def v(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def mm(q):return (p.ToMM(q.x),p.ToMM(q.y))
def ref_owned(ref):
 try:return 5200<=int(ref.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))<5400
 except ValueError:return False

def rect(item):
 b=item.GetBoundingBox(False,False) if isinstance(item,p.FOOTPRINT) else item.GetBoundingBox()
 return tuple(p.ToMM(z) for z in (b.GetX(),b.GetY(),b.GetRight(),b.GetBottom()))
def overlap(a,b,gap=0):return a[0]<b[2]+gap and a[2]>b[0]-gap and a[1]<b[3]+gap and a[3]>b[1]-gap

def position(fp,x,y,angle):
 if fp.GetLayer()!=p.B_Cu:fp.Flip(fp.GetPosition(),False)
 fp.SetOrientationDegrees(angle);fp.SetPosition(v(x,y))

def snapshot(board):
 return {f.GetReference():(mm(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer()) for f in board.GetFootprints()}

def obstacles(board,omit,fixed=None):
 bodies=[];copper=[]
 for f in board.GetFootprints():
  if f.GetReference() in omit or (fixed is not None and f.GetReference() not in fixed):continue
  if f.GetLayer()==p.B_Cu:bodies.append((rect(f),f.GetReference()))
  for q in f.Pads():
   if not q.IsOnLayer(p.B_Cu):continue
   copper.append((rect(q),q.GetNetname(),f.GetReference()+'.'+q.GetNumber()))
 for t in board.GetTracks():
  if t.IsOnLayer(p.B_Cu):copper.append((rect(t),t.GetNetname(),'track/via:'+str(t.m_Uuid)))
 return bodies,copper

class Grid:
 def __init__(self,items):
  self.items=items;self.bins={}
  for i,item in enumerate(items):
   a=item[0]
   for x in range(math.floor(a[0]/3),math.floor(a[2]/3)+1):
    for y in range(math.floor(a[1]/3),math.floor(a[3]/3)+1):self.bins.setdefault((x,y),set()).add(i)
 def near(self,a):
  inds=set()
  for x in range(math.floor((a[0]-1)/3),math.floor((a[2]+1)/3)+1):
   for y in range(math.floor((a[1]-1)/3),math.floor((a[3]+1)/3)+1):inds.update(self.bins.get((x,y),()))
  return [self.items[i] for i in inds]

def cell_geometry(fps,plan):
 for ref,(x,y,a) in plan.items():position(fps[ref],x,y,a)
 boxes={ref:rect(fps[ref]) for ref in plan}
 # Actual numbered copper pads; unnumbered paste apertures are not obstacles.
 pads=[(rect(q),q.GetNetname(),ref+'.'+q.GetNumber()) for ref in plan for q in fps[ref].Pads() if q.IsOnLayer(p.B_Cu)]
 bb=(min(a[0] for a in boxes.values()),min(a[1] for a in boxes.values()),max(a[2] for a in boxes.values()),max(a[3] for a in boxes.values()))
 return boxes,pads,bb

def shift(a,x,y):return (a[0]+x,a[1]+y,a[2]+x,a[3]+y)

def fit_cell(board,fps,plan,occupied,region=REGION,fixed=None):
 boxes,pads,bounds=cell_geometry(fps,plan)
 internal=[(a,b) for i,a in enumerate(boxes) for b in list(boxes)[i+1:] if overlap(boxes[a],boxes[b],.10)]
 if internal:return None,{'reason':'template_body_conflict','pairs':internal}
 bodies,copper=obstacles(board,set(plan)|occupied,fixed)
 bodies,copper=Grid(bodies),Grid(copper)
 best=None;nearest=None
 for xi in range(math.ceil((region[0]-bounds[0])*2),math.floor((region[2]-bounds[2])*2)+1):
  x=xi/2
  for yi in range(math.ceil((region[1]-bounds[1])*2),math.floor((region[3]-bounds[3])*2)+1):
   y=yi/2;bad=[]
   for ref,b in boxes.items():
    r=shift(b,x,y)
    for foreign,name in bodies.near(r):
     if overlap(r,foreign,.15):bad.append((ref,name,'body'))
   for b,net,ref in pads:
    r=shift(b,x,y)
    for foreign,other,name in copper.near(r):
     gap=max(.3,voltage_domains.clearance_mm(net),voltage_domains.clearance_mm(other))
     if net==other and net:continue
     if overlap(r,foreign,gap):bad.append((ref,name,'copper'))
   if nearest is None or len(bad)<nearest['conflicts']:
    nearest={'anchor_mm':[x,y],'conflicts':len(bad),'examples':bad[:12]}
   if not bad:
    score=(x-28)**2+(y-35)**2
    if best is None or score<best[0]:best=(score,x,y)
 if best:
  _,x,y=best
  for ref,(dx,dy,a) in plan.items():position(fps[ref],x+dx,y+dy,a)
  return [x,y],{'bounds_mm':list(shift(bounds,x,y)),'conflicts':0}
 return None,{'reason':'no_free_rigid_cell_in_assigned_region','local_bounds_mm':bounds,'nearest':nearest}

def assert_unrouted(board,fps):
 ownpads=[q for ref,f in fps.items() if ref_owned(ref) for q in f.Pads() if q.GetNumber()]
 for t in board.GetTracks():
  if t.GetNetname().startswith(('LP5_','LP33_')):raise ValueError('Existing local buck copper: moving footprints would detach tracks')
  for q in ownpads:
   if q.GetNetname()!=t.GetNetname() or not q.IsOnLayer(t.GetLayer()):continue
   if q.HitTest(t.GetStart()) or q.HitTest(t.GetEnd()):raise ValueError('Existing copper touches owned pad '+q.GetParentFootprint().GetReference()+'.'+q.GetNumber())

def propose(board,fixed=None,region=REGION):
 voltage_domains.provenance() # Fail closed when the real netlist was not audited.
 fps={f.GetReference():f for f in board.GetFootprints()};before=snapshot(board)
 assert_unrouted(board,fps)
 required={r for plan in CELLS.values() for r in plan}
 if not required<=set(fps):raise ValueError('Missing cell refs: '+str(sorted(required-set(fps))))
 # Both cells temporarily omitted from obstacles during their own search;
 # the accepted first cell is a real obstacle for the second one.
 report={'region_mm':region,'cells':{},'status':'PLACEMENT_NOT_ROUTED','rules_modified':False}
 pending=set(required)
 for name,plan in CELLS.items():
  pending-=set(plan)
  anchor,detail=fit_cell(board,fps,plan,pending,region=region,fixed=fixed)
  report['cells'][name]={'anchor_mm':anchor,**detail}
  if anchor is not None and fixed is not None:fixed.update(plan)
  if anchor is None:
   for ref in plan:
    (x,y),a,layer=before[ref]
    if fps[ref].GetLayer()!=layer:fps[ref].Flip(fps[ref].GetPosition(),False)
    fps[ref].SetOrientationDegrees(a);fps[ref].SetPosition(v(x,y))
 after=snapshot(board)
 for ref,old in before.items():
  if not ref_owned(ref) and after[ref]!=old:raise AssertionError('Foreign footprint moved: '+ref)
 report['unchanged_foreign_footprints']=len(before)-sum(ref_owned(r) for r in before)
 return report

def segment_rect_hit(a,b,r):
 # Liang-Barsky line clipping against a clearance-inflated rectangle.
 dx,dy=b[0]-a[0],b[1]-a[1];lo,hi=0.,1.
 for pp,qq in ((-dx,a[0]-r[0]),(dx,r[2]-a[0]),(-dy,a[1]-r[1]),(dy,r[3]-a[1])):
  if abs(pp)<1e-12:
   if qq<0:return False
  elif pp<0:lo=max(lo,qq/pp)
  else:hi=min(hi,qq/pp)
  if lo>hi:return False
 return True

def segment_distance(a,b,c,d):
 # Minimum Euclidean distance between two closed 2-D segments, not their
 # axis-aligned boxes (diagonal box overlap falsely blocks local ground).
 def cross(u,w):return u[0]*w[1]-u[1]*w[0]
 def sub(u,w):return (u[0]-w[0],u[1]-w[1])
 ab,cd,ac=sub(b,a),sub(d,c),sub(c,a)
 denom=cross(ab,cd)
 if abs(denom)>1e-12:
  t,u=cross(ac,cd)/denom,cross(ac,ab)/denom
  if 0<=t<=1 and 0<=u<=1:return 0.
 def point(q,u,w):
  dw=sub(w,u);ll=dw[0]**2+dw[1]**2
  t=max(0.,min(1.,((q[0]-u[0])*dw[0]+(q[1]-u[1])*dw[1])/ll)) if ll else 0.
  return math.hypot(q[0]-u[0]-t*dw[0],q[1]-u[1]-t*dw[1])
 return min(point(a,c,d),point(b,c,d),point(c,a,b),point(d,a,b))

class LocalRouter:
 def __init__(self,board,fps,fixed,report):
  self.board,self.fps,self.fixed,self.report=board,fps,set(fixed),report
  self.tracks=[];self.vias=[];self.blocked=[];self.cache={};self.pad_shapes={}
 def obstacles(self,layer):
  if layer in self.cache:return self.cache[layer]
  out=[]
  for f in self.board.GetFootprints():
   if f.GetReference() not in self.fixed and not ref_owned(f.GetReference()):continue
   for q in f.Pads():
    if q.IsOnLayer(layer):
     owner=f.GetReference()+'.'+q.GetNumber()
     out.append((rect(q),q.GetNetname(),owner,None))
     self.pad_shapes[(layer,owner)]=q.GetEffectiveShape(layer)
  for t in self.board.GetTracks():
   if t.IsOnLayer(layer):out.append((rect(t),t.GetNetname(),'copper:'+t.GetNetname()+':'+t.m_Uuid.AsString(),(mm(t.GetStart()),mm(t.GetEnd()),p.ToMM(t.GetWidth(layer) if isinstance(t,p.PCB_VIA) else t.GetWidth())/2)))
  self.cache[layer]=out
  return out
 def path(self,net,pts,width=.2,label='',check_only=False,layer=p.B_Cu):
  obs=self.obstacles(layer);bad=[]
  for a,b in zip(pts,pts[1:]):
   for r,n,owner,shape in obs:
    if n==net:continue
    # No fine-pitch exception is silently applied. A branch that cannot meet
    # the shared voltage policy is rejected whole, even at its own IC pads.
    clearance=max(voltage_domains.clearance_mm(n),voltage_domains.clearance_mm(net))
    if lm_boot_escape.permits(self.board,net,a,b,width,layer,owner):clearance=.25
    e=clearance+width/2-1e-6
    if not overlap((min(a[0],b[0])-e,min(a[1],b[1])-e,max(a[0],b[0])+e,max(a[1],b[1])+e),r):continue
    if shape:
     c,d,radius=shape
     hit=segment_distance(a,b,c,d)<e+radius
    else:hit=self.pad_shapes[(layer,owner)].Collide(p.SHAPE_SEGMENT(v(*a),v(*b),p.FromMM(width)),p.FromMM(clearance-1e-6))
    if hit:bad.append(owner)
  if bad:
   
   if not check_only:self.blocked.append({'label':label,'net':net,'obstacles':sorted(set(bad))})
   return False
  if check_only:return True
  ni=self.board.FindNet(net)
  for a,b in zip(pts,pts[1:]):
   t=p.PCB_TRACK(self.board);t.SetStart(v(*a));t.SetEnd(v(*b));t.SetWidth(p.FromMM(width));t.SetLayer(layer);t.SetNet(ni);self.board.Add(t)
   self.tracks.append({'uuid':t.m_Uuid.AsString(),'net':net,'start_mm':a,'end_mm':b,'width_mm':width,'layer':self.board.GetLayerName(layer),'label':label})
  self.cache.clear()
  return True
 def via(self,xy,label,check_only=False,net='GND'):
  r=(xy[0]-.3,xy[1]-.3,xy[0]+.3,xy[1]+.3);bad=[]
  # Same-net copper may merge, but drilled holes still require a physical
  # web of laminate. Check all holes, including GND vias and NPTH pads.
  for t in self.board.GetTracks():
   if isinstance(t,p.PCB_VIA):
    centre=mm(t.GetPosition())
    if math.dist(xy,centre)<.15+p.ToMM(t.GetDrillValue())/2+.25-1e-6:
     bad.append('hole:'+t.m_Uuid.AsString())
  for f in self.board.GetFootprints():
   if f.GetReference() not in self.fixed and not ref_owned(f.GetReference()):continue
   for pad in f.Pads():
    drill=mm(pad.GetDrillSize())
    if max(drill)>0 and math.dist(xy,mm(pad.GetPosition()))<.15+max(drill)/2+.25-1e-6:
     bad.append('hole:'+f.GetReference()+'.'+pad.GetNumber())
  for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu):
   for foreign,n,owner,shape in self.obstacles(layer):
    if n==net:continue
    gap=max(.3,voltage_domains.clearance_mm(n),voltage_domains.clearance_mm(net))
    hit=segment_distance(xy,xy,shape[0],shape[1])<.3+gap+shape[2] if shape else overlap(r,foreign,gap)
    if hit:bad.append(owner)
  if bad:
   if not check_only:self.blocked.append({'label':label,'net':net,'obstacles':sorted(set(bad))})
   return False
  if check_only:return True
  q=p.PCB_VIA(self.board);q.SetPosition(v(*xy));q.SetWidth(p.FromMM(.6));q.SetDrill(p.FromMM(.3));q.SetViaType(p.VIATYPE_THROUGH);q.SetLayerPair(p.F_Cu,p.B_Cu);q.SetNet(self.board.FindNet(net));self.board.Add(q)
  self.cache.clear()
  self.vias.append({'uuid':q.m_Uuid.AsString(),'net':net,'xy_mm':xy,'diameter_mm':.6,'drill_mm':.3,'label':label});return True
 def front_bridge(self,net,start,end,label):
  # Only an explicitly requested low-current sense/control connection is
  # considered: short B.Cu pad exits, all-layer-checked vias, and a checked
  # F.Cu dogleg shielded from B.Cu switching by the inner ground plane.
  def candidates(xy):
   found=[]
   for distance in (1.2,1.5,1.8,2.2):
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
     point=(xy[0]+dx*distance,xy[1]+dy*distance)
     if self.via(point,label,True,net) and self.path(net,[xy,point],.2,label,True):found.append(point)
   return found[:8]
  for a in candidates(start):
   for b in candidates(end):
    paths=[[a,b],[a,(a[0],b[1]),b],[a,(b[0],a[1]),b]]
    for offset in (-3.,3.,-6.,6.):
     y=max(a[1],b[1])+offset
     paths.append([a,(a[0],y),(b[0],y),b])
    for pts in paths:
     if not self.path(net,pts,.2,label,True,p.F_Cu):continue
     # The accepted branch is inserted atomically after all its obstacles
     # were checked. Same-net segments may join but no foreign item moves.
     assert self.path(net,[start,a],.2,label)
     assert self.path(net,[end,b],.2,label)
     assert self.via(a,label,False,net)
     assert self.via(b,label,False,net)
     assert self.path(net,pts,.2,label,False,p.F_Cu)
     return True
  self.blocked.append({'label':label,'net':net,'obstacles':['No checked B.Cu exit / all-layer via / F.Cu sense corridor']})
  return False

def route_cells(board,fps,fixed,report):
 router=LocalRouter(board,fps,fixed,report)
 def run(name,plans):
  anchor=report['cells'][name]['anchor_mm']
  if anchor is None:return
  x,y=anchor
  for net,pts,w,label in plans:router.path(net,[(x+a,y+b) for a,b in pts],w,label)
 # Intentional short power paths, pin necks and feedback paths. A path is
 # rejected as a whole on collision; no item is silently cut or net-swapped.
 run('3v3',[
 ('LP33_SW',[(-1.4625,-.25),(-2,-.25),(-2,.75),(-1.4625,.75)],.2,'TPS SW pin bus'),
 ('LP33_SW',[(-1.4625,.25),(-2,.25)],.2,'TPS SW middle pin'),
 ('LP33_SW',[(-2,.25),(-4.345,.5)],.6,'TPS SW to inductor'),
 ('+3V3',[(-7.655,.5),(-9.2,.5),(-10.8,1.975)],.6,'TPS inductor to Cout'),
 ('+5V_CORE',[(1.4625,.25),(2.2,.25),(2.2,.75),(1.4625,.75)],.2,'TPS PVIN bus'),
 ('+5V_CORE',[(2.2,.75),(3.7,2.25),(4.5,2.25)],.6,'TPS input capacitor to PVIN'),
 ('+5V_CORE',[(1.4625,-.25),(3,-.25),(6,-1.55)],.2,'TPS AVIN bypass'),
 ('+5V_CORE',[(.25,-1.4625),(.25,-2.5),(1,-2.5),(1,-4.7),(7.5,-4.7),(7.5,-1.55),(6,-1.55)],.2,'TPS FSW high'),
 ('LP33_FB',[(-.75,-1.4625),(-.75,-3),(-.825,-5.5),(-2.375,-5.5)],.2,'TPS quiet FB divider'),
 ('+3V3',[(-10.8,1.975),(-13,1.975),(-13,-4.675),(-6,-4.675),(-4.025,-4.675),(-4.025,-5.5)],.2,'TPS divider and PG pullup output sense'),
 ('GND',[(.825,-5.5),(.825,-6.7),(.25,-6.7),(.25,-3.2),(-.25,-3.2),(-.25,-1.4625)],.2,'TPS divider quiet AGND return'),
 ('+3V3',[(-11.625,5),(-13,5),(-13,1.975)],.2,'TPS output bleed supply'),
 ('LP33_SS',[(1.4625,-.75),(2.05,-.75),(2.05,-3.5)],.2,'TPS soft start'),
 ('+3V3',[(.25,1.4625),(.25,3.5),(-7.655,3.5),(-7.655,.5)],.2,'TPS VOS separate output sense'),
 ('GND',[(-.25,-1.4625),(-.25,0)],.2,'TPS AGND to EP'),
 ('GND',[(.75,-1.4625),(.75,0)],.2,'TPS DEF to EP'),
 ('GND',[(-.25,1.4625),(-.25,0)],.2,'TPS PGND15 to EP'),
 ('GND',[(-.75,1.4625),(-.75,0)],.2,'TPS PGND16 to EP'),
 ('LP5_PG_RAW',[(.75,1.4625),(.75,3.8),(2,3.8)],.2,'TPS EN breakout; connect LM PG globally'),
 ])
 run('5v',[
 ('VBAT_LOGIC_PROTECTED',[(-.45,-1.8625),(-.45,-2.7),(.45,-2.7),(.45,-1.8625)],.2,'LM PVIN bus'),
 ('VBAT_LOGIC_PROTECTED',[(0,-1.8625),(0,-2.7)],.2,'LM PVIN middle'),
 ('VBAT_LOGIC_PROTECTED',[(0,-2.7),(0,-4),(.55,-4)],.5,'LM HF input cap'),
 ('VBAT_LOGIC_PROTECTED',[(0,-4),(0,-6.525),(-4,-6.525)],.7,'LM bulk input cap pair'),
 ('GND',[(2.5,-1.8625),(2.5,-4),(2.45,-4)],.5,'LM HF cap ground to PGND'),
 ('GND',[(1.5,-1.8625),(1.5,-2.6),(2.5,-2.6)],.2,'LM PGND24'),
 ('GND',[(2,-1.8625),(2,-2.6)],.2,'LM PGND25'),
 ('GND',[(1.5,-1.8625),(1.5,-.35)],.4,'LM PGND to exposed pad'),
 ('GND',[(0,-9.475),(4,-9.475),(4,-4),(2.45,-4)],.6,'LM bulk input return to HF ground'),
 ('GND',[(-4,-9.475),(0,-9.475)],.6,'LM bulk capacitor ground pair'),
 ('LP5_SW',[(.55,1.8625),(.55,2.8),(2.5,2.8),(2.5,1.8625)],.2,'LM SW pin bus'),
 ('LP5_SW',[(1,1.8625),(1,2.8)],.2,'LM SW pin4'),
 ('LP5_SW',[(1.5,1.8625),(1.5,2.8)],.2,'LM SW pin3'),
 ('LP5_SW',[(2,1.8625),(2,2.8)],.2,'LM SW pin2'),
 ('LP5_SW',[(2.5,2.8),(4.4,2.8),(5.59,2)],.8,'LM SW to inductor'),
 ('LP5_SW',[(2.95,5),(2.95,3.55),(2.5,2.8)],.2,'LM BOOT capacitor SW return'),
 ('+5V_CORE',[(10.41,2),(12,2),(14,1.475),(18,1.475)],.8,'LM output capacitor row1'),
 ('+5V_CORE',[(12,2),(12,6.975),(14,6.975),(18,6.975)],.8,'LM output capacitor row2'),
 ('LP5_FB',[(-2.9875,.75),(-4,.75),(-4.875,.8)],.2,'LM FB to upper resistor'),
 ('GND',[(-2.9875,.25),(-1.5,.25)],.2,'LM AGND13 to EP'),
 ('GND',[(-2.9875,-.25),(-1.5,-.25)],.2,'LM AGND14 to EP'),
 ('GND',[(-2.9875,-.75),(-1.5,-.75)],.2,'LM AGND15 to EP'),
 ('GND',[(-.55,1.8625),(-.55,.4)],.2,'LM PGND7 to EP'),
 ('GND',[(-2,-1.8625),(-2,-.4)],.2,'LM MODE to EP'),
 ('GND',[(-1.05,-1.8625),(-1.05,-.4)],.2,'LM NC19 ground to EP'),
 ('GND',[(1.05,-1.8625),(1.05,-.4)],.2,'LM NC23 ground to EP'),
 ('GND',[(2.9875,-.75),(1.5,-.75)],.2,'LM NC27 ground to EP'),
 ('GND',[(2.9875,-.25),(1.5,-.25)],.2,'LM NC28 ground to EP'),
 ('GND',[(2.9875,.25),(1.5,.25)],.2,'LM NC29 ground to EP'),
 ('GND',[(2.9875,.75),(1.5,.75)],.2,'LM NC30 ground to EP'),
 ('LP5_EN',[(-1.5,-1.8625),(-1.5,-3),(-3.675,-4)],.2,'LM EN divider to pin'),
 ('LP5_EN',[(-3.675,-4),(-3.675,-2.9),(-9.325,-2.9),(-9.325,-3.8)],.2,'LM EN divider midpoint'),
 ('LP5_VCC',[(-1,1.8625),(-1,4.55)],.2,'LM VCC bypass'),
 ('+5V_CORE',[(-1.5,1.8625),(-1.5,3.3),(-4.5,3.3),(-4.5,4.55)],.2,'LM BIAS local bypass'),
 ('LP5_SS',[(-2.5,1.8625),(-2.5,2.75),(-7.55,2.75),(-7.55,4.7)],.2,'LM soft start'),
 ('LP5_FB',[(-9,-1.45),(-6.525,-1.7),(-6.525,-.45),(-4.875,-.45),(-4.875,.8)],.2,'LM FB lower resistor and Cff'),
 ('+5V_CORE',[(-9,.45),(-6.525,.8)],.2,'LM Cff parallel upper resistor'),
 ('GND',[(-4.875,-1.7),(-4,-1.7),(-4,-.25),(-2.9875,-.25)],.2,'LM divider quiet AGND return'),
 ('GND',[(-9.45,4.7),(-10.5,4.7),(-10.5,1.7),(-3.8,1.7),(-3.8,1.2),(-2.9875,1.2),(-2,1.2),(-2,.4)],.2,'LM SS quiet AGND return'),
 ('+5V_CORE',[(-9,.45),(-11.7,.45),(-11.7,12),(20,12),(20,6.975),(18,6.975)],.3,'LM output sense away from SW'),
 
 ('+5V_CORE',[(-4.825,12),(-4.825,10)],.2,'LM PG pullup feed'),
 ('LP5_PG_RAW',[(-3.175,10),(-1.325,10)],.2,'LM PG bias divider'),
 ])
 anchor=report['cells']['5v']['anchor_mm']
 if anchor is not None:
  x,y=anchor
  escape=[(x,y+1.8625),(x,y+2.54)]
  continuation=[(x,y+2.54),(x,y+3.5),(x+1.05,y+3.5),(x+1.05,y+5)]
  if router.path('LP5_BOOT',escape,.2,'LM bounded BOOT escape',True) and router.path('LP5_BOOT',continuation,.2,'LM BOOT capacitor continuation',True):
   report['boot_escape_area']=lm_boot_escape.add_area(board)
   report['additional_rules']=lm_boot_escape.rule_text()
   report['rules_modified']=True
   assert router.path('LP5_BOOT',escape,.2,'LM bounded BOOT escape')
   assert router.path('LP5_BOOT',continuation,.2,'LM BOOT capacitor continuation')
  else:router.blocked.append({'label':'LM BOOT loop','net':'LP5_BOOT','obstacles':['Bounded escape or ordinary continuation obstructed']})
 for name in ('5v','3v3'):
  anchor=report['cells'][name]['anchor_mm']
  if anchor is None:continue
  x,y=anchor
  offsets=[(a,b) for a in (-1.5,-.5,.5,1.5) for b in (-.35,.35)] if name=='5v' else [(a,b) for a in (-.4,.4) for b in (-.4,.4)]
  for a,b in offsets:router.via((x+a,y+b),name+' EP thermal candidate')
 # Cap ground stitching: test both the escape segment and through-via on
 # all four copper layers before adding either. No orphan-via fallback.
 for name,plan in CELLS.items():
  if report['cells'][name]['anchor_mm'] is None:continue
  for ref in plan:
   if not ref.startswith('C') or ref=='C5206':continue
   for pad in fps[ref].Pads():
    if pad.GetNetname()!='GND':continue
    xy=mm(pad.GetPosition());done=False
    for distance in (1.2,1.5,1.8,2.2):
     for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
      end=(xy[0]+dx*distance,xy[1]+dy*distance)
      if router.via(end,ref+' GND stitching',True) and router.path('GND',[xy,end],.4,ref+' ground escape',True):
       router.via(end,ref+' GND stitching');router.path('GND',[xy,end],.4,ref+' ground escape');done=True;break
     if done:break
    if not done:router.blocked.append({'label':ref+' GND stitching','net':'GND','obstacles':['No safe local all-layer via/escape candidate']})
 report['local_routes']=router.tracks;report['thermal_vias']=router.vias;report['blocked_routes']=router.blocked
 report['status']='PARTIAL_LOCAL_ROUTING_REQUIRES_NATIVE_DRC_AND_COMPLETION'
 return report

def place_and_route(board,fps,nets,fixed_references,region=REGION):
 """Pre-pack hook for partial local buck placement and validated copper.

 Call before new module packing. Do not call on a routed whole board: moving
 the own cells would disconnect their pre-existing tracks. The integration
 lead owns generic placement of the separate D5200/D5201 input protection.
 """
 report=propose(board,set(fixed_references),region)
 report['voltage_domains']=voltage_domains.provenance()
 report['placed_references']=[r for name,plan in CELLS.items() if report['cells'][name]['anchor_mm'] is not None for r in plan]
 return route_cells(board,fps,fixed_references,report)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
 ap.add_argument('--netlist',type=Path,required=True)
 a=ap.parse_args()
 if a.input.resolve()==a.output.resolve():raise ValueError('Input must never be overwritten')
 voltage_domains.configure(a.netlist)
 board=p.LoadBoard(str(a.input))
 # Integration calls this before new-module packing. Offline snapshot review
 # includes only donor200..399 and known fixed MCU/IGN/connectors as bodies.
 fixed={f.GetReference() for f in board.GetFootprints() if f.GetReference().lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ').isdigit() and 200<=int(f.GetReference().lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))<400}
 fixed.update(['U101','J601','J602','J603','J604'])
 report=propose(board,fixed)
 report=route_cells(board,{f.GetReference():f for f in board.GetFootprints()},fixed,report)
 report['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
 report['voltage_domains']=voltage_domains.provenance()
 a.output.parent.mkdir(parents=True,exist_ok=True);p.SaveBoard(str(a.output),board)
 a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'cells':report['cells'],'tracks':len(report.get('local_routes',[])),'vias':len(report.get('thermal_vias',[])),'blocked':report.get('blocked_routes',[])}))
if __name__=='__main__':main()
