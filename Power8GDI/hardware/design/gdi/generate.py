"""Generate reference-derived GDI stage sheets; never a manufacturing release.

The retained source topology is independently checked against KiCad XML exports.
No device timing, current profile, active polarity or engine qualification is
inferred by this mechanical extraction. See GDI_SCHEMATIC_EVIDENCE.md.
"""
from pathlib import Path
from copy import deepcopy
import csv
import hashlib
import json
import re
import uuid
from sexpr import parse, dump, child, children, prop, walk, Quoted as Q

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SOURCE = ROOT / 'GDI-4ch/GDI-4ch.kicad_sch'
NS = uuid.UUID('c9f4fa06-20b4-494e-b20d-3e1eebff692d')
SHIFT_X, SHIFT_Y = 269.24, 109.22  # 1.27 mm grid multiples


def uid(name):
    return str(uuid.uuid5(NS, name))


def inside(xy):
    return 278 <= float(xy[1]) <= 590 and 133 <= float(xy[2]) <= 365


def choose(node):
    if node[0] == 'wire':
        return all(inside(p) for p in children(child(node, 'pts'), 'xy'))
    at = child(node, 'at')
    return at is not None and inside(at)


def label(name, x, y, angle=0, global_=False):
    typ = 'global_label' if global_ else 'label'
    data = [typ, Q(name)]
    if global_:
        data.append(['shape', 'bidirectional'])
    data.extend([['at', str(x), str(y), str(angle)], ['effects', ['font', ['size', '0.9', '0.9']], ['justify', 'left']], ['uuid', uid(f'{typ}:{name}:{x}:{y}')]])
    return data


def renamed(name, stage):
    name = name.lstrip('/')
    p = 'PT' + stage
    explicit = {'+3.3V': '+3V3', '+5V': '+5V_GDI_' + stage,
                '+BATT': 'VBAT_GDI_' + stage, 'GND': 'GND',
                'MOSI': 'GDI_SPI2_MOSI', 'MISO': 'GDI_SPI2_MISO', 'SCLK': 'GDI_SPI2_SCK',
                'CSB': p + '_CS', 'RESETB': p + '_RESET', 'FLAG_0': p + '_FLAG',
                'DRVEN': p + '_DEVICE_DRVEN', 'START6': 'HPFP1' if stage == 'A' else 'HPFP2',
                'VCC2P5': p + '_VCC1P5', 'Vdrive': p + '_VBOOST',
                'H2': p + '_H1', 'H4': p + '_H3', 'H5':p + '_H1', 'H6':p + '_H3'}
    if name in explicit:
        return explicit[name]
    if re.fullmatch('START[1-4]', name):
        return 'DI' + str(int(name[-1]) + (4 if stage == 'B' else 0))
    return p + '_' + name


def main():
    src = parse(SOURCE.read_text(encoding='utf-8'))
    selected = [s for s in children(src, 'symbol') if choose(s)]
    physical = [s for s in selected if not prop(s, 'Reference')[2].startswith('#')]
    by_ref = {str(prop(s, 'Reference')[2]): s for s in physical}
    refs = sorted(by_ref, key=lambda r: (re.sub(r'\d', '', r), int(re.search(r'\d+', r)[0])))
    source_libs = {s[1]: s for s in children(child(src, 'lib_symbols'), 'symbol')}
    regulator_template = next(s for s in children(src,'symbol') if prop(s,'Reference')[2]=='U3')
    source_names = sorted(set(child(s, 'lib_id')[1] for s in physical) | {child(regulator_template,'lib_id')[1]})
    mapping = {}
    bom = []
    for stage, base in [('A', 200), ('B', 300)]:
        counters = {}
        refmap = {}
        for ref in refs:
            prefix = re.sub(r'\d', '', ref).replace('S', 'TP')
            counters[prefix] = counters.get(prefix, base) + 1
            refmap[ref] = prefix + str(counters[prefix])
        sheetid = uid('stage_' + stage)
        project = 'stage_' + stage.lower()
        out = ['kicad_sch', ['version', '20250114'], ['generator', 'eeschema'], ['uuid', sheetid], ['paper', Q('A3')],
               ['title_block', ['title', Q('Power8GDI Stage ' + stage + ' - reference draft')],
                ['date', Q('2026-10-21')], ['rev', Q('engineering draft 0.1')],
                ['comment', '1', Q('Derived from rusEFI GDI4 rev.d; license unresolved; values not load-qualified')],
                ['comment', '2', Q('Hardware inhibit, microcode, load mapping and thermal design BLOCKED')]], ['lib_symbols']]
        libs = child(out, 'lib_symbols')
        lib_ids = {}
        for name in source_names:
            lib = deepcopy(source_libs[name])
            oldleaf = name.split(':')[-1]
            newleaf = 'MC33PT2001AE' if name == 'chips:MC33816' else name.replace(':', '_').replace('-', '_')
            lib_ids[name] = 'Power8GDI_GDI:' + newleaf
            lib[1] = Q(lib_ids[name])
            for sub in walk(lib):
                if sub[0] == 'symbol' and len(sub) > 1 and sub[1].startswith(oldleaf + '_'):
                    sub[1] = Q(sub[1].replace(oldleaf + '_', newleaf + '_', 1))
            if name == 'chips:MC33816':
                prop(lib, 'Value')[2] = Q('MC33PT2001AE')
                for sub in walk(lib):
                    if sub[0] != 'pin' or child(sub, 'number') is None:
                        continue
                    pin = int(child(sub, 'number')[1])
                    if pin in (17, 19, 21, 24, 39, 48, 65):
                        sub[1] = 'power_in'
                    elif pin in (20, 40):
                        sub[1] = 'power_out'
                    elif pin in (15, *range(41, 48), 50, 53, 56, 59, 62):
                        sub[1] = 'tri_state' if pin == 15 else 'output'
                    elif pin in (*range(4, 13), 18, 22, 23, 64):
                        sub[1] = 'bidirectional'
                    else:
                        sub[1] = 'input'
                    names = {3: 'RESETB', 13: 'CSB', 16: 'SCLK', 20: 'VCC1P5', 39: 'VBATT', 65: 'PGND'}
                    if pin in names:
                        child(sub, 'name')[1] = Q(names[pin])
            libs.append(lib)
        for item in src[1:]:
            if not isinstance(item, list) or item[0] not in ('symbol', 'wire', 'junction', 'label', 'no_connect') or not choose(item):
                continue
            node = deepcopy(item)
            if node[0] == 'symbol':
                ref = str(prop(node, 'Reference')[2])
                if ref.startswith('#'):
                    at = child(node, 'at')
                    out.append(label(renamed(prop(node, 'Value')[2], stage), round(float(at[1])-SHIFT_X, 4), round(float(at[2])-SHIFT_Y, 4), global_=True))
                    continue
                newref = refmap[ref]
                prop(node, 'Reference')[2] = Q(newref)
                child(node, 'lib_id')[1] = Q(lib_ids[child(node, 'lib_id')[1]])
                fpname = 'REF_' + ref
                prop(node, 'Footprint')[2] = Q('Power8GDI_GDI:' + fpname)
                if prop(node, 'Value')[2] == 'DNP':
                    if child(node, 'dnp'):
                        child(node, 'dnp')[1] = 'yes'
                    else:
                        node.append(['dnp', 'yes'])
                if ref=='U1':
                    node[:]=[v for v in node if not (isinstance(v,list) and v[0]=='property' and v[1]=='LCSC')]
                node[:] = [n for n in node if not (isinstance(n, list) and n[0] == 'instances')]
                node.append(['instances', ['project', Q(project), ['path', Q('/' + sheetid), ['reference', Q(newref)], ['unit', '1']]]])
                bom.append({'stage': stage, 'reference': newref, 'source_reference': ref, 'value': str(prop(node, 'Value')[2]),
                            'footprint': 'Power8GDI_GDI:' + fpname, 'source_footprint': str(prop(item, 'Footprint')[2]),
                            'qualification': 'REFERENCE_ONLY', 'population': 'DNP' if str(prop(node, 'Value')[2]) == 'DNP' else 'REVIEW_REQUIRED'})
            elif node[0] == 'label':
                node[1] = Q(renamed(node[1], stage))
                # Global names are the explicitly exposed wiring contract. Local
                # anonymous nets remain sheet-local, never accidentally shared.
                node[0] = 'global_label'
                node.insert(2, ['shape', 'bidirectional'])
                font=child(child(node,'effects'),'font')
                child(font,'size')[1:]=['0.75','0.75']
            for sub in walk(node):
                if sub[0] in ('at', 'xy') and len(sub) >= 3:
                    sub[1] = str(round(float(sub[1]) - SHIFT_X, 4))
                    sub[2] = str(round(float(sub[2]) - SHIFT_Y, 4))
                if sub[0] == 'uuid':
                    sub[1] = uid(stage + ':' + sub[1])
            out.append(node)
        # Deliberate unpopulated isolation boundary, not a complete safety gate.
        r = deepcopy(by_ref['R123'])
        oldat = child(r, 'at')
        dx, dy = 218.44-float(oldat[1]), 19.05-float(oldat[2])
        for sub in walk(r):
            if sub[0] == 'at':
                sub[1] = str(round(float(sub[1])+dx, 4)); sub[2] = str(round(float(sub[2])+dy, 4))
            if sub[0] == 'uuid':
                sub[1] = uid(stage + ':isolation:' + sub[1])
        ref = 'R' + str(base+99)
        prop(r, 'Reference')[2] = Q(ref)
        child(r, 'lib_id')[1] = Q(lib_ids[child(r, 'lib_id')[1]])
        prop(r, 'Value')[2] = Q('DNP_ENABLE_BOUNDARY')
        prop(r, 'Footprint')[2] = Q('Power8GDI_GDI:REF_R123')
        r[:] = [n for n in r if not (isinstance(n,list) and n[0] in ('instances','dnp'))]
        r.extend([['dnp','yes'],['instances',['project',Q(project),['path',Q('/'+sheetid),['reference',Q(ref)],['unit','1']]]]])
        out.append(r)
        out.extend([label('PT'+stage+'_DRVEN_GATED',218.44,15.24,global_=True),label('PT'+stage+'_DEVICE_DRVEN',218.44,22.86,global_=True)])
        out.append(['text',Q('R'+str(base+99)+' remains DNP pending PT electrical/shutdown qualification.\nHPFP START6 is wired; loaded microcode/mask still requires verification.\nHardware permission and protected battery input are on separate GDI sheets.'), ['at','15.24','17.78','0'], ['effects',['font',['size','1.1','1.1']],['justify','left']],['uuid',uid(stage+':note')]])
        # Independent provisional 5 V rail. NCV78M05AB pin mapping is verified
        # from onsemi MC78M00/D rev29; PT2001 current/thermal budget is UNKNOWN.
        candidates = [
            (regulator_template,'U'+str(base+49),'NCV78M05ABDTRKG',304.8,50.8,'REF_U3'),
            (by_ref['C17'],'C'+str(base+98),'330n 50V X7R',279.4,63.5,'REF_C17'),
            (by_ref['C17'],'C'+str(base+99),'100n 25V X7R',327.66,63.5,'REF_C17'),
            (by_ref['R123'],'R'+str(base+98),'910 1% minimum load',350.52,63.5,'REF_R123')]
        for template,newref,value,x,y,fp in candidates:
            part=deepcopy(template); at=child(part,'at');dx=x-float(at[1]);dy=y-float(at[2])
            for sub in walk(part):
                if sub[0]=='at':
                    sub[1]=str(round(float(sub[1])+dx,4));sub[2]=str(round(float(sub[2])+dy,4))
                if sub[0]=='uuid':sub[1]=uid(stage+':regulator:'+newref+':'+sub[1])
            prop(part,'Reference')[2]=Q(newref);prop(part,'Value')[2]=Q(value)
            prop(part,'Footprint')[2]=Q('Power8GDI_GDI:'+fp)
            # Remove inherited sourcing fields: candidate parts have no approved MPN for passives.
            part[:]=[n for n in part if not (isinstance(n,list) and (n[0]=='instances' or (n[0]=='property' and n[1]=='LCSC')))]
            child(part,'lib_id')[1]=Q(lib_ids[child(part,'lib_id')[1]])
            part.append(['instances',['project',Q(project),['path',Q('/'+sheetid),['reference',Q(newref)],['unit','1']]]])
            if newref.startswith('U'):
                prop(part,'Datasheet')[2]=Q('https://www.onsemi.com/pdf/datasheet/mc78m00-d.pdf')
                pins=[('VBAT_GDI_'+stage,x-7.62,y),('+5V_GDI_'+stage,x+7.62,y),('GND',x,y+7.62)]
            else:
                pins=[('VBAT_GDI_'+stage if newref=='C'+str(base+98) else '+5V_GDI_'+stage,x,y-3.81),('GND',x,y+3.81)]
            out.append(part)
            for name,lx,ly in pins:out.append(label(name,round(lx,4),round(ly,4),global_=True))
            bom.append({'stage':stage,'reference':newref,'source_reference':'NEW_REGULATOR_CANDIDATE', 'value':value,
                        'footprint':'Power8GDI_GDI:'+fp,'source_footprint':str(prop(template,'Footprint')[2]),'qualification':'THERMAL_CURRENT_BUDGET_UNKNOWN','population':'REVIEW_REQUIRED'})
        out.append(['text',Q('Independent 5V candidate: 7-20V regulation range; 35V ABS MAX is not a surge rating.\nPT2001 VCC5/VCCIO current UNKNOWN; 500mA requires adequate heatsinking.\nVBAT_GDI_'+stage+' comes from LM74800 protection sheet; external fuse and transient tests required.'),['at','266.7','83.82','0'],['effects',['font',['size','0.9','0.9']],['justify','left']],['uuid',uid(stage+':regulator-note')]])
        for part in children(out,'symbol'):
            inst=child(part,'instances')
            inst.append(['project',Q('Power8GDI_Core'),['path',Q('/f4d21065-0a5b-5086-a08e-1af9469f04bd/'+sheetid),['reference',Q(prop(part,'Reference')[2])],['unit','1']]])
        (HERE / (project + '.kicad_sch')).write_text(dump(out)+'\n',encoding='utf-8')
        mapping[stage] = {'sheet_uuid':sheetid,'reference_map':refmap,'isolation_reference':ref,'source_component_count':len(refmap)}
        bom.append({'stage':stage,'reference':ref,'source_reference':'NEW_ISOLATION_BOUNDARY','value':'DNP_ENABLE_BOUNDARY',
                    'footprint':'Power8GDI_GDI:REF_R123','source_footprint':'Resistor_SMD:R_0603_1608Metric','qualification':'MUST_REMAIN_DNP','population':'DNP'})
    library=['kicad_symbol_lib',['version','20241209'],['generator','kicad_symbol_editor']]
    for lib in libs[1:]:
        lib=deepcopy(lib);lib[1]=Q(lib[1].split(':')[-1]);library.append(lib)
    (HERE/'Power8GDI_GDI.kicad_sym').write_text(dump(library)+'\n',encoding='utf-8')
    for filename,typ,ext in [('sym-lib-table','KiCad','kicad_sym'),('fp-lib-table','KiCad','pretty')]:
        tag='sym_lib_table' if filename.startswith('sym') else 'fp_lib_table'
        (HERE/filename).write_text(f'({tag}\n (lib (name "Power8GDI_GDI")(type "{typ}")(uri "${{KIPRJMOD}}/Power8GDI_GDI.{ext}")(options "")(descr "Source-derived GDI4 rev.d; release blocked"))\n)\n')
    (HERE/'reference_mapping.json').write_text(json.dumps(mapping,indent=2)+'\n',encoding='utf-8')
    with (HERE/'bom_reference.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(bom[0]));writer.writeheader();writer.writerows(bom)
    print('Generated 2 stages,',len(refs),'source components + 5 new components each; release BLOCKED.')


if __name__ == '__main__':
    main()
