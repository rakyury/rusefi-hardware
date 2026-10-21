# Power8GDI task allocation

**Integration target:** `power8gdi-rev-a`

**Review branch:** `codex/power8gdi-resume-20261021`

**Review:** https://github.com/rakyury/rusefi-hardware/pull/1 (draft)
**Checkpoint:** 2026-10-21, connected electrical engineering review; manufacturing release BLOCKED.

Latest: [20-sheet / 631-component electrical integration](../docs/INTEGRATION_2026_10_21_ELECTRICAL.md). Actual review PCB: 499 unconnected items, 752 DRC findings; no full-routing claim. Earlier offline milestones below remain historical.

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
