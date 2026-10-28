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

**Quantization and numerical contract (2026-10-21):** scale, offset and limits are rounded to their binary32 wire representations before cell quantization. The exporter rounds each raw cell to nearest-even `int16`. A decoded engineering cell is calculated using a binary64 multiply and add, then rounded once to binary32. Intermediate/final nonfinite values and values outside the finite binary32 range are rejected. The rounded engineering cell must lie inside the serialized `minimum..maximum` exactly; neither decoder adds a tolerance or widens the imported limits. Export accuracy is bounded by half a stored-scale LSB plus final binary32 rounding noise. Axis bins that collide after binary32 conversion are rejected.

Both evaluators interpolate the same rounded engineering cells. The host C++ implementation uses binary64 axis fractions and interpolation, then rounds the output to binary32; this avoids overflow when finite binary32 axis endpoints have a difference exceeding `FLT_MAX`. Python's preview returns binary64, so cross-language lookup comparisons allow the final binary32 rounding error. Build without fast-math; the compatibility probe uses `-ffp-contract=off` for reproducible operations.

**Compatibility:** the version number and byte layout remain P4DM v1. Acceptance is deliberately stricter than the first experimental implementation: old blobs whose cells exceeded their declared limits only by the former tolerance now fail validation. Re-export those maps after correcting their range or quantization; do not silently relax their limits. Previously, Python also expanded limits on every import; repeated valid import/export now preserves the wire limits. Wide multiply/offset cancellation that previously failed only in C++ is now evaluated consistently.

**Data integrity ≠ automotive safety:** CRC32 covers only the payload, not the header, and does not provide authentication, anti-rollback, atomic flash updates or safe interpretation by ECU. Semantic checks reject invalid metadata and values, but a header edit that remains semantically valid cannot be detected by this checksum. Do not enable device write/Burn until a matching authenticated/verified firmware configuration protocol and all fail-safe tests exist.

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

The cross-language gate `configurator/tests/test_map4d_parity.py` compiles `firmware/tests/map4d_probe.cpp` with a C++17 GCC/Clang-compatible compiler, chosen by `CXX` or PATH. Alternatively set `POWER8GDI_MAP4D_PROBE` to the absolute path of an already built probe. A missing compiler fails the gate instead of skipping it. It verifies an independently written C++ fixture against Python byte-for-byte, parses C++ output in Python, reads Python output in C++, checks known asymmetric/non-affine interpolation values, and exercises nonlinear maps, singleton axes, extreme floats, CRC-valid semantic failures and the 4096-cell memory boundary.

Windows commands from the repository root:

```powershell
$env:PYTHONPATH = 'Power8GDI/configurator'
py -3.12 -m pytest -q Power8GDI/configurator/tests/test_map4d.py Power8GDI/configurator/tests/test_map4d_binary.py Power8GDI/configurator/tests/test_map4d_parity.py
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -ffp-contract=off -IPower8GDI/firmware/include Power8GDI/firmware/tests/test_map4d.cpp -o "$env:TEMP/power8gdi-map4d.exe"
& "$env:TEMP/power8gdi-map4d.exe"
clang++ -std=c++17 -O2 -Wall -Wextra -Werror -ffp-contract=off -IPower8GDI/firmware/include Power8GDI/firmware/tests/test_map4d_blob.cpp -o "$env:TEMP/power8gdi-map4d-blob.exe"
& "$env:TEMP/power8gdi-map4d-blob.exe"
```

Host evidence: Python 3.12 / pytest 9.1.1, clang 21.1.6 targeting x86_64 Windows; 24 Python tests and both C++ assertion executables passed. No MCU timing or engine validation was performed. The stand-alone view currently validates every cell on every evaluation (O(cell count)) and uses binary64 arithmetic; both CPU cost and any future cached-validation design require MCU integration review and measurement.
