"""Geometry corrections; does not change DRC constraints or add exclusions."""
from collections import defaultdict
import math
import pcbnew as p


def box(item,margin=0):
    b=item.GetBoundingBox()
    return (p.ToMM(b.GetX())-margin,p.ToMM(b.GetY())-margin,
            p.ToMM(b.GetRight())+margin,p.ToMM(b.GetBottom())+margin)


def overlap(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]


class Spatial:
    def __init__(self):self.cells=defaultdict(list)
    def keys(self,b):
        for x in range(math.floor(b[0]/5),math.floor(b[2]/5)+1):
            for y in range(math.floor(b[1]/5),math.floor(b[3]/5)+1):yield x,y
    def add(self,b):
        for key in self.keys(b):self.cells[key].append(b)
    def collides(self,b):return any(overlap(b,c) for k in self.keys(b) for c in self.cells[k])


def arrange_references(board):
    """Keep legible 0.8 mm silk references, physically clear of mask/graphics.

    Duplicate donor user-text labels are removed only when they duplicate the
    actual reference field at the same position. No reference is hidden.
    A reference that cannot fit locally remains visible and is reported.
    """
    layers={p.F_SilkS:p.F_Mask,p.B_SilkS:p.B_Mask}
    obstacles={layer:Spatial() for layer in layers};duplicates=[]
    footprints=list(board.GetFootprints())
    for fp in footprints:
        for g in list(fp.GraphicalItems()):
            if isinstance(g,p.PCB_TEXT) and g.GetText() in (fp.GetReference(),'${REFERENCE}'):
                if math.dist((g.GetPosition().x,g.GetPosition().y),
                             (fp.Reference().GetPosition().x,fp.Reference().GetPosition().y))<p.FromMM(.1):
                    duplicates.append(fp.GetReference());fp.Remove(g);continue
            if g.GetLayer() in obstacles:obstacles[g.GetLayer()].add(box(g,.15))
        for pad in fp.Pads():
            for silk,mask in layers.items():
                if pad.IsOnLayer(mask):obstacles[silk].add(box(pad,.20))
    for g in board.GetDrawings():
        if g.GetLayer() in obstacles:obstacles[g.GetLayer()].add(box(g,.15))
    moved=[];unplaced=[]
    for fp in sorted(footprints,key=lambda f:f.GetReference()):
        field=fp.Reference();layer=field.GetLayer()
        if layer not in obstacles or not field.IsVisible():continue
        original=field.GetPosition();origin=(p.ToMM(original.x),p.ToMM(original.y))
        field.SetTextSize(p.VECTOR2I(p.FromMM(.8),p.FromMM(.8)))
        field.SetTextThickness(p.FromMM(.15))
        candidates=[origin]
        for radius in [0.5,1,1.5,2,2.5,3,3.5,4,4.5,5]:
            steps=round(radius/.5)
            for dx in range(-steps,steps+1):
                for dy in (-steps,steps):candidates.append((origin[0]+dx*.5,origin[1]+dy*.5))
            for dy in range(-steps+1,steps):
                for dx in (-steps,steps):candidates.append((origin[0]+dx*.5,origin[1]+dy*.5))
        found=False
        for x,y in candidates:
            field.SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)));bounds=box(field,.15)
            if bounds[0]<.3 or bounds[1]<.3 or bounds[2]>244.7 or bounds[3]>164.7:continue
            if obstacles[layer].collides(bounds):continue
            obstacles[layer].add(bounds);found=True
            if (x,y)!=origin:moved.append({'reference':fp.GetReference(),'from_mm':origin,'to_mm':[x,y]})
            break
        if not found:
            field.SetPosition(original);obstacles[layer].add(box(field,.15));unplaced.append(fp.GetReference())
    return {'duplicate_reference_texts_removed':duplicates,'references_repositioned':moved,
            'references_without_free_local_position':unplaced,'reference_height_mm':.8,'hidden_references_added':0}


def remove_dangling(board):
    """Peel genuinely dangling copper using KiCad's own connectivity predicate.

    Run only after zone filling. Keep all vias: a one-layer via may still be a
    future branch endpoint or intended thermal stitching; don't infer that it
    is disposable from the warning alone.
    """
    removed=[];blocked=[];seen=set();board.BuildConnectivity()
    count_before=board.GetConnectivity().GetUnconnectedCount(False)
    while True:
        conn=board.GetConnectivity()
        dead=next((t for t in board.GetTracks() if not isinstance(t,p.PCB_VIA)
              and t.m_Uuid.AsString() not in seen and conn.TestTrackEndpointDangling(t,True)),None)
        if dead is None:break
        for t in [dead]:
            record={'net':t.GetNetname(),'layer':board.GetLayerName(t.GetLayer()),
                            'start_mm':[p.ToMM(t.GetStart().x),p.ToMM(t.GetStart().y)],
                            'end_mm':[p.ToMM(t.GetEnd().x),p.ToMM(t.GetEnd().y)],'width_mm':p.ToMM(t.GetWidth())}
            seen.add(t.m_Uuid.AsString());previous=board.GetConnectivity().GetUnconnectedCount(False)
            # The Python Remove wrapper flips ownership and can destroy a
            # pointer still held by KiCad connectivity (KiCad9 SWIG). Native
            # detach keeps that pointer alive through the connectivity rebuild.
            board.RemoveNative(t)
            board.BuildConnectivity()
            if board.GetConnectivity().GetUnconnectedCount(False)>previous:
                board.Add(t);board.BuildConnectivity();blocked.append(record)
            else:removed.append(record)
    count_after=board.GetConnectivity().GetUnconnectedCount(False)
    if count_after>count_before:raise ValueError('Dangling cleanup increased the connectivity gap count')
    return {'dangling_tracks_removed':removed,'unconnected_before':count_before,'unconnected_after':count_after,
            'retained_to_preserve_connectivity':blocked,
            'method':'KiCad TestTrackEndpointDangling after zone fill; no via deletion'}
