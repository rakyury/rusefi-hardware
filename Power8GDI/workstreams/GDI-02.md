# GDI-02 — GDI power electronics

**Status:** TWO CONNECTED REFERENCE-DERIVED STAGES; load/enable qualification BLOCKED.
**Profile:** `.github/agents/gdi-power.agent.md`
**Topic branch:** `codex/power8gdi-gdi-20261021`
**Owned paths:** Power8GDI/hardware/gdi/ and docs/GDI_*

## Assigned task
Use revision-matched open GDI4 schematic to design 2 independently disabled PT2001 stages for 8 DI and 2 HPFP; verify boost circuits, sense/Kelvin paths, thermal, current limits and fault gating.

## Acceptance and handoff
Create scoped PR into `power8gdi-rev-a` containing source, reports and explicit limitations. Report ERC/DRC/firmware build/test results with commands and SHA. Never claim physical tests without data.

## Latest electrical evidence

[Connected schematic, actual PCB and full open gates](../docs/INTEGRATION_2026_10_21_ELECTRICAL.md).

## Earlier evidence
- PR: https://github.com/rakyury/rusefi-hardware/pull/1 (draft integration)
- Evidence: [report](../docs/GDI_02_SOURCE_AUDIT.md)
- Tests: 24 contract tests; structure gate 0; qualification gate 2
- Hardware validation: NOT RUN
- Manufacturing readiness: NOT APPROVED

## Earlier base-branch manual progress (463c8fa)

Historical evidence before the later integration; current results are above.
Dual PT2001 software safety policy committed and host tested; independent hardware drive/kill circuitry, GDI boost supply, analog validation and oscilloscope dummy load NOT BUILT/NOT RUN.
