"""Compact Power6GDI floorplan study: block area demand, envelope options, zones.

Pure Python; runs without pcbnew. Inputs are the current GDI6 candidate PCB
(for actual footprint boxes), the root netlist (for sheet -> block mapping) and
body_overrides.json (bodies and heights for pad-only footprints).

Outputs a JSON study, a zone SVG and a console summary. Utilization figures are
component bounding-box area over zone area; they are a screening metric
calibrated against the routed rusEFI GDI-4ch board (41 % on two layers), not a
routing proof. No electrical, thermal or manufacturing claim follows.
"""
from __future__ import annotations
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pcb_sexpr  # noqa: E402

BLOCK_RULES = [
    ('GDI bank A', 'GDI power stage/A'),
    ('GDI bank B', 'GDI power stage/B'),
    ('Ignition', 'Ignition'),
    ('Direct protected low-side', 'Low-side outputs'),
    ('Low-side shared', 'Low-side outputs'),
    ('Buffered analog', 'Analog inputs'),
    ('Dual sensor', 'Analog inputs'),
    ('Hall and SENT', 'Digital/SENT/VR inputs'),
    ('Additional Hall', 'Digital/SENT/VR inputs'),
    ('Differential VR', 'Digital/SENT/VR inputs'),
    ('CAN', 'CAN/LIN'),
    ('MCU', 'MCU core'),
    ('Self-powered USB', 'MCU core'),
    ('microSD', 'MCU core'),
    ('Latched hardware', 'MCU core'),
    ('knock', 'Knock'),
    ('Four TE34', 'Connectors'),
    ('gdi', 'GDI protection'),
    ('motor4', 'Motor bridges'),
    ('wbo', 'WBO'),
    ('logic power', 'Logic power'),
]


def block_of(sheet_name: str) -> str:
    for prefix, block in BLOCK_RULES:
        if sheet_name.startswith(prefix):
            return block
    return 'unassigned:' + sheet_name


def load_overrides(path: Path):
    data = json.loads(path.read_text())
    return data['overrides'], data.get('default_z_mm', 1.8)


def apply_override(fp, overrides, default_z):
    for o in overrides:
        if o['match'] in fp.lib_id:
            w, h = o['width_mm'], o['height_mm']
            if abs((fp.rotation % 180) - 90) < 1e-6:
                w, h = h, w
            return dict(width=w, height=h, z=o['z_mm'], z_known=o['z_mm'] is not None, override=o['match'])
    return dict(width=fp.width, height=fp.height, z=default_z, z_known=False, override=None)


def load_parts(pcb: Path, netlist: Path, overrides_path: Path):
    board = pcb_sexpr.read_board(pcb)
    sheets = {c.attrib['ref']: c.find('sheetpath').get('names').strip('/')
              for c in ET.parse(netlist).findall('components/comp')}
    overrides, default_z = load_overrides(overrides_path)
    parts = []
    for fp in board['footprints']:
        if fp.dnp:
            continue
        geo = apply_override(fp, overrides, default_z)
        sheet = sheets.get(fp.ref, '')
        parts.append(dict(ref=fp.ref, value=fp.value, lib_id=fp.lib_id, side=fp.side, sheet=sheet,
                          block=block_of(sheet) if sheet else ('Connectors' if fp.ref.startswith('J60') else 'unassigned:no-sheet'),
                          width=geo['width'], height=geo['height'], area=round(geo['width'] * geo['height'], 2),
                          z=geo['z'], z_known=geo['z_known'], box_source=fp.box_source, override=geo['override']))
    return parts, board


def demand(parts):
    d = defaultdict(lambda: {'count': 0, 'F': 0.0, 'B': 0.0, 'max_z_F': 0.0, 'max_z_B': 0.0})
    for p in parts:
        e = d[p['block']]
        e['count'] += 1
        e[p['side']] += p['area']
        key = 'max_z_' + p['side']
        if p['z'] is not None:
            e[key] = max(e[key], p['z'])
    for e in d.values():
        e['F'] = round(e['F'], 1)
        e['B'] = round(e['B'], 1)
    return dict(sorted(d.items(), key=lambda kv: -(kv[1]['F'] + kv[1]['B'])))


ENVELOPES = {
    'current_245x165': dict(board_w=245, board_d=165, connector_faces=1, note='GDI6 candidate as of 2026-10-28; abandoned for compact redesign'),
    'pro8_like_190x88': dict(board_w=190, board_d=88, connector_faces=1, note='EMU PRO-8/16 depth (outer 95 mm); 4 x TE34 need 186 mm width'),
    'single_190x130': dict(board_w=190, board_d=130, connector_faces=1, note='outer about 197 x 137'),
    'single_190x150': dict(board_w=190, board_d=150, connector_faces=1, note='outer about 197 x 157'),
    'single_190x160': dict(board_w=190, board_d=160, connector_faces=1, note='outer about 197 x 167; study baseline'),
    'two_faces_100x180': dict(board_w=100, board_d=180, connector_faces=2, note='2 + 2 connectors on opposite faces'),
}

CONNECTOR_DEPTH = 37.5      # TE34 body depth on the board, from PCB_CONNECTORS.md plus margin
PIN_BAND_BACK = 12.0        # back-side band blocked by the four PTH pin rows and mounting holes
EDGE_KEEPOUT = 2.5          # component keepout from the outline (fastener and wall clearance, mm)


def evaluate(parts, env, density_targets=(0.40, 0.50, 0.60)):
    W, D = env['board_w'], env['board_d']
    faces = env['connector_faces']
    strip = CONNECTOR_DEPTH * faces
    front_avail = (W - 2 * EDGE_KEEPOUT) * (D - strip - EDGE_KEEPOUT * (2 - faces + 0))
    back_avail = (W - 2 * EDGE_KEEPOUT) * (D - PIN_BAND_BACK * faces - 2 * EDGE_KEEPOUT)
    dem = demand(parts)
    front_demand = sum(e['F'] for b, e in dem.items() if b != 'Connectors')
    back_demand = sum(e['B'] for e in dem.values())
    gdi_front = sum(e['F'] for b, e in dem.items() if b.startswith('GDI power stage'))
    out = dict(env, front_avail_mm2=round(front_avail), back_avail_mm2=round(back_avail),
               front_demand_mm2=round(front_demand), back_demand_mm2=round(back_demand),
               front_util=round(front_demand / front_avail, 3) if front_avail > 0 else None,
               back_util=round(back_demand / back_avail, 3) if back_avail > 0 else None,
               gdi_front_share_of_front_avail=round(gdi_front / front_avail, 3) if front_avail > 0 else None,
               connector_strip_fits=(4 * 46.5 <= W if faces == 1 else 2 * 46.5 <= W))
    verdicts = {}
    for t in density_targets:
        ok = out['front_util'] is not None and out['front_util'] <= t and out['back_util'] <= t and out['connector_strip_fits']
        verdicts[f'at_{int(t*100)}pct'] = 'fits' if ok else 'overfull'
    out['verdict'] = verdicts
    return out


def height_budget(parts, wall=3.0, clearance=1.0, pcb=1.6):
    front = [p for p in parts if p['side'] == 'F' and p['z'] is not None]
    back = [p for p in parts if p['side'] == 'B' and p['z'] is not None]
    unknown = sorted({p['lib_id'] for p in parts if not p['z_known'] and max(p['width'], p['height']) > 8})
    zf = max(front, key=lambda p: p['z'])
    zb = max(back, key=lambda p: p['z'])
    stack = wall + clearance + zb['z'] + pcb + zf['z'] + clearance + wall
    back_low = sorted({p['z'] for p in back}, reverse=True)
    low_alt = next((z for z in back_low if z <= 4.0), 4.0)
    stack_if_back_low = wall + clearance + low_alt + pcb + zf['z'] + clearance + wall
    return dict(front_max=dict(ref=zf['ref'], z=zf['z'], value=zf['value']),
                back_max=dict(ref=zb['ref'], z=zb['z'], value=zb['value']),
                back_tall_parts=[dict(ref=p['ref'], z=p['z'], value=p['value']) for p in back if p['z'] > 4.0],
                outer_height_mm=round(stack, 1), outer_height_if_back_le_4mm=round(stack_if_back_low, 1),
                assumptions=dict(wall_mm=wall, clearance_mm=clearance, pcb_mm=pcb),
                unknown_height_footprints=unknown)


def zone_plan(parts, plan: dict):
    """Check a hand-written zone plan: containment, overlap per side, utilization."""
    W, D = plan['board_w'], plan['board_d']
    dem = demand(parts)
    report = []
    by_side = defaultdict(list)
    for z in plan['zones']:
        x0, y0, x1, y1 = z['rect']
        inside = 0 <= x0 < x1 <= W and 0 <= y0 < y1 <= D
        area = (x1 - x0) * (y1 - y0)
        need = sum(dem.get(b, {}).get(z['side'], 0.0) for b in z['blocks'])
        util = need / area if area else None
        by_side[z['side']].append((z['name'], (x0, y0, x1, y1)))
        report.append(dict(name=z['name'], side=z['side'], rect=z['rect'], blocks=z['blocks'], area_mm2=round(area),
                           demand_mm2=round(need), utilization=round(util, 3) if util is not None else None,
                           inside_board=inside, target=plan['density_target'],
                           ok=inside and util is not None and util <= plan['density_target']))
    overlaps = []
    for side, zs in by_side.items():
        for i in range(len(zs)):
            for j in range(i + 1, len(zs)):
                a, b = zs[i][1], zs[j][1]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    overlaps.append((side, zs[i][0], zs[j][0]))
    covered = defaultdict(set)
    for z in plan['zones']:
        for b in z['blocks']:
            covered[z['side']].add(b)
    uncovered = [(b, s) for b, e in dem.items() for s in ('F', 'B') if e[s] > 0 and b not in covered[s] and b != 'Connectors']
    return dict(zones=report, overlaps=overlaps, uncovered_block_sides=uncovered,
                all_ok=not overlaps and not uncovered and all(r['ok'] for r in report))


def zones_svg(plan: dict, zone_report: dict, path: Path):
    W, D = plan['board_w'], plan['board_d']
    s = 4.0
    pad = 20
    width = int(2 * W * s + 3 * pad)
    height = int(D * s + 2 * pad + 30)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" font-family="monospace" font-size="11">',
           f'<rect width="{width}" height="{height}" fill="#fff"/>']
    for k, side in enumerate(('F', 'B')):
        ox = pad + k * (W * s + pad)
        oy = pad + 20
        out.append(f'<text x="{ox}" y="{pad + 10}">{"FRONT (top, tall parts)" if side == "F" else "BACK (SMD, viewed through board)"} {W}x{D} mm</text>')
        out.append(f'<rect x="{ox}" y="{oy}" width="{W * s}" height="{D * s}" fill="none" stroke="#000" stroke-width="2"/>')
        for c in plan['connectors']:
            x0, y0, x1, y1 = c['rect']
            fill = '#ddd' if side == 'F' else '#f3f3f3'
            out.append(f'<rect x="{ox + x0 * s}" y="{oy + y0 * s}" width="{(x1 - x0) * s}" height="{(y1 - y0) * s}" fill="{fill}" stroke="#555"/>')
            out.append(f'<text x="{ox + x0 * s + 4}" y="{oy + y1 * s - 6}">{c["name"]}</text>')
        for r in zone_report['zones']:
            if r['side'] != side:
                continue
            x0, y0, x1, y1 = r['rect']
            color = '#cfe8cf' if r['ok'] else '#f5c6c6'
            out.append(f'<rect x="{ox + x0 * s}" y="{oy + y0 * s}" width="{(x1 - x0) * s}" height="{(y1 - y0) * s}" fill="{color}" stroke="#333"/>')
            out.append(f'<text x="{ox + x0 * s + 4}" y="{oy + y0 * s + 14}">{r["name"]}</text>')
            out.append(f'<text x="{ox + x0 * s + 4}" y="{oy + y0 * s + 28}">{r["demand_mm2"]}/{r["area_mm2"]} mm2 = {int(round((r["utilization"] or 0) * 100))}%</text>')
    out.append('</svg>')
    path.write_text('\n'.join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pcb', default=str(HERE.parent / 'gdi6_candidate' / 'Power8GDI_Review.kicad_pcb'))
    ap.add_argument('--netlist', default=str(HERE.parents[1] / 'core.net'))
    ap.add_argument('--overrides', default=str(HERE / 'body_overrides.json'))
    ap.add_argument('--plan', default=str(HERE / 'floorplan_190x160.json'))
    ap.add_argument('--out', default=str(HERE / 'output'))
    args = ap.parse_args(argv)
    parts, board = load_parts(Path(args.pcb), Path(args.netlist), Path(args.overrides))
    dem = demand(parts)
    envs = {k: evaluate(parts, v) for k, v in ENVELOPES.items()}
    hb = height_budget(parts)
    plan = json.loads(Path(args.plan).read_text())
    zr = zone_plan(parts, plan)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    study = dict(source_pcb=args.pcb, source_outline=board['outline'], footprints_fitted=len(parts),
                 block_demand=dem, envelopes=envs, height_budget=hb, zone_plan=plan['name'], zone_report=zr,
                 warning='Bounding-box screening only; no routing, thermal, EMC or manufacturing claim.')
    (out / 'floorplan_study.json').write_text(json.dumps(study, indent=1) + '\n')
    (out / 'parts.json').write_text(json.dumps(parts, indent=0) + '\n')
    zones_svg(plan, zr, out / 'zones.svg')
    print(f"fitted footprints: {len(parts)}  source outline: {board['outline']}")
    print('\nblock demand (mm2, bounding boxes):')
    for b, e in dem.items():
        print(f"  {b:28} n={e['count']:4} F={e['F']:8.0f} B={e['B']:8.0f}  zF={e['max_z_F']:5.1f} zB={e['max_z_B']:5.1f}")
    print('\nenvelopes:')
    for k, e in envs.items():
        print(f"  {k:22} F {e['front_demand_mm2']:6}/{e['front_avail_mm2']:6} = {e['front_util']}, B {e['back_demand_mm2']:6}/{e['back_avail_mm2']:6} = {e['back_util']}  GDI/front={e['gdi_front_share_of_front_avail']}  {e['verdict']}")
    print(f"\nheight: front max {hb['front_max']}, back max {hb['back_max']} -> outer {hb['outer_height_mm']} mm; if back <= 4 mm: {hb['outer_height_if_back_le_4mm']} mm")
    print(f"  back parts above 4 mm: {[(p['ref'], p['z']) for p in hb['back_tall_parts']]}")
    print(f"  unknown heights: {hb['unknown_height_footprints']}")
    print(f"\nzone plan {plan['name']}: all_ok={zr['all_ok']} overlaps={zr['overlaps']} uncovered={zr['uncovered_block_sides']}")
    for r in zr['zones']:
        print(f"  {'OK ' if r['ok'] else 'BAD'} {r['side']} {r['name']:30} {r['demand_mm2']:6}/{r['area_mm2']:6} = {r['utilization']}")
    return 0 if zr['all_ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
