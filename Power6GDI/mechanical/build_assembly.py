"""Reproducible concept CAD, not a manufacturer-matched or approved assembly.

Import constructs no geometry and performs no filesystem writes. The source of
all dimensions is assembly_manifest.json; exports belong in a build directory.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE_MANIFEST = HERE / 'assembly_manifest.json'
DEFAULT_OUTPUT = HERE / 'build' / 'assembly'
STEP_NAMES = {'Base': 'Power8GDI_Base_PRELIM.step', 'Lid': 'Power8GDI_Lid_PRELIM.step',
              'PCB': 'Power8GDI_PCB_ENVELOPE.step'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_manifest(path=SOURCE_MANIFEST):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    validate_parameters(config)
    return config


def validate_parameters(config):
    p = config['parameters']
    if config['units'] != 'mm' or p['concept_only'] is not True:
        raise ValueError('Only explicit millimetre concept geometry is supported')
    if config['status'] != 'PRELIMINARY_CLEARANCE_ENVELOPE_ONLY':
        raise ValueError('Concept status must be retained')
    for key, value in p.items():
        if key in ('concept_only', 'connector_x'):
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'Invalid numeric parameter: {key}')
        if key != 'connector_y' and value <= 0:
            raise ValueError(f'Positive dimension required: {key}')
    if len(p['connector_x']) != 4 or not all(math.isfinite(x) for x in p['connector_x']):
        raise ValueError('Exactly four finite connector centres required')
    if p['floor'] >= p['pcb_bottom_z'] or p['pcb_bottom_z'] + p['pcb_thickness'] >= p['base_z']:
        raise ValueError('PCB must sit above the floor and below the lid')
    if p['wall'] * 2 >= min(p['housing_x'], p['housing_y']):
        raise ValueError('Housing walls leave no interior')
    for axis in ('x', 'y'):
        if p[f'pcb_{axis}'] > p[f'housing_{axis}'] - 2 * p['wall']:
            raise ValueError(f'PCB does not fit housing on {axis}')
    if not config['pcb_mounts'] or len({tuple(point) for point in config['pcb_mounts']}) != len(config['pcb_mounts']):
        raise ValueError('Unique PCB mount coordinates required')
    for x, y in config['pcb_mounts']:
        if abs(x) + p['pcb_standoff_radius'] >= p['pcb_x'] / 2 or abs(y) + p['pcb_standoff_radius'] >= p['pcb_y'] / 2:
            raise ValueError('PCB support exceeds board envelope')
    for name, part in config['component_envelopes'].items():
        if len(part) != 5 or not all(math.isfinite(v) for v in part) or min(part[:3]) <= 0:
            raise ValueError(f'Invalid component envelope: {name}')
        width, depth, height, x, y = part
        if abs(x) + width / 2 > p['pcb_x'] / 2 or abs(y) + depth / 2 > p['pcb_y'] / 2:
            raise ValueError(f'Component exceeds board footprint: {name}')
        if p['pcb_bottom_z'] + p['pcb_thickness'] + height >= p['base_z']:
            raise ValueError(f'Component reaches lid: {name}')
    if p['connector_bottom_z'] <= p['pcb_bottom_z'] + p['pcb_thickness']:
        raise ValueError('Connector body intersects board envelope')
    if p['connector_bottom_z'] + p['connector_height'] >= p['base_z']:
        raise ValueError('Connector reaches lid')


def build_shapes(config):
    """Return independent CadQuery shapes without exporting them."""
    import cadquery as cq
    validate_parameters(config)
    p = config['parameters']
    epsilon = p['boolean_overlap']

    def box(x, y, z, xyz):
        return cq.Workplane('XY').box(x, y, z, centered=(True, True, False)).translate(xyz)

    def cylinder(radius, height, x, y, z):
        return cq.Workplane('XY').circle(radius).extrude(height).translate((x, y, z))

    base = box(p['housing_x'], p['housing_y'], p['base_z'], (0, 0, 0))
    base = base.cut(box(p['housing_x'] - 2 * p['wall'], p['housing_y'] - 2 * p['wall'],
                        p['base_z'] - p['floor'] + epsilon, (0, 0, p['floor'])))
    screw_centres = list(itertools.product((-p['screw_x'], p['screw_x']), (-p['screw_y'], p['screw_y'])))
    for x, y in screw_centres:
        base = base.union(cylinder(p['perimeter_boss_radius'], p['base_z'] - p['floor'], x, y, p['floor']))
        base = base.cut(cylinder(p['pilot_radius'], p['base_z'] - p['base_pilot_bottom_z'] + epsilon,
                                 x, y, p['base_pilot_bottom_z']))
    for x, y in config['pcb_mounts']:
        base = base.union(cylinder(p['pcb_standoff_radius'], p['pcb_bottom_z'] - p['floor'], x, y, p['floor']))
        base = base.cut(cylinder(p['pilot_radius'], p['pcb_bottom_z'] - p['floor'] + epsilon, x, y, p['floor']))
    clearance = p['connector_opening_clearance']
    for x in p['connector_x']:
        base = base.cut(box(p['connector_width'] + clearance, p['wall'] + 2 * epsilon,
                            p['connector_height'] + clearance,
                            (x, -p['housing_y'] / 2 + p['wall'] / 2, p['connector_bottom_z'] - clearance / 2)))
    lid = box(p['housing_x'], p['housing_y'], p['lid_z'], (0, 0, p['base_z']))
    for x, y in screw_centres:
        lid = lid.cut(cylinder(p['m3_clearance'] / 2, p['lid_z'] + 2 * epsilon, x, y, p['base_z'] - epsilon))
    pcb = box(p['pcb_x'], p['pcb_y'], p['pcb_thickness'], (0, 0, p['pcb_bottom_z']))
    for x, y in config['pcb_mounts']:
        pcb = pcb.cut(cylinder(p['pcb_hole_diameter'] / 2, p['pcb_thickness'] + 2 * epsilon,
                               x, y, p['pcb_bottom_z'] - epsilon))
    parts = {name: box(width, depth, height, (x, y, p['pcb_bottom_z'] + p['pcb_thickness']))
             for name, (width, depth, height, x, y) in config['component_envelopes'].items()}
    connectors = {}
    face = config['connector_face_cavities']
    for index, x in enumerate(p['connector_x']):
        connector = box(p['connector_width'], p['connector_depth'], p['connector_height'],
                        (x, p['connector_y'], p['connector_bottom_z']))
        for row in range(face['rows']):
            for column in range(face['columns']):
                connector = connector.cut(box(face['width'], face['depth'], face['height'],
                    (x + (column - (face['columns'] - 1) / 2) * face['pitch_x'],
                     p['connector_y'] - p['connector_depth'] / 2 + face['front_offset_y'],
                     p['connector_bottom_z'] + face['offset_z'] + row * face['pitch_z'])))
        connectors[f'J_{"ABCD"[index]}_34PIN_ENVELOPE'] = connector
    shapes = {name: shape.val() for name, shape in {'Base': base, 'Lid': lid, 'PCB': pcb, **parts, **connectors}.items()}
    if set(shapes) != set(config['solids']):
        raise ValueError('Manifest solid inventory does not match generated geometry')
    return shapes


def bounds(shape):
    box = shape.BoundingBox()
    return {name: getattr(box, name) for name in ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax')}


def validate_geometry(shapes, config):
    """Check solids and positive-volume clashes, not engineering tolerances."""
    report = {'status': 'PASS_CONCEPT_GEOMETRY_ONLY', 'parts': {}, 'collision_pairs': []}
    tolerance = config['validation']['volume_tolerance_mm3']
    for name, shape in shapes.items():
        volume = shape.Volume()
        if not shape.isValid() or len(shape.Solids()) != 1 or not math.isfinite(volume) or volume <= 0:
            raise ValueError(f'Invalid or disconnected solid: {name}')
        report['parts'][name] = {'volume_mm3': volume, 'bounds_mm': bounds(shape), 'solid_count': 1}
    for (name_a, shape_a), (name_b, shape_b) in itertools.combinations(shapes.items(), 2):
        a = report['parts'][name_a]['bounds_mm']
        b = report['parts'][name_b]['bounds_mm']
        if any(min(a[f'{axis}max'], b[f'{axis}max']) - max(a[f'{axis}min'], b[f'{axis}min']) <= 1e-7 for axis in 'xyz'):
            continue
        overlap = shape_a.intersect(shape_b).Volume()
        if overlap > tolerance:
            report['collision_pairs'].append({'parts': [name_a, name_b], 'volume_mm3': overlap})
    if report['collision_pairs']:
        raise ValueError('Concept solid collisions: ' + json.dumps(report['collision_pairs']))
    p = config['parameters']
    report['clearances_mm'] = {
        'pcb_to_inner_wall_x': (p['housing_x'] - 2 * p['wall'] - p['pcb_x']) / 2,
        'pcb_to_inner_wall_y': (p['housing_y'] - 2 * p['wall'] - p['pcb_y']) / 2,
        'tallest_component_to_lid': p['base_z'] - max(report['parts'][name]['bounds_mm']['zmax'] for name in config['component_envelopes']),
        'connector_to_lid': p['base_z'] - (p['connector_bottom_z'] + p['connector_height']),
        'connector_body_to_board': p['connector_bottom_z'] - p['pcb_bottom_z'] - p['pcb_thickness'],
    }
    return report


def generate(output_dir=DEFAULT_OUTPUT, manifest_path=SOURCE_MANIFEST):
    import cadquery as cq
    manifest_path = Path(manifest_path).resolve()
    output = Path(output_dir).resolve()
    if output == HERE:
        raise ValueError('Use a build/output directory; source directory is not an export target')
    config = load_manifest(manifest_path)
    shapes = build_shapes(config)
    validation = validate_geometry(shapes, config)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.power8gdi-cad-', dir=output.parent) as temporary:
        staging = Path(temporary)
        (staging / 'stl').mkdir()
        for name, shape in shapes.items():
            cq.exporters.export(shape, str(staging / 'stl' / f'{name}.stl'),
                                tolerance=config['export']['stl_tolerance_mm'],
                                angularTolerance=config['export']['stl_angular_tolerance_rad'])
        for name, filename in STEP_NAMES.items():
            cq.exporters.export(shapes[name], str(staging / filename))
        connectors = cq.Compound.makeCompound([shape for name, shape in shapes.items() if name.startswith('J_')])
        assembly = cq.Compound.makeCompound(list(shapes.values()))
        cq.exporters.export(connectors, str(staging / 'Power8GDI_Connectors_ENVELOPE.step'))
        cq.exporters.export(assembly, str(staging / 'Power8GDI_Assembly_PRELIM.step'))
        generated = dict(config)
        generated['generation'] = {'source_manifest_sha256': sha256(manifest_path),
                                   'generator_sha256': sha256(__file__), 'cadquery_version': cq.__version__}
        generated['geometry_validation'] = validation
        generated['exports'] = {path.relative_to(staging).as_posix(): {'sha256': sha256(path), 'bytes': path.stat().st_size}
                                for path in sorted(staging.rglob('*')) if path.is_file()}
        (staging / 'assembly_manifest.json').write_text(json.dumps(generated, indent=2) + '\n', encoding='utf-8')
        output.mkdir(parents=True, exist_ok=True)
        (output / 'stl').mkdir(exist_ok=True)
        for relative in generated['exports']:
            os.replace(staging / relative, output / relative)
        os.replace(staging / 'assembly_manifest.json', output / 'assembly_manifest.json')
    return generated


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--manifest', type=Path, default=SOURCE_MANIFEST)
    args = parser.parse_args(argv)
    generated = generate(args.output_dir, args.manifest)
    print(f'PASS: {len(generated["solids"])} concept solids, {len(generated["exports"])} exports -> {args.output_dir.resolve()}')
    print('Concept only; manufacturer CAD, actual PCB fit and hardware validation remain pending.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
