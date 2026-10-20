# Launch brief: Power8GDI Rev A — Codex parallel execution

**Repo:** https://github.com/rakyury/rusefi-hardware  
**Base branch:** `power8gdi-rev-a`  
**Primary task board:** `Power8GDI/workstreams/ROADMAP.md`  
**Agent definitions:** `.github/agents/*.agent.md`  
**This file is instructions only. It does not launch agents.**

## Codex coordinator instruction

Read `AGENTS.md`, `Power8GDI/AGENTS.md` and all eight workstream briefs. Execute the Power8GDI Rev A engineering program using concurrent subagents or isolated Codex threads/worktrees, where the platform supports them.

Launch or delegate these specialists **in parallel with nonoverlapping file ownership**, do not merely output a plan:

| Role | Brief | First concrete deliverable |
|---|---|---|
| Electrical/PCB | `HW-01.md` | Real KiCad hierarchy, connector part numbers, F7 pinmux conflict list, ERC |
| GDI Power | `GDI-02.md` | Rev-matched PT2001 dual-stage circuit review and verified GDI hardware sheets |
| Firmware | `FW-03.md` | Independently buildable F7 firmware target with dual HPFP/GDI safe-state tests |
| 4D | `MAP-04.md` | C++ host-tested 3-axis/one-output interpolation and Python golden vectors |
| PyQt Configurator | `UI-05.md` | Runnable offline 4D-capable editor with pytest, using racing_dash architecture |
| Mechanical CAD | `CAD-06.md` | Vendor-matched connector envelope, case/base/lid STEP and 3D assembly angles |
| QA | `QA-07.md` | ERC/DRC/firmware/GUI/fit/test release gates and issue register |
| Integration lead | `INT-08.md` | Track independently isolated branches, review and integrate verified output |

### Execution requirements

- Start with **7 parallel specialist workstreams**, and run coordination as the eighth logical role. Start only the number that your Codex environment actually supports; queue the rest rather than pretending they run.
- Each worker must have a dedicated worktree / topic branch from `power8gdi-rev-a` (or no writes if only reviewing). Never perform simultaneous writes to identical paths.
- Do not alter rusEFI original GDI4 hardware sources. Import/read reference sources, cite SHA and license; new design under `Power8GDI/`.
- For firmware, keep engine-timed injector and pump pulses on deterministic MCU outputs, not CAN.
- For GUI, no hardware “Burn”/write action until matching rusEFI protocol, firmware signature and persistence checks pass.
- Always commit actual deliverables and tests, with PRs targeting `power8gdi-rev-a`; attach build logs and exact commands.
- Target deliverables: full electrical schematic, fully routed and verified PCB with complete Gerbers/BOM/CPL, multiangle 3D of real board/case/headers, case STEP and dimensioned drawings, reproducibly built tested firmware, separately packaged Python configurator.
- Mark all physical/EMC/thermal/engine verification pending unless measured. Do not claim the manufacturing release is complete without satisfying the QA gate.

### If Codex does not support subagent launch

Open seven independent Codex tasks on the same repository and branch, one per role above, asking each to read its respective workstream brief and work on a dedicated topic branch. Keep Integration Lead in a separate task once contributions are available.

### Status update format

Report worker launched/queued (verified state only), working branch, changed files/commit, tests pass/fail, blockers, next artifact, and dependent workstreams.
