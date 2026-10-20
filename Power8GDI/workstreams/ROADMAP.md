# Power8GDI task allocation

**Integration branch:** `power8gdi-rev-a`
**State:** eight reusable GitHub Copilot agent profiles and eight task briefs CREATED; no background agents are running.
**Issue tracker:** disabled on this GitHub fork (HTTP 410); task briefs tracked in Git.

| Task | Specialist | Independent starting work | Status |
|---|---|---|---|
| HW-01 | Hardware schematic | Power8GDI/hardware/ and docs/HW_* | READY |
| GDI-02 | GDI power electronics | Power8GDI/hardware/gdi/ and docs/GDI_* | READY |
| FW-03 | STM32F7 ECU firmware | Power8GDI/firmware/ excluding 4D engine files | READY |
| MAP-04 | 4D maps | Power8GDI/firmware/include/map4d.h, 4D tests and docs/MAP_* | READY |
| UI-05 | Python PyQt6 configurator | Power8GDI/configurator/ and docs/UI_* | READY |
| CAD-06 | Mechanical CAD | Power8GDI/mechanical/ and docs/CAD_* | READY |
| QA-07 | Release validation | Power8GDI/tests/ and docs/RELEASE_* | READY |
| INT-08 | Integration coordination | Power8GDI/workstreams/ROADMAP.md and docs/INTEGRATION_* | READY |

## Parallel waves
Wave 0 (independent): MCU/pinmux/schematic audit HW; GDI power-stage review GDI; Map4D parity MAP; offline PyQt UI; official connector CAD + envelope CAD; QA design.
Wave 1: coherent electrical schema ERC; GDI interfaces and F7 dual HPFP firmware; 4D serialization + Python transport; actual PCB-to-case fit.
Wave 2: laid-out PCB DRC plus fabrication/BOM/CPL, STEP case, reproducible flashed MCU firmware and GUI validation.
Wave 3: prototypes, bench waveforms and fault injections, thermal/EMC, documented qualified manufacturing release.

## Latest local evidence (2026-10-21)
C++ host Map4D and dual HPFP supervisor tests passed.
Python editor 17 tests passed after fixing obsolete expected table count 9 -> 11.
GPIO/pinout 11 tests and CAD envelope 6 tests passed.
None of this substitutes for actual KiCad ERC/DRC, Power8GDI firmware target build, MCU-in-loop or hardware validation.

## Running agents
The current connected toolset can write GitHub repository content but has no action to start Copilot background agents. GitHub custom-agent profiles must be invoked by a supported Copilot surface. For GitHub cloud agent, profiles generally need to be merged into the repository default branch. Keep `main` unchanged until review.
