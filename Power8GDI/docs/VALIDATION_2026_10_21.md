# Power8GDI Rev A — verified offline deliverables and blockers (2026-10-21)

## Completed in this iteration

- Added standalone C++ `Map4DBlob` parser with a strict 48-byte LE header and CRC32, fixed 4096 `int16` storage, axes and physical-range validation; no dynamic memory/exceptions.
- Added Python P4DM v1 importer/exporter, corrupt-file rejection and signed int16 quantization.
- Fixed PyQt6 `app.py` 4D layer selection, editing and undo/redo targeting for `[Z][Y][X]` maps; layer switch cannot show edits from a different Z plane.
- Added C++ wire-parser tests and Python binary-format tests; retained existing 4D interpolation and HPFP planning tests.
- Existing envelope-based enclosure STEP/render files are preliminary: vendor connector models, PCB copper, fasteners and thermal validation remain outstanding.

## Exact host commands and outcomes

- `bash firmware/tests/run_host_tests.sh`: PASS.
- `bash firmware/tests/run_map4d_wire_tests.sh`: PASS.
- `bash firmware/tests/run_dual_hpfp_tests.sh`: PASS.
- `python -m unittest discover -s tests -v` under `configurator/`: **24 tests, PASS**.
- `python -m compileall ...`: PASS.
- GUI Qt runtime smoke tests: **NOT RUN** (PyQt6 not installed in validation runtime).

## Release blockers — DO NOT ORDER YET

- MCU package, pinmux table and all SPI/EXTI/ADC/DMA timers not locked.
- GDI hardware PT2001 and dual pump driver not integrated in an electrical schematic; **no verified 8 DI / 2 HPFP schematics**.
- Real vendor TE 34-pin header footprints and STEP models not integrated; PCB is only a planning outline.
- KiCad ERC/DRC and gerber/assembly BOM/pick-place release: **NOT RUN / NOT READY** (KiCad CLI unavailable in current validation environment).
- Firmware Power8GDI target build: **NOT RUN / NOT READY**. Existing dual-HPFP module does not implement real scheduling or rail closed-loop control.
- Device flash/Burn protocol **NOT AVAILABLE**. The GUI is strictly offline and maps are demonstrators, not tuning recommendations.
- Engine/injector/thermal/EMC/fault-injection physical acceptance tests **NOT RUN**.

## Follow-on F7/GDI safety work

- Added a dual PT2001 global permit state machine and tests; both modules disable on fault or loss of sync and require manual stopped-engine acknowledgment. This is **host-only policy**, not a wired hardware kill circuit.
- Added a shared-rail/single-pump compatibility mode and separate-rail mode, with configuration freeze while armed.
- Added resource-budget audit tracking **32 unresolved required MCU-side functions**; `--strict` appropriately fails and therefore manufacturing release stays blocked.
- STM32F767IIT6 LQFP176 is a **provisional candidate**, not a verified KiCad MCU resource allocation.
