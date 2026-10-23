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


def prepare(source, output, project, netlist):
    if source.resolve()==output.resolve():
        raise ValueError('Fixture must not overwrite source')
    voltage_domains.configure(netlist)
    original_rules=project.with_suffix('.kicad_dru').read_text()
    names=sorted(voltage_domains.gdi_high_voltage_nets())
    terms=' || '.join("A.NetName == '"+name.replace("'", "\\'")+"'" for name in names)
    rules=original_rules+'\n(rule "Audited PT switching domains" (condition "'+terms+'") (constraint clearance (min 0.6mm)))\n'
    def config():
        shutil.copyfile(project,output.with_suffix('.kicad_pro'))
        output.with_suffix('.kicad_dru').write_text(rules)
    output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,output)
    config()
    board=p.LoadBoard(str(output))
    keep={'U101','J601','J602','J603','J604'}
    removed=0
    for f in list(board.GetFootprints()):
        ref=f.GetReference()
        try: number=int(ref.lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
        except ValueError: number=-1
        if not (200<=number<400 or 5200<=number<5400 or ref in keep):
            board.Remove(f)
            removed+=1
    filler=p.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    p.SaveBoard(str(output),board)
    # KiCad may rewrite project settings while saving; preserve the exact
    # reviewed input constraints for the subsequent native DRC invocation.
    config()
    print({'fixture':str(output),'kept':len(board.GetFootprints()),'removed_unplaced':removed,
           'full_board_release_check':False,'voltage_domains':voltage_domains.provenance()})


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for name in ('source','output','project','netlist'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args()
    prepare(args.source,args.output,args.project,args.netlist)
