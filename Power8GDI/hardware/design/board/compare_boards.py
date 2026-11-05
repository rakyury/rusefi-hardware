"""Geometric equality of two builder outputs, ignoring UUIDs and timestamps.

Used to prove a builder refactor preserves placement and copper exactly:
footprint position/orientation/side, pad nets, track/via geometry and nets,
zone outlines and Edge.Cuts. Exit 1 lists the first differences.
"""
import json
import sys
from collections import Counter
import pcbnew as p


def nm(v):return (v.x,v.y)


def snapshot(path):
    b=p.LoadBoard(str(path))
    fps={}
    for f in b.GetFootprints():
        fps[f.GetReference()]=(nm(f.GetPosition()),round(f.GetOrientationDegrees(),6),f.GetLayer(),
                               tuple(sorted((q.GetNumber(),q.GetNetname()) for q in f.Pads())))
    tracks=Counter()
    for t in b.GetTracks():
        if isinstance(t,p.PCB_VIA):tracks[('via',t.GetNetname(),nm(t.GetPosition()),t.GetWidth(p.F_Cu),t.GetDrillValue())]+=1
        else:tracks[('track',t.GetNetname(),t.GetLayer(),tuple(sorted((nm(t.GetStart()),nm(t.GetEnd())))),t.GetWidth())]+=1
    zones=Counter()
    for z in b.Zones():
        o=z.Outline();pts=tuple(nm(o.CVertex(i)) for i in range(o.TotalVertices()))
        zones[(z.GetNetname(),z.GetLayer(),z.GetIsRuleArea(),pts)]+=1
    edges=Counter((nm(d.GetStart()),nm(d.GetEnd())) for d in b.GetDrawings() if d.GetLayer()==p.Edge_Cuts)
    b.BuildConnectivity()
    return {'footprints':fps,'tracks':tracks,'zones':zones,'edges':edges,
            'unconnected':b.GetConnectivity().GetUnconnectedCount(False)}


def compare(a,b):
    diffs=[]
    fa,fb=a['footprints'],b['footprints']
    for ref in sorted(set(fa)|set(fb)):
        if fa.get(ref)!=fb.get(ref):diffs.append(f'footprint {ref}: {fa.get(ref,"missing")[:3]} != {fb.get(ref,"missing")[:3]}')
    for key in ('tracks','zones','edges'):
        only_a=a[key]-b[key];only_b=b[key]-a[key]
        if only_a or only_b:diffs.append(f'{key}: {sum(only_a.values())} only in first, {sum(only_b.values())} only in second; e.g. {list(only_a)[:2]} / {list(only_b)[:2]}')
    if a['unconnected']!=b['unconnected']:diffs.append(f"unconnected {a['unconnected']} != {b['unconnected']}")
    return diffs


if __name__=='__main__':
    first,second=snapshot(sys.argv[1]),snapshot(sys.argv[2])
    diffs=compare(first,second)
    print(json.dumps({'footprints':len(first['footprints']),'tracks_vias':sum(first['tracks'].values()),
                      'zones':sum(first['zones'].values()),'unconnected':first['unconnected'],
                      'identical':not diffs,'differences':diffs[:20]},indent=2))
    sys.exit(1 if diffs else 0)
