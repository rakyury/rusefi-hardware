# Power6GDI intervention arbitration (FW-03, host-only)

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
| cylinder cut | the largest percent wins | on a tie the **earlier** request wins; every non-zero requester is recorded as a candidate. Fuel and spark winners are also kept separately by `CutMode` (see `FuelArbiter`) |

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
- **Apply** (`P8_SIM_APPLY=1`): the Power6GDI default config, so strategy offsets apply for the table only and the protective retard applies for every owner. The hook returns stock trim + (arbiter − rusEFI), so the arbiter drives the spark angle. On the next cylinder the glue checks rusEFI's final `timingAdvance[0]` against the arbiter angle + trim + spark latency correction.
- Scenarios (`P8_SIM_SCENARIO`), all through rusEFI's own code paths and configuration:
  - `knock`: knock events via `KnockController::onKnockSenseCompleted` every 5 cycles from cycle 10 (aggression 10 %, max retard 8 deg, `knockSuppressMinTps` 0).
  - `owners`: knock as above, soft rev limiter (hard limit 1250 rpm, hysteresis 200, retard 4 deg, about 3 deg at the simulator's 1200 rpm), crank-to-idle taper 10 revolutions, and the engine walked through the owners every 300 cycles: table (TPS 50 %), idle (TPS 0, idle target 1200 rpm), coasting/overrun (idle target 700 rpm), ALS (always on), launch (always active, launch rpm 1000, launch angle 5 deg), table. TPS is a sensor mock (`Sensor::setMockValue`, as the `set_sensor_mock` console command).
- Run inside WSL: `bash Power6GDI/firmware/rusefi_sim/run_sim_arbitration.sh ~/rusefi 12`. It fails on any mismatch, an owner not reached, knock or limiter retard missing for an owner, a final-angle error, or an apply-mode difference outside the non-table cycles.

Result 2026-10-21, rusEFI master `f911562`, WSL Ubuntu 24.04, 12 s per run at the emulated 1200 rpm. Owner cycles are table / overrun / idle / ALS / launch / cranking.

| mode / scenario | cycles | mismatches | owner cycles | knock / limiter retard seen for | final-angle checks, errors | cycles different from rusEFI |
|---|---|---|---|---|---|---|
| shadow / none | 2401 | 0 | 2350/0/0/0/0/51 | — | — | 0 |
| shadow / knock | 2401 | 0 (max 0.015 deg) | 2350/0/0/0/0/51 | knock: cranking, table | — | 0 |
| shadow / owners | 2401 | 0 (max 0.015 deg) | 1150/300/300/300/300/51 | every owner / every owner | — | 0 |
| apply / owners | 2401 | 0 | 1150/300/300/300/300/51 | every owner / every owner | 2400, 0 (max 0.010 deg) | 1251 = all non-table cycles |

Example from the apply run, launch owner: launch angle 5.00, knock 7.99, limiter 2.99. rusEFI gives −5.98; Power6GDI gives −2.99 (knock kept, limiter retard not stacked on the launch angle).

Limits: the simulator runs at one constant speed (1200 rpm) with a mocked TPS; no load, no real knock signal, no ramp comparison (rusEFI has none). The arbiter covers ignition only: fuel, lambda, boost and cylinder cut are not wired. Simulator only: no F7 target build, no hardware, no engine.

Observed in rusEFI while mapping:
- CLT/IAT timing corrections are skipped during cranking unless `useAdvanceCorrectionsForCranking` is set; knock retard is applied in all modes.
- The idle table replaces the angle after the ALS correction is added, so at closed throttle with a separate idle table rusEFI idle silently wins over ALS. Power6GDI makes the owner priority explicit and configurable.

## Fuel, lambda and cylinder cut (`FuelArbiter`)

Source: `firmware/arbitration/fuel_arbiter.{h,cpp}`. Tests: `firmware/tests/test_fuel_arbitration.cpp` (run by `run_arbitration_tests.sh`). The cylinder count is a parameter (1..12, firing order validated as a permutation); the Power6GDI default is 6 with firing order 1-5-3-6-2-4. Tests use 4, 6 and 8.

- **Fuel multiplier per cylinder** = accumulator fuel factor × stock per-cylinder trim; 0 for a fuel-cut cylinder; 0 everywhere on any accumulator fuel cut.
- **Separate fuel and spark cut winners.** Each cut request names what it cuts (`CutMode::Fuel`, `Spark`, `FuelAndSpark`). The accumulator keeps the largest fuel request and the largest spark request separately (tie: earlier request). A larger spark-only request (ALS) therefore cannot hide a protective fuel cut (overboost). EMU keeps one winner with its type; see `EMU_LESSONS.md` L8.
- **Direct injection rule.** A spark cut whose winner is not in `sparkOnlyAllowedMask` (default: ALS, launch, rolling launch) is executed as a fuel+spark cut at the larger of the fuel and spark percentages: no raw fuel into a cylinder that does not fire.
- **Which cylinders.** An error accumulator gives the number of cylinders to cut this cycle, so the long-run fraction equals the request. Each cylinder carries a debt (its share minus its cuts); the largest debts are cut, so every cylinder takes its share within one cut. Equal debts prefer cylinders evenly spaced in firing order from a start that rotates every cycle (6 cylinders at 50 %: every other firing event, alternating halves). A plain rotating walk was tried first and aliased: 4 cylinders at 62.5 % cut two cylinders four times as often as the other two (`cutDistributionExactAndRotating` catches it).
- **Lambda target** = accumulator rule (offsets, then floors, then ceilings; the richer limit wins), then clamped to `[lambdaMin, lambdaMax]`. A sweep or test modulation is an offset (`LambdaSource::Sweep`), so it cannot pass a ceiling. EMU replaces the final target with the sweep value after its limits; see L7.
- **Closed-loop freeze** while any fuel or spark cut is active and for `closedLoopHoldCycles` afterwards: the sensor then sees air from cut cylinders or unburnt mixture.
- Faults: invalid configuration → fuel cut on every cylinder; non-finite base lambda → `safeLambda`; non-finite or non-positive trim → 1.0 for that cylinder. Each sets `fault`.

## rusEFI simulator: fuel and cylinder cut

Source: `firmware/rusefi_sim/p8_fuel_sim.cpp`, check `run_sim_fuel.sh`.

- Hook: `custom_board_getCylinderFuelTrim`, called per cylinder in `engine2.cpp`; rusEFI multiplies the result with the untrimmed mass, the bank trim and the knock fuel trim. Setting the hook replaces rusEFI's trim table lookup, so the glue computes the stock trim itself (same `interpolate3d` as `fuel_math.cpp`).
- Inputs on cylinder 0: knock fuel trim (protective enrichment); rusEFI `LimpManager::allowInjection()` mapped by `ClearReason` (hard limit, boost, oil, lambda guard, stop, ETB, GDI → fuel-cut sources; launch and injector duty → 100 % fuel cylinder cut; anything else → `FuelCutSource::External`); `fuelComputer.targetLambda` as the base lambda.
- **Shadow** (default): no Power6GDI strategy requests. The arbiter's per-cylinder multipliers must equal stock trim × knock trim, it must cut every cylinder exactly when rusEFI cuts injection, and its lambda target must equal rusEFI's. Stock trim is returned.
- **Apply** (`P8_SIM_APPLY=1`, scenario `fuelcut` only): additionally a progressive soft rev-limit cylinder cut (Power6GDI strategy, fuel only, 0..100 % across rusEFI's soft window `[limit − hysteresis, limit]`). The hook returns arbiter multiplier ÷ knock trim, so the arbiter drives `injectionMass[]`. The next cycle checks that cut cylinders have mass exactly 0 and the others the arbiter ratio.
- Scenario `fuelcut`, five phases of 300 cycles: knock fuel trim; soft window (limit 1300, hysteresis 200: 50 % at 1200 rpm); hard-limit fuel cut (limit 1100); launch fuel cut; table.
- `P8_SIM_CYLINDERS=6` switches the simulator to six cylinders, firing order 1-5-3-6-2-4, through rusEFI's normal configuration-change path once rusEFI allows it (`hasRememberedConfiguration`). The check runs 6 and 4 cylinders.

Result 2026-11-05, rusEFI master `f911562`, 12 s per run at the emulated 1200 rpm:

| cylinders / mode | cycles | mismatches | mass checks / errors | rusEFI full-cut cycles = arbiter all-cut | cut reasons seen | soft-cut cycles | cut events / expected | per cylinder |
|---|---|---|---|---|---|---|---|---|
| 6 / shadow | 2401 | 0 | 2400 / 0 | 599 = 599 | hard limit, launch | 0 | — | — |
| 6 / apply | 2401 | 0 | 2400 / 0 | 599 = 599 (599 cycles with mass 0 on every cylinder) | hard limit, launch | 300 | 900 / 900.0 | 150 each |
| 4 / shadow | 2401 | 0 | 2400 / 0 | 599 = 599 | hard limit, launch | 0 | — | — |
| 4 / apply | 2401 | 0 | 2400 / 0 | 599 = 599 (599 with mass 0) | hard limit, launch | 300 | 600 / 600.0 | 150 each |

Knock fuel trim reached rusEFI's 1.30 limit in every run. The ignition check (`run_sim_arbitration.sh`) still passes unchanged with the fuel glue in the same build.

Limits:
- Lambda target and closed-loop freeze are computed and compared, not applied: rusEFI has no hook for them. In the scenario rusEFI's target stays 1.000, so the lambda comparison is a pass-through check only. Spark-cut masks are not applied.
- A zero-trim cut relies on `getInjectionDuration(0) == 0`. On a target the cut must move to the injection event: `wallFuel.adjust()` runs on the per-cylinder mass before the duration, and the HPFP feed-forward reads `injectionMass[0] × cylinders`, so a cut of cylinder 0 would zero the pump feed-forward.
- One constant speed, no load, synthetic knock. Simulator only.

## Not done yet

- TunerStudio configuration for the arbiter; a real board target instead of the simulator glue.
- Boost arbitration wired into rusEFI; lambda target and closed-loop freeze applied; spark-cut masks applied.
- Cylinder cut at the injection event instead of a zero trim (wall fuel, HPFP feed-forward).
- Target build for the F7 board, timing measurements, engine validation.
