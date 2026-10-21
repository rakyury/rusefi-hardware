# Power8GDI intervention arbitration (FW-03, host-only)

Status: **host-tested reference logic, not yet wired into a rusEFI build or the simulator.** No MCU, timer or engine-scheduler calls. Not validated on an engine.

Source: `firmware/arbitration/`. Tests: `firmware/tests/test_arbitration.cpp`, `bash firmware/tests/run_arbitration_tests.sh`.

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
- Accumulator offsets are applied only to the sources in `correctionsApplyMask`, by default the table only. This is a deliberate default and can be changed in configuration.
- Source changes are rate limited by the rate of the selected source. A rate of 0 means an immediate change.
- A non-finite request is ignored. An invalid configuration, a non-finite table angle or a non-finite dt gives `safeAdvance` and sets `fault`.

## Not done yet

- rusEFI integration: mapping onto rusEFI engine modules / limp manager / ignition and fuel computers, and the TunerStudio configuration.
- Simulator run, target build for the F7 board, timing measurements, engine validation.
