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
