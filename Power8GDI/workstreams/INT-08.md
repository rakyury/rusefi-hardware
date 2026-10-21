# INT-08 — Integration coordination

**Status:** INTEGRATED OFFLINE CHECKPOINT; review and production gates pending.
**Profile:** `.github/agents/integration-lead.agent.md`
**Topic branch:** `codex/power8gdi-resume-20261021`
**Owned paths:** Power8GDI/workstreams/ROADMAP.md and docs/INTEGRATION_*

## Assigned task
Track 7 specialist PRs, source versions, MCU/PCB/CAD/calibration/transport interfaces, merge safety, dependencies and manufacture/firmware release gates.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Latest electrical evidence

[Connected schematic, actual PCB and full open gates](../docs/INTEGRATION_2026_10_21_ELECTRICAL.md).

## Earlier evidence
- PR: https://github.com/rakyury/rusefi-hardware/pull/1 (draft integration)
- Evidence: [report](../docs/INTEGRATION_2026_10_21.md)
- Tests: portable Windows/Linux host and CAD validation; draft PR
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Earlier base-branch manual progress (463c8fa)

Historical evidence before the later integration; current results are above.
Manual integration commits through c1def6c... (development branch). Agent definitions exist but are not running. All design/manufacturing release gates remain blocked pending full schematics, PCB footprints/routes, firmware target and physical tests.
