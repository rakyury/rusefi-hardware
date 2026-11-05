"""Derive downstream inputs from the compact zone plan.

1. layout_constraints.json: outline, connector centres and per-side zone
   rectangles in board coordinates for the pcbnew builder (functional_layout)
   once it runs on a machine with KiCad. Nothing here places a footprint.
2. mechanical/assembly_manifest.json: concept enclosure manifest for
   build_assembly.py, with board size, connector centres and component
   envelopes taken from the zone plan and the heights from the study.

Both outputs are data; the geometry claims remain screening-level.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compact_floorplan as cf  # noqa: E402

MECHANICAL = HERE.parents[3] / 'mechanical'

# Enclosure concept parameters (mm). Corner lid bosses sit outside the board
# corners, which is what pushes the housing 13 mm wider than the board.
ENCLOSURE = dict(wall=3.0, floor=4.0, boss_radius=3.0, board_gap=0.5, back_side_clearance=1.0,
                 top_clearance=1.0, lid_z=6.0, connector_width=40.0, connector_depth=44.0,
                 connector_height=25.0, connector_on_board_depth=36.5)


def board_to_cad(x, y, plan):
    """Zone plan origin is top-left with the connector face at +y; CAD is centred with the face at -Y."""
    return x - plan['board_w'] / 2, -(y - plan['board_d'] / 2)


def zone_z(parts, zone):
    zs = [p['z'] for p in parts if p['side'] == zone['side'] and p['block'] in zone['blocks'] and p['z'] is not None]
    return max(zs) if zs else 1.8


def layout_constraints(plan, parts):
    cols = []
    for c in plan['connectors']:
        x0, y0, x1, y1 = c['rect']
        cols.append(dict(name=c['name'], centre_mm=[round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)], rect=c['rect']))
    zones = [dict(name=z['name'], side=z['side'], rect=z['rect'], blocks=z['blocks'], max_z_mm=zone_z(parts, z))
             for z in plan['zones']]
    return dict(status='SCREENING_CONSTRAINTS_NOT_A_PLACEMENT', outline_mm=[plan['board_w'], plan['board_d']],
                connectors=cols, zones=zones, density_target=plan['density_target'],
                note='Consumed by functional_layout once run under pcbnew; coordinates in KiCad board mm, origin top-left.')


def mechanical_manifest(plan, parts, previous):
    e = ENCLOSURE
    W, D = plan['board_w'], plan['board_d']
    back_z = max([p['z'] for p in parts if p['side'] == 'B' and p['z'] is not None] + [0.0])
    front_z = max([p['z'] for p in parts if p['side'] == 'F' and p['z'] is not None] + [0.0])
    pcb_t = previous['parameters']['pcb_thickness']
    pcb_bottom = e['floor'] + e['back_side_clearance'] + back_z
    base_z = pcb_bottom + pcb_t + front_z + e['top_clearance']
    base_z = float(int(base_z + 0.999))
    housing_x = W + 2 * (e['board_gap'] + 2 * e['boss_radius']) + 1.0
    housing_y = D + 2 * (e['board_gap'] + 2 * e['boss_radius']) + 1.0
    conn_x = [round(board_to_cad(*(((c['rect'][0] + c['rect'][2]) / 2), 0), plan)[0], 2) for c in plan['connectors']]
    envelopes = {}
    for z in plan['zones']:
        if z['side'] != 'F':
            continue
        x0, y0, x1, y1 = z['rect']
        cx, cy = board_to_cad((x0 + x1) / 2, (y0 + y1) / 2, plan)
        key = ''.join(ch if ch.isalnum() else '_' for ch in z['name']).strip('_').upper()[:28]
        envelopes[key] = [round(x1 - x0 - 1, 2), round(y1 - y0 - 1, 2), zone_z(parts, z), round(cx, 2), round(cy, 2)]
    mounts = [[-W / 2 + 6, -D / 2 + 6], [-W / 2 + 6, D / 2 - 6], [W / 2 - 6, -D / 2 + 6], [W / 2 - 6, D / 2 - 6]]
    params = dict(previous['parameters'])
    params.update(dict(pcb_x=float(W), pcb_y=float(D), housing_x=housing_x, housing_y=housing_y, base_z=base_z,
                       lid_z=e['lid_z'], wall=e['wall'], floor=e['floor'], pcb_bottom_z=round(pcb_bottom, 2),
                       connector_width=e['connector_width'], connector_depth=e['connector_depth'],
                       connector_bottom_z=round(pcb_bottom + pcb_t + 1.0, 2), connector_height=e['connector_height'],
                       connector_x=conn_x, connector_y=round(-D / 2 - e['connector_depth'] / 2 + e['connector_on_board_depth'], 2),
                       screw_x=round(housing_x / 2 - e['boss_radius'], 2), screw_y=round(housing_y / 2 - e['boss_radius'], 2),
                       perimeter_boss_radius=e['boss_radius'], pcb_standoff_radius=3.0))
    m = dict(previous)
    m['parameters'] = params
    m['pcb_mounts'] = mounts
    m['component_envelopes'] = envelopes
    m['solids'] = ['Base', 'Lid', 'PCB'] + list(envelopes) + [f'J_{k}_34PIN_ENVELOPE' for k in 'ABCD']
    m['geometry_fidelity'] = {s: ('concept CAD' if s in ('Base', 'Lid') else 'envelope') for s in m['solids']}
    m['derived_from'] = dict(zone_plan=plan['name'], generator='hardware/design/board/compact/export_constraints.py',
                             decision='2026-10-29 single board, 190 mm width kept, enclosure height may grow',
                             heights_mm=dict(front_max=front_z, back_max=back_z, te34_header='not from STEP; envelope 23 mm'))
    return m


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pcb', default=str(HERE.parent / 'gdi6_candidate' / 'Power8GDI_Review.kicad_pcb'))
    ap.add_argument('--netlist', default=str(HERE.parents[1] / 'core.net'))
    ap.add_argument('--plan', default=str(HERE / 'floorplan_190x160.json'))
    ap.add_argument('--previous-manifest', default=str(MECHANICAL / 'assembly_manifest.json'))
    ap.add_argument('--out', default=str(HERE / 'output'))
    ap.add_argument('--write-mechanical', action='store_true', help='overwrite mechanical/assembly_manifest.json')
    args = ap.parse_args(argv)
    parts, _ = cf.load_parts(Path(args.pcb), Path(args.netlist), HERE / 'body_overrides.json')
    plan = json.loads(Path(args.plan).read_text())
    previous = json.loads(Path(args.previous_manifest).read_text())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'layout_constraints.json').write_text(json.dumps(layout_constraints(plan, parts), indent=1) + '\n')
    manifest = mechanical_manifest(plan, parts, previous)
    (out / 'assembly_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    if args.write_mechanical:
        (MECHANICAL / 'assembly_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    p = manifest['parameters']
    print(f"board {p['pcb_x']} x {p['pcb_y']}, housing {p['housing_x']} x {p['housing_y']} x {p['base_z'] + p['lid_z']} mm, "
          f"pcb bottom z {p['pcb_bottom_z']}, connectors x {p['connector_x']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
