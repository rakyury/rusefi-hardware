# Power8GDI intervention arbitration (FW-03, host-only)

Status: **host-tested; runs in the rusEFI simulator in shadow mode (compares, does not drive the engine).** No MCU, timer or engine-scheduler calls. Not validated on an engine.

Source: `firmware/arbitration/`. Tests: `firmware/tests/test_arbitration.cpp`, `bash firmware/tests/run_arbitration_tests.sh`.

Design lessons from the EMU PRO analysis (problems we avoid): `EMU_LESSONS.md`.

## Why

Many subsystems want to change fuel, ignition, lambda, boost or cut cylinders at the same time. Examples: limiters, launch, anti-lag, traction, knock, protections, gear shift. All requests go into one accumulator each cycle under fixed rules, so the result never depends on hidden call order. Every active source is visible as a bit mask for logging.

## Rules (`InterventionAccumulator`)

| quantity | combination | notes |
|---|---|---|
| fuel | product of factors | any fuel-cut source forces 0 |
| ignition | sum of offsets (deg, + = advance) | final sum clamped to `[ignitionOffsetMin, ignitionOffsetMax]` |
| lambda target | base + sum of offsets, then max(floors), then min(ceilings) | on a floor/ceiling conflict the richer limit wins |
| boost target | product of factors | clamped to `[0, boostFactorMax]` |
| cylinder cut | the largest percent wins | on a tie the **earlier** request wins; every non-zero requester is recorded as a candidate |

The accumulator rejects and counts non-finite or out-of-range requests (`rejectedRequests()`). A rejected request has no effect on the result.

## Fixed task order (`TaskCycle`)

- Tasks run strictly in registration order. `update()` runs only in the task's slots of a 20-slot period, at a rate that divides 20. `contribute()` runs every cycle.
- Update phases are spread deterministically over the least-loaded slots.
- The accumulator is reset at the start of every cycle.
- Final stages (ignition angle, fuel, cylinder cut) are registered with `isFinal = true`. A contributing task registered after a final stage is rejected (`OrderViolation`), so every request of a cycle is visible to every final stage in the same cycle. Registration order is also the cylinder-cut tie-break priority.

## Ignition source priority (`IgnitionArbiter`)

- Exactly one source owns the angle. The default priority is cranking > launch control > anti-lag > idle > overrun > table. The priority list is configurable and must be a permutation of all sources.
- All accumulator offsets are applied to the sources in `correctionsApplyMask`, by default the table only. Every other owner (launch, anti-lag, idle, overrun, cranking) still gets the **protective retard**: knock, coolant and charge temperature (`protectiveIgnitionMask`), retard only, never advance. EMU PRO drops knock retard in these modes; see `EMU_LESSONS.md` L1.
- Owner changes are rate limited by the rate of the selected owner. A rate of 0 means an immediate change. Only the owner's base angle is ramped; corrections are added after the ramp, so a knock retard acts in the same cycle (L1b).
- A non-finite request is ignored. An invalid configuration, a non-finite table angle or a non-finite dt gives `safeAdvance` and sets `fault`.

## rusEFI simulator, shadow mode

Source: `firmware/rusefi_sim/`. rusEFI is not modified: the simulator Makefile includes `$(BOARD_DIR)/board_common.mk`, which adds the arbitration sources and `p8_arbitration_shadow.cpp`.

- Hook: `custom_board_getCylinderIgnitionTrim`. rusEFI calls it right after it computes the corrected advance of the cycle. On cylinder 0 the glue runs `IgnitionArbiter` on the same inputs and compares; it returns the stock per-cylinder trim, so rusEFI behaviour is unchanged.
- Inputs: owner (cranking / anti-lag / launch spark retard / idle / table) with rusEFI's wrapped base advance, knock retard (protective) and the limp/soft-limiter retard. `correctionsApplyMask` covers every owner, because rusEFI applies both retards in every mode (`engine2.cpp`). Expected difference: scaled-channel quantization only (tolerance 0.1 deg).
- Scenario `P8_SIM_SCENARIO=knock` sends knock events through rusEFI's own `KnockController::onKnockSenseCompleted` (cycles 10-49 while cranking, 600-999 running) and sets aggression 10 %, max retard 8 deg, `knockSuppressMinTps` 0.
- Run inside WSL: `bash Power8GDI/firmware/rusefi_sim/run_sim_shadow.sh ~/rusefi 15`.

Result 2026-10-21, rusEFI master `f911562`, WSL Ubuntu 24.04, 15 s at the simulator's emulated 1200 rpm:

| scenario | cycles | mismatches | max delta | knock cycles | max knock retard | owners seen |
|---|---|---|---|---|---|---|
| none | 3001 | 0 | 0.000 deg | 0 | 0 | cranking 51, table 2950 |
| knock | 3001 | 0 | 0.017 deg | 1496 | 7.99 deg | knock while cranking and on the table |

Limits of this result: idle, overrun, anti-lag and launch owners were not reached by the default simulator setup; the limiter retard stayed 0; the ramp is not compared (rusEFI has none). The Power8GDI default (strategy offsets for the table only, protective retard for every owner) is not driving anything yet: applying the arbiter output through the trim hooks is the next step.

Observed in rusEFI while mapping: CLT/IAT timing corrections are skipped during cranking unless `useAdvanceCorrectionsForCranking` is set; knock retard is applied in all modes.

## Not done yet

- rusEFI integration: mapping onto rusEFI engine modules / limp manager / ignition and fuel computers, and the TunerStudio configuration.
- Driving the engine from the arbiter output in the simulator; idle/overrun/ALS/launch scenarios.
- Target build for the F7 board, timing measurements, engine validation.
