import math
import struct
import unittest
import zlib

from power8gdi_configurator.map4d_binary import (
    MapBinaryError, encode_map4d, decode_map4d, HEADER_SIZE,
)
from power8gdi_configurator.project import CalibrationTable4D


class Map4DBinaryTests(unittest.TestCase):
    def example(self):
        return CalibrationTable4D(
            name='Test', description='test', x_label='MAP', y_label='RPM',
            z_label='Ethanol', value_unit='deg',
            x_bins=[0., 100.], y_bins=[1000., 3000.], z_bins=[0., 85.],
            values=[[[1, 11], [3, 13]], [[21, 31], [23, 33]]],
            minimum=-20, maximum=40,
        )

    def test_header_and_roundtrip(self):
        data = encode_map4d(self.example(), scale=.01)
        self.assertEqual(data[:4], b'P4DM')
        self.assertEqual(struct.unpack_from('<H', data, 4)[0], 1)
        self.assertEqual(len(data), HEADER_SIZE + (2+2+2)*4 + 2*8)
        self.assertEqual(zlib.crc32(data[48:]), struct.unpack_from('<I', data, 36)[0])
        parsed = decode_map4d(data)
        self.assertAlmostEqual(parsed.interpolate(50, 2000, 42.5), 17, places=5)
        self.assertEqual(parsed.x_bins, [0,100])
        self.assertEqual(parsed.z_bins, [0,85])

    def test_crc_corruption(self):
        data = bytearray(encode_map4d(self.example()))
        data[-1] ^= 0x55
        with self.assertRaisesRegex(MapBinaryError, 'CRC'):
            decode_map4d(data)

    def test_magic_version_unknown_flag_reserved(self):
        base = encode_map4d(self.example())
        for off, byte in [(0, 0), (4, 2), (14, 1), (40, 1)]:
            data = bytearray(base)
            data[off] = byte
            with self.subTest(off=off), self.assertRaises(MapBinaryError):
                decode_map4d(data)

    def test_truncated_and_extra_bytes(self):
        base = encode_map4d(self.example())
        for blob in [b'', base[:47], base[:-1], base + b'!']:
            with self.subTest(length=len(blob)), self.assertRaises(MapBinaryError):
                decode_map4d(blob)

    def test_bad_shapes_and_nonfinite_payload(self):
        base = encode_map4d(self.example())
        corrupt = bytearray(base)
        struct.pack_into('<H', corrupt, 8, 0)
        with self.assertRaises(MapBinaryError):
            decode_map4d(corrupt)
        corrupt = bytearray(base)
        struct.pack_into('<f', corrupt, 48, math.nan)
        struct.pack_into('<I', corrupt, 36, zlib.crc32(corrupt[48:]))
        with self.assertRaisesRegex(MapBinaryError, 'Unsafe map payload'):
            decode_map4d(corrupt)

    def test_quantization_out_of_range(self):
        with self.assertRaises(MapBinaryError):
            encode_map4d(self.example(), scale=0)
        with self.assertRaises(MapBinaryError):
            encode_map4d(self.example(), scale=.00001)

    def test_int16_sign_and_order(self):
        t = self.example()
        t.values[0][0][0] = -10
        blob = encode_map4d(t, scale=.01)
        raw = struct.unpack_from('<8h', blob, 48 + (2+2+2)*4)
        self.assertEqual(raw[:4], (-1000, 1100, 300, 1300))
        self.assertAlmostEqual(decode_map4d(blob).values[0][0][0], -10., places=5)

    def test_repeated_exchange_preserves_limits(self):
        table = self.example()
        for _ in range(20):
            table = decode_map4d(encode_map4d(table))
            self.assertEqual((table.minimum, table.maximum), (-20, 40))

    def test_wire_scale_is_used_before_quantization(self):
        table = self.example()
        # This value straddles a rounding threshold only after scale is stored
        # as float32. Quantizing with the caller's double gave the wrong cell.
        scale = .1
        value = 100.5 * scale + 1e-8
        table.values[0][0][0] = value
        blob = encode_map4d(table, scale=scale)
        self.assertEqual(struct.unpack_from('<h', blob, 72)[0], 100)

    def test_float32_axis_collision_and_scale_underflow(self):
        table = self.example()
        table.x_bins = [1., 1. + 1e-8]
        with self.assertRaises(MapBinaryError):
            encode_map4d(table)
        with self.assertRaises(MapBinaryError):
            encode_map4d(self.example(), scale=1e-100)

    def test_wire_offset_is_used_before_quantization(self):
        table = CalibrationTable4D('Offset', '', 'X', 'Y', 'Z', 'u',
                                    [0.], [0.], [0.], [[[1.00000005]]], 0, 2)
        blob = encode_map4d(table, scale=1e-8, offset=1.00000004)
        self.assertEqual(struct.unpack_from('<h', blob, 60)[0], 5)

if __name__ == '__main__':
    unittest.main()
