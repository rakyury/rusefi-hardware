import json
import math
import tempfile
import unittest
from pathlib import Path

from power8gdi_configurator.project import (
    FORMAT_VERSION, CalibrationProject, CalibrationTable4D, default_project
)


class Map4DTests(unittest.TestCase):
    @staticmethod
    def example():
        # Same synthetic affine function and shape as firmware C++ host test.
        return CalibrationTable4D(
            name='Demo / 4D', description='affine parity test',
            x_label='MAP', y_label='RPM', z_label='Ethanol', value_unit='deg',
            x_bins=[0, 100], y_bins=[1000, 3000], z_bins=[0, 100],
            values=[[[1, 11], [3, 13]], [[21, 31], [23, 33]]],
            minimum=-100, maximum=100,
        )

    def test_midpoint_trilinear_cpp_parity(self):
        t = self.example()
        self.assertAlmostEqual(17, t.interpolate(50, 2000, 50))
        self.assertAlmostEqual(1, t.interpolate(-900, -999, -1))
        self.assertAlmostEqual(33, t.interpolate(900, 9999, 200))
        self.assertAlmostEqual(31, t.interpolate(100, 1000, 100))
        self.assertAlmostEqual(23, t.interpolate(0, 3000, 100))

    def test_single_axis_supported(self):
        t = self.example()
        t.z_bins = [0]
        t.values = t.values[:1]
        self.assertAlmostEqual(7, t.interpolate(50, 2000, 500))

    def test_reject_axis_collision(self):
        t = self.example()
        t.z_bins = [0, 0]
        with self.assertRaises(ValueError):
            t.validate()

    def test_nonfinite_fails_closed(self):
        t = self.example()
        for val in [math.nan, math.inf, -math.inf]:
            with self.assertRaises(ValueError):
                t.interpolate(10, 2000, val)
            with self.assertRaises(ValueError):
                t.set_value(0, 0, 0, val)

    def test_shape_and_bounds(self):
        t = self.example()
        t.values[0][0].pop()
        with self.assertRaises(ValueError):
            t.validate()
        t = self.example()
        t.values[0][0][0] = 900
        with self.assertRaises(ValueError):
            t.validate()

    def test_4096_budget(self):
        t = CalibrationTable4D('test', 'test', 'x', 'y', 'z', '%',
                               list(range(32)), list(range(32)), list(range(5)),
                               [[[5 for _ in range(32)] for _ in range(32)] for _ in range(5)],
                               0, 100)
        with self.assertRaises(ValueError):
            t.validate()

    def test_version2_project_and_legacy_read(self):
        p = default_project()
        self.assertEqual(FORMAT_VERSION, p.format_version)
        self.assertEqual(11, len(p.tables))
        self.assertIsInstance(p.tables['Ignition / Ethanol 4D'], CalibrationTable4D)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'sample.json'
            p.save(f)
            self.assertEqual(p.to_dict(), CalibrationProject.load(f).to_dict())
            dct = json.loads(f.read_text())
            dct['format_version'] = 1
            dct['cylinders'] = 8
            dct.pop('profile_id')
            dct.pop('imported_format_version')
            dct['tables'] = {k:v for k,v in dct['tables'].items() if 'z_bins' not in v}
            migrated = CalibrationProject.from_dict(dct)
            self.assertEqual(migrated.format_version, FORMAT_VERSION)
            self.assertEqual(9, len(migrated.tables))


if __name__ == '__main__':
    unittest.main()
