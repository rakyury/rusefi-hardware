"""Transfer reference copper only after physical pad/net and endpoint graph audit.

No connectivity is inferred from straight line distance. The source board's
KiCad connectivity graph determines every retained copper component. Branches
ending only at removed logic/connectors are peeled from the graph.
"""
from collections import defaultdict, deque
import pcbnew as p


def uid(item):
    return item.m_Uuid.AsString()


def audited_copper(source, refmap, assignments):
    source.BuildConnectivity()
    conn = source.GetConnectivity()
    footprints = {f.GetReference(): f for f in source.GetFootprints()}
    remap, anchors, retained_pads = defaultdict(set), {}, {}
    for oldref, newref in refmap.items():
        if oldref not in footprints:
            raise ValueError(f"Reference PCB missing footprint {oldref}")
        for pad in footprints[oldref].Pads():
            key = (newref, pad.GetNumber())
            if not pad.GetNumber() or key not in assignments:
                continue
            oldnet, newnet = pad.GetNetname(), assignments[key]
            # NC on a retained IC is not an invitation to copy the old removed
            # channel's copper or zones. The physical pad stays on the PCB,
            # but its historical net is excluded from the donor graph.
            if newnet.startswith('unconnected-'):
                continue
            if not oldnet:
                raise ValueError(f"Reference pad {oldref}.{pad.GetNumber()} has no copper net")
            remap[oldnet].add(newnet)
            retained_pads[uid(pad)] = pad
            anchors[uid(pad)] = key
    conflicts = {net: sorted(names) for net, names in remap.items() if len(names) != 1}
    if conflicts:
        raise ValueError(f"Source PCB copper would short distinct schematic nets: {conflicts}")
    netmap = {name: next(iter(values)) for name, values in remap.items()}
    tracks = {uid(t): t for t in source.GetTracks() if t.GetNetname() in netmap}
    allitems = tracks | retained_pads
    graph = {key: set() for key in allitems}
    ground_vias = {key for key,t in tracks.items() if isinstance(t,p.PCB_VIA) and netmap[t.GetNetname()] == 'GND'}
    for key, item in allitems.items():
        for neighbour in [*conn.GetConnectedTracks(item), *conn.GetConnectedPads(item)]:
            other = uid(neighbour)
            if other in allitems and other != key:
                graph[key].add(other); graph[other].add(key)
    # Peel dead-end copper. Ground vias are genuine plane endpoints, not fake
    # connection claims; the board's In1 GND zone is filled and DRC checked later.
    protected = set(anchors) | ground_vias
    queue = deque(key for key, ns in graph.items() if key not in protected and len(ns) <= 1)
    removed = set()
    while queue:
        key = queue.popleft()
        if key in removed:
            continue
        removed.add(key)
        for other in graph[key]:
            graph[other].discard(key)
            if other not in protected and len(graph[other]) <= 1:
                queue.append(other)
        graph[key].clear()
    selected, visited, groups = set(), set(), []
    for key in graph.keys() - removed:
        if key in visited:
            continue
        component, pending = set(), [key]
        while pending:
            current = pending.pop()
            if current in component: continue
            component.add(current); visited.add(current)
            pending.extend(graph[current] - component)
        pads = component & anchors.keys()
        vias = component & ground_vias
        accepted = len(pads) >= 2 or (len(pads) >= 1 and len(vias) >= 1)
        if accepted:
            selected.update(component & tracks.keys())
        groups.append({"net": allitems[key].GetNetname(), "pads": sorted(f'{anchors[k][0]}.{anchors[k][1]}' for k in pads),
                       "ground_plane_vias": len(vias), "copper_items": len(component & tracks.keys()), "accepted": accepted})
    # A track-node graph can have two neighbours at one end and an open other
    # end. Audit each physical endpoint too, then peel newly exposed tails.
    endpoint_removed=0
    while True:
        rejected=set()
        for key in selected:
            track=tracks[key]
            if isinstance(track,p.PCB_VIA):continue
            for point in (track.GetStart(),track.GetEnd()):
                neighbours=(graph[key] & (selected | anchors.keys()))
                if not any(allitems[other].HitTest(point,1000) for other in neighbours):
                    rejected.add(key);break
        if not rejected:break
        selected-=rejected;endpoint_removed+=len(rejected)
    return netmap, [tracks[key] for key in sorted(selected)], {
        "source_tracks_vias": len(list(source.GetTracks())), "mapped_candidates": len(tracks),
        "dead_end_items_removed": len(removed), "endpoint_tail_items_removed":endpoint_removed,
        "retained_tracks_vias": len(selected),
        "components": groups,
    }
