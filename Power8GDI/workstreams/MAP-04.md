# MAP-04 — 4D maps

**Status:** MANUAL DEVELOPMENT IN PROGRESS / agent profile has NOT been launched.
**Profile:** `.github/agents/calibration4d.agent.md`
**Topic branch:** `power8gdi/map-04`
**Owned paths:** Power8GDI/firmware/include/map4d.h, 4D tests and docs/MAP_*

## Assigned task
Implement three-axis scalar map with [Z][Y][X], trilinear interpolation, validated axes, bounded memory, versioned persistence, Python/C++ golden vectors and invalid-input fail-closed semantics.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Evidence
- PR: pending
- Tests: pending
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Verified manual progress (2026-10-21)
Map4D trilinear evaluator and P4DM v1 CRC32 binary codec in C++ and Python with offline golden tests. Format NOT wired into live rusEFI INI/configuration pages.
