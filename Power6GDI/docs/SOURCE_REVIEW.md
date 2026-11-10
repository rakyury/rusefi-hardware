# Design references and evidence (Rev A)

This directory is a **new original design**, not a claim that existing public boards can be merged without analysis.

| Source | Confirmed available | Candidate reuse | Limitation |
|---|---|---|---|
| [Proteus (mck1117)](https://github.com/mck1117/proteus) | Full KiCad schematic/PCB, BOM/positions/gerbers for v0.7 | Input protection, dual knock front-end, power rails, smart outputs, VR, ETB H-bridges | Different PCB revisions and MCU variants; v0.7 BOM lists F427, NOT our selected F7 |
| [rusEFI GDI4](https://github.com/rusefi/rusefi-hardware/tree/main/GDI-4ch) | KiCad .kicad_sch/.kicad_pcb, Gerbers, embedded firmware | PT2001 injection/HPFP power-stage reference design, boost supply, current sense, diagnostics | Confirm hardware revision, BOM/DNP and test suitability before reuse |
| [Power4GDI](https://wiki.rusefi.com/Power4GDI/) | Public reference schematic, ECU firmware target | Existing F7 ECU/PT2001 integration | Open edit-ready manufacturing PCB was not established |
| [GDI8 documentation](https://wiki.rusefi.com/GDI8/) | 8 injector / 2 HPFP architecture described | Architecture benchmark | Separate verified PCB project and complete integration not established |
| [GM E92](https://wiki.rusefi.com/PnP-E92/) | Docs and obfuscated public bundle | GDI V8 behavior comparison | No verified full public KiCad PCB and source firmware set |

## Key source facts

- Power4GDI `board_configuration.cpp` assigns injector trigger lines H144_LS_1..4.
- Its internal PT2001 configuration uses H144_LS_7 as DRVEN, H144_LS_8 as RESETB, and H144_LS_6 as HPFP.
- It uses SPI2 for PT2001, sharing the bus with other peripheral chip selects.
- Proteus public PCB files are valuable layout examples but have no GDI high-voltage power stage.
- The separate GDI4 firmware has compile-time `EFI_PT2001_CHIPS` and a second SPI CS configuration, but its multi-chip RESET/DRVEN controls are shared and hardware fault handling requires hardening.

## Implementation decisions

1. Two independent PT2001 sections, dedicated chip-select, reset, drive-enable and fault feedback on our board.
2. Do not reuse any original pin table blindly; create a new F7 electrical pin/resource table and validate TIM/ADC/DMA/SPI/EXTI allocations.
3. Keep the four 34-pin connector labels **provisional** pending high-voltage spacing, pin current and connector derating verification.
4. Reserve at least one protected auxiliary PWM for BMW B58 oil-pressure solenoid; actual electrical rating and fail state must come from valve characterization.
5. Hardware-in-loop and fault-injection bench testing is mandatory before vehicle or engine use.

## Follow-up requested by the user: Power4GDI, GDI8 and E92 (2026-10-25)

- The public [Power4GDI/AlphaECU 4K GDI schematic](https://wiki.rusefi.com/Hardware-files/Hellen/alphax-4K-GDI-a-schematic.pdf)
  identifies revision `a`, 2024-07-21, KiCad 8.0.4. Its root has four DI
  outputs with paired positive feeds, one pump output and START1..6. This is
  useful connection evidence, but does not establish a B58 Gen2 injector
  current profile or an orderable BOM for the new six-cylinder board.
- The [GDI8 documentation](https://wiki.rusefi.com/GDI8/) explicitly describes
  eight injectors and two HPFP outputs, with pressure control performed by the
  external ECU. It also warns of limited main-ECU integration and one-HPFP
  firmware support. Treat that warning as documentation evidence, not a
  substitute for auditing a pinned current firmware revision. Our two-pump
  controller and no-Lua integration remain required work.
- The [GM E92 project](https://wiki.rusefi.com/PnP-E92/) is a V8 Ecotec3 ECU
  prototype. The public page distinguishes harness compatibility from full
  vehicle CAN integration and links a
  [public firmware bundle](https://rusefi.com/fw-private/rusefi_bundle_pnp-e92_obfuscated_public.zip)
  and [pinout](https://rusefi.com/docs/pinouts/GM-E92/). It is a relevant V8 DI
  reference, but those resources do not supply a verified editable complete
  schematic/PCB/BOM or qualify BMW B58 Gen2 injectors. No complete public
  E92 manufacturing source set was established in this review; this is a
  search result, not a claim that such sources cannot exist.

The approved physical target remains six DI, six optional PI, two HPFPs,
DBW + EWG and one lambda controller. The user has now selected B58B30 Gen2
DI and `IDX1050` PI injectors; see the active scope for the remaining exact
part/characterization checks. Channel counts alone are not load compatibility.
