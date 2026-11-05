# Power8GDI intervention arbitration (FW-03, host-only)

Status: **host-tested; runs in the rusEFI simulator, in shadow mode and driving the spark angle (apply mode). Not on hardware.** No MCU, timer or engine-scheduler calls. Not validated on an engine.

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

## rusEFI simulator: shadow and apply modes

Source: `firmware/rusefi_sim/`. rusEFI is not modified: the simulator Makefile includes `$(BOARD_DIR)/board_common.mk`, which adds the arbitration sources and `p8_arbitration_sim.cpp`.

- Hook: `custom_board_getCylinderIgnitionTrim`. rusEFI calls it right after it computes the corrected advance of the cycle. On cylinder 0 the glue runs `IgnitionArbiter` on the same inputs.
- Inputs: the angle owner with rusEFI's wrapped base advance, knock retard (protective) and the limp/soft-limiter retard (strategy). Owner order follows rusEFI `getRunningAdvance()`: cranking, launch (returns early), idle / coasting table (replaces the angle, ALS included), ALS correction, table. Coasting with `useIdleAdvanceWhileCoasting` is mapped to the Overrun owner.
- **Shadow** (default): `correctionsApplyMask` covers every owner, because rusEFI applies both retards in every mode (`engine2.cpp`). The arbiter angle must equal rusEFI's (tolerance 0.1 deg, scaled channels); the stock trim is returned.
- **Apply** (`P8_SIM_APPLY=1`): the Power8GDI default config, so strategy offsets apply for the table only and the protective retard applies for every owner. The hook returns stock trim + (arbiter − rusEFI), so the arbiter drives the spark angle. On the next cylinder the glue checks rusEFI's final `timingAdvance[0]` against the arbiter angle + trim + spark latency correction.
- Scenarios (`P8_SIM_SCENARIO`), all through rusEFI's own code paths and configuration:
  - `knock`: knock events via `KnockController::onKnockSenseCompleted` every 5 cycles from cycle 10 (aggression 10 %, max retard 8 deg, `knockSuppressMinTps` 0).
  - `owners`: knock as above, soft rev limiter (hard limit 1250 rpm, hysteresis 200, retard 4 deg, about 3 deg at the simulator's 1200 rpm), crank-to-idle taper 10 revolutions, and the engine walked through the owners every 300 cycles: table (TPS 50 %), idle (TPS 0, idle target 1200 rpm), coasting/overrun (idle target 700 rpm), ALS (always on), launch (always active, launch rpm 1000, launch angle 5 deg), table. TPS is a sensor mock (`Sensor::setMockValue`, as the `set_sensor_mock` console command).
- Run inside WSL: `bash Power8GDI/firmware/rusefi_sim/run_sim_arbitration.sh ~/rusefi 12`. It fails on any mismatch, an owner not reached, knock or limiter retard missing for an owner, a final-angle error, or an apply-mode difference outside the non-table cycles.

Result 2026-10-21, rusEFI master `f911562`, WSL Ubuntu 24.04, 12 s per run at the emulated 1200 rpm. Owner cycles are table / overrun / idle / ALS / launch / cranking.

| mode / scenario | cycles | mismatches | owner cycles | knock / limiter retard seen for | final-angle checks, errors | cycles different from rusEFI |
|---|---|---|---|---|---|---|
| shadow / none | 2401 | 0 | 2350/0/0/0/0/51 | — | — | 0 |
| shadow / knock | 2401 | 0 (max 0.015 deg) | 2350/0/0/0/0/51 | knock: cranking, table | — | 0 |
| shadow / owners | 2401 | 0 (max 0.015 deg) | 1150/300/300/300/300/51 | every owner / every owner | — | 0 |
| apply / owners | 2401 | 0 | 1150/300/300/300/300/51 | every owner / every owner | 2400, 0 (max 0.010 deg) | 1251 = all non-table cycles |

Example from the apply run, launch owner: launch angle 5.00, knock 7.99, limiter 2.99. rusEFI gives −5.98; Power8GDI gives −2.99 (knock kept, limiter retard not stacked on the launch angle).

Limits: the simulator runs at one constant speed (1200 rpm) with a mocked TPS; no load, no real knock signal, no ramp comparison (rusEFI has none). The arbiter covers ignition only: fuel, lambda, boost and cylinder cut are not wired. Simulator only: no F7 target build, no hardware, no engine.

Observed in rusEFI while mapping:
- CLT/IAT timing corrections are skipped during cranking unless `useAdvanceCorrectionsForCranking` is set; knock retard is applied in all modes.
- The idle table replaces the angle after the ALS correction is added, so at closed throttle with a separate idle table rusEFI idle silently wins over ALS. Power8GDI makes the owner priority explicit and configurable.

## Not done yet

- TunerStudio configuration for the arbiter; a real board target instead of the simulator glue.
- Fuel, lambda, boost and cylinder-cut arbitration wired into rusEFI.
- Target build for the F7 board, timing measurements, engine validation.
