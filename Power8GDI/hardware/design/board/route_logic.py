"""Export/import a strictly scoped offline logic routing candidate.

Existing copper is protected in DSN and is NEVER replaced by SES import.
Only new copper on the explicit allowlist is copied from the imported session.
Power, GDI, Kelvin, timing, CAN bus pairs and analogue harness paths are excluded.
The result must still pass the independent full KiCad DRC before acceptance.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import pcbnew as p


ALLOW = {
    'CAN1_TX','CAN1_RX','CAN1_STB','LIN1_TX','LIN1_RX','LIN1_EN',
    'SWDIO','SWCLK','SWO','BOOT0',
    'SAFETY_ARM_REQUEST','SAFETY_CLEAR_N','SAFETY_FAULT_N','SAFETY_HEARTBEAT',
    'HW_KILL_N','HW_ACTUATOR_ENABLE','HW_ACTUATOR_ENABLE_N',
    *{f'IGN{i}{suffix}' for i in range(1,9) for suffix in ('','_GATED','_BUFFER','_LOGIC_OUT')},
    *{f'{domain}_{suffix}' for domain in ('DBW','EWG') for suffix in
      ('DIR','DIR_N','DISABLE','ENABLE','NOT_DISABLED','PWM','PWM_ENABLED','IN1_GATED','IN2_GATED')},
    *{f'{name}{i}' for name in ('CAM','SENT') for i in range(1,5)},
    'CRANK',
}


def block_end(text, start):
    depth=0; quoted=False; escaped=False
    for index in range(start,len(text)):
        char=text[index]
        if escaped: escaped=False; continue
        if char=='\\' and quoted: escaped=True;continue
        if char=='"': quoted=not quoted
        elif not quoted:
            if char=='(':depth+=1
            elif char==')':
                depth-=1
                if depth==0:return index+1
    raise ValueError('Unbalanced DSN block')


def signature(item):
    """Integer KiCad geometry; never compare copper merely by reference UUID."""
    if isinstance(item,p.PCB_VIA):
        return ('via',item.GetNetname(),item.GetPosition().x,item.GetPosition().y,item.GetWidth(),item.GetDrillValue())
    return ('track',item.GetNetname(),int(item.GetLayer()),item.GetStart().x,item.GetStart().y,
            item.GetEnd().x,item.GetEnd().y,item.GetWidth())


def export(board_path,dsn):
    board=p.LoadBoard(str(board_path))
    names={pad.GetNetname() for fp in board.GetFootprints() for pad in fp.Pads() if pad.GetNetname()}
    allowed=sorted(names & ALLOW);protected=sorted(names-ALLOW)
    # Reserve the two entire GDI domains, instead of asking a generic router
    # to normalize thousands of donor power/sense segments. This is an export
    # proxy ONLY; the source board stays unchanged, and import only adds copper.
    regions=[(0,0,155,93),(155,0,245,148)]
    inside=lambda q:any(x0<=p.ToMM(q.x)<=x1 and y0<=p.ToMM(q.y)<=y1 for x0,y0,x1,y1 in regions)
    removed=0
    for t in list(board.GetTracks()):
        if (isinstance(t,p.PCB_VIA) and inside(t.GetPosition())) or (
            not isinstance(t,p.PCB_VIA) and inside(t.GetStart()) and inside(t.GetEnd())):
            if t.GetNetname() in ALLOW:raise ValueError('Allowed net intersects reserved GDI export region')
            board.RemoveNative(t);removed+=1
    for x0,y0,x1,y1 in regions:
        for layer in [p.F_Cu,p.In2_Cu,p.B_Cu]:
            zone=p.ZONE(board);zone.SetLayer(layer);zone.SetIsRuleArea(True)
            zone.SetDoNotAllowTracks(True);zone.SetDoNotAllowVias(True);zone.SetDoNotAllowCopperPour(True)
            poly=zone.Outline();poly.NewOutline()
            for x,y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:poly.Append(p.FromMM(x),p.FromMM(y))
            board.Add(zone)
    assert p.ExportSpecctraDSN(board,str(dsn))
    text=dsn.read_text()
    # Only the reviewed allowlist has connection targets in the export proxy.
    # Other pads stay physical obstacles. This also protects against a router
    # version accidentally ignoring the ignored-net-class option.
    network_start=text.index('(network');network_end=block_end(text,network_start)
    network=text[network_start:network_end]
    starts=list(re.finditer(r'\(net ("(?:[^"\\]|\\.)*"|[^\s()]+)\s',network))
    for match in reversed(starts):
        raw=match.group(1);name=json.loads(raw) if raw.startswith('"') else raw
        if name in ALLOW:continue
        end=block_end(network,match.start());part=network[match.start():end]
        pins=re.search(r'\(pins\s+([^\s()]+)(?:\s+[^()]*)?\)',part)
        if pins:part=part[:pins.start()]+'(pins '+pins.group(1)+')'+part[pins.end():]
        network=network[:match.start()]+part+network[end:]
    text=text[:network_start]+network+text[network_end:]
    start=text.index('(class ');end=block_end(text,start)
    # pcbnew LoadBoard does not import the project netclasses into DSN. Supply
    # the routing rules explicitly, never accept the export's implicit defaults.
    quote=lambda name:json.dumps(name)
    classes=[]
    for name,members in [('RouteLogic',allowed),('Protected',protected)]:
        classes.append('(class '+name+' '+' '.join(map(quote,members))+
                       ' (circuit (use_via "Via[0-3]_600:300_um")) (rule (width 250) (clearance 200)))')
    text=text[:start]+'\n'.join(classes)+text[end:]
    text=text.replace('(type route)','(type protect)')
    dsn.write_text(text)
    metadata={'source_board_sha256':hashlib.sha256(board_path.read_bytes()).hexdigest(),
              'allowed_nets':allowed,'protected_nets':protected,'all_existing_copper_protected':True,
              'routing_width_mm':.25,'clearance_mm':.2,'via_mm':[.6,.3],
              'routable_layers':['F.Cu','In2.Cu','B.Cu'],'ground_plane_reserved':'In1.Cu',
              'export_only_gdi_keepout_regions_mm':regions,'donor_copper_replaced_by_keepout_in_export_only':removed}
    dsn.with_suffix('.scope.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Exported {len(allowed)} allowed / {len(protected)} protected nets')


def import_session(board_path,ses,output):
    original=p.LoadBoard(str(board_path));routed=p.LoadBoard(str(board_path))
    before=Counter(signature(t) for t in original.GetTracks())
    assert p.ImportSpecctraSES(routed,str(ses))
    nets={n.GetNetname():n for n in original.GetNetsByNetcode().values()}
    additions=[]; seen=set(before)
    for track in routed.GetTracks():
        if track.GetNetname() not in ALLOW or signature(track) in seen:continue
        if not isinstance(track,p.PCB_VIA) and track.GetLayer()==p.In1_Cu:
            raise ValueError('Router attempted to route on the reserved ground plane')
        # Export rounds to 0.1um; retain originals and avoid duplicated imports
        # whose endpoints differ only by exporter rounding.
        sig=signature(track)
        def rounded(s):return tuple(round(x/100)*100 if isinstance(x,int) and i>1 else x for i,x in enumerate(s))
        if rounded(sig) in {rounded(s) for s in seen}:continue
        clone=track.Duplicate();original.Add(clone);clone.SetNet(nets[track.GetNetname()]);seen.add(sig)
        additions.append(sig)
    assert before <= Counter(signature(t) for t in original.GetTracks())
    output.parent.mkdir(parents=True,exist_ok=True)
    p.SaveBoard(str(output),original)
    for name in (board_path.with_suffix('.kicad_pro').name,'fp-lib-table'):
        source=board_path.parent/name
        target=output.with_suffix('.kicad_pro') if name.endswith('.kicad_pro') else output.parent/name
        if source.resolve()!=target.resolve():shutil.copy2(source,target)
    original=p.LoadBoard(str(output));original.BuildConnectivity();p.ZONE_FILLER(original).Fill(original.Zones())
    p.SaveBoard(str(output),original)
    (output.parent/'logic_routing_report.json').write_text(json.dumps({
        'source_board_sha256':hashlib.sha256(board_path.read_bytes()).hexdigest(),
        'session_sha256':hashlib.sha256(ses.read_bytes()).hexdigest(),
        'original_copper_preserved':True,'new_copper_items':len(additions),
        'new_copper_by_net':dict(Counter(s[1] for s in additions)),
        'requires_independent_full_drc':True
    },indent=2)+'\n')
    print(f'Imported {len(additions)} allowed copper items; every original segment/via preserved')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=['export','import'])
    parser.add_argument('board',type=Path);parser.add_argument('route_file',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.operation=='export':export(args.board,args.route_file)
    else:
        if args.output is None:parser.error('import requires --output')
        import_session(args.board,args.route_file,args.output)
