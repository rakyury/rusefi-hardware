# Power8GDI — release-quality checklist

**No manufacturing release currently.** Completing KiCad files, 3D views or a
successful firmware compile by itself does not make an ECU safe for operation.

## Required outputs

| Artifact | Current state | Acceptance criteria |
|---|---|---|
| Electrical schematic | Connected hierarchy; current Huge/GDI8 module integration in progress | Complete hierarchical sheets; ERC clear or justified exceptions; verified references / analog and power rails / PT2001 dual GDI integration |
| PCB | Earlier routed reference is superseded; current functional placement/routing in progress | Correct TE footprints; placed/routed signals; validated stackup and return currents; DRC zero critical; reviewed HV spacing and high-current derating |
| PCB 3D CAD/views | Provisional envelopes | Board STEP from real KiCad footprint placement, official component models, actual materials |
| Mechanical enclosure | CAD concept | Mated TE connector STEP/cutouts; seal, screw bosses, fasteners, gasket design; CNC drawing and tolerance limits; thermal conduction and installation vibration checks |
| Manufacturing package | Not started | Gerbers, drill, BOM manufacturer P/N, substitutions, pick-place, stackup fab drawing, revision and licensed fab files |
| Firmware | Single-PF7 baselines / dual-HPFP planning module | Unique Power8GDI target compiles in user's Docker; safe outputs, two PT2001 drivers, eight DI and two HPFP scheduler support; protocol and calibration schema; CI + hardware-in-loop tests |
| Configurator | Offline desktop MVP | Full validated device protocol + MSQ import/export; OTA-safe flash/burn; emergency state; robust telemetry, dynamic tables, logs, Python packaging and test lab evidence |

## Mandatory engineering checks before a motor or injector is energized

1. Validate source publication licenses and transitive library dependencies.
2. Verify each TE Superseal board + harness body key, actual electrical spacing, mating height, connector current/voltage rating and strain relief.
3. PCB stackup, galvanic return paths, ground isolation and EMC protection independently reviewed.
4. External test loads only: Vbatt crank/brownout, transient, reverse polarity, cold start and watchdog.
5. Injectors: check boost charge/peak/hold waveform and clamp, switching times, no unintended pulses.
6. HPFP: independent phasing, invalid pressure transducer, out-of-range commanded current, synchronism loss, rail overpressure.
7. Knock: sensor gain, filter, cross-talk and cylinder identification in presence of GDI transients.
8. ETB and EWG: independent fail-safe/overcurrent and actual position redundancy.
9. Lin and SENT: EMC and timeout, avoid blocking engine timing interrupts.
10. Test thermal coupling at expected 12/14/24 V, rework, connector sealing and waterproofing.

**Release gate remains CLOSED until all critical criteria verified.**
