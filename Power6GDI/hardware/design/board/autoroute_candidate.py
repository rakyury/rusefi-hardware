"""Import a Freerouting session into a copy of a candidate; label it, never bless it.

Pipeline (run under the pinned KiCad image, from the repository root):

  python3 Power6GDI/hardware/design/board/autoroute_candidate.py export <candidate.kicad_pcb> <work dir>
      writes <work dir>/board.dsn from a copy of the candidate
  <Freerouting CLI> on board.dsn -> board.ses   (external tool; its options are not assumed here)
  python3 Power6GDI/hardware/design/board/autoroute_candidate.py import <candidate.kicad_pcb> <work dir> <output dir>

The import step copies the candidate, applies the .ses, REMOVES every track and
via the router produced on an excluded net (HARNESS_IGN* by default: their
2.5 mm rule is incompatible with the 3 mm TE34 pitch and the J602 pinout is an
open owner decision), refills zones, counts connectivity and writes
autoroute_report.json. The output is an AUTOROUTED CANDIDATE: machine-generated
copper that nobody has reviewed for return paths, loop areas, current, thermal
or EMC behaviour. The hand-checked placement candidate is left untouched.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys
import pcbnew as p

EXCLUDE=re.compile(r'HARNESS_IGN[1-8]$')


def digest(path):return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def export(candidate,work):
    work.mkdir(parents=True,exist_ok=True)
    board=p.LoadBoard(str(candidate))
    if not p.ExportSpecctraDSN(board,str(work/'board.dsn')):raise RuntimeError('DSN export failed')
    (work/'export.json').write_text(json.dumps({'candidate':str(candidate),'candidate_sha256':digest(candidate),
        'dsn_sha256':digest(work/'board.dsn'),'unconnected_before':board.GetConnectivity().GetUnconnectedCount(False)},indent=2)+'\n')
    print('exported',work/'board.dsn')


def import_session(candidate,work,out):
    out.mkdir(parents=True,exist_ok=True)
    meta=json.loads((work/'export.json').read_text())
    if meta['candidate_sha256']!=digest(candidate):raise ValueError('Candidate changed since the DSN export; export again')
    for name in ('Power8GDI_Review.kicad_pcb','Power8GDI_Review.kicad_pro','Power8GDI_Review.kicad_dru','fp-lib-table'):
        src=candidate.parent/name
        if src.exists():shutil.copy(src,out/name)
    dest=out/'Power8GDI_Review.kicad_pcb'
    board=p.LoadBoard(str(dest));board.BuildConnectivity()
    before_items={t.m_Uuid.AsString() for t in board.GetTracks()}
    if not p.ImportSpecctraSES(board,str(work/'board.ses')):raise RuntimeError('SES import failed')
    added=[t for t in board.GetTracks() if t.m_Uuid.AsString() not in before_items]
    removed=[]
    for t in added:
        if EXCLUDE.match(t.GetNetname()):
            removed.append({'net':t.GetNetname(),'type':'via' if t.Type()==p.PCB_VIA_T else 'track'});board.RemoveNative(t)
    board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());board.BuildConnectivity()
    after=board.GetConnectivity().GetUnconnectedCount(False)
    title=board.GetTitleBlock();title.SetTitle('Power6GDI AUTOROUTED CANDIDATE / machine copper, not reviewed / DO NOT FABRICATE')
    p.SaveBoard(str(dest),board)
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from build_board import project_file
    project_file(dest.with_suffix('.kicad_pro'),None,board)
    kept=[t for t in added if not EXCLUDE.match(t.GetNetname())]
    report={'qualification':'AUTOROUTED_CANDIDATE_NOT_REVIEWED_DO_NOT_FABRICATE',
            'source_candidate':str(candidate),'source_candidate_sha256':meta['candidate_sha256'],
            'dsn_sha256':meta['dsn_sha256'],'ses_sha256':digest(work/'board.ses'),
            'router_items_added':len(kept),'router_tracks':sum(t.Type()!=p.PCB_VIA_T for t in kept),'router_vias':sum(t.Type()==p.PCB_VIA_T for t in kept),
            'excluded_nets_pattern':EXCLUDE.pattern,'router_items_removed_on_excluded_nets':len(removed),
            'unconnected_before':meta['unconnected_before'],'unconnected_after':after,
            'nets_touched':sorted({t.GetNetname() for t in kept}),
            'review_status':'none: return paths, loop areas, current, thermal and EMC not assessed; DRC must be run separately'}
    (out/'autoroute_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('router_items_added','router_items_removed_on_excluded_nets','unconnected_before','unconnected_after')},indent=2))


if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='export':export(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
    elif mode=='import':import_session(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve(),Path(sys.argv[4]).resolve())
    else:raise SystemExit(__doc__)
