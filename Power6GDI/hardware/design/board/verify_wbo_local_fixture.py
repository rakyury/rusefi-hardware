"""Native KiCad DRC on an explicit WBO diagnostic tile, never the source board.

Retain all copper/pads/zones within a 3mm margin around a tile of owned WBO
geometry. Straight tracks are clipped only outside this expanded boundary;
only pads outside it are removed. Actual nets/widths/layers/clearance rules are
preserved. Footprint mismatch and dangling endpoints are expected artifacts of
cropping. This is evidence for local copper clearance, not a whole-board pass.
Subdivide tiles with >=450 clearance findings or >=190 findings of any other
violation type. KiCad also caps some types at 199, not only 499; truncated output
cannot prove zero findings. Tiles0,1,2,3 cover the entire
channel; dotted paths recursively quarter a tile. Use a complete leaf cover.
"""
import argparse
from collections import Counter
import hashlib
import tempfile
import json, shutil, subprocess, re,sys
from pathlib import Path
import pcbnew as p
ap=argparse.ArgumentParser(description=__doc__)
for key in ('board','placement','fixed','project','output'):
 ap.add_argument('--'+key,type=Path,required=True)
ap.add_argument('--channel',type=int,choices=(1,2),required=True)
ap.add_argument('--tile',required=True)
args=ap.parse_args()
if not re.fullmatch(r'[0-3](\.[0-3])*',args.tile):raise ValueError('Invalid quadtree tile')
root=args.project.resolve().parent;local=args.output.resolve();local.mkdir(parents=True,exist_ok=True)
ch=args.channel;prefix=5600+(ch-1)*200
report=json.loads(args.placement.read_text());fixed=set(json.loads(args.fixed.read_text())['fixed_references'])
if hashlib.sha256(args.board.read_bytes()).hexdigest()!=report['output_board_sha256']:
 raise ValueError('Placement report does not describe the supplied board')
refs={r for r in report['placed_references'] if prefix<=int(r[1:])<prefix+200}
b=p.LoadBoard(str(args.board))
placed=fixed|set(report['placed_references'])
for fp in b.GetFootprints():
 if fp.GetReference() not in placed and (fp.GetPosition().x!=0 or fp.GetPosition().y!=0):
  raise ValueError('Placed obstacle missing from fixed/WBO contract: '+fp.GetReference())

def bounds(o):
 bb=o.GetBoundingBox(False,False) if isinstance(o,p.FOOTPRINT) else o.GetBoundingBox()
 return tuple(p.ToMM(x) for x in (bb.GetX(),bb.GetY(),bb.GetRight(),bb.GetBottom()))
boxes=[bounds(f) for f in b.GetFootprints() if f.GetReference() in refs]
added=set(report['added_copper_uuids'])
for t in b.GetTracks():
 box=bounds(t)
 if t.m_Uuid.AsString() in added and (153 if ch==1 else 198)<=((box[0]+box[2])/2)<=(197 if ch==1 else 242):boxes.append(box)
raw=(min(x[0] for x in boxes),min(x[1] for x in boxes),max(x[2] for x in boxes),max(x[3] for x in boxes))
tilekey=args.tile
core=raw
for tile in map(int,tilekey.split('.')):
 xm=(core[0]+core[2])/2;ym=(core[1]+core[3])/2
 core=(core[0] if tile%2==0 else xm,core[1] if tile<2 else ym,xm if tile%2==0 else core[2],ym if tile<2 else core[3])
roi=(core[0]-3,core[1]-3,core[2]+3,core[3]+3)
def touches(o):
 z=bounds(o);return z[0]<roi[2] and z[2]>roi[0] and z[1]<roi[3] and z[3]>roi[1]
removed=[]
for f in list(b.GetFootprints()):
 if not touches(f) or f.GetReference() not in placed:b.Remove(f);removed.append(f)
for f in b.GetFootprints():
 for pad in list(f.Pads()):
  if not touches(pad):f.Remove(pad);removed.append(pad)
def clip(t):
 if isinstance(t,p.PCB_VIA):return touches(t)
 if isinstance(t,p.PCB_ARC):raise ValueError('Arc clipping requires separate verified implementation')
 a=t.GetStart();z=t.GetEnd();x,y=p.ToMM(a.x),p.ToMM(a.y);dx=p.ToMM(z.x-a.x);dy=p.ToMM(z.y-a.y);lo,hi=0.,1.
 for pp,qq in ((-dx,x-roi[0]),(dx,roi[2]-x),(-dy,y-roi[1]),(dy,roi[3]-y)):
  if abs(pp)<1e-12:
   if qq<0:return False
   continue
  v=qq/pp
  if pp<0:lo=max(lo,v)
  else:hi=min(hi,v)
  if lo>hi:return False
 t.SetStart(p.VECTOR2I(round((x+lo*dx)*1e6),round((y+lo*dy)*1e6)))
 t.SetEnd(p.VECTOR2I(round((x+hi*dx)*1e6),round((y+hi*dy)*1e6)))
 return True
for t in list(b.GetTracks()):
 if not clip(t):b.Remove(t);removed.append(t)
for z in list(b.Zones()):
 if not touches(z):b.Remove(z);removed.append(z)
temporary=tempfile.TemporaryDirectory(prefix='wbo-fixture-');tmp=Path(temporary.name)
name='wbo'+str(ch)+'_'+tilekey.replace('.','-');out=tmp/(name+'.kicad_pcb');p.SaveBoard(str(out),b)
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(args.project.with_suffix(ext),out.with_suffix(ext))
table=(root/'fp-lib-table').read_text()
def cp(m):
 uri=m.group(1)
 if '${KIPRJMOD}' not in uri:return m.group(0)
 src=Path(uri.replace('${KIPRJMOD}',str(root))).resolve();shutil.copytree(src,tmp/src.name,dirs_exist_ok=True)
 return '(uri "${KIPRJMOD}/'+src.name+'")'
(tmp/'fp-lib-table').write_text(re.sub(r'\(uri "([^"]+)"\)',cp,table))
condition=' || '.join("A.NetName == '"+n+"'" for n in report['switching_domain_nets'])
with out.with_suffix('.kicad_dru').open('a') as f:f.write('\n(rule "PT switching domains target" (condition "'+condition+'") (constraint clearance (min 0.6mm)))\n')
subprocess.run(['kicad-cli','pcb','drc','--format','json','--all-track-errors','--severity-all','-o',str(local/(name+'_scoped_drc.json')),str(out)],check=True)
drc=json.loads((local/(name+'_scoped_drc.json')).read_text())
counts=Counter(item['type'] for item in drc.get('violations',[]))
near_cap={kind:count for kind,count in counts.items() if count >= (450 if kind=='clearance' else 190)}
(local/(name+'_coverage.json')).write_text(json.dumps({'type_counts':dict(counts),'subdivision_thresholds':{'clearance':450,'other_violation_types':190},'requires_subdivision':bool(near_cap),'near_cap_types':near_cap},indent=2)+'\n')
if near_cap:
 raise RuntimeError('DRC tile requires subdivision before local zero-findings claims: '+str(near_cap))
(local/(name+'_fixture.json')).write_text(json.dumps({'input_board_sha256':hashlib.sha256(args.board.read_bytes()).hexdigest(),'project_sha256':hashlib.sha256(out.with_suffix('.kicad_pro').read_bytes()).hexdigest(),'rules_sha256':hashlib.sha256(out.with_suffix('.kicad_dru').read_bytes()).hexdigest(),'tile':args.tile,'roi_mm':roi,'core_mm':core,'track_clip_only_outside_roi':True,'pads_removed_only_outside_roi':True,'channel':ch,'footprints_retained':len(list(b.GetFootprints())),'tracks_vias_retained':len(list(b.GetTracks())),'zones_retained':len(list(b.Zones())),'all_layer_obstacles_within_roi_retained':True},indent=2)+'\n')
