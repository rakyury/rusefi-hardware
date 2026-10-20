# CAD-06 — Mechanical CAD

**Status:** MANUAL DEVELOPMENT IN PROGRESS / agent profile has NOT been launched.
**Profile:** `.github/agents/mechanical-cad.agent.md`
**Topic branch:** `power8gdi/cad-06`
**Owned paths:** Power8GDI/mechanical/ and docs/CAD_*

## Assigned task
Create base/lid/assembly STEP using verified TE connector STEP and actual PCB layout, sealed enclosure, thermal and fastening features. Generate board/assembled/exploded multiangle 3D renders and dimensional drawings.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Evidence
- PR: pending
- Tests: pending
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Verified manual progress (2026-10-21)
Provisional CadQuery enclosure/assembly and STEP + six envelope renders available in developer package; 6 envelope tests PASS. Real TE mating STEP, actual placed PCB, gasket, heat-transfer and tolerance stackup NOT VERIFIED.
