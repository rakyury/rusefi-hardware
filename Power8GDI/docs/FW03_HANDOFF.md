# FW-03 handoff: intervention arbitration on rusEFI

Updated 2026-10-23. Read this first, then `ARBITRATION.md` and `EMU_LESSONS.md`.

## 1. Goal and principle

Power8GDI firmware is our own firmware on top of rusEFI. FW-03 builds the **intervention arbitration**: one place where limiters, launch, anti-lag, knock, traction, protections and similar features request fuel, ignition, lambda, boost and cylinder-cut changes. Fixed rules combine the requests, so the result never depends on hidden call order.

**The ECUMASTER EMU PRO analysis is a list of problems to avoid, not a design to copy.** The analysis lives in a separate repository, `C:\projects\emu-pro-firmware-research` (`rea/REPORT_RU.md`, `rea/PSEUDOCODE_RU.md`). Every design decision is written as: EMU problem (with evidence) → what Power8GDI does instead → the test that checks it. See `EMU_LESSONS.md`. Do not write "behaves like EMU PRO" in code, docs or commits.

Project rules (`Power8GDI/AGENTS.md`):
- Never modify upstream rusEFI sources; Power8GDI code lives under `Power8GDI/`.
- Feature branch → PR into `power8gdi-rev-a`.
- Never claim hardware or engine readiness without measurements.
- The owner asked for verification in the **rusEFI simulator**, not on their own HIL rig (R2.EngineSimulator is not used here).

## 2. Where things are

| what | where |
|---|---|
| repository | `rakyury/rusefi-hardware` (fork), local sparse clone `C:\projects\rusefi-hardware` (only `Power8GDI/` + `.github`) |
| host-testable modules | `Power8GDI/firmware/arbitration/` (accumulator, task cycle, ignition arbiter) |
| host tests | `Power8GDI/firmware/tests/test_arbitration.cpp`, `run_arbitration_tests.sh`, `run_all_host_tests.sh` |
| simulator glue | `Power8GDI/firmware/rusefi_sim/` (`board_common.mk`, `p8_arbitration_sim.cpp`, `run_sim_arbitration.sh`) |
| design docs | `Power8GDI/docs/ARBITRATION.md`, `Power8GDI/docs/EMU_LESSONS.md` |
| task card | `Power8GDI/workstreams/FW-03.md` |
| rusEFI for the simulator | WSL Ubuntu-24.04, `~/rusefi` (ext4, not `/mnt/c`), master `f911562` |

## 3. Branches and PRs

| PR | branch | base | content | state |
|---|---|---|---|---|
| #2 | `power8gdi/fw-03-arbitration` | `power8gdi-rev-a` | host-tested arbitration; protective knock retard for every angle owner (`313b4f1`); `EMU_LESSONS.md` | open, not reviewed |
| #3 | `power8gdi/fw-03-sim` | `power8gdi/fw-03-arbitration` (stacked) | simulator glue, shadow + apply modes, scenarios (`402e993`, `ed42a70`) | open, not reviewed |
| #1 | `codex/power8gdi-resume-20261021` | — | earlier electrical/PCB/offline tools work by another agent | draft, not FW-03 |

Merge order: #2 first, then retarget #3 to `power8gdi-rev-a`. Nothing is merged yet.

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
cd /mnt/c/projects/rusefi-hardware/Power8GDI/firmware && bash tests/run_all_host_tests.sh
# Windows Git Bash
export PATH=/c/msys64/ucrt64/bin:$PATH
SANITIZE=" " bash Power8GDI/firmware/tests/run_arbitration_tests.sh
```

Simulator check (builds the simulator with `BOARD_DIR` set to the glue, then four runs with pass/fail conditions):

```bash
# inside WSL
bash /mnt/c/projects/rusefi-hardware/Power8GDI/firmware/rusefi_sim/run_sim_arbitration.sh ~/rusefi 12
# from Windows Git Bash: path conversion must be off
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/projects/rusefi-hardware/Power8GDI/firmware/rusefi_sim/run_sim_arbitration.sh
```

Expected last line: `Power8GDI arbitration in rusEFI simulator: PASS`.

Manual runs: `P8_SIM_SCENARIO=none|knock|owners`, `P8_SIM_APPLY=0|1`, `P8_SIM_DEBUG=1` (idle phase / TPS / rpm every 100 cycles), then `./build/rusefi_simulator <seconds>` in `~/rusefi/simulator`. The report line starts with `P8SHADOW`.

## 6. How the simulator integration works

- `simulator/Makefile` includes `$(BOARD_DIR)/board_common.mk` when `BOARD_DIR` is set. Ours adds the arbitration sources and the glue to `MODULES_CPPSRC`. Upstream is untouched. The default board's `prepend.txt` has no `EFI_LUA`/`EFI_LTFT_CONTROL` defines, so overriding `BOARD_DIR` loses nothing.
- The hook is `custom_board_getCylinderIgnitionTrim` (`board_overrides.h`). rusEFI calls it in `engine2.cpp` right after `correctedIgnitionAdvance`, inside the same cycle. The simulator's `setup_custom_board_overrides()` is fixed upstream, so the hook is installed by a static initializer. That is safe: `std::optional<fn ptr>` is constant-initialized.
- Cylinder 0 call: build the accumulator from rusEFI's knock retard (protective) and the limp/soft-limiter retard (strategy), pick the angle owner, run `IgnitionArbiter`. Cylinder 1 call (apply mode): check rusEFI's final `engineState.timingAdvance[0]`.
- Owner order follows rusEFI `getRunningAdvance()`: cranking → launch (returns early) → idle / coasting table (replaces the angle) → ALS correction → table.
- Shadow: mask = every owner (rusEFI semantics), so the arbiter must equal rusEFI. Apply: Power8GDI default config. The trim hook returns stock trim + (arbiter − rusEFI).

## 7. Results (rusEFI `f911562`, 12 s per run, emulated 1200 rpm)

Owner cycles below are table / overrun / idle / ALS / launch / cranking.

| mode / scenario | mismatches | owner cycles | notes |
|---|---|---|---|
| shadow / none | 0 | 2350/0/0/0/0/51 | |
| shadow / knock | 0 | 2350/0/0/0/0/51 | knock up to 7.99°, cranking and table |
| shadow / owners | 0 | 1150/300/300/300/300/51 | knock + limiter retard for every owner |
| apply / owners | 0 | 1150/300/300/300/300/51 | 2400 final-angle checks, 0 errors (max 0.010°); differs from rusEFI in exactly the 1251 non-table cycles |

Host tests: arbitration, Map4D, 4D blob, dual HPFP, dual PT2001: all PASS.

## 8. Decisions made (do not reopen without a reason)

1. **Protective retard for every owner** (knock, coolant, charge temperature; retard only, never advance). EMU drops knock retard when launch/ALS/idle/overrun/cranking owns the angle (L1).
2. **Ramp only the owner's base angle**; corrections are added after the ramp, so a knock retard is never delayed (L1b).
3. **Strategy offsets (limiters, traction, shift...) apply to the table only by default** (`correctionsApplyMask`), so they do not stack on a deliberate launch/ALS angle. This is configurable. It is a design choice, not a proven optimum; revisit with the tuner if needed.
4. **Lambda: on a floor/ceiling conflict the richer limit wins.** EMU lets the "minimum" floor override the nitrous ceiling, which gives a lean mixture on nitrous (L2).
5. Cylinder-cut tie-break = explicit registration order, all requesters logged in `cutCandidateMask()` (L3).

## 9. Known limits

- The simulator runs at one constant 1200 rpm, no load. TPS is a sensor mock (`Sensor::setMockValue`) and knock is synthetic (`KnockController::onKnockSenseCompleted`).
- Only ignition is wired into rusEFI. Fuel, lambda, boost and cylinder cut exist only as host-tested accumulator logic.
- Not mapped: flat-shift torque reduction owner, nitrous ignition retard.
- No F7 target build, no TunerStudio config, no hardware, no engine.
- `EMU_LESSONS.md` L6 (explicit rounding for float → int channels) is still open.

## 10. Next steps (owner has not chosen yet)

1. **Fuel / cylinder cut via `custom_board_getCylinderFuelTrim`**: same shadow → apply pattern as ignition; scenarios with the rev limiter fuel cut and launch.
2. **TunerStudio configuration** for the arbiter (owner priority, `correctionsApplyMask`, protective mask, limits).
3. **F7 target build**: a Power8GDI board directory for the real STM32F7 instead of the simulator glue.
4. Before fuel work, check `fuel_math.cpp`: `getCylinderFuelTrim` replaces the per-cylinder trim table when the hook is set, so the glue must call the stock trim itself (as the ignition glue does with `getInterpolatedIgnitionTrim`).

## 11. Gotchas

- In the simulator, `efiPrintf` is not shown in stdout after init: use `printf` in glue code.
- Idle in the simulator needs a valid TPS (mock) and a short `afterCrankingIACtaperDuration`, or the idle controller stays in `CrankToIdleTaper` for the whole run.
- The Claude Bash tool eats one level of backslashes in heredocs: `\n` inside C strings becomes a real newline. Edit such lines with an editor, not a heredoc.
- From Git Bash, run `wsl ... /mnt/c/...` with `MSYS_NO_PATHCONV=1`. Pass environment variables through a script file run inside WSL.
- The rusEFI repository is large. Build in the WSL ext4 file system (`~/rusefi`), not in `/mnt/c`.
