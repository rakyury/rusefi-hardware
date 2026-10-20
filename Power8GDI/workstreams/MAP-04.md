# MAP-04 — 4D maps

**Status:** HOST CODEC/PARITY DELIVERED; MCU timing pending.
**Profile:** `.github/agents/calibration4d.agent.md`
**Topic branch:** `codex/power8gdi-map-20261021`
**Owned paths:** Power8GDI/firmware/include/map4d.h, 4D tests and docs/MAP_*

## Assigned task
Implement three-axis scalar map with [Z][Y][X], trilinear interpolation, validated axes, bounded memory, versioned persistence, Python/C++ golden vectors and invalid-input fail-closed semantics.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Evidence
- PR: https://github.com/rakyury/rusefi-hardware/pull/1 (draft integration)
- Evidence: [report](../docs/MAP4D_P4DM_V1.md)
- Tests: bidirectional Python/C++ parity and two C++ map suites
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED
