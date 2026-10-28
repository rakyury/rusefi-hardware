"""Guarded supervisor-to-pull-up reset branch; native DRC remains required."""
from collections import Counter
from pathlib import Path
import math
import pcbnew as p
import voltage_domains
from route_wbo_local import Copper, LAYERS, vec, xy, bounds
from route_wbo_can import signature

NET = 'WBO1_nRESET'
POINTS = ((171.3625,84.95),(172.3625,84.45),(172.6125,82.7),
          (173.1125,82.2),(174.3625,82.45),(175.1125,83.2),
          (175.3625,83.95),(176.0,84.825))


def route(board, netlist=None):
    voltage_domains.configure(netlist or Path(__file__).resolve().parents[1]/'core.net')
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    if (fps['U5612'].GetValue() != 'TPS3808G33QDBVRQ1'
            or fps['R5662'].GetValue() != '10k'):
        raise ValueError('Reset devices changed')
    def pad(ref, pin):
        found = [q for q in fps[ref].Pads() if q.GetNumber() == pin]
        if len(found) != 1:
            raise ValueError('Reset pad contract changed: '+ref+'.'+pin)
        return found[0]
    for ref, pin, position in (('U5612','1',POINTS[0]),('R5662','1',POINTS[-1])):
        q = pad(ref,pin)
        if (q.GetNetname() != NET or not q.IsOnLayer(p.B_Cu)
                or fps[ref].GetLayer() != p.B_Cu or math.dist(xy(q),position) > 1e-5):
            raise ValueError('Reset endpoint contract changed')
    for ref, pin, net in (('U5612','2','GND'),('U5612','3','WBO1_3V3'),
                          ('U5612','5','WBO1_3V3'),('U5612','6','WBO1_3V3'),
                          ('R5662','2','WBO1_3V3')):
        if pad(ref,pin).GetNetname() != net:
            raise ValueError('Reset supply/pull-up contract changed')
    net = pad('U5612','1').GetNet()
    items = []
    for a,b in zip(POINTS,POINTS[1:]):
        t = p.PCB_TRACK(board)
        t.SetStart(vec(*a)); t.SetEnd(vec(*b)); t.SetLayer(p.B_Cu)
        t.SetWidth(p.FromMM(.2)); t.SetNet(net); items.append(t)
    old = list(board.GetTracks())
    existing = Counter(signature(t) for t in old)
    wanted = [signature(t) for t in items]
    present = [existing[s] for s in wanted]
    if any(n > 1 for n in present):
        raise ValueError('Duplicate reset branch geometry')
    if all(present):
        return []
    if any(present):
        raise ValueError('Partial reset branch exists; review before routing')
    for target in wanted:
        if any(actual[:4] == target[:4] for actual in existing):
            raise ValueError('Existing reset branch width differs')
    pads = [q for f in board.GetFootprints() for q in f.Pads()]
    copper = Copper()
    for item in pads+old+[z for z in board.Zones() if z.GetNetname() != 'GND' or z.GetIsRuleArea()]:
        for layer in LAYERS:
            copper.add(item,layer)
    holes = [(xy(t),p.ToMM(t.GetDrillValue())/2) for t in old if isinstance(t,p.PCB_VIA)]
    holes += [(xy(q),max(p.ToMM(q.GetDrillSize().x),p.ToMM(q.GetDrillSize().y))/2)
              for q in pads if q.GetDrillSize().x or q.GetDrillSize().y]
    # Check every segment before adding any; same-net drill holes are obstacles too.
    for item in items:
        shape = item.GetEffectiveShape()
        if any(shape.Collide(p.SHAPE_CIRCLE(vec(*h),p.FromMM(r)),p.FromMM(.26)) for h,r in holes):
            raise ValueError('Reset track hole clearance blocked')
        if not copper.clear(shape,bounds(item,.01),p.B_Cu,NET):
            raise ValueError('Reset copper clearance blocked')
    for item in items:
        board.Add(item)
    return [{'net':NET,'from':'U5612.1','to':'R5662.1','layer':'B.Cu',
             'points_mm':POINTS,'width_mm':.2,'segments':len(items),'vias':0,
             'length_mm':round(sum(math.dist(a,b) for a,b in zip(POINTS,POINTS[1:])),6),
             'added_uuids':[t.m_Uuid.AsString() for t in items]}]


def update_report(report, routes):
    """Mark only the reviewed pair complete; other reset branches stay pending."""
    if not routes:
        return
    if isinstance(report, dict):
        if 'unrouted_local_pairs' in report:
            pending = []
            for entry in report['unrouted_local_pairs']:
                if (entry.get('net') == NET and entry.get('from') == 'U5612.1'
                        and entry.get('to') == 'R5662.1'):
                    complete = {k:v for k,v in entry.items() if k != 'reason'}
                    complete.update(routes[0])
                    report.setdefault('local_routes', []).append(complete)
                else:
                    pending.append(entry)
            report['unrouted_local_pairs'] = pending
        for value in report.values():
            update_report(value, routes)
    elif isinstance(report, list):
        for value in report:
            update_report(value, routes)
