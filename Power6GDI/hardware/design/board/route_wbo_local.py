"""Place current dual WBO and conservatively route short local connections.

Call before generic placement. Existing copper and fixed footprints are immutable.
Geometry is seeded by the pinned Hellen reference, never by copied copper. This
is a partial router: blocked connections are reported, never forced or excluded
from DRC. Run with KiCad's pcbnew Python (KiCad 9).
"""
import argparse
from collections import defaultdict
import json
import hashlib
import math
from pathlib import Path
import pcbnew as p
import voltage_domains

HERE = Path(__file__).resolve().parent
DEFAULT_REGIONS = {1: (153, 52, 197, 142), 2: (198, 52, 242, 142)}
LAYERS = (p.F_Cu, p.In1_Cu, p.In2_Cu, p.B_Cu)


def vec(x, y):
    return p.VECTOR2I(round(x * 1e6), round(y * 1e6))


def xy(item):
    q = item.GetPosition()
    return p.ToMM(q.x), p.ToMM(q.y)


def bounds(item, margin=0):
    b = item.GetBoundingBox(False, False) if isinstance(item, p.FOOTPRINT) else item.GetBoundingBox()
    return (p.ToMM(b.GetX())-margin, p.ToMM(b.GetY())-margin,
            p.ToMM(b.GetRight())+margin, p.ToMM(b.GetBottom())+margin)


def overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def inside(a, b):
    return b[0] <= a[0] and b[1] <= a[1] and a[2] <= b[2] and a[3] <= b[3]


def move(fp, x, y, angle, back):
    if (fp.GetLayer() == p.B_Cu) != back:
        fp.Flip(fp.GetPosition(), False)
    fp.SetOrientationDegrees(angle)
    fp.SetPosition(vec(x, y))


class Copper:
    """Spatial broad phase, then KiCad copper shape clearance (no sampling)."""
    def __init__(self):
        self.bins = defaultdict(list)
        self.items = []

    @staticmethod
    def cells(b):
        for x in range(math.floor(b[0]/5), math.floor(b[2]/5)+1):
            for y in range(math.floor(b[1]/5), math.floor(b[3]/5)+1):
                yield x, y

    def add(self, item, layer):
        if not item.IsOnLayer(layer):
            return
        if isinstance(item, p.ZONE):
            # Preserve donor power-zone outline even before zone refill.
            shape = item.Outline()
        else:
            try:
                shape = item.GetEffectiveShape(layer)
            except TypeError:
                shape = item.GetEffectiveShape()
        # Hold the item and its shape owner alive for SWIG.
        entry = (item, shape, item.GetNetname(), bounds(item, 2.6))
        self.items.append(entry)
        for cell in self.cells(entry[3]):
            self.bins[layer, cell].append(entry)

    def clear(self, shape, b, layer, net):
        seen = set()
        for cell in self.cells(b):
            for item, other, othernet, ob in self.bins[layer, cell]:
                ident = id(item)
                if ident in seen or othernet == net:
                    continue
                seen.add(ident)
                gap = max(voltage_domains.clearance_mm(net), voltage_domains.clearance_mm(othernet))
                if isinstance(item, p.PAD) and item.GetAttribute() == p.PAD_ATTRIB_NPTH:
                    gap = max(gap, .25)  # board hole-to-copper rule
                if overlap(b, ob) and other.Collide(shape, p.FromMM(gap+.01)):
                    return False
        return True


def fingerprint(fp):
    return (xy(fp), fp.GetOrientationDegrees(), fp.GetLayer(),
            sorted((q.GetNumber(), q.GetNetname(), xy(q)) for q in fp.Pads()))


def track_fingerprint(t):
    return (t.GetNetname(), t.GetLayer(), t.GetStart().x, t.GetStart().y,
            t.GetEnd().x, t.GetEnd().y, t.GetWidth(p.F_Cu) if isinstance(t, p.PCB_VIA) else t.GetWidth(),
            t.GetDrillValue() if isinstance(t, p.PCB_VIA) else None)


def place_and_route(board, fps, nets, fixed_references, regions=None):
    regions = {int(k): tuple(v) for k, v in (regions or DEFAULT_REGIONS).items()}
    manifest = json.loads((HERE.parent/'wbo/parts.json').read_text())
    refs = {r['ref'] for r in manifest}
    if len(refs) != 87 or not refs <= set(fps):
        raise ValueError('Current 87-part WBO manifest/footprints required; old 148-part board is unsafe')
    if refs & set(fixed_references):
        raise ValueError('WBO cannot move fixed references')
    for r in manifest:
        if fps[r['ref']].GetValue() != r['value']:
            raise ValueError('Stale WBO value: '+r['ref'])
        for pad in fps[r['ref']].Pads():
            expected = r['pins'].get(pad.GetNumber(), '')
            if expected and pad.GetNetname() != expected:
                raise ValueError('WBO pad/net mismatch: '+r['ref']+'.'+pad.GetNumber())
    originals = {r: fingerprint(f) for r, f in fps.items() if r not in refs}
    old_tracks = list(board.GetTracks())
    old_ids = {t.m_Uuid.AsString() for t in old_tracks}
    old_geometry = [track_fingerprint(t) for t in old_tracks]
    if any(t.GetNetname().startswith(('WBO1_', 'WBO2_')) for t in old_tracks):
        raise ValueError('Refusing to reposition previously routed WBO')
    # Dependency supplied by the board integration branch (998f104 or newer).
    # Fail closed if its primary-source connectivity audit is unavailable.
    from audit_gdi_voltage_domains import discover
    try:
        voltage_domains.provenance()
    except RuntimeError:
        voltage_domains.configure(HERE.parent/'core.net')
    domains = discover(Path(voltage_domains.provenance()['path']))
    for name, entry in domains.items():
        for node in entry['nodes']:
            pads = [q for q in fps[node['ref']].Pads() if q.GetNumber() == node['pin']]
            if not pads or any(q.GetNetname() != name for q in pads):
                raise ValueError('PT domain XML/board mismatch: '+node['ref']+'.'+node['pin'])
    copper = Copper()
    bodies = defaultdict(list)
    for r in fixed_references:
        f = fps[r]
        bodies[f.GetLayer()].append((r, bounds(f, .2)))
        for pad in f.Pads():
            for layer in LAYERS:
                copper.add(pad, layer)
    for t in old_tracks:
        for layer in LAYERS:
            copper.add(t, layer)
    # Preserve original power-zone copper envelopes, also before zone refill.
    for z in board.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != 'GND':
            for layer in LAYERS:
                copper.add(z, layer)
    source = json.loads((HERE.parent/'wbo/layout_reference.json').read_text())['footprints']
    seed = {s[f'target_ref_ch{ch}']: s for ch in (1,) for s in source}
    report = {'placed_references': [], 'local_routes': [], 'unrouted_local_pairs': [],
              'placements': [], 'original_copper_count': len(old_tracks),
              'source_layout_only_no_copper_import': True, 'production_ready': False}
    report['switching_domain_nets'] = sorted(domains)
    report['voltage_domains'] = voltage_domains.provenance()
    report['critical_proximity']=[]

    def valid(f, region):
        b = bounds(f, .2)
        if not inside(b, region) or any(overlap(b, bb) for _, bb in bodies[f.GetLayer()]):
            return False
        for pad in f.Pads():
            for layer in LAYERS:
                if pad.IsOnLayer(layer) and not copper.clear(pad.GetEffectiveShape(layer), bounds(pad, .4), layer, pad.GetNetname()):
                    return False
        return True

    def offsets(radius, step):
        yield 0, 0
        for n in range(1, round(radius/step)+1):
            ring = [(i*step, j*step) for i in range(-n, n+1) for j in range(-n, n+1) if max(abs(i), abs(j)) == n]
            yield from sorted(ring, key=lambda q: q[0]**2+q[1]**2)

    for ch in (1,):
        base = 5600+(ch-1)*200
        region = regions[ch]
        origin = (region[0]+3, region[1]+4)
        target = {}
        # Match source side/angle; larger modern components get real-body fit.
        for r in refs:
            if not base <= int(r[1:]) < base+200:
                continue
            if r in seed:
                s = seed[r]; sx, sy = s['source_position_mm']
                target[r] = (origin[0]+(sx-78.2647)*1.5, origin[1]+(sy-81.5)*1.5,
                             s['source_rotation_degrees'], s['source_layer']=='B.Cu')
        # New supply, reset and heater-inhibit grouped at the source core.
        new = {
            'U3': (9, 21, 90), 'U4': (5, 29, 0), 'U12': (17, 28, 0), 'Q0': (34, 16, -90),
            'R60': (12, 27, 90), 'R61': (10, 34, 0), 'R62': (20, 28, 90), 'R63': (9, 24, 90),
            'C60': (9, 27, 90), 'C61': (0, 29, 0), 'C62': (10, 31, 180),
            'C63': (17, 31, 0), 'C64': (12, 21, 90),
            'U10': (26, 29, 0), 'U11': (32, 29, 0), 'Q20': (32, 34, 0),
            'R40': (23, 32, 90), 'R41': (35, 29, 90), 'R42': (35, 34, 90),
            'R43': (29, 29, 90), 'R44': (25, 24, 0), 'R45': (35, 21, 90), 'R64': (29, 35, 0), 'R65': (32, 37, 0),
            'C40': (26, 26, 0), 'C41': (32, 26, 0),
            'D10': (5, 46, 0), 'D11': (15, 46, 0), 'C50': (19, 44, 90), 'C51': (27, 46, 0),
        }
        for key, (x,y,a) in new.items():
            r = key[0]+str(base+int(key[1:]))
            if r in refs:
                target[r] = (origin[0]+x, origin[1]+y, a, True)
        channel = [r for r in refs if base <= int(r[1:]) < base+200]
        if set(channel) != set(target):
            raise ValueError('Missing placement targets: '+str(set(channel)-set(target)))
        # Reserve original IC/power-package positions, then place precision
        # decoupling against actual IC pads before other passives consume space.
        # All these assignments preserve the manifest's exact electrical nets.
        proximity={
            'C60':('U4',7,1,3.5),'C62':('U4',10,1,4),'C61':('U4',1,1,4),
            'C64':('U3',2,1,3.5),'C63':('U12',6,1,3.5),
            'C40':('U10',5,1,3.5),'C41':('U11',5,1,3.5),
            'C1':('U0',4,1,3.5),'C2':('U1',5,1,3.5),
            'C12':('U2',1,1,3.5),'C14':('U2',5,1,3.5),'C15':('U2',17,1,3.5),
            'C11':('U2',5,1,4),'C13':('U5',3,1,3.5),'C18':('U5',5,1,3.5),
            'C17':('U3',1,1,3.5),'R63':('U4',7,2,4.5),'R60':('U4',7,1,4.5),
        }
        full=lambda key:key[0]+str(base+int(key[1:]))
        priorities={full(key):(full(a),ap,cp,limit) for key,(a,ap,cp,limit) in proximity.items()}
        # Reserve each IC's bypass parts immediately, before another IC or
        # heater package can consume its only short legal escape corridor.
        sequence=[]
        for ic in ('U4','U3','U12','U10','U11','U0','U1','U2','U5'):
            anchor=full(ic)
            if anchor in channel:sequence.append(anchor)
            sequence.extend(r for r,(a,_,_,_) in priorities.items() if a==anchor)
        priority_order={r:i for i,r in enumerate(sequence)}
        channel.sort(key=lambda r: (0 if r in priority_order else 1 if r.startswith(('U','Q','D','J')) or r.endswith('51') else 2,priority_order.get(r,999),r))
        for r in channel:
            f=fps[r]; x,y,a,back=target[r]
            found=False
            if r in priorities:
                anchor,ap,cp,limit=priorities[r];af=fps[anchor]
                aq=next(q for q in af.Pads() if q.GetNumber()==str(ap))
                cq=next(q for q in f.Pads() if q.GetNumber()==str(cp))
                if aq.GetNetname()!=cq.GetNetname():raise ValueError('Critical placement net changed: '+r)
                ax,ay=xy(aq);outward=(ax-xy(af)[0],ay-xy(af)[1])
                dirs=sorted([(math.cos(i*math.pi/8),math.sin(i*math.pi/8)) for i in range(16)],key=lambda v:-(v[0]*outward[0]+v[1]*outward[1]))
                # Same side first, then the other side only within the strict
                # pin-to-pin budget. A blocked cap is not silently scattered.
                for side in (af.GetLayer()==p.B_Cu,af.GetLayer()!=p.B_Cu):
                    for radius in [i*.25 for i in range(3,round(limit*4)+1)]:
                        for dx,dy in dirs:
                            for angle in (0,90,180,270):
                                move(f,0,0,angle,side);px,py=xy(cq)
                                move(f,ax+dx*radius-px,ay+dy*radius-py,angle,side)
                                if valid(f,region):found=True;break
                            if found:break
                        if found:break
                    if found:break
                if not found:raise RuntimeError(f'Critical proximity blocked: {r} to {anchor}.{ap} within {limit}mm')
                report['critical_proximity'].append({'ref':r,'anchor':anchor+'.'+str(ap),'pad':str(cp),'pad_distance_mm':round(math.dist(xy(aq),xy(cq)),3),'maximum_mm':limit,'same_side':f.GetLayer()==af.GetLayer()})
            else:
                for side in (back, not back):
                    for dx,dy in offsets(6, .5):
                        move(f,x+dx,y+dy,a,side)
                        if valid(f,region):found=True;break
                    if found:break
            if not found:
                # Explicit finite fallback remains in the owned region/side.
                positions=[(xx/2,yy/2) for xx in range(round(region[0]*2)+4,round(region[2]*2)-4)
                           for yy in range(round(region[1]*2)+4,round(region[3]*2)-4)]
                for xx,yy in sorted(positions,key=lambda q:(q[0]-x)**2+(q[1]-y)**2):
                    move(f,xx,yy,a,back)
                    if valid(f,region):found=True;break
            if not found:
                raise RuntimeError('No legal WBO placement for '+r)
            bodies[f.GetLayer()].append((r,bounds(f,.2)))
            for pad in f.Pads():
                for layer in LAYERS:copper.add(pad,layer)
            report['placed_references'].append(r)
            report['placements'].append({'ref':r,'xy_mm':xy(f),'side':f.GetLayerName(),
                                         'seed_displacement_mm':round(math.dist(xy(f),(x,y)),3)})

    # Route ONLY compact local WBO signals/precision rails, not heater current,
    # harness connections, shared CAN, global rails or main-controller signals.
    bynet=defaultdict(list)
    for r in sorted(refs):
        for pad in fps[r].Pads():
            name=pad.GetNetname()
            if name.startswith(('WBO1_', 'WBO2_')) and pad.GetNumber():bynet[name].append(pad)
    def paths(a,b):
        yield [a,b]
        yield [a,(a[0],b[1]),b]
        yield [a,(b[0],a[1]),b]
        d=min(abs(b[0]-a[0]),abs(b[1]-a[1]));sx=1 if b[0]>=a[0] else -1;sy=1 if b[1]>=a[1] else -1
        yield [a,(a[0]+sx*d,a[1]+sy*d),b]
        yield [a,(b[0]-sx*d,b[1]-sy*d),b]
        for offset in (0, .75, -.75, 1.5, -1.5, 3, -3):
            mx=(a[0]+b[0])/2+offset;my=(a[1]+b[1])/2+offset
            yield [a,(mx,a[1]),(mx,b[1]),b]
            yield [a,(a[0],my),(b[0],my),b]
    def region_for(q):
        return regions[1 if int(q.GetParentFootprint().GetReference()[1:])<5800 else 2]
    def checked_path(a,b,layer,name,region):
        for points in paths(a,b):
            if not all(region[0] <= x <= region[2] and region[1] <= y <= region[3] for x,y in points):continue
            segments=[(u,v) for u,v in zip(points,points[1:]) if math.dist(u,v)>.00001]
            if all(copper.clear(p.SHAPE_SEGMENT(vec(*u),vec(*v),p.FromMM(.2)),
                                (min(u[0],v[0])-.11,min(u[1],v[1])-.11,max(u[0],v[0])+.11,max(u[1],v[1])+.11),layer,name)
                   for u,v in segments):return segments
        return None
    def emit(segments,layer,name):
        for u,v in segments:
            t=p.PCB_TRACK(board);t.SetStart(vec(*u));t.SetEnd(vec(*v));t.SetWidth(p.FromMM(.2));t.SetLayer(layer);t.SetNet(nets[name]);board.Add(t);copper.add(t,layer)
    def via_clear(point,name,region):
        x,y=point;b=(x-.325,y-.325,x+.325,y+.325)
        if not inside(b,region):return False
        shape=p.SHAPE_CIRCLE(vec(x,y),p.FromMM(.325))
        if not all(copper.clear(shape,b,layer,name) for layer in LAYERS):return False
        # No via-in-pad process is specified. Same-net pads must also be kept
        # clear of the via annulus, although electrical clearance allows them.
        for item,other,othernet,ob in copper.items:
            if isinstance(item,p.PAD) and othernet==name and overlap(b,ob) and other.Collide(shape,p.FromMM(.1)):
                return False
        return True
    def add_via(point,name):
        v=p.PCB_VIA(board);v.SetPosition(vec(*point));v.SetWidth(p.FromMM(.65));v.SetDrill(p.FromMM(.3))
        v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNet(nets[name]);board.Add(v)
        for layer in LAYERS:copper.add(v,layer)
    def escapes(q,layer,name,limit=6):
        x,y=xy(q);region=region_for(q);result=[]
        for radius in (1,1.5,2,2.5,3):
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                point=(x+dx*radius,y+dy*radius)
                if not via_clear(point,name,region):continue
                segments=checked_path((x,y),point,layer,name,region)
                if segments is not None:
                    result.append((point,segments))
                    if len(result)>=limit:return result
        return result
    def via_route(a,b,name):
        first=a.GetParentFootprint().GetLayer();last=b.GetParentFootprint().GetLayer()
        region=region_for(a);starts=escapes(a,first,name)
        if first!=last:
            for point,stub in starts:
                path=checked_path(point,xy(b),last,name,region)
                if path is None:continue
                emit(stub,first,name);add_via(point,name);emit(path,last,name)
                return {'vias_mm':[point],'length_mm':round(sum(math.dist(u,v) for u,v in stub+path),3)}
        else:
            middle=p.F_Cu if first==p.B_Cu else p.B_Cu
            ends=escapes(b,last,name)
            choices=sorted(((math.dist(x,y),x,sx,y,sy) for x,sx in starts for y,sy in ends),key=lambda t:t[0])
            for distance,x,sx,y,sy in choices:
                if distance<.9:continue
                path=checked_path(x,y,middle,name,region)
                if path is None:continue
                emit(sx,first,name);add_via(x,name);emit(path,middle,name);add_via(y,name);emit(sy,last,name)
                return {'vias_mm':[x,y],'length_mm':round(sum(math.dist(u,v) for u,v in sx+path+sy),3)}
        return None
    pairs=[]
    pair_keys=set()
    def add_pair(a,b,priority=1):
        if a.GetNetname()!=b.GetNetname():raise ValueError('Critical decoupling pin contract changed')
        key=tuple(sorted((a.GetParentFootprint().GetReference()+'.'+a.GetNumber(),b.GetParentFootprint().GetReference()+'.'+b.GetNumber())))
        if key not in pair_keys:
            pairs.append((priority,math.dist(xy(a),xy(b)),a.GetNetname(),a,b));pair_keys.add(key)
    def pad(ref,number):
        return next(q for q in fps[ref].Pads() if q.GetNumber()==str(number))
    # Explicit high-fanout rail branches are otherwise excluded from the MST.
    # These actual pin contracts take precedence over general signal routing.
    for ch in (1,):
        n=5600+200*(ch-1)
        critical=[('U4',1,'C61',1),('U4',1,'U4',2),('U4',2,'U4',3),('U4',3,'U4',6),
                  ('U4',9,'U4',10),('U4',10,'C62',1),('U4',7,'C60',1),
                  ('U4',7,'R63',2),('R63',1,'U3',2),('U3',2,'C64',1),
                  ('C60',1,'R60',1),('U12',6,'C63',1),('U10',5,'C40',1),('U11',5,'C41',1),
                  ('U0',4,'C1',1),('U2',17,'C15',1)]
        for ar,ap,br,bp in critical:
            a=ar[0]+str(n+int(ar[1:]));b=br[0]+str(n+int(br[1:]))
            add_pair(pad(a,ap),pad(b,bp),0)
    for name,pads in bynet.items():
        if len(pads)>12 or 'HEATER_NEG' in name or 'HEATER_POS' in name:continue
        # Minimum spanning forest; avoid gratuitous redundant copper.
        linked={0}
        while len(linked)<len(pads):
            distance,i,j=min((math.dist(xy(pads[i]),xy(pads[j])),i,j) for i in linked for j in range(len(pads)) if j not in linked)
            add_pair(pads[i],pads[j]);linked.add(j)
    for priority,distance,name,a,b in sorted(pairs,key=lambda x:(x[0],x[1])):
        endpoint=lambda q:q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
        entry={'net':name,'from':endpoint(a),'to':endpoint(b),'distance_mm':round(distance,3)}
        common=[l for l in (p.F_Cu,p.B_Cu) if a.IsOnLayer(l) and b.IsOnLayer(l)]
        if distance>16 or (not common and priority!=0):
            entry['reason']='distance >16 mm' if distance>16 else 'opposite sides; intentional via routing pending'
            report['unrouted_local_pairs'].append(entry);continue
        success=False
        for layer in common:
            segments=checked_path(xy(a),xy(b),layer,name,region_for(a))
            if segments is not None:
                emit(segments,layer,name)
                entry.update({'layer':board.GetLayerName(layer),'segments':len(segments),'length_mm':round(sum(math.dist(u,v) for u,v in segments),3)})
                report['local_routes'].append(entry);success=True;break
        if not success and priority==0:
            crossing=via_route(a,b,name)
            if crossing:
                entry.update(crossing);entry['layer']='F.Cu/B.Cu';report['local_routes'].append(entry);success=True
        if not success:
            entry['reason']='all short candidate paths obstructed';report['unrouted_local_pairs'].append(entry)
    report['ground_drops']=[];report['ground_drops_pending']=[]
    for ch in (1,):
        n=5600+200*(ch-1)
        # Low-current precision/control returns only; heater power return is
        # deliberately excluded from these 0.2mm stubs.
        for rr,pin in [('C1',2),('C15',2),('C40',2),('C41',2),('C60',2),('C61',2),('C62',2),('C63',2),('C64',2),('U3',3),('U4',11),('U12',2)]:
            ref=rr[0]+str(n+int(rr[1:]));q=pad(ref,pin)
            if q.GetNetname()!='GND':raise ValueError('Ground drop pin contract changed: '+ref)
            candidates=escapes(q,fps[ref].GetLayer(),'GND',1)
            if not candidates:report['ground_drops_pending'].append(ref+'.'+str(pin));continue
            point,segments=candidates[0];emit(segments,fps[ref].GetLayer(),'GND');add_via(point,'GND')
            report['ground_drops'].append({'pad':ref+'.'+str(pin),'via_mm':point,'stub_length_mm':round(sum(math.dist(u,v) for u,v in segments),3),'ground_plane_refill_required':True})
    # First-node outline crosses the adjacent J5600 mask opening.
    from layout_repairs import repair_wbo_silk
    report['silk_repairs']=repair_wbo_silk(board)
    # Former second-node silk repairs are inapplicable: WBO2 is absent.
    assert all(fingerprint(fps[r])==state for r,state in originals.items()), 'Non-WBO footprint mutated'
    assert old_ids <= {t.m_Uuid.AsString() for t in board.GetTracks()}, 'Original copper removed'
    assert old_geometry == [track_fingerprint(t) for t in old_tracks], 'Original copper geometry changed'
    report['non_wbo_footprints_unchanged']=True
    report['original_copper_preserved']=True
    report['added_copper_uuids']=sorted(t.m_Uuid.AsString() for t in board.GetTracks() if t.m_Uuid.AsString() not in old_ids)
    report['original_copper_geometry_sha256']=hashlib.sha256(repr(old_geometry).encode()).hexdigest()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--fixed',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--netlist',type=Path,help='Authoritative core.net for the PCB snapshot')
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():raise ValueError('Use a separate output board')
    board=p.LoadBoard(str(args.input));fps={f.GetReference():f for f in board.GetFootprints()}
    if args.netlist:voltage_domains.configure(args.netlist)
    nets={n.GetNetname():n for n in board.GetNetsByNetcode().values()}
    report=place_and_route(board,fps,nets,json.loads(args.fixed.read_text())['fixed_references'])
    p.SaveBoard(str(args.output),board)
    report['input_board_sha256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    report['output_board_sha256']=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:len(report[k]) for k in ('placed_references','local_routes','unrouted_local_pairs')}))
