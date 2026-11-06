"""Explicit gate/emitter paths for the six fixed power cells.

No collector, shared power return or Kelvin lead is autorouted here. The emitter
neck is a preliminary 1.0 mm geometry, not a current/temperature qualification.
Every connection is checked against actual saved-source pad net assignments.
"""
import pcbnew as p


def route(board, footprints, nets, add_track):
    report=[]
    def pad(ref, pin):
        return next(q for q in footprints[ref].Pads() if q.GetNumber()==str(pin))
    def xy(q):return (p.ToMM(q.GetPosition().x),p.ToMM(q.GetPosition().y))
    def connect(a,b,bends,width):
        if not a.GetNetname() or a.GetNetname()!=b.GetNetname():
            raise ValueError(f'Ignition route endpoint net mismatch: {a.GetNetname()} / {b.GetNetname()}')
        if not a.IsOnLayer(p.F_Cu) or not b.IsOnLayer(p.F_Cu):
            raise ValueError('Fixed ignition endpoints must both be on F.Cu')
        add_track(board,nets[a.GetNetname()],[xy(a),*bends,xy(b)],width,p.F_Cu)
        report.append({'net':a.GetNetname(),'from':a.GetParentFootprint().GetReference()+'.'+a.GetNumber(),
                       'to':b.GetParentFootprint().GetReference()+'.'+b.GetNumber(),'width_mm':width})
    for ch in range(1,7):
        n=5420+20*(ch-1)
        gate=pad(f'Q{n}',1);emitter=pad(f'Q{n}',3)
        series=pad(f'R{n+5}',2);pulldown_g=pad(f'R{n+6}',1);pulldown_e=pad(f'R{n+6}',2)
        shunt=pad(f'R{n+7}',1)
        gx,gy=xy(gate);ex,ey=xy(emitter);sx,sy=xy(shunt)
        branch=gx-3.35
        connect(series,gate,[],.3)
        connect(pulldown_g,gate,[(branch,xy(pulldown_g)[1]),(branch,gy)],.3)
        connect(pulldown_e,emitter,[(branch,ey)],.3)
        connect(emitter,shunt,[(sx,ey+abs(ex-sx))],1.0)
    return report


if __name__=='__main__':
    # Incremental application is deliberately refused after the first run.
    # The full builder uses route() directly on a newly constructed board.
    import argparse,json
    from pathlib import Path
    from build_board import add_track,project_file
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('board',type=Path)
    args=parser.parse_args()
    report_path=args.board.parent/'board_report.json'
    data=json.loads(report_path.read_text())
    if data.get('ignition_local_routes'):raise ValueError('Local ignition routes already applied')
    board=p.LoadBoard(str(args.board));fps={f.GetReference():f for f in board.GetFootprints()}
    for ch in range(1,7):fps[f'R{5426+20*(ch-1)}'].SetOrientationDegrees(270)
    nets={n.GetNetname():n for n in board.GetNetsByNetcode().values()}
    data['ignition_local_routes']=route(board,fps,nets,add_track)
    board.BuildConnectivity();p.ZONE_FILLER(board).Fill(board.Zones());board.BuildConnectivity()
    p.SaveBoard(str(args.board),board);project_file(args.board.with_suffix('.kicad_pro'))
    data['tracks_vias']=len(list(board.GetTracks()))
    data['unconnected_count']=board.GetConnectivity().GetUnconnectedCount(False)
    report_path.write_text(json.dumps(data,indent=2)+'\n')
    print('Added 24 checked local ignition connections; harness/return/Kelvin paths remain open')
