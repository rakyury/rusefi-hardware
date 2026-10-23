"""Local logic-power placement/route module; only refs5200..5399 may move.

Runs in pinned KiCad9 Python. Input is never overwritten. Existing copper is
preserved. A rigid local power cell must clear every foreign pad/track/via and
same-side component before being accepted. No global auto-router or DRC-rule
modification is performed. Stage-one placement proposal reports failures.
"""
from __future__ import annotations
import argparse, json, math, hashlib
from pathlib import Path
import pcbnew as p

REGION=(5.,5.,151.,55.)
# x,y,angle in B.Cu local coordinates. Dense supply/BOOT/FB placement has a
# deliberate side: switching right, low-level feedback/soft start left.
CELLS={
 '5v':{
 'U5200':(0,0,90),'L5200':(8,2,0),
 'C5200':(0,-8,90),'C5201':(-4,-8,90),'C5202':(1.5,-4,0),
 'C5203':(0,5,90),'C5204':(-4.5,6.5,0),'C5205':(-8.5,7.5,0),
 'C5206':(-8.5,4.7,0),'C5207':(-9,-.5,90),
 'C5208':(14,0,90),'C5209':(18,0,90),'C5210':(14,5.5,90),'C5211':(18,5.5,90),
 'R5200':(-5.7,.8,0),'R5201':(-5.7,-1.7,0),
 'R5202':(-4.5,-4,0),'R5203':(-8.5,-3.8,0),
 'R5204':(-4,10,0),'R5205':(-.5,10,0)},
 '3v3':{
 'U5300':(0,0,0),'L5300':(-6,.5,180),
 'C5300':(4.5,1.3,90),'C5301':(3,-3.5,0),
 'C5302':(-10.8,.5,90),'C5303':(6,-2.5,90),
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
     gap=.6 if any(z in other for z in ('VBOOST','Vdrive_coil','Vdrive_shunt')) else .3
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

def propose(board,fixed=None,region=REGION):
 fps={f.GetReference():f for f in board.GetFootprints()};before=snapshot(board)
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
    (x,y),a,layer=before[ref];position(fps[ref],x,y,a)
 for ref,old in before.items():
  if not ref_owned(ref) and snapshot(board)[ref]!=old:raise AssertionError('Foreign footprint moved: '+ref)
 report['unchanged_foreign_footprints']=len(before)-sum(ref_owned(r) for r in before)
 return report

def place_and_route(board,fps,nets,fixed_references,region=REGION):
 """Pre-pack hook. Stage one places two cells; route stage is not yet approved.

 Call before new module packing. Do not call on a routed whole board: moving
 the own cells would disconnect their pre-existing tracks. The integration
 lead owns generic placement of the separate D5200/D5201 input protection.
 """
 report=propose(board,set(fixed_references),region)
 report['placed_references']=[r for name,plan in CELLS.items() if report['cells'][name]['anchor_mm'] is not None for r in plan]
 report['local_routes']=[]
 return report

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--report',type=Path,required=True)
 a=ap.parse_args()
 if a.input.resolve()==a.output.resolve():raise ValueError('Input must never be overwritten')
 board=p.LoadBoard(str(a.input))
 # Integration calls this before new-module packing. Offline snapshot review
 # includes only donor200..399 and known fixed MCU/IGN/connectors as bodies.
 fixed={f.GetReference() for f in board.GetFootprints() if f.GetReference().lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ').isdigit() and 200<=int(f.GetReference().lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))<400}
 fixed.update(['U101','J601','J602','J603','J604'])
 report=propose(board,fixed)
 report['input_sha256']=hashlib.sha256(a.input.read_bytes()).hexdigest()
 a.output.parent.mkdir(parents=True,exist_ok=True);p.SaveBoard(str(a.output),board)
 a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
