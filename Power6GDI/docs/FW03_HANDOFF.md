# FW-03 handoff: intervention arbitration on rusEFI

Updated 2026-11-05. Read this first, then `ARBITRATION.md` and `EMU_LESSONS.md`.

**What changed on 2026-11-05:** FW-03 (PRs #2 and #3) is merged into the Sport GDI6 integration (branch `power6gdi/fw-03-gdi6`, stacked on PR #4 `codex/sport-gdi6-20261025`). Fuel, lambda target and per-cylinder cut arbitration (`FuelArbiter`) is host-tested and wired into the rusEFI simulator through the fuel trim hook, in shadow and apply modes, with 6 and 4 cylinders. Active scope is six cylinders (`docs/SCOPE_2026_10_25_SPORT_GDI6.md`); the cylinder count is a parameter.

## 1. Goal and principle

Power6GDI firmware is our own firmware on top of rusEFI. FW-03 builds the **intervention arbitration**: one place where limiters, launch, anti-lag, knock, traction, protections and similar features request fuel, ignition, lambda, boost and cylinder-cut changes. Fixed rules combine the requests, so the result never depends on hidden call order.

**The ECUMASTER EMU PRO analysis is a list of problems to avoid, not a design to copy.** The analysis lives in a separate repository, `C:\projects\emu-pro-firmware-research` (`rea/REPORT_RU.md`, `rea/PSEUDOCODE_RU.md`). Every design decision is written as: EMU problem (with evidence) → what Power6GDI does instead → the test that checks it. See `EMU_LESSONS.md`. Do not write "behaves like EMU PRO" in code, docs or commits.

Project rules (`Power6GDI/AGENTS.md`):
- Never modify upstream rusEFI sources; Power6GDI code lives under `Power6GDI/`.
- Feature branch → PR into `power8gdi-rev-a`.
- Never claim hardware or engine readiness without measurements.
- The owner asked for verification in the **rusEFI simulator**, not on their own HIL rig (R2.EngineSimulator is not used here).

## 2. Where things are

| what | where |
|---|---|
| repository | `rakyury/rusefi-hardware` (fork), local sparse clone `C:\projects\rusefi-hardware` (only `Power6GDI/` + `.github`) |
| host-testable modules | `Power6GDI/firmware/arbitration/` (accumulator, task cycle, ignition arbiter, fuel arbiter) |
| host tests | `Power6GDI/firmware/tests/test_arbitration.cpp`, `test_fuel_arbitration.cpp`, `run_arbitration_tests.sh`, `run_all_host_tests.sh`; also `python Power6GDI/tools/run_checks.py --suite host` (entries `arbitration`, `fuel-arbitration`) |
| simulator glue | `Power6GDI/firmware/rusefi_sim/` (`board_common.mk`, `p8_arbitration_sim.cpp` + `run_sim_arbitration.sh` for ignition, `p8_fuel_sim.cpp` + `run_sim_fuel.sh` for fuel / cylinder cut) |
| design docs | `Power6GDI/docs/ARBITRATION.md`, `Power6GDI/docs/EMU_LESSONS.md` |
| task card | `Power6GDI/workstreams/FW-03.md` |
| rusEFI for the simulator | WSL Ubuntu-24.04, `~/rusefi` (ext4, not `/mnt/c`), master `f911562` |

## 3. Branches and PRs

| PR | branch | base | content | state |
|---|---|---|---|---|
| #2 | `power8gdi/fw-03-arbitration` | `power8gdi-rev-a` | host-tested arbitration; protective knock retard for every angle owner (`313b4f1`); `EMU_LESSONS.md` | open, not reviewed |
| #3 | `power8gdi/fw-03-sim` | `power8gdi/fw-03-arbitration` (stacked) | simulator glue, shadow + apply modes, scenarios (`402e993`, `ed42a70`) | open, not reviewed |
| #1 | `codex/power8gdi-resume-20261021` | — | earlier electrical/PCB/offline tools work by another agent | draft, not FW-03 |
| #4 | `codex/sport-gdi6-20261025` | `power8gdi-rev-a` | Sport GDI6 integration (schematic, BOM, DI dispatch guard, configurator) | draft |
| — | `power6gdi/fw-03-gdi6` | `codex/sport-gdi6-20261025` (stacked on #4) | merge of #3 (with #2) into the GDI6 integration; fuel / lambda / cylinder-cut arbitration; simulator fuel glue | local, not pushed |

Nothing is merged into `power8gdi-rev-a` yet. `power6gdi/fw-03-gdi6` already contains #2 and #3, so once #4 is merged, this branch can be proposed instead of #2/#3.

## 4. Environment setup (Windows server + WSL)

Already done on server `WIN-V7K2CF64NGO`. To recreate elsewhere:

```bash
wsl --install -d Ubuntu-24.04            # needs VirtualMachinePlatform + a reboot
# inside WSL:
sudo apt-get install -y build-essential gcc-multilib g++-multilib git make
git clone --recurse-submodules https://github.com/rusefi/rusefi.git ~/rusefi
make -C ~/rusefi/simulator -j$(nproc)   # stock simulator, about 1 min on 16 cores
```

The first build generates `ramdisk_image*.h` and `VariableRegistryValues.java` in the rusEFI tree. Those are build output; leave them uncommitted.

## 5. How to verify

Host tests (Windows MinGW has no libubsan, so `SANITIZE=" "` disables it; WSL runs with UBSan):

```bash
# WSL, full set with UBSan
cd /mnt/c/projects/rusefi-hardware/Power6GDI/firmware && bash tests/run_all_host_tests.sh
# Windows Git Bash
export PATH=/c/msys64/ucrt64/bin:$PATH
SANITIZE=" " bash Power6GDI/firmware/tests/run_arbitration_tests.sh
```

Simulator check (builds the simulator with `BOARD_DIR` set to the glue, then four runs with pass/fail conditions):

```bash
# inside WSL
bash /mnt/c/projects/rusefi-hardware/Power6GDI/firmware/rusefi_sim/run_sim_arbitration.sh ~/rusefi 12
# from Windows Git Bash: path conversion must be off
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/projects/rusefi-hardware/Power6GDI/firmware/rusefi_sim/run_sim_arbitration.sh
```

Expected last line: `Power6GDI arbitration in rusEFI simulator: PASS`.

Fuel / cylinder-cut check (same build, four runs: 6 and 4 cylinders, shadow and apply):

```bash
bash /mnt/c/projects/rusefi-hardware/Power6GDI/firmware/rusefi_sim/run_sim_fuel.sh ~/rusefi 12
```

Expected last line: `Power6GDI fuel arbitration in rusEFI simulator: PASS`.

Manual runs: `P8_SIM_SCENARIO=none|knock|owners|fuelcut`, `P8_SIM_APPLY=0|1`, `P8_SIM_CYLINDERS=6`, `P8_SIM_DEBUG=1` (idle phase / TPS / rpm every 100 cycles), then `./build/rusefi_simulator <seconds>` in `~/rusefi/simulator`. Report lines start with `P8SHADOW` (ignition) and `P8FUEL` (fuel).

If the build fails with `No rule to make target .../arbitration/...cpp`, the simulator's dependency files point at another checkout of the glue: delete `~/rusefi/simulator/.dep/{intervention_accumulator,task_cycle,ignition_arbiter,fuel_arbiter,p8_arbitration_sim,p8_fuel_sim}.o.d` and rebuild.

## 6. How the simulator integration works

- `simulator/Makefile` includes `$(BOARD_DIR)/board_common.mk` when `BOARD_DIR` is set. Ours adds the arbitration sources and the glue to `MODULES_CPPSRC`. Upstream is untouched. The default board's `prepend.txt` has no `EFI_LUA`/`EFI_LTFT_CONTROL` defines, so overriding `BOARD_DIR` loses nothing.
- The hook is `custom_board_getCylinderIgnitionTrim` (`board_overrides.h`). rusEFI calls it in `engine2.cpp` right after `correctedIgnitionAdvance`, inside the same cycle. The simulator's `setup_custom_board_overrides()` is fixed upstream, so the hook is installed by a static initializer. That is safe: `std::optional<fn ptr>` is constant-initialized.
- Cylinder 0 call: build the accumulator from rusEFI's knock retard (protective) and the limp/soft-limiter retard (strategy), pick the angle owner, run `IgnitionArbiter`. Cylinder 1 call (apply mode): check rusEFI's final `engineState.timingAdvance[0]`.
- Owner order follows rusEFI `getRunningAdvance()`: cranking → launch (returns early) → idle / coasting table (replaces the angle) → ALS correction → table.
- Shadow: mask = every owner (rusEFI semantics), so the arbiter must equal rusEFI. Apply: Power6GDI default config. The trim hook returns stock trim + (arbiter − rusEFI).
- Fuel: hook `custom_board_getCylinderFuelTrim` (`fuel_math.cpp`, called per cylinder from `engine2.cpp`). It replaces rusEFI's trim table lookup, so the glue computes the stock trim with the same `interpolate3d`. Cylinder 0 call: knock fuel trim, `LimpManager::allowInjection()` reason and `fuelComputer.targetLambda` go into the accumulator and `FuelArbiter`. Shadow returns the stock trim; apply returns arbiter multiplier ÷ knock trim. The next cycle compares rusEFI's `injectionMass[]` with what was returned. Details and limits: `ARBITRATION.md`, section "rusEFI simulator: fuel and cylinder cut".

## 7. Results (rusEFI `f911562`, 12 s per run, emulated 1200 rpm)

Owner cycles below are table / overrun / idle / ALS / launch / cranking.

| mode / scenario | mismatches | owner cycles | notes |
|---|---|---|---|
| shadow / none | 0 | 2350/0/0/0/0/51 | |
| shadow / knock | 0 | 2350/0/0/0/0/51 | knock up to 7.99°, cranking and table |
| shadow / owners | 0 | 1150/300/300/300/300/51 | knock + limiter retard for every owner |
| apply / owners | 0 | 1150/300/300/300/300/51 | 2400 final-angle checks, 0 errors (max 0.010°); differs from rusEFI in exactly the 1251 non-table cycles |

Host tests: arbitration, Map4D, 4D blob, dual HPFP, dual PT2001: all PASS.

Re-run 2026-11-05 on `power6gdi/fw-03-gdi6` (after merging into the GDI6 integration): identical numbers.

Fuel / cylinder cut, scenario `fuelcut`, 2026-11-05, same rusEFI and speed:

| cylinders / mode | mismatches | injectionMass checks / errors | full-cut cycles rusEFI = arbiter | soft cylinder cut |
|---|---|---|---|---|
| 6 / shadow | 0 | 2400 / 0 | 599 = 599 | not requested |
| 6 / apply | 0 | 2400 / 0 | 599 = 599, mass 0 on every cylinder | 300 cycles, 900 cut events = 900.0 expected, 150 per cylinder |
| 4 / shadow | 0 | 2400 / 0 | 599 = 599 | not requested |
| 4 / apply | 0 | 2400 / 0 | 599 = 599, mass 0 on every cylinder | 300 cycles, 600 = 600.0, 150 per cylinder |

Host tests 2026-11-05 (WSL, g++ 13.3, UBSan): `run_all_host_tests.sh` all PASS (now including `test_fuel_arbitration`), GDI6 dispatch guard PASS (16 scenario groups).

## 8. Decisions made (do not reopen without a reason)

1. **Protective retard for every owner** (knock, coolant, charge temperature; retard only, never advance). EMU drops knock retard when launch/ALS/idle/overrun/cranking owns the angle (L1).
2. **Ramp only the owner's base angle**; corrections are added after the ramp, so a knock retard is never delayed (L1b).
3. **Strategy offsets (limiters, traction, shift...) apply to the table only by default** (`correctionsApplyMask`), so they do not stack on a deliberate launch/ALS angle. This is configurable. It is a design choice, not a proven optimum; revisit with the tuner if needed.
4. **Lambda: on a floor/ceiling conflict the richer limit wins.** EMU lets the "minimum" floor override the nitrous ceiling, which gives a lean mixture on nitrous (L2).
5. Cylinder-cut tie-break = explicit registration order, all requesters logged in `cutCandidateMask()` (L3).
6. **Fuel and spark cut winners are separate** (`CutMode`): a larger spark-only request cannot hide a fuel cut (L8).
7. **Direct injection:** a spark cut from a source not allowed spark-only (default allowed: ALS, launch, rolling launch) is executed as a fuel+spark cut at the larger percentage.
8. **Cut cylinders by debt**, not by a rotating walk: exact long-run share, every cylinder within one cut, equal shares spread in firing order.
9. **Lambda sweep / test modulation is an offset**, ceilings last (L7).
10. **Closed-loop freeze** during any cut plus a hold time.

## 9. Known limits

- The simulator runs at one constant 1200 rpm, no load. TPS is a sensor mock (`Sensor::setMockValue`) and knock is synthetic (`KnockController::onKnockSenseCompleted`).
- Ignition and per-cylinder fuel (multipliers, fuel cylinder cut) are wired into rusEFI. Lambda target and closed-loop freeze are computed and compared but not applied (no rusEFI hook); in the scenario rusEFI's target stays 1.000, so that comparison is pass-through only. Spark-cut masks and boost are not wired.
- The fuel cut is a zero trim. On a target it must move to the injection event: `wallFuel.adjust()` acts on the per-cylinder mass, and the HPFP feed-forward reads `injectionMass[0] × cylinders`, so a cut of cylinder 0 would zero the pump feed-forward.
- Not mapped: flat-shift torque reduction owner, nitrous ignition retard.
- No F7 target build, no TunerStudio config, no hardware, no engine.
- `EMU_LESSONS.md` L6 (explicit rounding for float → int channels) is still open.

## 10. Next steps (owner has not chosen yet)

1. **Cut at the injection event and spark cut**: per-cylinder fuel and spark masks applied where rusEFI schedules the events, so wall fuel and the HPFP feed-forward stay correct; then the GDI6 dispatch guard (`dual_gdi/gdi6_dispatch_guard`) sees the same masks.
2. **Lambda target / closed-loop freeze**: needs a hook or a board-level replacement for the target lambda and STFT hold.
3. **TunerStudio or own-client configuration** for the arbiter (owner priority, `correctionsApplyMask`, protective mask, `sparkOnlyAllowedMask`, limits).
4. **F7 target build**: a Power6GDI board directory for the real STM32F7 instead of the simulator glue.

Done 2026-11-05: fuel / cylinder cut via `custom_board_getCylinderFuelTrim` (the glue computes the stock trim itself).

## 11. Gotchas

- In the simulator, `efiPrintf` is not shown in stdout after init: use `printf` in glue code.
- Idle in the simulator needs a valid TPS (mock) and a short `afterCrankingIACtaperDuration`, or the idle controller stays in `CrankToIdleTaper` for the whole run.
- The Claude Bash tool eats one level of backslashes in heredocs: `\n` inside C strings becomes a real newline. Edit such lines with an editor, not a heredoc.
- From Git Bash, run `wsl ... /mnt/c/...` with `MSYS_NO_PATHCONV=1`. Pass environment variables through a script file run inside WSL.
- The rusEFI repository is large. Build in the WSL ext4 file system (`~/rusefi`), not in `/mnt/c`.
