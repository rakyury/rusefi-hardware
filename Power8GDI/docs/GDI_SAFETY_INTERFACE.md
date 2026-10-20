# Power8GDI dual PT2001 permit architecture — host prototype

**Status:** testable controller-independent **software policy only**. Does not configure PT2001, drive a real GPIO, start an injector pulse, control rail pressure or bypass the mandatory independent hardware disable path. Before firmware integration, validate behavior against the actual driver IC, high-voltage power circuits, watchdog, and event scheduler.

## Real-time arrangement

```text
                              +--------------------+
Crank/cam sync ----------+--->| Atomic observations|  2x PT2001 readiness
BATT / power-good -------+--->| and fault snapshot |  stale-diagnostic deadline
Rail pressure flags -----+--->|                    |  rail config and pumps
E-stop interlock --------+--->+---------+----------+
                                         |
                                         v
                                   DualPt2001Safety
                                         |
                               global permits OR hardware kill
                                         |
                             +-----------+-----------+
                             v                       v
                           PT2001 A                 PT2001 B
                      DRVEN/RESET/FLAG          DRVEN/RESET/FLAG
                      Injector 1-4               Injector 5-8
                      HPFP channel 1             HPFP channel 2
```

- Both PT2001 sections are mandatory for 8 DI even if only one HPFP is installed. Separate CS/RESET/DRVEN/FAULT resources required. The software decision is **not** itself the hardwired kill circuit.
- Both sections' enables and **all eight injector command permits** go low if either driver faults, supply is lost, E-stop asserts, rail becomes invalid, pressure is unsafe, diagnostics age out or synchronized operation is lost.
- Fault state latches; no automatic restart. Acknowledge requires a stopped, unsynchronized, non-running engine and healthy drivers/sensors, and must only be requested by an explicit user or service action.
- Changing rail topology, installed pump count or sensor configuration while armed is detected and latched as `ConfigurationInvalid`.
- **Shared-rail mode:** one healthy rail pressure sensor may be configured for a single or dual pump; if two pressure sensors are configured, both must be healthy. **Independent-rail mode:** each installed pump requires its own healthy sensor.
- All outputs initialize disabled. `requestHardwareKill=true` when disarmed/faulted; keep hardware driver supply/DRVEN fail-safe by external circuitry even if firmware freezes.
- PT2001 diagnostic age, sensor limits, register signature, flag polarity and voltage sensing must be normalized and measured in hardware driver layer. `diagnosticsFresh=true` without a real deadline is invalid.

## Current module and limitations

- `firmware/dual_gdi/dual_pt2001_safety.h` and `.cpp` implement no-heap, fixed-size deterministic decisions.
- `firmware/tests/test_dual_pt2001_safety.cpp` covers startup, both chip failure sources, stale data, rail validity, supply, E-stop, synchronism loss, fault latching/acknowledge, one-pump shared rail and configuration freeze.
- The real engine injection scheduler must enforce `injectorCommand`, HPFP scheduler must enforce `hpfpCommand`, and the driver GPIO path must enforce `drvenAllowed` with a separate emergency hardware path. Periodic software evaluation alone cannot guarantee a timely shutdown.
- The pure-state module **is not ISR/thread-safe**; hardware interrupts must immediately cut DRVEN and transfer a fault indication through a concurrency-safe path. The integration layer must define critical-section ownership and ordering.
- Pulse timing, injector driver sequence and pump peak/hold currents are deliberately absent and must be adapted from revision-pinned rusEFI GDI4/Power4GDI sources and verified on a non-engine dummy-load bench.

## Test commands

```bash
bash Power8GDI/firmware/tests/run_gdi_safety_tests.sh
bash Power8GDI/firmware/tests/run_all_host_tests.sh
```

**Production blocker:** this module is a design artifact. It does not constitute a safe-to-energize ECU without electrical/real-time verification and hardware fault-injection measurements.
