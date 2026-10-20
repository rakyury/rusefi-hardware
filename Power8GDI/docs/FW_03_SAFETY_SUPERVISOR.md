# FW-03: dual HPFP safety policy and host evidence

Date: 2026-10-21. Base: `1ff4b732c121a33e1f15e169df428c90be87b3c7`.
Scope: controller-independent C++17 policy and host tests. **No MCU target,
electrical pulse scheduler, firmware flash, ECU connection or hardware test.**

## Defect and contract

`evaluateDualHpfp()` deliberately evaluates only the current input. A transient
driver/synchronization/sensor fault disappears from its output on the first valid
sample. Using that pure allocator as an enable supervisor would therefore restart
both pumps and release GDI inhibition without an explicit re-arm. The system
safety requirement in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) needs a
persistent policy layer. The allocator's existing API and behavior are preserved.

`DualHpfpSafetySupervisor` is that separate policy layer. Its output still uses
`SupervisorOutput`; it never drives a GPIO or schedules an event.

| Current state | Event | Next state | Result |
|---|---|---|---|
| Newly constructed | Any number of valid `update` calls | Disarmed | Zero demands; pumps OFF; GDI inhibited; no invented fault |
| Any state | Invalid `update` or invalid `tryRearm` | FaultLatched | Both pumps and GDI inhibited; first fault retained |
| FaultLatched | Input becomes valid | FaultLatched | No automatic recovery |
| Any state | Explicit `tryRearm(valid snapshot)` | Armed | Returns true; latch cleared; no drive output emitted by this call |
| Armed | Valid `update` | Armed | Current allocator result allowed |
| Armed | `disarm()` | Disarmed | Returns an inhibited output for immediate application |
| FaultLatched | `disarm()` | FaultLatched | Returns an inhibited output; preserves the latch |

`tryRearm()` is an explicit event method, not a persistent readiness Boolean.
A failed request is consumed: later valid input cannot complete it implicitly.
Every subsequent `update()` checks its own input again, including the first update
after successful re-arming. The first fault in an episode remains the reported
diagnostic until a valid explicit re-arm; later faults do not overwrite it.

The application must retain one supervisor for the engine-control lifetime and
serialize calls. It must apply every returned `update`/`disarm` result immediately,
cancel pending pump/injector events when inhibited, and use a deliberate approved
re-arm event. Reconstructing the class each cycle or calling `tryRearm()` merely
because readiness returned would defeat this policy. This class is not a
thread-safe or interrupt-safe hardware disable mechanism.

## Validation scope

The new transition test covers **46 invalid input cases** across shared and
independent rail modes: synchronization loss, invalid topology, each driver,
each capacity (zero, negative, NaN, positive/negative infinity), required rail
sensors and demands (outside 0..100, NaN, positive/negative infinity).

Each case checks an armed fault, repeated healthy samples after the fault,
rejected invalid re-arm, manual disarm retaining the latch, explicit valid
recovery, invalid startup arm, invalid arm while already armed, and faults while
disarmed. Additional checks cover initial OFF state, manual stop/restart,
first-fault retention, changed conditions between re-arm and update, 0/100%
boundaries, and unchanged shared/independent allocation semantics. Existing
allocator contract tests remain in the suite.

The runner prints commands and compiler versions, uses temporary build folders,
compiles with C++17, warnings as errors and assertions enabled, and propagates
compile/test failures. Python 3.8+ and a C++17 GCC/Clang toolchain are sufficient.
`CXX` or `--cxx` selects one compiler executable. UBSan is enabled by default on
Linux/macOS with non-recovering errors; the Windows default explicitly reports
`sanitizer: none`. `--sanitize undefined` requests UBSan where supported;
`--sanitize none` disables it explicitly.

From repository root:

```powershell
py -3.12 Power8GDI/firmware/tests/run_dual_hpfp_tests.py
```

```sh
python3 Power8GDI/firmware/tests/run_dual_hpfp_tests.py
# Existing shell/aggregate entrypoint remains supported:
bash Power8GDI/firmware/tests/run_dual_hpfp_tests.sh
```

## Recorded host results

Windows command actually run from the feature checkout:

```powershell
& 'C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe' 'Power8GDI\firmware\tests\run_dual_hpfp_tests.py'
```

Python 3.12.10; Clang 21.1.6; target `x86_64-unknown-windows-msvc`; exit code 0:

```text
HPFP host platform: win32; sanitizer: none
dual HPFP supervisor contract tests: PASS
dual HPFP latched safety transitions: PASS (46 fault cases; startup, disarm, recovery, re-arm, first-fault, boundaries)
HPFP host suite: PASS
```

Linux was actually tested using an already installed Docker image, a read-only
source mount and disabled networking. No image download or package installation
was required. Both the Python entrypoint and shell wrapper passed. Exact wrapper
command used on the Windows host:

```powershell
docker run --rm --network none --mount 'type=bind,source=C:\Users\User\Documents\Codex\2026-10-21\ghj\work\power8gdi-fw\Power8GDI\firmware,target=/src,readonly' --entrypoint bash sipeed/maixcdk-builder:latest /src/tests/run_dual_hpfp_tests.sh
```

Image ID: `sha256:20c16e9ad2650de563d1d2f9a73cee029c01c553b94b7e036ba910f542e3dba9`.
Python 3.8.10; GCC `9.4.0 (Ubuntu 9.4.0-1ubuntu1~20.04.2)`; exit code 0:

```text
HPFP host platform: linux; sanitizer: undefined
dual HPFP supervisor contract tests: PASS
dual HPFP latched safety transitions: PASS (46 fault cases; startup, disarm, recovery, re-arm, first-fault, boundaries)
HPFP host suite: PASS
```

The initial Linux invocation exposed Python 3.8's eager evaluation of `list[str]`
annotations. Deferred annotations fixed the portability failure before the
successful runs above. The container is only a host test environment, not the
approved Power8GDI firmware build environment. macOS was not tested.

## Exact blockers for a real F7 board target

1. This checkout is `rusefi-hardware`. Its root and `.gitmodules` do not contain a
   pinned rusEFI ECU core checkout/submodule with a Power8GDI board target. The
   hardware repository's ChibiOS and component submodules do not supply that
   target. Select/review a core revision, initialize its dependencies and record
   its compiler/build container before claiming a reproducible MCU build.
2. [F7_RESOURCE_PLAN.md](F7_RESOURCE_PLAN.md) still leaves the exact MCU/package,
   AF/timer/DMA/ADC/EXTI allocation and several signals unresolved. In the recorded
   Power4GDI reference, `PF12/PF13/PF14` already serve HPFP1/DRVEN/RESETB. They cannot
   also be assigned DI6/DI7/DI8 without a reviewed schematic and firmware change.
3. The second PT2001 still needs verified independent CS, DRVEN, RESET and fault
   inputs, power/fault-disable circuitry, SPI arbitration and an agreed mapping
   for two independently scheduled pump command paths. No placeholder pins were
   invented in this change.
4. The policy is not wired into rusEFI's pump controller, crank/cam scheduler,
   PT2001 drivers, physical disable lines or boot/brownout path. Demand allocation
   does not implement closed-loop pressure control, phase/current regulation,
   cancellation of pending electrical pulses or a watchdog.
5. Input Booleans are caller assertions, not measured evidence. This model has no
   timestamps, supply/boost measurements, driver status registers, overpressure
   threshold, sensor plausibility or re-arm dwell policy. In particular, the
   architecture's validated supply-state requirement must be implemented in the
   future driver/readiness integration before a real re-arm is permitted.

**Status:** host policy tests PASS on Windows and Linux. Full STM32F7 firmware
build, MCU-in-loop, reset/brownout behavior, physical fault injection, thermal,
EMC and engine tests **NOT RUN**. No production or manufacturing readiness claim.
