# GDI-02 — GDI power electronics

**Status:** MANUAL DEVELOPMENT IN PROGRESS / agent profile has NOT been launched.
**Profile:** `.github/agents/gdi-power.agent.md`
**Topic branch:** `power8gdi/gdi-02`
**Owned paths:** Power8GDI/hardware/gdi/ and docs/GDI_*

## Assigned task
Use revision-matched open GDI4 schematic to design 2 independently disabled PT2001 stages for 8 DI and 2 HPFP; verify boost circuits, sense/Kelvin paths, thermal, current limits and fault gating.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Evidence
- PR: pending
- Tests: pending
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Verified manual progress (2026-10-21)
Dual PT2001 software safety policy committed and host tested; independent hardware drive/kill circuitry, GDI boost supply, analog validation and oscilloscope dummy load NOT BUILT/NOT RUN.
