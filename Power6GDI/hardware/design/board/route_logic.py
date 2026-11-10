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
import os
from pathlib import Path
import re
import shutil
import pcbnew as p
import voltage_domains


ALLOW = {
    *{f'{bus}{n}_{sig}' for n in (1,2) for bus,sigs in [('CAN',('TX','RX','STB')),('LIN',('TX','RX','EN'))] for sig in sigs},
    'SWDIO','SWCLK','SWO','BOOT0',
    'SAFETY_ARM_REQUEST','SAFETY_CLEAR_N','SAFETY_FAULT_N','SAFETY_HEARTBEAT',
    'HW_KILL_N','HW_ACTUATOR_ENABLE','HW_ACTUATOR_ENABLE_N',
    *{f'IGN{i}{suffix}' for i in range(1,9) for suffix in ('','_WINDOW','_GUARDED')},
    'IGN_OC_OK','IGN_OC_OK_CLEAN','IGN_SAFE_EN',
    *{f'{domain}_{suffix}' for domain in ('DBW','EWG','MOTOR3','MOTOR4') for suffix in
      ('DIR','DIR_FILTERED','DISABLE','DIS_GATED','PWM','PWM_FILTERED','SPI_SO')},
    'MOTOR_CS_N','MOTOR_MISO_BUFFERED','MOTOR_SPI_SCK','MOTOR_SPI_SI',
    *{f'{name}{i}' for name in ('CAM','SENT') for i in range(1,5)},
    'CRANK',
}
PRECISION_REGIONS=((153,52,197,142),(198,52,242,142))


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
        return ('via',item.GetNetname(),item.GetPosition().x,item.GetPosition().y,item.GetWidth(p.F_Cu),item.GetDrillValue())
    return ('track',item.GetNetname(),int(item.GetLayer()),item.GetStart().x,item.GetStart().y,
            item.GetEnd().x,item.GetEnd().y,item.GetWidth())


def export(board_path,dsn):
    voltage_domains.configure(Path(__file__).resolve().parent.parent/'core.net')
    board=p.LoadBoard(str(board_path))
    names={pad.GetNetname() for fp in board.GetFootprints() for pad in fp.Pads() if pad.GetNetname()}
    # Preserve all pads' original net membership: deleting protected net pins
    # from DSN would silently turn HV pads into ordinary no-net obstacles.
    rules=board_path.with_suffix('.kicad_dru').read_text()
    explicit={}
    for line in rules.splitlines():
        match=re.search(r'\(constraint clearance \(min ([\d.]+)mm\)',line)
        if match:
            for name in re.findall(r"A\.NetName == '([^']+)'",line):explicit[name]=max(explicit.get(name,0),float(match.group(1)))
    missing=[n for n in names if voltage_domains.clearance_mm(n)>.2 and explicit.get(n,0)<voltage_domains.clearance_mm(n)]
    if missing:raise ValueError('Saved source rules do not cover current voltage policy: '+str(sorted(missing)))
    deferred=set()
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            x,y=p.ToMM(pad.GetPosition().x),p.ToMM(pad.GetPosition().y)
            if any(x0<=x<=x1 and y0<=y<=y1 for x0,y0,x1,y1 in PRECISION_REGIONS):deferred.add(pad.GetNetname())
    allowed=sorted((names & ALLOW)-deferred);protected=sorted(names-set(allowed))
    # Keep every real segment/via as a protected physical obstacle. The former
    # whole-island B.Cu keepouts incorrectly blocked all newly placed B.Cu IO.
    # In1 is reserved for ground, independently of external router settings.
    zone=p.ZONE(board);zone.SetLayer(p.In1_Cu);zone.SetIsRuleArea(True)
    zone.SetDoNotAllowTracks(True);zone.SetDoNotAllowVias(False);zone.SetDoNotAllowCopperPour(False)
    poly=zone.Outline();poly.NewOutline()
    for x,y in [(0,0),(245,0),(245,165),(0,165)]:poly.Append(p.FromMM(x),p.FromMM(y))
    board.Add(zone)
    # WBO precision placement is still being refined. Do not freeze it by
    # routing unrelated digital copper under or across either analogue island.
    for layer in (p.F_Cu,p.In2_Cu,p.B_Cu):
        for x0,y0,x1,y1 in PRECISION_REGIONS:
            region=p.ZONE(board);region.SetLayer(layer);region.SetIsRuleArea(True)
            region.SetDoNotAllowTracks(True);region.SetDoNotAllowVias(True);region.SetDoNotAllowCopperPour(False)
            outline=region.Outline();outline.NewOutline()
            for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):outline.Append(p.FromMM(x),p.FromMM(y))
            board.Add(region)
    assert p.ExportSpecctraDSN(board,str(dsn))
    text=dsn.read_text()
    start=text.index('(class ');end=block_end(text,start)
    # pcbnew LoadBoard does not import the project netclasses into DSN. Supply
    # the routing rules explicitly, never accept the export's implicit defaults.
    quote=lambda name:json.dumps(name)
    classes=[]
    ignition=[n for n in protected if re.fullmatch(r'HARNESS_IGN[1-8]',n)]
    boost=sorted(set(protected)&voltage_domains.gdi_high_voltage_nets())
    battery=[n for n in protected if n.startswith('VBAT') or n in voltage_domains.battery_alias_nets()]
    ordinary=sorted(set(protected)-set(ignition+boost+battery))
    for name,members,width,clearance in [('RouteLogic',allowed,250,200),('Protected',ordinary,250,200),
                                       ('ProtectedBattery',battery,600,300),('ProtectedBoost',boost,800,600),
                                       ('ProtectedIgnition',ignition,1500,2500)]:
        classes.append('(class '+name+' '+' '.join(map(quote,members))+
                       f' (circuit (use_via "Via[0-3]_600:300_um")) (rule (width {width}) (clearance {clearance})))')
    text=text[:start]+'\n'.join(classes)+text[end:]
    text=text.replace('(type route)','(type protect)')
    dsn.write_text(text)
    metadata={'source_board_sha256':hashlib.sha256(board_path.read_bytes()).hexdigest(),
              'source_project_sha256':hashlib.sha256(board_path.with_suffix('.kicad_pro').read_bytes()).hexdigest(),
              'source_custom_rules_sha256':hashlib.sha256(board_path.with_suffix('.kicad_dru').read_bytes()).hexdigest(),
              'voltage_domains':voltage_domains.provenance(),
              'allowed_nets':allowed,'protected_nets':protected,'all_existing_copper_protected':True,
              'deferred_allowlist_nets_inside_precision_regions':sorted(deferred & ALLOW),
              'precision_region_export_keepouts_mm':PRECISION_REGIONS,
              'all_pad_net_memberships_preserved':True,
              'routing_width_mm':.25,'clearance_mm':.2,'via_mm':[.6,.3],
              'routable_layers':['F.Cu','In2.Cu','B.Cu'],'ground_plane_reserved':'In1.Cu',
              'export_only_gdi_keepout_regions_mm':[],'donor_copper_replaced_by_keepout_in_export_only':0,
              'protected_netclasses':['Protected','ProtectedBattery','ProtectedBoost','ProtectedIgnition']}
    dsn.with_suffix('.scope.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Exported {len(allowed)} allowed / {len(protected)} protected nets')


def import_session(board_path,ses,output):
    if board_path.resolve()==output.resolve():raise ValueError('Routing import must preserve its source board')
    scope=json.loads(ses.with_suffix('.scope.json').read_text())
    if scope['source_board_sha256']!=hashlib.sha256(board_path.read_bytes()).hexdigest():
        raise ValueError('Routing source board changed after DSN export; refusing stale SES')
    for key,suffix in [('source_project_sha256','.kicad_pro'),('source_custom_rules_sha256','.kicad_dru')]:
        if scope[key]!=hashlib.sha256(board_path.with_suffix(suffix).read_bytes()).hexdigest():
            raise ValueError('Routing source rules changed after DSN export; refusing stale SES')
    allowed=set(scope['allowed_nets'])
    if not allowed<=ALLOW:raise ValueError('Scope contains nets outside reviewed digital allowlist')
    original=p.LoadBoard(str(board_path));routed=p.LoadBoard(str(board_path))
    before=Counter(signature(t) for t in original.GetTracks())
    assert p.ImportSpecctraSES(routed,str(ses))
    nets={n.GetNetname():n for n in original.GetNetsByNetcode().values()}
    additions=[]; seen=set(before)
    for track in routed.GetTracks():
        if track.GetNetname() not in allowed or signature(track) in seen:continue
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
    def copy_rules():
        for name in (board_path.with_suffix('.kicad_pro').name,board_path.with_suffix('.kicad_dru').name,'fp-lib-table'):
            source=board_path.parent/name
            target=output.with_suffix(source.suffix) if source.suffix in ('.kicad_pro','.kicad_dru') else output.parent/name
            if name=='fp-lib-table':
                text=source.read_text()
                text=re.sub(r'\$\{KIPRJMOD\}/([^\"]+)',lambda m:'${KIPRJMOD}/'+os.path.relpath((board_path.parent/m.group(1)).resolve(),output.parent),text)
                if source.resolve()!=target.resolve():target.write_text(text)
            else:shutil.copy2(source,target)
    # The second load/fill needs the real rules already in place, then restore
    # their bytes after SaveBoard in case KiCad persisted an in-process cache.
    copy_rules()
    original=p.LoadBoard(str(output));original.BuildConnectivity();p.ZONE_FILLER(original).Fill(original.Zones())
    p.SaveBoard(str(output),original)
    copy_rules()
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
