"""Guarded GND stitching: one via per GND island, next to one of its pads.

Runs on a saved, zone-filled board. An island is a group of GND pads that
KiCad's connectivity (tracks and fills included) does not join to the In1
ground plane. For each island one short 0.3 mm stub and one 0.65/0.3 mm via
are added beside a pad, after checking every candidate against actual copper
of other nets on F/In2/B (voltage-domain clearances), all drill holes, all
mask openings and the board edge. Islands with no admissible position are
reported, never forced. No rule is relaxed; nothing existing is moved.

This is connectivity work for a placement candidate, not a return-path,
current or EMC design: the plane itself, its cuts and the stitching density
remain review items.
"""
from collections import defaultdict
from pathlib import Path
import json
import math
import sys
import pcbnew as p
sys.path.insert(0,str(Path(__file__).resolve().parent))
import voltage_domains
import layout_profile
from route_wbo_local import Copper,LAYERS,vec,xy,bounds

NET='GND'
VIA_D,VIA_DRILL,STUB_W=.65,.3,.3
import itertools
DIRECTIONS=tuple((round(math.cos(a),6),round(math.sin(a),6)) for a in (k*math.pi/8 for k in range(16)))
STEPS=tuple(i*.5 for i in range(13))  # up to 6 mm beyond the pad body
EDGE_MARGIN=1.0
CHECK_LAYERS=(p.F_Cu,p.In2_Cu,p.B_Cu)  # In1 is the GND plane itself


def plane_polygon(board):
    zones=[z for z in board.Zones() if z.GetNetname()==NET and z.IsOnLayer(p.In1_Cu) and not z.GetIsRuleArea()]
    if len(zones)!=1:raise ValueError('Expected one In1 GND plane zone')
    poly=zones[0].GetFilledPolysList(p.In1_Cu)
    if not poly.OutlineCount():raise ValueError('GND plane is not filled; fill zones before stitching')
    return poly


def islands(board):
    """GND pad groups (pads, tracks, vias) that do not reach the In1 plane."""
    c=board.GetConnectivity();poly=plane_polygon(board)
    pads=[q for f in board.GetFootprints() for q in f.Pads() if q.GetNetname()==NET]
    def reaches_plane(item):
        # Same-net vias get thermal spokes: test the annulus, not the centre point.
        # SWIG hands vias back as PCB_TRACK from GetConnectedTracks: test Type(), not isinstance.
        if item.Type()==p.PCB_VIA_T:return poly.Collide(item.GetEffectiveShape(p.In1_Cu),0)
        if item.Type()==p.PCB_PAD_T and item.GetAttribute()==p.PAD_ATTRIB_PTH:return poly.Collide(item.GetEffectiveShape(p.In1_Cu),0)
        return False
    seen=set();plane=[];groups=[]
    for q in pads:
        if q.m_Uuid.AsString() in seen:continue
        queue=[q];members=[];connected=False
        while queue:
            item=queue.pop();key=item.m_Uuid.AsString()
            if key in seen:continue
            seen.add(key)
            if item.Type()==p.PCB_PAD_T:members.append(item)
            if reaches_plane(item):connected=True
            queue.extend(list(c.GetConnectedPads(item))+list(c.GetConnectedTracks(item)))
        if connected:plane.extend(members)
        else:groups.append(members)
    return plane,groups


def obstacles(board):
    copper=Copper();holes=[];pads=[q for f in board.GetFootprints() for q in f.Pads()]
    tracks=list(board.GetTracks())
    for item in pads+tracks+[z for z in board.Zones() if z.GetNetname()!=NET or z.GetIsRuleArea()]:
        for layer in CHECK_LAYERS:copper.add(item,layer)
    holes=[(xy(t),p.ToMM(t.GetDrillValue())/2) for t in tracks if isinstance(t,p.PCB_VIA)]
    holes+=[(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
    return copper,holes,pads


def admissible(board,pad,point,copper,holes,pads,outline):
    """Via at point plus a stub from the pad centre; None if anything collides."""
    w,h=outline
    if not (EDGE_MARGIN<=point[0]<=w-EDGE_MARGIN and EDGE_MARGIN<=point[1]<=h-EDGE_MARGIN):return None
    r=VIA_DRILL/2
    if any(math.dist(point,hp)<r+hr+.26 for hp,hr in holes):return None
    v=p.PCB_VIA(board);v.SetPosition(vec(*point));v.SetWidth(p.FromMM(VIA_D));v.SetDrill(p.FromMM(VIA_DRILL))
    v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(pad.GetNet())
    circle=p.SHAPE_CIRCLE(vec(*point),p.FromMM(VIA_D/2))
    for q in pads:
        for layer,mask in ((p.F_Cu,p.F_Mask),(p.B_Cu,p.B_Mask)):
            if q.IsOnLayer(mask) and q.GetEffectiveShape(layer).Collide(circle,p.FromMM(.1)+max(0,q.GetSolderMaskExpansion(mask))):return None
    if not all(copper.clear(circle,bounds(v,.01),layer,NET) for layer in CHECK_LAYERS):return None
    layer=p.B_Cu if pad.IsOnLayer(p.B_Cu) and not pad.IsOnLayer(p.F_Cu) else p.F_Cu
    t=p.PCB_TRACK(board);t.SetStart(pad.GetPosition());t.SetEnd(vec(*point));t.SetLayer(layer);t.SetWidth(p.FromMM(STUB_W));t.SetNet(pad.GetNet())
    shape=t.GetEffectiveShape()
    if any(shape.Collide(p.SHAPE_CIRCLE(vec(*hp),p.FromMM(hr)),p.FromMM(.26)) for hp,hr in holes if math.dist(hp,point)>1e-6):return None
    if not copper.clear(shape,bounds(t,.01),layer,NET):return None
    return v,t


def candidates(pad):
    b=pad.GetBoundingBox();cx,cy=xy(pad)
    hw,hh=p.ToMM(b.GetWidth())/2,p.ToMM(b.GetHeight())/2
    for step in STEPS:
        for dx,dy in DIRECTIONS:
            # Distance from the pad centre to its bounding box along this direction.
            base=min(hw/abs(dx) if dx else 1e9,hh/abs(dy) if dy else 1e9)
            d=base+VIA_D/2+.3+step
            yield (round(cx+dx*d,3),round(cy+dy*d,3))


def stitch(board):
    voltage_domains.configure(Path(__file__).resolve().parents[1]/'core.net')
    outline=layout_profile.outline()
    board.BuildConnectivity()
    plane,groups=islands(board)
    copper,holes,pads=obstacles(board)
    added=[];failed=[]
    for group in groups:
        done=None
        for pad in sorted(group,key=lambda q:-p.ToMM(q.GetBoundingBox().GetWidth())*p.ToMM(q.GetBoundingBox().GetHeight())):
            for point in candidates(pad):
                hit=admissible(board,pad,point,copper,holes,pads,outline)
                if hit:done=(pad,point,hit);break
            if done:break
        if not done:
            failed.append({'pads':[q.GetParentFootprint().GetReference()+'.'+q.GetNumber() for q in group],'reason':'no admissible via position within %g mm of the pad body'%(STEPS[-1]+VIA_D/2+.3)});continue
        pad,point,(v,t)=done
        board.Add(v);board.Add(t)
        for layer in CHECK_LAYERS:copper.add(v,layer);copper.add(t,layer)
        holes.append((point,VIA_DRILL/2))
        added.append({'pad':pad.GetParentFootprint().GetReference()+'.'+pad.GetNumber(),'via_mm':list(point),'layer':board.GetLayerName(t.GetLayer()),
                      'via_uuid':v.m_Uuid.AsString(),'stub_uuid':t.m_Uuid.AsString(),'stub_length_mm':round(math.dist(xy(pad),point),3)})
    return {'plane_pads':len(plane),'islands':len(groups),'stitched':len(added),'unstitched':failed,'via_mm':[VIA_D,VIA_DRILL],'stub_width_mm':STUB_W,'added':added}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board',type=Path)
    parser.add_argument('--layout-profile',type=Path,default=layout_profile.DEFAULT)
    args=parser.parse_args()
    layout_profile.configure(args.layout_profile)
    report_path=args.board.parent/'board_report.json';data=json.loads(report_path.read_text())
    if data.get('ground_stitch'):raise ValueError('Ground stitching already applied to this candidate')
    board=p.LoadBoard(str(args.board));board.BuildConnectivity()
    before=board.GetConnectivity().GetUnconnectedCount(False)
    result=stitch(board)
    board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());board.BuildConnectivity()
    after=board.GetConnectivity().GetUnconnectedCount(False)
    _,remaining=islands(board)
    result.update({'unconnected_before':before,'unconnected_after':after,'gnd_islands_after_fill':len(remaining)})
    if after>=before:raise ValueError('Stitching did not reduce the connectivity gap; not saving')
    p.SaveBoard(str(args.board),board)
    from build_board import project_file
    project_file(args.board.with_suffix('.kicad_pro'),None,board)
    data['ground_stitch']=result;data['tracks_vias']=len(list(board.GetTracks()));data['unconnected_count']=after
    report_path.write_text(json.dumps(data,indent=2)+'\n')
    (args.board.parent/'ground_stitch.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('plane_pads','islands','stitched','unconnected_before','unconnected_after','gnd_islands_after_fill')},indent=2))
    print('unstitched islands:',len(result['unstitched']))
