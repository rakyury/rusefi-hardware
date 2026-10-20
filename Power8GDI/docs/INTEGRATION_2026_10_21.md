# Power8GDI offline development checkpoint — 2026-10-21

Review: https://github.com/rakyury/rusefi-hardware/pull/1 (draft into
`power8gdi-rev-a`). Work began from `1ff4b732c121a33e1f15e169df428c90be87b3c7`.
Concurrent upstream `673e68b08957ec1e71e9834a8e1dbdc2b51ed0d9` was merged,
preserving its dual-PT2001 policy and including its tests in the portable runner.
Upstream GDI4 reference designs were read, not modified.

## Integrated specialist contributions

| Role | Original isolated commit | Evidence |
|---|---|---|
| UI-05 | `095e819cf68a4f97d4f408212a89980cabbd3168` | [UI lifecycle](UI_OFFLINE_EDITOR_VALIDATION.md) |
| FW-03 | `a4c71c7ce37afd78993c3d118fb1f404e624a5fe` | [HPFP policy](FW_03_SAFETY_SUPERVISOR.md) |
| MAP-04 | `0296f9e221cb39fa9b79e8da1a1cb7331770a09a` | [Wire contract](MAP4D_P4DM_V1.md) |
| HW-01 | `40c8cbe8e26a566f091eb1d0ea8f07978574c59a` | [MCU audit](HW_RESOURCE_AUDIT.md) |
| GDI-02 | `17be0069d69b81a0bc0870814e0154d3d31800b4` | [GDI source audit](GDI_02_SOURCE_AUDIT.md) |
| CAD-06 | `6ec46b2e9e8b706bdc206d3ae1f28e5451ab5710` | [CAD evidence](CAD_REPRODUCIBLE_CONCEPT.md) |
| QA-07 | `9298ca644913eca0404c10867fe7e7096a7a8aee` | [Independent review](RELEASE_QA_2026_10_21.md) |

Integration added map search, exact command/log reporting, Windows/Linux CI and
separate CAD regeneration. [EMU PRO interface observations](UI_REFERENCE_OBSERVATIONS.md)
contain no private calibration data or application images. The user-authorized
study did not connect to an ECU or change/save calibration settings.

## Reproduce

Use Python 3.12 and a GCC-compatible C++17 compiler (`CXX` may name its executable).

```text
python -m pip install -e "./Power8GDI/configurator[dev]"
python Power8GDI/tools/run_checks.py --suite host
python -m pip install -r Power8GDI/mechanical/requirements-cad.txt
python Power8GDI/tools/run_checks.py --suite cad
python Power8GDI/mechanical/render_views.py --input-dir build/power8gdi-checks/cad-assets --output-dir build/power8gdi-checks/renders
```

Linux additionally runs `--suite host --sanitizers`. Separate GUI and CAD
environments are supported. Reports contain revision, dirty state, exact
subprocess commands, return codes and logs. GUI tests use Qt offscreen; the local
preview explicitly loads Windows Segoe UI because offscreen font discovery
otherwise omitted it. Fonts are not redistributed.

Initial Windows evidence at `ff5bcde`: four C++ suites; 72 Python/Qt tests with
21 subtests; 17 static-interface, 12 resource-audit and 24 GDI-contract tests;
14 CAD tests, all passed. Independent QA then increased configurator coverage to
78 tests, fixing malformed metadata imports and atomic save temp-file isolation.
Final integrated evidence including upstream policy fixes is recorded below.

## Remaining engineering gates

- MCU candidate remains provisional. 26 required functions have no resource row,
  32 existing rows are UNASSIGNED, five conditional conflicts and 13 missing
  evidence groups remain. Structure passes; release validation remains blocked.
- GDI4 rev.d schematic/PCB and BOM disagree on U1; the old symbol supply name
  disagrees with NXP. Safe levels, package mapping and licensing remain unresolved.
- HPFP allocation and GDI permits are separate host models. Actual driver and
  scheduler integration must combine permits and establish measured shutdown
  timing. Neither model is a flashable ECU firmware build.
- P4DM full-cell validation is linear in map size and uses double arithmetic;
  MCU execution time and memory budget have not been measured.
- CAD fixes a measured 77.3266 mm3 board/boss intersection, but remains a concept.
  Vendor TE geometry, actual PCB fit, seals and physical measurements are absent.
- Electrical schematic/ERC, routed PCB/DRC, fabrication release, thermal/EMC,
  bench fault injection and engine qualification are incomplete.

No ECU connection, flash, calibration burn or physical output actuation was made.

## Final local verification

Host code at `7ca4518` passed all five C++ suites, 78 Python/Qt tests with 21
subtests, 17 static-interface, 12 MCU-audit and 24 GDI-contract tests on Windows
Python 3.12.10 and clang 21.1.6. Documentation/CI setup edits were pending during
this run and are explicitly reflected by the report's dirty flag. CAD's 14 tests
passed after regeneration; CAD source has not changed since that run.

The additional policy review (`addd62db52f53fea3122261f3f3388f47df555d6`,
integrated as `7ca4518`) requires confirmed standstill to acknowledge a fault and
both pumps/sensors for the fixed eight-DI independent-rail configuration. All
16 equipment-presence combinations are covered. The physical provider must still
establish fresh standstill evidence; a boolean is not a hardware measurement.

An installed wheel (`0.1.0.dev1`) was opened, filtered, switched between Z layers,
rendered and closed successfully. The wheel contains no ECU-write implementation.

Initial GitHub CI passed Windows host and Linux CAD jobs; Linux Qt could not
load `libEGL.so.1`. The workflow now installs `libegl1`. The PR checks and attached
run artifacts are the authority for subsequent CI results, not this local record.

Upstream `6abecaa9fff202ef2c4be1cdfec28b6a6ce03b5c` subsequently added 26 explicit
UNASSIGNED rows and five narrower resource-budget tests. The snapshot and its
regression expectations were regenerated against that source. Static-interface
coverage is now 22 tests; no additional GPIO allocation or qualification was made.
