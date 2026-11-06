"""Original dual GDI input protection and hardware permission gates.

Manufacturer pin definitions are recorded in protection_sources.json. This is
an engineering schematic, not a claim of automotive pulse or load qualification.
"""
from pathlib import Path
import csv
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from core_schlib import Sheet, box_symbol, uid, parse, children, child, dump

ROOT_UUID = uid('Power8GDI_Core')
LIB = 'Power8GDI_GDIProtection'
FP = {
    'controller': 'Power8GDI_GDIProtection:LM74800_DRR0012E',
    'fet': 'Package_TO_SOT_SMD:TO-252-2',
    'gate': 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm',
    'R': 'Resistor_SMD:R_0603_1608Metric',
    'C': 'Capacitor_SMD:C_0805_2012Metric',
    'TVS': 'Diode_SMD:D_SMC',
}


def ic(name, left, right, footprint):
    count = max(len(left), len(right))
    pins = []
    for values, x, angle in [(left, -20.32, 0), (right, 20.32, 180)]:
        for i, (number, label, kind) in enumerate(values):
            pins.append((str(number), label, kind, x, (count - 1) * 2.54 - i * 5.08, angle))
    return box_symbol(name, pins, footprint, width=35.56, height=(count + 1) * 5.08)


def passive(name, fp, prefix):
    return box_symbol(name, [('1', '1', 'passive', -5.08, 0, 0),
                             ('2', '2', 'passive', 5.08, 0, 180)],
                      fp, width=5.08, height=2.54, prefix=prefix)


def main():
    fpdir = HERE / (LIB + '.pretty')
    fpdir.mkdir(exist_ok=True)
    footprint = ['(footprint "LM74800_DRR0012E" (version 20241229) (generator "pcbnew") (layer "F.Cu")',
        '(descr "TI DRR0012E, drawing4224874/C11/2023; floating1.3x2.5mm EP; no thermal vias")',
        '(attr smd)',
        '(fp_text reference "REF**" (at 0 -2.4) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        '(fp_text value "LM74800QDRRRQ1" (at 0 2.4) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
        '(fp_rect (start -1.5 -1.5) (end 1.5 1.5) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
        '(fp_rect (start -1.95 -1.75) (end 1.95 1.75) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
        '(fp_line (start -1.1 -1.65) (end 1.1 -1.65) (stroke (width 0.12) (type default)) (layer "F.SilkS"))',
        '(fp_line (start -1.1 1.65) (end 1.1 1.65) (stroke (width 0.12) (type default)) (layer "F.SilkS"))',
        '(fp_circle (center -1.75 -1.7) (end -1.65 -1.7) (stroke (width 0.1) (type default)) (fill solid) (layer "F.SilkS"))']
    for pin in range(1,13):
        x = -1.39 if pin <= 6 else 1.39
        y = -1.25+(pin-1)*.5 if pin <= 6 else 1.25-(pin-7)*.5
        footprint.append(f'(pad "{pin}" smd roundrect (at {x} {y}) (size 0.62 0.25) (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))')
    footprint.append('(pad "13" smd rect (at 0 0) (size 1.3 2.5) (layers "F.Cu" "F.Mask"))')
    for y in (-.64,.64):
        footprint.append(f'(pad "" smd rect (at 0 {y}) (size 1.15 1.06) (layers "F.Paste"))')
    footprint.append(')')
    (fpdir/'LM74800_DRR0012E.kicad_mod').write_text('\n'.join(footprint)+'\n')
    symbols = {}
    sheets = []
    parts = []
    controller = ic('LM74800QDRRRQ1',
        [(1, 'DGATE', 'output'), (2, 'A', 'input'), (3, 'VSNS', 'input'),
         (4, 'SW', 'passive'), (5, 'OV', 'input'), (6, 'EN/UVLO', 'input')],
        [(12, 'C', 'input'), (11, 'CAP', 'output'), (10, 'VS', 'power_in'),
         (9, 'OUT', 'input'), (8, 'HGATE', 'output'), (7, 'GND', 'power_in'),
         (13, 'EP_FLOAT', 'no_connect')], FP['controller'])
    fet = ic('IPD90N10S4_06', [(1, 'G', 'input')],
             [(2, 'D_TAB', 'passive'), (3, 'S', 'passive')], FP['fet'])
    r, c, tvs = (passive('GDI_PROT_R', FP['R'], 'R'),
                 passive('GDI_PROT_C', FP['C'], 'C'),
                 passive('GDI_PROT_TVS_BIDIR', FP['TVS'], 'D'))

    def finish(s):
        # Short custom symbols need fields above/below their body rather than
        # the helper's right-aligned default, which collides with net labels.
        for index, item in enumerate(s.items):
            if not item.startswith('(symbol '):
                continue
            expr = parse(item)
            at = child(expr, 'at'); x, y = float(at[1]), float(at[2])
            sym = s.symbols[str(child(expr, 'lib_id')[1]).split(':')[-1]]
            offset = max(abs(p['y']) for p in sym.pins.values()) + 7.62
            for prop in children(expr, 'property'):
                if prop[1] not in ('Reference', 'Value'):
                    continue
                child(prop, 'at')[1:3] = [str(x), str(y + (offset if prop[1]=='Value' else -offset))]
                effects = child(prop, 'effects')
                effects[:] = [v for v in effects if not (isinstance(v, list) and v[0]=='justify')]
            s.items[index] = dump(expr)
        s.write(HERE.parent)
        path = HERE.parent / (s.name + '.kicad_sch')
        text = path.read_text(encoding='utf-8').replace('Power8GDI_Core:', LIB + ':')
        for p in s.parts:
            old = f'(project "Power8GDI_Core" (path "/{ROOT_UUID}/{s.sheet_id}" (reference "{p["ref"]}") (unit 1)))'
            extra = f'(project "{Path(s.name).name}" (path "/{s.uuid}" (reference "{p["ref"]}") (unit 1)))'
            text = text.replace(old, old + ' ' + extra)
        path.write_text(text, encoding='utf-8', newline='\n')
        path.with_suffix('.kicad_pro').write_text('{}\n')
        sheets.append({'name': s.name, 'sheet_uuid': s.uuid,
                       'root_instance_uuid': s.sheet_id, 'parts': len(s.parts)})
        parts.extend(s.parts)
        symbols.update(s.symbols)

    for stage, base in [('A', 5000), ('B', 5050)]:
        s = Sheet('gdi/protection_' + stage.lower(),
                  f'GDI bank {stage}: protected battery feed', root=ROOT_UUID, paper='A2')
        s.text(f'GDI {stage} INPUT: separate externally fused battery feed', 20, 15, 2)
        s.text('Common-drain MOSFETs: input is Q1 SOURCE, midpoint joins DRAINS, output is Q2 SOURCE.', 20, 24)
        s.text('LM74800 exposed pad MUST FLOAT. Keep copper under pad isolated; do not use GND thermal vias.', 20, 31)
        p = 'GDI_' + stage + '_'
        raw, mid, rail = 'VBAT_GDI_' + stage + '_FUSED', p + 'MID', 'VBAT_GDI_' + stage
        dg, hg = p + 'DGATE', p + 'HGATE'
        cap, ov, sw, en = p + 'CAP', p + 'OV', p + 'SW', p + 'POWER_EN'
        def put(sym, prefix, offset, value, x, y, nets, note='', footprint=None):
            s.component(sym, prefix + str(base + offset), value, x, y,
                        {str(k): v for k, v in nets.items()}, note=note, footprint=footprint)
        put(fet, 'Q', 1, 'IPD90N10S4-06', 85, 75, {1: dg, 2: mid, 3: raw},
            'Input blocking FET. Source=input; drain/tab=common-drain midpoint. 100V, +/-20V VGS.')
        put(fet, 'Q', 2, 'IPD90N10S4-06', 365, 75, {1: hg, 2: mid, 3: rail},
            'Output disconnect FET. Source=protected output; drain/tab=midpoint. Hot SOA remains a gate.')
        put(controller, 'U', 1, 'LM74800QDRRRQ1', 225, 150,
            {1: dg, 2: raw, 3: raw, 4: sw, 5: ov, 6: en,
             7: 'GND', 8: hg, 9: rail, 10: mid, 11: cap, 12: mid, 13: None},
            'TI SNOSD95C table6-1: exposed thermal pad floating, not GND. Common-drain topology.')
        put(tvs, 'D', 1, 'SMCJ33CA', 85, 155, {1: raw, 2: 'GND'},
            'Bidirectional TVS candidate. Surge energy/hot clamp/fuse coordination must be qualified.')
        put(c, 'C', 1, '100n 100V X7R', 365, 155, {1: mid, 2: 'GND'},
            'Place adjacent to VS/GND pins.')
        # Per-bank explicit pull-downs ensure an unpowered/tri-stated source does
        # not leave the controller enable or external MOSFET gates floating.
        values = [
            (r, 'R', 1, '140k 0.1%', sw, ov, 'OV upper divider; use >=75V rated 0805', 'Resistor_SMD:R_0805_2012Metric'),
            (r, 'R', 2, '10k 0.1%', ov, 'GND', 'OV nominal18.465V; conservative static bound17.864..19.075V including R(SW),200nA bias and divider tolerance', None),
            (r, 'R', 3, '1k 1%', 'HW_ACTUATOR_ENABLE', en, 'Hardware latch powers bank for configuration before per-bank DRVEN request', None),
            (r, 'R', 4, '10k 1%', en, 'GND', 'Default off; external enable low must meet <=0.3V shutdown requirement', None),
            (r, 'R', 5, '1M 1%', dg, raw, 'DGATE-source fallback; ~13uA when on', None),
            (r, 'R', 6, '1M 1%', hg, rail, 'HGATE-source fallback; adds load to55uA nominal source', None),
            (c, 'C', 2, '100n 25V X7R', cap, mid, 'Required charge-pump capacitor CAP-to-VS, never CAP-to-GND', None),
            (c, 'C', 3, '100n 100V X7R', raw, 'GND', 'Input bypass at protection entry', None),
            (c, 'C', 4, '100n 50V X7R', rail, 'GND', 'Protected output bypass; existing GDI bulk retained', None),
            (r, 'R', 7, '1k 1%', hg, p + 'SLEW', 'TI figure9-3 series resistor improves HGATE turnoff', None),
            (c, 'C', 5, '22n 100V X7R', p + 'SLEW', 'GND', 'Soft-start candidate: ramp and hot MOSFET SOA must use actual downstream capacitance', None),
            (r, 'R', 8, '10k 1%', rail, 'GND', 'Input-bulk bleed; does not discharge boosted rail or guarantee safe touch', None),
        ]
        for index, (sym, prefix, offset, value, a, b, note, fp) in enumerate(values):
            put(sym, prefix, offset, value, 80 + (index % 4) * 135,
                235 + (index // 4) * 38, {1: a, 2: b}, note, fp)
        s.text('OV disconnect protects the 5V regulator normal input envelope; dynamic overshoot has NOT been measured.', 20, 355)
        s.text('External fuse is REQUIRED; this controller has no precision overcurrent limit. Fuse rating depends on load and harness.', 20, 363)
        s.text('Power removal does not instantly remove stored boost energy. DRVEN hardware inhibit remains a separate path.', 20, 371)
        s.text('Startup: hold DI/HPFP commands and DRVEN low; ARM bank power; wait for rails; reset/program/verify PT; then permit DRVEN.', 20, 379)
        finish(s)

    s = Sheet('gdi/permission', 'Independent GDI permissions and default-off outputs', root=ROOT_UUID)
    s.text('HARDWARE PERMISSION: stage request AND latched actuator enable', 20, 15, 2)
    s.text('No extra MCU GPIOs. R299/R399 isolation links retain their explicit qualification hold.', 20, 24)
    gate = ic('SN74LVC2G08QDCURQ1', [(1, '1A', 'input'), (2, '1B', 'input'),
              (5, '2A', 'input'), (6, '2B', 'input')],
              [(7, '1Y', 'output'), (3, '2Y', 'output'), (8, 'VCC', 'power_in'), (4, 'GND', 'power_in')], FP['gate'])
    s.component(gate, 'U5101', gate.name, 200, 85,
        {'1':'PTA_DRVEN', '2':'HW_ACTUATOR_ENABLE', '7':'PTA_DRVEN_GATED',
         '5':'PTB_DRVEN', '6':'HW_ACTUATOR_ENABLE', '3':'PTB_DRVEN_GATED', '8':'+3V3','4':'GND'},
        note='TI DCU8 pin table; Ioff when VCC=0. Gate output low unless both inputs high.')
    passives = [('R5101','10k 1%','PTA_DRVEN','GND'), ('R5102','10k 1%','PTB_DRVEN','GND'),
        ('R5103','10k 1%','PTA_DRVEN_GATED','GND'), ('R5104','10k 1%','PTB_DRVEN_GATED','GND'),
        ('R5105','10k 1%','PTA_DEVICE_DRVEN','GND'), ('R5106','10k 1%','PTB_DEVICE_DRVEN','GND'),
        ('C5101','100n 25V X7R','+3V3','GND')]
    for i,(ref,value,a,b) in enumerate(passives):
        s.component(r if ref[0]=='R' else c, ref, value, 75 + (i % 3)*130,
                    145 + (i // 3)*35, {'1':a, '2':b})
    s.text('Gate never interprets FLAG0 as a fault without its programmed meaning. Per-bank CS, RESET and DRVEN stay distinct.',20,245)
    s.text('This sheet implements logic gating; PT electrical thresholds, power sequencing and pump shutdown configuration still need validation.',20,253)
    finish(s)
    library='(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor")\n' + '\n'.join(
        x.body.replace('Power8GDI_Core:', '') for x in symbols.values()) + '\n)\n'
    (HERE / (LIB + '.kicad_sym')).write_text(library, encoding='utf-8', newline='\n')
    table = HERE / 'sym-lib-table'
    original = table.read_text()
    if f'(name "{LIB}")' not in original:
        table.write_text(original.rstrip()[:-1] + f'\n (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.kicad_sym")(options "")(descr "GDI protection and gating")))\n')
    table = HERE / 'fp-lib-table'
    original = table.read_text()
    if f'(name "{LIB}")' not in original:
        table.write_text(original.rstrip()[:-1] + f'\n (lib (name "{LIB}")(type "KiCad")(uri "${{KIPRJMOD}}/{LIB}.pretty")(options "")(descr "TI DRR0012E land pattern")))\n')
    manifest = {'schema_version':1, 'root_uuid':ROOT_UUID, 'sheets':sheets, 'parts':parts,
        'ov_rising_v': {'nominal':1.231*15, 'min_static':1.195*(1+140000*.999/(10000*1.001))-.0000002*(140000*1.001+46),
                        'max_static':1.267*(1+(140000*1.001+46)/(10000*.999))+.0000002*(140000*1.001+46)},
        'inputs':['VBAT_GDI_A_FUSED','VBAT_GDI_B_FUSED','HW_ACTUATOR_ENABLE','PTA_DRVEN','PTB_DRVEN','+3V3','GND'],
        'outputs':['VBAT_GDI_A','VBAT_GDI_B','PTA_DRVEN_GATED','PTB_DRVEN_GATED'],
        'release_status':'BLOCKED_LOAD_AND_TRANSIENT_VALIDATION', 'hardware_tested':False,
        'unresolved':['Exact injector/pump profiles, energy, simultaneous scheduling and MCU microcode image',
                      'PT DRVEN electrical thresholds and complete configured shutdown path',
                      'Hot MOSFET SOA during startup and repeated OV recovery; fuse/TVS coordination',
                      'Measured protected-rail overshoot, ramp, partial-power/backfeed and thermal behavior']}
    (HERE / 'protection_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    with (HERE / 'protection_bom.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=['ref','value','footprint','dnp','note'])
        writer.writeheader(); writer.writerows({k:p[k] for k in writer.fieldnames} for p in parts)
    print(f'Generated {len(sheets)} connected GDI protection/gate sheets, {len(parts)} components.')


if __name__ == '__main__':
    main()
