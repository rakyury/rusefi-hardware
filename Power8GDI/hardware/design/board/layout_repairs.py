"""Guarded repairs for the revised GDI6 shunt lands and oscillator silk.

No pad, net, via, rule or upstream donor geometry is removed or moved.
"""
import math
from pathlib import Path
import sys
import pcbnew as p
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gdi.oscillator_silk import SILK_EDITS

def xy(q):return (p.ToMM(q.x),p.ToMM(q.y))
def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def point(fp,q):
    a=-math.radians(fp.GetOrientationDegrees());x,y=xy(fp.GetPosition())
    return (x+q[0]*math.cos(a)-q[1]*math.sin(a),y+q[0]*math.sin(a)+q[1]*math.cos(a))
def same(a,b):return math.dist(a,b)<.00001

def repair_returns(board):
    fps={f.GetReference():f for f in board.GetFootprints()};plans=[]
    for ref in ('R215','R315'):
        f=fps[ref]
        if str(f.GetFPID().GetLibItemName())!='REF_R26' or f.GetLayer()!=p.F_Cu:
            raise ValueError('Unexpected pump-return footprint '+ref)
        pad=next(q for q in f.Pads() if q.GetNumber()=='4')
        if pad.GetNetname()!='GND' or not same(xy(pad.GetSize()),(1.93,1.65)):
            raise ValueError('Unexpected pump-return pad '+ref)
        position=point(f,(.8,-1.1))
        vias=[t for t in board.GetTracks() if isinstance(t,p.PCB_VIA) and same(xy(t.GetPosition()),position)]
        if len(vias)!=1 or vias[0].GetNetname()!='GND':raise ValueError('Missing original return via '+ref)
        via=vias[0]
        if abs(p.ToMM(via.GetWidth(p.F_Cu))-.6)>1e-6:raise ValueError('Return via size changed '+ref)
        a,b=xy(via.GetPosition()),xy(pad.GetPosition())
        existing=any(not isinstance(t,p.PCB_VIA) and t.GetLayer()==p.F_Cu and t.GetNetname()=='GND'
                     and ((same(xy(t.GetStart()),a) and same(xy(t.GetEnd()),b)) or (same(xy(t.GetStart()),b) and same(xy(t.GetEnd()),a))) for t in board.GetTracks())
        if not existing:plans.append((ref,pad,a,b))
    result=[]
    for ref,pad,a,b in plans:
        track=p.PCB_TRACK(board);track.SetLayer(p.F_Cu);track.SetNet(pad.GetNet())
        track.SetWidth(p.FromMM(.6));track.SetStart(vec(a));track.SetEnd(vec(b));board.Add(track)
        result.append({'reference':ref,'pad':'4','net':'GND','width_mm':.6,'start_mm':a,'end_mm':b,'uuid':track.m_Uuid.AsString()})
    return result

def repair_silk(board):
    plans=[]
    for f in board.GetFootprints():
        if f.GetReference() not in ('Y201','Y301'):continue
        if str(f.GetFPID().GetLibItemName())!='REF_Y2' or f.GetLayer()!=p.F_Cu:raise ValueError('Unexpected oscillator footprint')
        shapes=[g for g in f.GraphicalItems() if isinstance(g,p.PCB_SHAPE) and g.GetLayer()==p.F_SilkS]
        if len(shapes)!=5:raise ValueError('Unexpected oscillator silk count')
        for old,new in SILK_EDITS:
            olda,oldb=point(f,old[:2]),point(f,old[2:]);newa,newb=point(f,new[:2]),point(f,new[2:])
            matches=[g for g in shapes if g.GetShape()==p.SHAPE_T_SEGMENT and same(xy(g.GetStart()),olda) and same(xy(g.GetEnd()),oldb)]
            if not matches:
                if any(same(xy(g.GetStart()),newa) and same(xy(g.GetEnd()),newb) for g in shapes):continue
                raise ValueError('Unexpected oscillator silk segment')
            if len(matches)!=1:raise ValueError('Ambiguous oscillator silk segment')
            plans.append((f.GetReference(),matches[0],newa,newb))
    for ref,g,a,b in plans:g.SetStart(vec(a));g.SetEnd(vec(b))
    return [{'reference':ref,'uuid':g.m_Uuid.AsString(),'start_mm':a,'end_mm':b} for ref,g,a,b in plans]


def repair_wbo_silk(board):
    """Clear J5600 mask while preserving the D5604 pin-1 triangle."""
    f=next(f for f in board.GetFootprints() if f.GetReference()=='D5604')
    if ((str(f.GetFPID().GetLibNickname()),str(f.GetFPID().GetLibItemName())) not in (('Package_TO_SOT_SMD','SOT-23'),('Power8GDI_Board','SOT-23_D5604_J5600_Clearance')) or f.GetValue()!='PESD1CAN'
        or f.GetLayer()!=p.B_Cu or abs(f.GetOrientationDegrees())>1e-6
        or not same(xy(f.GetPosition()),(160.59045,73.2))):
        raise ValueError('Unexpected D5604 placement')
    shapes=[g for g in f.GraphicalItems() if isinstance(g,p.PCB_SHAPE)]
    tiny_old=((159.83045,71.64),(159.83045,71.69))
    tiny_new=((160.91045,71.64),(160.91045,71.69))
    tiny_candidates=[g for g in shapes if g.GetShape()==p.SHAPE_T_SEGMENT and g.GetLayer()==p.B_SilkS
                     and any(same(xy(g.GetStart()),a) and same(xy(g.GetEnd()),b) for a,b in (tiny_old,tiny_new))]
    if len(tiny_candidates)!=1:raise ValueError('Unexpected D5604 outline stub')
    tiny=tiny_candidates[0]
    start=(161.35045,71.64);old=(159.83045,71.64);new=(160.91045,71.64)
    candidates=[g for g in shapes if g.GetShape()==p.SHAPE_T_SEGMENT and g.GetLayer()==p.B_SilkS
                and same(xy(g.GetStart()),start) and (same(xy(g.GetEnd()),old) or same(xy(g.GetEnd()),new))]
    if len(candidates)!=1:raise ValueError('Unexpected D5604 top outline')
    top=candidates[0]
    if abs(p.ToMM(top.GetWidth())-.12)>1e-6:raise ValueError('Unexpected D5604 stroke width')
    # Check the proposed stroke against mask openings across the whole board.
    probe=p.PCB_SHAPE(f);probe.SetShape(p.SHAPE_T_SEGMENT);probe.SetLayer(p.B_SilkS)
    probe.SetWidth(top.GetWidth());probe.SetStart(vec(start));probe.SetEnd(vec(new))
    for a,b in ((start,new),tiny_new):
        probe.SetStart(vec(a));probe.SetEnd(vec(b))
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.IsOnLayer(p.B_Mask) and pad.GetEffectiveShape(p.B_Cu).Collide(
                    probe.GetEffectiveShape(),p.FromMM(.20)+max(0,pad.GetSolderMaskExpansion(p.B_Mask))):
                    raise ValueError('D5604 proposed silk intersects mask: '+fp.GetReference())
    changes=[]
    if not same(xy(tiny.GetStart()),tiny_new[0]):
        tiny.SetStart(vec(tiny_new[0]));tiny.SetEnd(vec(tiny_new[1]))
        changes.append({'uuid':tiny.m_Uuid.AsString(),'change':'move non-orientation stub to shortened outline end'})
    if not same(xy(top.GetEnd()),new):
        top.SetEnd(vec(new));changes.append({'uuid':top.m_Uuid.AsString(),'change':'shorten outline','end_mm':new})
    return changes
