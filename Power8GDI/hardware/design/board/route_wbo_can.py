"""Guarded two-net WBO logic routing; no placement or electrical changes.

Plans are qualified against every footprint and existing copper at call time.
Ground-zone refill and native DRC remain required verification gates.
"""
from pathlib import Path
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper, LAYERS, vec, xy, bounds

PLANS=(
 ('WBO1_CAN_RX','21','4',(169.5,63.75),
  ((168.00295,64.575),(169.5,64.575),(169.5,63.75)),
  ((169.5,63.75),(167.913975,63.75),(167.913975,67.055558),(166.32795,67.055558))),
 ('WBO1_CAN_TX','22','1',(169.5,62.75),
  ((168.00295,65.375),(170.251475,65.375),(170.251475,62.75),(169.5,62.75)),
  ((169.5,62.75),(166.32795,63.245558))),
)

def signature(t):
    if isinstance(t,p.PCB_VIA):return ('via',t.GetNetname(),xy(t),p.ToMM(t.GetWidth(p.F_Cu)),p.ToMM(t.GetDrillValue()),t.TopLayer(),t.BottomLayer())
    return ('track',t.GetNetname(),t.GetLayer(),tuple(sorted(((p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)),(p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y))))),p.ToMM(t.GetWidth()))

def route(board,netlist=None):
    voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
    fps={f.GetReference():f for f in board.GetFootprints()}
    if fps['U5602'].GetValue()!='STM32F042K6T6' or fps['U5605'].GetValue()!='TJA1051T/3/1J':raise ValueError('WBO devices changed')
    pad=lambda ref,pin:next(q for q in fps[ref].Pads() if q.GetNumber()==pin)
    for ref,pin,net in [('U5602','17','WBO1_3V3'),('U5605','5','WBO1_3V3'),('U5605','3','+5V_CORE')]:
        if pad(ref,pin).GetNetname()!=net:raise ValueError('WBO logic supply changed')
    plans=[]
    for name,ap,bp,via,front,back in PLANS:
        a,b=pad('U5602',ap),pad('U5605',bp)
        if a.GetNetname()!=name or b.GetNetname()!=name or not a.IsOnLayer(p.F_Cu) or not b.IsOnLayer(p.B_Cu):raise ValueError('WBO endpoint contract changed')
        if math.dist(xy(a),front[0])>1e-5 or math.dist(xy(b),back[-1])>1e-5:raise ValueError('WBO placement changed')
        v=p.PCB_VIA(board);v.SetPosition(vec(*via));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(a.GetNet())
        items=[v]
        for layer,points in ((p.F_Cu,front),(p.B_Cu,back)):
            for u,w in zip(points,points[1:]):
                t=p.PCB_TRACK(board);t.SetStart(vec(*u));t.SetEnd(vec(*w));t.SetWidth(p.FromMM(.2));t.SetLayer(layer);t.SetNet(a.GetNet());items.append(t)
        existing=[t for t in board.GetTracks() if t.GetNetname()==name]
        if existing:
            if sorted(map(signature,existing))!=sorted(map(signature,items)):raise ValueError('Existing WBO route differs; refusing overwrite')
            continue
        plans.append((name,items))
    if not plans:return []
    pads=[q for f in board.GetFootprints() for q in f.Pads()];tracks=list(board.GetTracks())
    copper=Copper()
    for item in pads+tracks+[z for z in board.Zones() if z.GetNetname()!='GND' or z.GetIsRuleArea()]:
        for layer in LAYERS:copper.add(item,layer)
    holes=[(xy(t),p.ToMM(t.GetDrillValue())/2) for t in tracks if isinstance(t,p.PCB_VIA)]
    holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2) for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
    # Preflight both nets before mutating the board; accepted RX objects become TX obstacles.
    for name,items in plans:
        for item in items:
            if isinstance(item,p.PCB_VIA):
                pt=xy(item);shape=p.SHAPE_CIRCLE(vec(*pt),p.FromMM(.325));layers=LAYERS
                if any(math.dist(pt,h)<.15+r+.26 for h,r in holes):raise ValueError('WBO via drill clearance blocked')
                for q in pads:
                    for layer,mask in ((p.F_Cu,p.F_Mask),(p.B_Cu,p.B_Mask)):
                        if q.IsOnLayer(mask) and q.GetEffectiveShape(layer).Collide(shape,p.FromMM(.1)+max(0,q.GetSolderMaskExpansion(mask))):raise ValueError('WBO via overlaps pad mask')
            else:
                shape=item.GetEffectiveShape();layers=(item.GetLayer(),)
                # Drill obstacles, including same-net ones; the planned transition itself is intentional.
                for h,r in holes:
                    if h==xy(items[0]):continue
                    if shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)):raise ValueError('WBO track hole clearance blocked')
            if not all(copper.clear(shape,bounds(item,.01),layer,name) for layer in layers):raise ValueError('WBO copper clearance blocked: '+name)
        for item in items:
            for layer in LAYERS:copper.add(item,layer)
        holes.append((xy(items[0]),.15))
    result=[]
    for name,items in plans:
        for item in items:board.Add(item)
        result.append({'net':name,'via_mm':xy(items[0]),'width_mm':.2,'via_diameter_mm':.65,'drill_mm':.3,
                       'added_uuids':[t.m_Uuid.AsString() for t in items],'segments':len(items)-1,
                       'length_mm':round(sum(p.ToMM(t.GetLength()) for t in items[1:]),6)})
    return result



def update_report(report,routes):
    """Move completed pairs out of the placement pass's pending list."""
    routed={r['net']:r for r in routes}
    if isinstance(report,dict):
        if 'unrouted_local_pairs' in report:
            pending=[]
            for entry in report['unrouted_local_pairs']:
                if entry.get('net') in routed:
                    complete={k:v for k,v in entry.items() if k!='reason'}
                    complete.update(routed[entry['net']]);complete['layer']='F.Cu/B.Cu'
                    report.setdefault('local_routes',[]).append(complete)
                else:pending.append(entry)
            report['unrouted_local_pairs']=pending
        for value in report.values():update_report(value,routes)
    elif isinstance(report,list):
        for value in report:update_report(value,routes)
