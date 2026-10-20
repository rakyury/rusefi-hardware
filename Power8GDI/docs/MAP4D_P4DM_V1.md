# Power8GDI P4DM v1 — experimental binary 4D calibration interchange

**Status:** offline/prototype **only**. Not a rusEFI `engine_configuration_s` layout, NVRAM page, USB/CAN protocol, flashed tune, or engine-safe calibration. A firmware integration patch must explicitly pin the same schema, test its MCU memory usage, and enforce a staging/commit boundary before device writes.

## Dimension terminology

4D calibration means **three inputs** (X, Y, Z) and a scalar dependent value. The evaluation is trilinear across eight corner samples. Rows and planes are stored as `values[z][y][x]`, with X fastest. Values outside axes are clamped; non-finite queries must fail and leave the provided output unchanged.

## Byte layout

All integer and floating-point fields are **little-endian**. Float32 is IEEE-754 binary32. No C structure packing or native padding is permitted.

| Byte | Field | Encoding |
|---:|---|---|
| 0 | Magic | ASCII `P4DM` |
| 4 | Version | uint16 = 1 |
| 6 | Header bytes | uint16 = 48 |
| 8 | X bin count | uint16, 1..32 |
| 10 | Y bin count | uint16, 1..32 |
| 12 | Z bin count | uint16, 1..32 |
| 14 | Flags | uint16 = 0 (`int16` samples) |
| 16 | Scale | float32, positive and finite |
| 20 | Offset | float32, finite |
| 24 | Minimum real value | float32 finite |
| 28 | Maximum real value | float32 finite |
| 32 | Payload length | uint32 |
| 36 | Payload CRC32 | uint32 CRC32 IEEE/ZIP over bytes starting at offset 48 |
| 40 | Reserved | uint32 = 0 |
| 44 | Reserved | uint32 = 0 |
| 48 | X-axis bins | `nx` × float32 |
| ... | Y-axis bins | `ny` × float32 |
| ... | Z-axis bins | `nz` × float32 |
| ... | Cells | `nx * ny * nz` × signed int16, X fastest |

Real value = `int16 * scale + offset`; raw values and decoded real engineering-unit values are validated against the `minimum..maximum` range. Axis bins strictly increase; non-finite inputs, corrupt CRCs, unknown fields and extra/truncated bytes are rejected. Maximum **4096** cells per table. Default dense table capacity: 4096 × 2 bytes = **8192 B**, plus three axis arrays of 32 × 4 bytes = **384 B**, plus metadata and alignment; allocate carefully on STM32F7.

**Quantization:** the Python exporter rounds each cell to nearest-even `int16` and rejects out-of-range/invalid values. A one-unit change in the raw sample changes the real value by `scale` engineering units. Parsing intentionally permits sub-LSB drift caused by encoding `scale` as binary32.

**Data integrity ≠ automotive safety:** CRC32 catches typical corruptions but does not provide authentication, anti-rollback, atomic flash updates or safe interpretation by ECU. Do not enable device write/Burn until a matching authenticated/verified firmware configuration protocol and all fail-safe tests exist.

## Reproducible host checks

```bash
cd Power8GDI
bash firmware/tests/run_host_tests.sh
bash firmware/tests/run_map4d_wire_tests.sh
bash firmware/tests/run_dual_hpfp_tests.sh
cd configurator
python -m unittest discover -s tests -v
```

The firmware host parser is at `firmware/include/map4d_blob.h`; the desktop exporter/importer is `configurator/power8gdi_configurator/map4d_binary.py`. These modules are tested independently from hardware and cannot by themselves command injectors.
