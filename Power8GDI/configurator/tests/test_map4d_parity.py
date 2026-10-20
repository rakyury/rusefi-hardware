"""Actual Python/C++ exchange tests; compile the production reader on the host.

Set POWER8GDI_MAP4D_PROBE to use an already built firmware/tests/map4d_probe.cpp,
or CXX to select a GCC/Clang-compatible C++17 host compiler. Missing compilers
are an error, never a silently skipped compatibility gate.
"""
import math
import os
from pathlib import Path
import random
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

from power8gdi_configurator.map4d_binary import MapBinaryError, decode_map4d, encode_map4d
from power8gdi_configurator.project import CalibrationTable4D


def fixture_table():
    cells = iter([-.25 * 20 - 3.5, -3.5, -.5, 2.5, 7.5, 11.5,
                  16.5, 21.5, 26.5, 31.5, 36.5, 46.5])
    return CalibrationTable4D(
        'Golden', 'Asymmetric non-affine fixture', 'X', 'Y', 'Z', 'u',
        [-100., 0., 250.], [1000., 3000.], [-20., 80.],
        [[[next(cells) for _ in range(3)] for _ in range(2)] for _ in range(2)],
        -10., 50.)


def wire(x, y, z, raw, scale, offset, lo, hi):
    """Build adversarial inputs directly, bypassing production validation."""
    payload = struct.pack(f'<{len(x)+len(y)+len(z)}f', *(x+y+z))
    payload += struct.pack(f'<{len(raw)}h', *raw)
    return struct.pack('<4sHHHHHHffffIIII', b'P4DM', 1, 48,
                       len(x), len(y), len(z), 0, scale, offset, lo, hi,
                       len(payload), zlib.crc32(payload), 0, 0) + payload


class Map4DParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='power8gdi-parity-')
        cls.addClassCleanup(cls.temp.cleanup)
        configured = os.environ.get('POWER8GDI_MAP4D_PROBE')
        if configured:
            cls.probe = Path(configured).resolve()
        else:
            cxx = os.environ.get('CXX')
            compiler = shlex.split(cxx) if cxx else [next(
                (shutil.which(c) for c in ('c++', 'clang++', 'g++') if shutil.which(c)), '')]
            if not compiler[0]:
                raise RuntimeError('C++17 compiler required for cross-language Map4D gate')
            firmware = Path(__file__).resolve().parents[2] / 'firmware'
            cls.probe = Path(cls.temp.name) / ('map4d-probe.exe' if os.name == 'nt' else 'map4d-probe')
            subprocess.run(compiler + ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                           '-ffp-contract=off', '-I' + str(firmware / 'include'),
                           str(firmware / 'tests' / 'map4d_probe.cpp'), '-o', str(cls.probe)],
                           check=True, capture_output=True, text=True)

    def cpp(self, blob, xyz=(125, 2000, 30)):
        path = Path(self.temp.name) / 'input.p4dm'
        path.write_bytes(blob)
        return subprocess.run([str(self.probe), str(path), *(str(v) for v in xyz)],
                              check=True, capture_output=True, text=True).stdout.strip()

    def assert_value(self, blob, xyz, expected):
        response = self.cpp(blob, xyz).split()
        self.assertEqual(response[0], 'OK')
        actual = float(response[2])
        self.assertTrue(math.isclose(actual, expected, rel_tol=2e-7, abs_tol=2e-6),
                        (xyz, expected, actual))

    def test_bidirectional_independent_fixture_and_golden_values(self):
        emitted = bytes.fromhex(subprocess.run([str(self.probe), 'fixture'],
                                  check=True, capture_output=True, text=True).stdout)
        python_blob = encode_map4d(fixture_table(), scale=.25, offset=-3.5)
        self.assertEqual(python_blob, emitted)  # Both writers agree byte-for-byte.
        decoded = decode_map4d(emitted)         # C++ -> Python production decoder.
        self.assertEqual(decoded.values, fixture_table().values)
        for xyz, expected in [((125, 2000, 30), 18.25), ((-50, 1000, -20), -6),
                              ((-999, 0, -99), -8.5), ((999, 9000, 900), 46.5),
                              ((250, 1000, 80), 26.5)]:
            self.assertAlmostEqual(decoded.interpolate(*xyz), expected)
            self.assert_value(python_blob, xyz, expected)  # Python -> C++ reader.

    def test_generated_nonlinear_maps_and_singleton_axes(self):
        rng = random.Random(4816)
        for nx, ny, nz in [(1, 1, 1), (1, 3, 2), (3, 1, 2), (3, 2, 1), (4, 3, 2)]:
            table = CalibrationTable4D('Random', '', 'X', 'Y', 'Z', 'u',
                [float(i*i+1) for i in range(nx)], [float(i*11) for i in range(ny)],
                [float(i*5-7) for i in range(nz)],
                [[[rng.randrange(-1000, 1001)*.125+2 for _ in range(nx)]
                  for _ in range(ny)] for _ in range(nz)], -200, 200)
            blob = encode_map4d(table, scale=.125, offset=2)
            decoded = decode_map4d(blob)
            for _ in range(5):
                xyz = tuple(struct.unpack('<f', struct.pack('<f', rng.uniform(bins[0]-2, bins[-1]+2)))[0]
                            for bins in (table.x_bins, table.y_bins, table.z_bins))
                self.assert_value(blob, xyz, decoded.interpolate(*xyz))

    def test_valid_extremes_cancelled_product_and_wide_axis(self):
        blobs = [
            (wire([0], [0], [0], [2], 3e38, -3e38, 0, 3.1e38), (0,0,0)),
            (wire([-3e38, 3e38], [0], [0], [-10, 10], 1, 0, -10, 10), (0,0,0)),
            (wire([0], [0], [0], [-32768], 1, 0, -32768, 32767), (0,0,0)),
            (wire([0], [0], [0], [32767], 1, 0, -32768, 32767), (0,0,0)),
        ]
        for blob, xyz in blobs:
            with self.subTest(xyz=xyz, size=len(blob)):
                self.assert_value(blob, xyz, decode_map4d(blob).interpolate(*xyz))

    def test_same_rejection_of_semantically_invalid_crc_valid_blobs(self):
        # Includes asymmetric range tolerance, an upper-bound violation of only
        # one float32 ULP, overflow, colliding axes and nonfinite wire metadata.
        invalid = [
            wire([0], [0], [0], [0], 1, 0, 1, 1e8),
            wire([0], [0], [0], [1], 1.0000001192092896, 0, 0, 1),
            wire([0], [0], [0], [3], 3e38, 0, 0, 3e38),
            wire([0, 0], [0], [0], [0, 1], 1, 0, -10, 10),
            wire([math.nan], [0], [0], [0], 1, 0, -10, 10),
            wire([0], [0], [0], [0], 0, 0, -10, 10),
            wire([0], [0], [0], [0], math.nan, 0, -10, 10),
            wire([0], [0], [0], [0], 1, math.inf, -10, 10),
            wire([0], [0], [0], [0], 1, 0, 2, 1),
        ]
        for index, blob in enumerate(invalid):
            with self.subTest(case=index):
                self.assertEqual(zlib.crc32(blob[48:]), struct.unpack_from('<I', blob, 36)[0])
                with self.assertRaises(MapBinaryError):
                    decode_map4d(blob)
                self.assertEqual(self.cpp(blob), 'REJECT')

    def test_invalid_live_inputs_preserve_output(self):
        blob = encode_map4d(fixture_table(), scale=.25, offset=-3.5)
        for value in (math.nan, math.inf, -math.inf):
            self.assertEqual(self.cpp(blob, (value, 2000, 30)), 'INVALID_INPUT')
            with self.assertRaises(ValueError):
                decode_map4d(blob).interpolate(value, 2000, 30)

    def test_memory_budget_boundary(self):
        axis = list(range(32))
        blob = wire(axis, axis, list(range(4)), [17] * 4096, 1, 0, 0, 20)
        self.assertEqual(decode_map4d(blob).values[3][31][31], 17)
        self.assertEqual(self.cpp(blob, (31, 31, 3)), 'OK 4096 17')
        for invalid in (wire(axis, axis, list(range(5)), [17] * 5120, 1, 0, 0, 20),
                        wire(list(range(33)), [0], [0], [17] * 33, 1, 0, 0, 20)):
            with self.assertRaises(MapBinaryError):
                decode_map4d(invalid)
            self.assertEqual(self.cpp(invalid), 'REJECT')


if __name__ == '__main__':
    unittest.main()
