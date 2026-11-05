"""Structural/mutation checks for local buck PCB edits (KiCad Python).

Native DRC remains a separate required check. These assertions cannot qualify
thermal performance or return-current quality.
"""
import argparse
import json
from pathlib import Path
import pcbnew as p
import route_logic_power_local as local


def copper(board):
    return {t.m_Uuid.AsString(): (t.GetNetname(), local.mm(t.GetStart()),
        local.mm(t.GetEnd()), t.GetLayer(),
        p.ToMM(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth()))
        for t in board.GetTracks()}


def pads(board):
    return {(f.GetReference(), q.GetNumber(), q.m_Uuid.AsString()): q.GetNetname()
        for f in board.GetFootprints() for q in f.Pads()}


def check(source, routed, netlist, report):
    local.voltage_domains.configure(netlist)
    a,b=p.LoadBoard(str(source)),p.LoadBoard(str(routed))
    before,after=local.snapshot(a),local.snapshot(b)
    assert all(after[r]==v for r,v in before.items() if not local.ref_owned(r))
    assert pads(a)==pads(b), 'Pad assignment or footprint inventory changed'
    old,new=copper(a),copper(b)
    assert all(new.get(k)==v for k,v in old.items()), 'Foreign copper changed'
    declared={r['uuid'] for r in report['local_routes']+report['thermal_vias']}
    assert set(new)-set(old)==declared, 'Undocumented copper added'
    assert all(r['width_mm']>=.2 for r in report['local_routes'])
    assert all(r['diameter_mm']>=.6 and r['drill_mm']>=.3 for r in report['thermal_vias'])
    try:
        local.assert_unrouted(b,{f.GetReference():f for f in b.GetFootprints()})
    except ValueError:
        guarded=True
    else:
        raise AssertionError('Routed-input mutation guard failed')
    # Deliberately impossible region forces restore of original coordinates,
    # angles AND front/back layers. Failed placement may not mutate the board.
    restored=local.propose(a,region=(0.,0.,.01,.01))
    assert all(v['anchor_mm'] is None for v in restored['cells'].values())
    assert local.snapshot(a)==before
    # Cross, parallel, separated, and degenerate via-as-point capsule cases.
    assert local.segment_distance((0,0),(1,1),(0,1),(1,0))==0
    assert abs(local.segment_distance((0,0),(1,0),(0,2),(1,2))-2)<1e-9
    assert abs(local.segment_distance((0,0),(0,0),(3,0),(4,0))-3)<1e-9
    assert local.segment_distance((0,0),(1,1),(0,.5),(.2,.7))>.2
    return {'status':'PASS_STRUCTURAL_AND_MUTATION_CHECKS',
        'foreign_footprints_preserved':sum(not local.ref_owned(r) for r in before),
        'original_copper_items_preserved':len(old), 'new_tracks':len(report['local_routes']),
        'new_vias':len(report['thermal_vias']), 'guard_rejects_existing_routes':guarded,
        'failed_placement_restores_original_layers':True,
        'voltage_domains':local.voltage_domains.provenance(),
        'native_drc_required':True, 'qualified_for_hardware':False}


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for key in ('input','routed','netlist','report','output'):
        ap.add_argument('--'+key,type=Path,required=True)
    args=ap.parse_args()
    result=check(args.input,args.routed,args.netlist,json.loads(args.report.read_text()))
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
