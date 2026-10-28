# Power8GDI task allocation

## Active continuation: 2026-10-25

The user has explicitly superseded the Huge/GDI8 channel counts with a strict
six-cylinder hardware redesign. Read [active scope](../docs/SCOPE_2026_10_25_SPORT_GDI6.md)
and [the imported analysis](../docs/research/2026-10-25-sport-ecu/README_RU.md).
Integration branch: `codex/sport-gdi6-20261025`, starting from local `2d0e66e`.
The original checkout and interrupted changes are preserved.

Execution order is schematic, derived BOM and 1/10 PCBA estimate, PCB/routing,
firmware integration, and the existing own configurator. Independent software
contracts may be developed while the hardware is being revised. The client must
reuse the user's Racing Dash VM and CAN work and include the requested service
tools. Three worker slots cover HW/GDI, FW/MAP, and UI with dependent CAD/QA
reviews queued; integration is coordinated separately. Current work is ongoing,
not a new production or hardware-validation milestone.

The following entries describe the previous eight-channel checkpoint.

**Integration target:** `power8gdi-rev-a`

**Review branch:** `codex/power8gdi-resume-20261021`

**Review:** https://github.com/rakyury/rusefi-hardware/pull/1 (draft)
**Checkpoint:** 2026-10-23, Huge/GDI8 scope and revised electrical integration in progress; manufacturing release BLOCKED.

Latest: [current engineering status](../docs/DESIGN_STATUS.md) and [approved Huge/GDI8 scope](../docs/SCOPE_2026_10_23_HUGE_GDI8.md). The [20-sheet / 631-component review](../docs/INTEGRATION_2026_10_21_ELECTRICAL.md), its 499 unconnected items and 752 DRC findings describe the earlier board only. The table below records historical milestones, not completion of the expanded hardware.

Seven specialist roles were executed in dedicated worktrees using three actual
concurrent worker slots, with integration as the eighth role. Roles were queued
and reused across those workers; seven simultaneous agents were not claimed.
GitHub Issues are disabled; these briefs remain the task tracker.

| Task | Delivered checkpoint | Remaining dependency |
|---|---|---|
| HW-01 | GPIO/resource audit, 12 tests | Exact MCU/package, complete AF/ADC/DMA/timer allocation, electrical hierarchy/ERC |
| GDI-02 | Source/hash audit and independent-stage contract, 24 tests | Resolve revision mismatch, safe levels, package mapping and license |
| FW-03 | Latched dual-HPFP host policy and fault matrix | Pinned rusEFI core, board pins, physical drivers, scheduler and F7 build |
| MAP-04 | Strict P4DM float32 codec and C++/Python parity | MCU latency/memory qualification and transport |
| UI-05 | Tested offline lifecycle, full precision edits, search and atomic save | Protocol/signature/persistence validation; no ECU writes enabled |
| CAD-06 | 18 solids, 5 STEP, 18 STL, 6 views, 14 tests | Vendor connector geometry, actual PCB layout, seal/thermal/physical fit |
| QA-07 | Independent review, reproduced defects and regression fixes | ERC/DRC, actual MCU build, hardware/EMC/thermal/engine evidence |
| INT-08 | Isolated contributions integrated in draft PR, portable runner and CI | Review and subsequent engineering milestones |

## Evidence

See [integration record](../docs/INTEGRATION_2026_10_21.md) for exact commands,
source commits and final results. The concurrently added upstream dual-PT2001
policy is included in the portable runner alongside the four existing C++ suites.
Its independent review also fixed missing stopped-engine evidence and incomplete
independent-rail validation, with dedicated regression coverage.

## Next dependency order

1. Freeze exact MCU order code/package and coherent resource allocation.
2. Resolve PT2001 revision/electrical evidence; complete protected power and a
   real electrical hierarchy with independent shutdown paths.
3. Pin rusEFI core and implement a board target against those reviewed contracts.
4. Produce routed PCB/ERC/DRC and vendor-based assembly/fit evidence.
5. Perform dummy-load fault injection, timing, thermal and EMC measurements before
   an engine or manufacturing release.

Passing structure, host or conceptual CAD checks does not satisfy these gates.

## Earlier base-branch context (463c8fa)

The following records the other chat and its earlier tool capabilities/test
counts. The latest electrical checkpoint and actual worker status are above.

### Agent capability in the earlier chat
The current connected toolset can write GitHub repository content but has no action to start Copilot background agents. GitHub custom-agent profiles must be invoked by a supported Copilot surface. For GitHub cloud agent, profiles generally need to be merged into the repository default branch. Keep `main` unchanged until review.

### Earlier manual integration update — 2026-10-21
- [Dual PT2001 safety logic and tests](https://github.com/rakyury/rusefi-hardware/commit/673e68b08957ec1e71e9834a8e1dbdc2b51ed0d9) — host only.
- [MCU resource tracker](https://github.com/rakyury/rusefi-hardware/commit/6abecaa9fff202ef2c4be1cdfec28b6a6ce03b5c) — 32 required allocations remain missing; manufacturing blocked.
- [Normal stop/synchronization state fix](https://github.com/rakyury/rusefi-hardware/commit/c1def6cb98f45cf590ad178af9761b2a5908d862) — host test passed.
- 24 offline Python tests, 16 static MCU/connector tests, 6 mechanical envelope tests, and C++ Map4D, P4DM, dual HPFP planning and dual GDI gate host tests pass locally. Real MCU firmware, ERC/DRC, electrical/EMC/thermal validation not complete.
- **No specialist Codex/Copilot agents have actually been launched by this chat.** Profile definitions are available for later parallel execution.
