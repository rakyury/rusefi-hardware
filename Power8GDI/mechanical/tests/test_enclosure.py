"""Fresh-export checks for concept CAD, never an IP/thermal/production signoff."""
from copy import deepcopy
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_assembly as builder

M = builder.load_manifest()
P = M['parameters']


class SourceContract(unittest.TestCase):
    def test_dimensions_and_connector_spacing(self):
        self.assertGreater(P['housing_x'], P['pcb_x'])
        self.assertGreater(P['housing_y'], P['pcb_y'])
        self.assertEqual(P['pcb_thickness'], 1.6)
        self.assertEqual(len(P['connector_x']), 4)
        for a, b in zip(sorted(P['connector_x']), sorted(P['connector_x'])[1:]):
            self.assertGreaterEqual(b-a, P['connector_width'] + 4)
        self.assertLessEqual(max(abs(x) for x in P['connector_x']) + P['connector_width']/2,
                             P['housing_x']/2 - P['wall'])

    def test_board_and_components_fit_parameter_envelope(self):
        builder.validate_parameters(M)
        for axis in 'xy':
            self.assertLessEqual(P[f'pcb_{axis}'], P[f'housing_{axis}'] - 2 * P['wall'])
        for _, _, height, _, _ in M['component_envelopes'].values():
            self.assertLess(P['pcb_bottom_z'] + P['pcb_thickness'] + height, P['base_z'])

    def test_status_explicit(self):
        self.assertEqual(M['status'], 'PRELIMINARY_CLEARANCE_ENVELOPE_ONLY')
        self.assertTrue(P['concept_only'])
        self.assertIn('NOT manufacturer STEP', M['warning'])

    def test_invalid_parameters_fail_before_export(self):
        for key, value in [('wall', float('nan')), ('pcb_x', 300), ('pcb_bottom_z', 1),
                           ('connector_height', 80), ('concept_only', False)]:
            with self.subTest(key=key):
                config = deepcopy(M)
                config['parameters'][key] = value
                with self.assertRaises(ValueError):
                    builder.validate_parameters(config)

    def test_generator_import_has_no_cad_or_filesystem_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            # No source manifest is copied: import must not even read it.
            modules = ['build_assembly.py', 'generate_enclosure.py', 'render_views.py']
            for name in modules:
                (target / name).write_bytes((ROOT / name).read_bytes())
            script = ('import runpy, sys; runpy.run_path(sys.argv[1]); '
                      'assert not {"cadquery", "vtk", "PIL"}.intersection(sys.modules)')
            for name in modules:
                with self.subTest(module=name):
                    result = subprocess.run([sys.executable, '-c', script, str(target / name)], cwd=target,
                                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                                            capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({path.name for path in target.iterdir()}, set(modules))

    def test_missing_generated_assets_are_failure_not_skip(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = dict(os.environ, POWER8GDI_CAD_OUTPUT=directory)
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                     'GeneratedAssemblyContract.test_cad_exports_exist'],
                                    env=environment, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Generate current CAD assets first', result.stderr)
            self.assertNotIn('skipped', result.stderr)


class GeneratedAssemblyContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.output = Path(os.environ.get('POWER8GDI_CAD_OUTPUT', str(builder.DEFAULT_OUTPUT))).resolve()
        manifest_path = cls.output / 'assembly_manifest.json'
        if not manifest_path.is_file():
            raise AssertionError('Generate current CAD assets first: python Power8GDI/mechanical/build_assembly.py '
                                 f'--output-dir "{cls.output}"')
        cls.generated = json.loads(manifest_path.read_text(encoding='utf-8'))
        # Missing dependency is deliberately an error; never a passing skip.
        import cadquery as cq
        cls.cq = cq
        cls.assembly = cq.importers.importStep(str(cls.output / 'Power8GDI_Assembly_PRELIM.step')).val()
        cls.solids = cls.assembly.Solids()
        cls.parts = {name: cq.importers.importStep(str(cls.output / filename)).val()
                     for name, filename in builder.STEP_NAMES.items()}

    def test_current_source_provenance(self):
        generation = self.generated['generation']
        self.assertEqual(generation['source_manifest_sha256'], builder.sha256(builder.SOURCE_MANIFEST))
        self.assertEqual(generation['generator_sha256'], builder.sha256(ROOT / 'build_assembly.py'))
        self.assertEqual(generation['cadquery_version'], self.cq.__version__)
        self.assertEqual(self.generated['parameters'], P)
        self.assertEqual(self.generated['pcb_mounts'], M['pcb_mounts'])
        self.assertEqual(self.generated['component_envelopes'], M['component_envelopes'])

    def test_cad_exports_exist(self):
        expected = set(builder.STEP_NAMES.values()) | {'Power8GDI_Assembly_PRELIM.step',
                    'Power8GDI_Connectors_ENVELOPE.step'} | {f'stl/{name}.stl' for name in M['solids']}
        self.assertEqual(set(self.generated['exports']), expected)
        for filename, metadata in self.generated['exports'].items():
            with self.subTest(filename=filename):
                target = self.output / filename
                self.assertTrue(target.is_file())
                self.assertGreater(target.stat().st_size, 100)
                self.assertEqual(target.stat().st_size, metadata['bytes'])
                self.assertEqual(builder.sha256(target), metadata['sha256'])

    def test_step_roundtrip_has_valid_positive_volume_solids(self):
        self.assertEqual(len(self.solids), len(M['solids']))
        self.assertTrue(self.assembly.isValid())
        for index, solid in enumerate(self.solids):
            with self.subTest(index=index):
                self.assertTrue(solid.isValid())
                self.assertTrue(math.isfinite(solid.Volume()))
                self.assertGreater(solid.Volume(), 0)
        connectors = self.cq.importers.importStep(str(self.output / 'Power8GDI_Connectors_ENVELOPE.step')).val()
        self.assertEqual(len(connectors.Solids()), 4)
        self.assertTrue(connectors.isValid())

    def test_step_dimensions_match_manifest(self):
        expected = {'Base': (P['housing_x'], P['housing_y'], P['base_z'], 0),
                    'Lid': (P['housing_x'], P['housing_y'], P['lid_z'], P['base_z']),
                    'PCB': (P['pcb_x'], P['pcb_y'], P['pcb_thickness'], P['pcb_bottom_z'])}
        for name, (x, y, z, zmin) in expected.items():
            with self.subTest(name=name):
                bounds = self.parts[name].BoundingBox()
                self.assertAlmostEqual(bounds.xlen, x, places=5)
                self.assertAlmostEqual(bounds.ylen, y, places=5)
                self.assertAlmostEqual(bounds.zlen, z, places=5)
                self.assertAlmostEqual(bounds.zmin, zmin, places=5)

    def test_all_roundtripped_solids_have_no_positive_volume_interference(self):
        # Test the actual STEP solids, not the generator's recorded PASS field.
        for (index_a, a), (index_b, b) in itertools.combinations(enumerate(self.solids), 2):
            aa, bb = builder.bounds(a), builder.bounds(b)
            if any(min(aa[f'{axis}max'], bb[f'{axis}max']) - max(aa[f'{axis}min'], bb[f'{axis}min']) <= 1e-7 for axis in 'xyz'):
                continue
            with self.subTest(parts=(index_a, index_b)):
                self.assertLessEqual(a.intersect(b).Volume(), M['validation']['volume_tolerance_mm3'])

    def test_board_does_not_intersect_base_corner_bosses(self):
        self.assertLessEqual(self.parts['Base'].intersect(self.parts['PCB']).Volume(),
                             M['validation']['volume_tolerance_mm3'])

    def test_validation_rejects_overlap_and_empty_geometry(self):
        box = self.cq.Workplane('XY').box(10, 10, 10).val()
        with self.assertRaisesRegex(ValueError, 'collisions'):
            builder.validate_geometry({'A': box, 'B': box}, M)
        with self.assertRaisesRegex(ValueError, 'Invalid or disconnected solid'):
            builder.validate_geometry({'Empty': self.cq.Compound.makeCompound([])}, M)

    def test_stl_meshes_are_closed_and_match_step_volumes(self):
        import vtk
        for name in M['solids']:
            with self.subTest(name=name):
                reader = vtk.vtkSTLReader()
                reader.SetFileName(str(self.output / 'stl' / f'{name}.stl'))
                reader.Update()
                mesh = reader.GetOutput()
                self.assertGreater(mesh.GetNumberOfCells(), 0)
                edges = vtk.vtkFeatureEdges()
                edges.SetInputData(mesh)
                edges.BoundaryEdgesOn()
                edges.NonManifoldEdgesOn()
                edges.FeatureEdgesOff()
                edges.ManifoldEdgesOff()
                edges.Update()
                self.assertEqual(edges.GetOutput().GetNumberOfCells(), 0)
                properties = vtk.vtkMassProperties()
                properties.SetInputData(mesh)
                properties.Update()
                volume = properties.GetVolume()
                self.assertGreater(volume, 0)
                expected = self.generated['geometry_validation']['parts'][name]['volume_mm3']
                self.assertAlmostEqual(volume / expected, 1, delta=0.002)
                if name in self.parts:
                    self.assertAlmostEqual(volume / self.parts[name].Volume(), 1, delta=0.002)


if __name__ == '__main__':
    unittest.main()
