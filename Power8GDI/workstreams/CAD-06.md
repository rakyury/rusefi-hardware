# CAD-06 — Mechanical CAD

**Status:** REPRODUCIBLE CONCEPT DELIVERED; vendor/physical fit BLOCKED.
**Profile:** `.github/agents/mechanical-cad.agent.md`
**Topic branch:** `codex/power8gdi-cad-20261021`
**Owned paths:** Power8GDI/mechanical/ and docs/CAD_*

## Assigned task
Create base/lid/assembly STEP using verified TE connector STEP and actual PCB layout, sealed enclosure, thermal and fastening features. Generate board/assembled/exploded multiangle 3D renders and dimensional drawings.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Evidence
- PR: https://github.com/rakyury/rusefi-hardware/pull/1 (draft integration)
- Evidence: [report](../docs/CAD_REPRODUCIBLE_CONCEPT.md)
- Tests: 14 geometry/provenance tests; 18 solids, 5 STEP, 18 STL, 6 views
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Earlier base-branch manual progress (463c8fa)

Historical evidence before the later integration; current results are above.
Provisional CadQuery enclosure/assembly and STEP + six envelope renders available in developer package; 6 envelope tests PASS. Real TE mating STEP, actual placed PCB, gasket, heat-transfer and tolerance stackup NOT VERIFIED.
