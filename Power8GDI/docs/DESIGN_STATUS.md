# Power8GDI Rev A — engineering status

**Stage:** schematic interface draft, **NOT** an electrically complete ECU, assembled PCB, or manufacturing release.

## Baseline

- Base hardware source: [rusEFI Power4GDI](https://wiki.rusefi.com/Power4GDI/).
- MCU: STM32F7 family, precise package and memory variant pending resource validation.
- 8 DI channels using **two independent PT2001 sections**.
- 2 independent HPFP channels; ECU software currently has a single HPFP controller and must be extended.
- 8 ignition logic outputs; DBW and EWG each require their own independent H-bridge.
- 4 VVT, 8 auxiliary PWM outputs (including B58 oil-pressure solenoid), protected outputs, 2 knock inputs, LIN, SENT, CAN, USB and SD.
- Four 34-position Superseal-family harness connectors A/B/C/D (136 contacts), **not** the standard Huge mixed 34/26 configuration.

## Current deliverables

- KiCad connector interface schematic with 136 labeled contacts.
- KiCad outline / functional area planning board, no footprints, no copper.
- CSV pin assignment.
- Python static pinout regression tests.

## Next electrical design tasks

1. Determine verified TE header and matching harness part numbers; create/load validated KiCad footprints.
2. Cross-check STM32F7 GPIO, peripheral alternate functions, timers, DMA, power and interrupts against actual MCU package and all ECU features.
3. Integrate Proteus power/protection, ignition, knock and motor-drive circuits with revision-specific BOM/PCB references.
4. Integrate two PT2001 power stages, verify reference schematics, snubbers, sense paths, board stackup and connector de-rating.
5. Design dual HPFP logic/driver and safe disable/reset/FAULT path; implement matching firmware drivers and tests.
6. LIN transceiver and full protocol stack; SENT multi-input ICU support and fault handling.
7. ERC, DRC, mechanical enclosure test, EMC, thermal and fault-injection bench validation before manufacturing.

**Safety gate:** do not order or energize this board on the basis of the preliminary drawing.
