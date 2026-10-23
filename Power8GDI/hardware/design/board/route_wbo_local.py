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
    if len(refs) != 174 or not refs <= set(fps):
        raise ValueError('Current 174-part WBO manifest/footprints required; old 148-part board is unsafe')
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
    seed = {s[f'target_ref_ch{ch}']: s for ch in (1, 2) for s in source}
    report = {'placed_references': [], 'local_routes': [], 'unrouted_local_pairs': [],
              'placements': [], 'original_copper_count': len(old_tracks),
              'source_layout_only_no_copper_import': True, 'production_ready': False}
    report['switching_domain_nets'] = sorted(domains)
    report['voltage_domains'] = voltage_domains.provenance()

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

    for ch in (1, 2):
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
            'U3': (2, 23, 90), 'U4': (5, 29, 0), 'U12': (17, 28, 0), 'Q0': (34, 16, -90),
            'R60': (4, 35, 90), 'R61': (9, 34, 0), 'R62': (20, 28, 90), 'R63': (2, 32, 90),
            'C60': (4, 32, 90), 'C61': (1, 27, 90), 'C62': (10, 29, 90),
            'C63': (17, 31, 0), 'C64': (1, 22, 90),
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
        # ICs first, then large power packages, then source analog passives.
        channel.sort(key=lambda r: (0 if r.startswith('U') else 1 if r.startswith(('Q','D','J')) or r.endswith('51') else 2, r))
        for r in channel:
            f=fps[r]; x,y,a,back=target[r]
            found=False
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
    pairs=[]
    for name,pads in bynet.items():
        if len(pads)>12 or 'HEATER_NEG' in name or 'HEATER_POS' in name:continue
        # Minimum spanning forest; avoid gratuitous redundant copper.
        linked={0}
        while len(linked)<len(pads):
            distance,i,j=min((math.dist(xy(pads[i]),xy(pads[j])),i,j) for i in linked for j in range(len(pads)) if j not in linked)
            pairs.append((distance,name,pads[i],pads[j]));linked.add(j)
    for distance,name,a,b in sorted(pairs,key=lambda x:x[0]):
        endpoint=lambda q:q.GetParentFootprint().GetReference()+'.'+q.GetNumber()
        entry={'net':name,'from':endpoint(a),'to':endpoint(b),'distance_mm':round(distance,3)}
        common=[l for l in (p.F_Cu,p.B_Cu) if a.IsOnLayer(l) and b.IsOnLayer(l)]
        if distance>16 or not common:
            entry['reason']='distance >16 mm' if distance>16 else 'opposite sides; intentional via routing pending'
            report['unrouted_local_pairs'].append(entry);continue
        success=False
        for layer in common:
            for points in paths(xy(a),xy(b)):
                segments=[(u,v) for u,v in zip(points,points[1:]) if math.dist(u,v)>.00001]
                if not all(copper.clear(p.SHAPE_SEGMENT(vec(*u),vec(*v),p.FromMM(.2)),
                                       (min(u[0],v[0])-.11,min(u[1],v[1])-.11,max(u[0],v[0])+.11,max(u[1],v[1])+.11),layer,name)
                           for u,v in segments):continue
                for u,v in segments:
                    t=p.PCB_TRACK(board);t.SetStart(vec(*u));t.SetEnd(vec(*v));t.SetWidth(p.FromMM(.2));t.SetLayer(layer);t.SetNet(nets[name]);board.Add(t);copper.add(t,layer)
                entry.update({'layer':board.GetLayerName(layer),'segments':len(segments),'length_mm':round(sum(math.dist(u,v) for u,v in segments),3)})
                report['local_routes'].append(entry);success=True;break
            if success:break
        if not success:
            entry['reason']='all short candidate paths obstructed';report['unrouted_local_pairs'].append(entry)
    assert all(fingerprint(fps[r])==state for r,state in originals.items()), 'Non-WBO footprint mutated'
    assert old_ids <= {t.m_Uuid.AsString() for t in board.GetTracks()}, 'Original copper removed'
    assert old_geometry == [track_fingerprint(t) for t in old_tracks], 'Original copper geometry changed'
    report['non_wbo_footprints_unchanged']=True
    report['original_copper_preserved']=True
    report['original_copper_geometry_sha256']=hashlib.sha256(repr(old_geometry).encode()).hexdigest()
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--fixed',type=Path,required=True);parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args()
    if args.input.resolve()==args.output.resolve():raise ValueError('Use a separate output board')
    board=p.LoadBoard(str(args.input));fps={f.GetReference():f for f in board.GetFootprints()}
    nets={n.GetNetname():n for n in board.GetNetsByNetcode().values()}
    report=place_and_route(board,fps,nets,json.loads(args.fixed.read_text())['fixed_references'])
    p.SaveBoard(str(args.output),board)
    report['input_board_sha256']=hashlib.sha256(args.input.read_bytes()).hexdigest()
    report['output_board_sha256']=hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:len(report[k]) for k in ('placed_references','local_routes','unrouted_local_pairs')}))
