"""Create an isolated pre-pack DRC fixture; never edit the source PCB.

Unplaced new modules are deliberately absent. Therefore the fixture tests
local copper against the imported donor and fixed MCU/connectors, not a full
board release. Keep both baseline and candidate fixtures under identical rules.
"""
import argparse
from pathlib import Path
import shutil
import pcbnew as p
import voltage_domains

def rect(item):
    box=item.GetBoundingBox(False,False) if isinstance(item,p.FOOTPRINT) else item.GetBoundingBox()
    return tuple(p.ToMM(v) for v in (box.GetX(),box.GetY(),box.GetRight(),box.GetBottom()))

def intersects(a,b):
    return a[0]<=b[2] and a[2]>=b[0] and a[1]<=b[3] and a[3]>=b[1]


def prepare(source, output, project, netlist, scope=None, full_board_scope=False):
    if source.resolve()==output.resolve():
        raise ValueError('Fixture must not overwrite source')
    if full_board_scope and scope is None:
        raise ValueError('Full-board spatial review requires explicit --scope')
    voltage_domains.configure(netlist)
    original_rules=project.with_suffix('.kicad_dru').read_text()
    names=sorted(voltage_domains.gdi_high_voltage_nets())
    terms=' || '.join("A.NetName == '"+name.replace("'", "\\'")+"'" for name in names)
    battery_terms=' || '.join("A.NetName == '"+name.replace("'", "\\'")+"'" for name in sorted(voltage_domains.battery_alias_nets()))
    rules=original_rules+'\n(rule "Audited battery aliases" (condition "'+battery_terms+'") (constraint clearance (min 0.3mm)))\n'
    rules+='\n(rule "Audited PT switching domains" (condition "'+terms+'") (constraint clearance (min 0.6mm)))\n'
    def config():
        shutil.copyfile(project,output.with_suffix('.kicad_pro'))
        output.with_suffix('.kicad_dru').write_text(rules)
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,output)
    config()
    board=p.LoadBoard(str(output))
    footprints=list(board.GetFootprints())
    tracks=list(board.GetTracks())
    zones=list(board.Zones())
    keep={'U101','J601','J602','J603','J604'}
    removed=0
    for f in footprints:
        ref=f.GetReference()
        try: number=int(ref.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        except ValueError: number=-1
        accepted=full_board_scope or (200<=number<400 or 5200<=number<5400 or ref in keep)
        if scope is not None:accepted=accepted and intersects(rect(f),scope)
        if not accepted:
            board.Remove(f)
            removed+=1
    removed_copper=0
    if scope is not None:
        # Retain complete crossing tracks/vias/pads and complete intersecting
        # zones on ALL layers. We never crop a crossing obstacle at the box.
        for track in tracks:
            if not intersects(rect(track),scope):
                board.Remove(track)
                removed_copper+=1
        for zone in zones:
            if not intersects(rect(zone),scope):board.Remove(zone)
    filler=p.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    p.SaveBoard(str(output),board)
    # KiCad may rewrite project settings while saving; preserve the exact
    # reviewed input constraints for the subsequent native DRC invocation.
    config()
    print({'fixture':str(output),'kept':len(board.GetFootprints()),'removed_unplaced_or_distant':removed,
           'scope_mm':scope,'removed_distant_copper':removed_copper,
           'footprint_filter':'all-intersecting-footprints' if full_board_scope else 'prepack-donor-buck-fixed-only',
           'full_board_release_check':False,'voltage_domains':voltage_domains.provenance()})


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ('source','output','project','netlist'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--scope',type=float,nargs=4)
    ap.add_argument('--full-board-scope',action='store_true',
                    help='Retain EVERY intersecting footprint, including new modules; requires --scope')
    args=ap.parse_args()
    prepare(args.source,args.output,args.project,args.netlist,args.scope,args.full_board_scope)
