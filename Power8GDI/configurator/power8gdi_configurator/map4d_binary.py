"""Experimental Power8GDI Map4D binary *offline interchange* format.

NOT a rusEFI EEPROM, INI, flash page, or bootloader protocol.  No automatic
engine writes.  This codec permits a versioned, CRC-checked exchange between
prototype firmware tests and desktop calibration tooling.

Little-endian format:
  0  magic P4DM              4 bytes
  4  version                 uint16 (1)
  6  fixed header size       uint16 (48)
  8  nx, ny, nz, flags       4 x uint16 (flags=0 -> int16 cells)
 16  scale, offset           2 x float32
 24  minimum, maximum        2 x float32 (real engineering units)
 32  payload bytes           uint32
 36  payload CRC32 IEEE      uint32
 40  reserved                2 x uint32 (zero)
 48  x bins, y bins, z bins  float32 axis arrays
 ... values                   signed int16, [z][y][x] X-fastest

Raw cell v in physical units is v * scale + offset. The converter rejects
values that cannot be represented to within half of one LSB plus float noise.
"""
from __future__ import annotations

import math
import struct
import zlib

from .project import CalibrationTable4D

MAGIC = b"P4DM"
VERSION = 1
HEADER_SIZE = 48
MAX_CELLS = 4096
MAX_AXIS = 32
_HEADER = struct.Struct('<4sHHHHHHffffIIII')
assert _HEADER.size == HEADER_SIZE


class MapBinaryError(ValueError):
    """Invalid, unsupported, or corrupted calibration blob."""


def encode_map4d(table: CalibrationTable4D, *, scale: float = 0.01,
                 offset: float = 0.0) -> bytes:
    """Quantize a validated map into an unsigned container with int16 cells."""
    table.validate()
    if not math.isfinite(scale) or scale <= 0 or not math.isfinite(offset):
        raise MapBinaryError('Positive finite scale and finite offset required')
    nx, ny, nz = len(table.x_bins), len(table.y_bins), len(table.z_bins)
    try:
        lo, hi = (float(struct.unpack('<f', struct.pack('<f', v))[0])
                  for v in (table.minimum, table.maximum))
        assert lo <= hi
        axes = struct.pack(f'<{nx + ny + nz}f',
                           *(table.x_bins + table.y_bins + table.z_bins))
        raw = []
        for slab in table.values:
            for row in slab:
                for value in row:
                    q = round((value - offset) / scale)
                    if not -32768 <= q <= 32767:
                        raise MapBinaryError('Map value exceeds int16 quantization range')
                    if abs((q * scale + offset) - value) > (scale * 0.5001 + 0.00001):
                        raise MapBinaryError('Map value cannot be quantized accurately')
                    raw.append(q)
        values = struct.pack(f'<{len(raw)}h', *raw)
        p = axes + values
        result = _HEADER.pack(MAGIC, VERSION, HEADER_SIZE, nx, ny, nz, 0,
                              scale, offset, lo, hi, len(p),
                              zlib.crc32(p) & 0xffffffff, 0, 0) + p
        decode_map4d(result)  # Check float32 rounding and bounds before export.
        return result
    except (OverflowError, struct.error, AssertionError) as exc:
        raise MapBinaryError(f'Invalid map range / floating point: {exc}') from exc


def decode_map4d(blob: bytes, *, name: str = 'Imported / Map4D') -> CalibrationTable4D:
    """Strict parse; forbids truncated, appended and CRC-corrupted contents."""
    if not isinstance(blob, (bytes, bytearray)) or len(blob) < HEADER_SIZE:
        raise MapBinaryError('Header too short')
    (magic, version, header_size, nx, ny, nz, flags,
     scale, offset, lo, hi, byte_count, crc, reserved1, reserved2) = _HEADER.unpack_from(blob)
    if magic != MAGIC or version != VERSION or header_size != HEADER_SIZE or flags != 0:
        raise MapBinaryError('Unsupported Map4D binary signature or version')
    if reserved1 or reserved2:
        raise MapBinaryError('Nonzero reserved header data')
    if not (1 <= nx <= MAX_AXIS and 1 <= ny <= MAX_AXIS and 1 <= nz <= MAX_AXIS):
        raise MapBinaryError('Unsupported axis size')
    cells = nx * ny * nz
    if cells > MAX_CELLS:
        raise MapBinaryError('Map exceeds ECU cell budget')
    expected = 4*(nx+ny+nz) + 2*cells
    if byte_count != expected or len(blob) != HEADER_SIZE + expected:
        raise MapBinaryError('Payload length mismatch')
    if not (math.isfinite(scale) and scale > 0 and math.isfinite(offset)
            and math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
        raise MapBinaryError('Invalid scale or physical limits')
    data = blob[HEADER_SIZE:]
    if zlib.crc32(data) & 0xffffffff != crc:
        raise MapBinaryError('CRC32 mismatch')
    axes = struct.unpack_from(f'<{nx+ny+nz}f', data, 0)
    x = list(axes[:nx]); y = list(axes[nx:nx+ny]); z = list(axes[nx+ny:])
    values = struct.unpack_from(f'<{cells}h', data, 4*(nx+ny+nz))
    it = iter(values)
    grids = [[[float(next(it)*scale + offset) for _ in range(nx)]
              for _ in range(ny)] for _ in range(nz)]
    table = CalibrationTable4D(
        name=name, description='Offline P4DM binary import; NOT a rusEFI page',
        x_label='X', y_label='Y', z_label='Z', value_unit='raw',
        x_bins=x, y_bins=y, z_bins=z, values=grids,
        minimum=lo - abs(lo)*1e-6 - 1e-6,
        maximum=hi + abs(hi)*1e-6 + 1e-6,
    )
    try:
        table.validate()
    except (ValueError, TypeError) as exc:
        raise MapBinaryError(f'Unsafe map payload: {exc}') from exc
    return table
