# Connected core schematic candidate

Status: **engineering candidate, release blocked**. `hardware/design/Power8GDI_Core.kicad_sch`
is a real KiCad 9 hierarchy with numbered component pins, footprints and exported
connectivity. It does not replace the earlier `Power8GDI_RevA` placeholder files.
This checkpoint owns five sheets and 86 physical components; its three integrated
external leaves bring the reviewed export to eight sheets and 373 components.
The external `power_input/` and `gdi/` generators remain separately owned.

## Implemented circuits

- U101 is provisional STM32F767IIT6, LQFP176, industrial -40 to 85 C. All 176 pads
  are represented. Each of 13 VDD pads has a nearby 100 nF placement requirement;
  supply islands, VCAP, reset, boot and SWD are electrically connected. VCAP1/2
  have separate 2.2 uF capacitors, with no external loads. BYPASS_REG is grounded
  and PDR_ON is high. All capacitor values require effective-capacitance review.
- Y101 is ASEM1-8.000MHZ-LC-T CMOS oscillator. Firmware must select **HSE bypass**;
  PH1 and PC14/15 remain NC. The custom ASEM footprint follows Abracon Rev P's
  four-pad drawing, with 0.9 mm pads on 2.1 by 1.9 mm centers. Assembly review is
  still required. No USB or SD connector is implemented by this checkpoint.
- U102 TLV1117LV33DCYR converts the parent's +5V_CORE to shared +3V3. It is an
  industrial candidate. At 0.30 A it dissipates approximately 0.51 W; the 1 A
  silicon rating does not establish a PCB thermal budget. The 3V3 load total,
  including both GDI VCCIO supplies, is not yet known. R101 feeds +3V3_A.
- U103 TCAN1042HGVDRQ1 has separate 5V VCC and 3V3 VIO, PESD2CAN protection,
  default standby pullup and optional DNP 120-ohm termination. CAN1_H/L are the
  bus nets. PH2 pad43 controls standby; low enables normal operation.
- U104 **TLIN1029ADRQ1** is a LIN responder candidate, with 3V3 open-drain RXD
  pullup, default sleep pulldown, recessive TXD pullup and 220 pF bus capacitor.
  PH3 pad44 controls EN; high enables normal operation. The A variant avoids
  the original part's duty-cycle erratum. VSUP is 4–36 V operating and 45 V
  absolute maximum. Fitted R111 requires parent D502 **SMBJ24CA**, specified
  38.9 V clamp at its rated test pulse; overshoot, temperature, energy and
  operation during a transient remain unverified. A commander pullup is not fitted.
- U110–U113 MIC4427YM provide eight non-inverting 5V smart-coil logic candidates,
  each with bypass capacitors and input/output pulldowns. **R128–R135 remain DNP**
  because actual coil input polarity/current and independent inhibit are unknown.
  IGN1..8 are MCU-side signals; IGN1_LOGIC_OUT..IGN8_LOGIC_OUT are separate harness
  boundaries. MIC4427 has no independent enable and is not an approved ignition
  driver. PC13's restricted drive capability remains a layout/load review item.

The original draft GPIO CSV is unchanged. All its assigned functions are carried
to their actual package pads; unassigned functions remain unassigned. PH2 and PH3
are additional **provisional GPIO** assignments in `core_manifest.json`, not AF/DMA
claims or a complete resource allocation. Sensor inputs, triggers, SENT, USB/SD,
additional CAN/LIN, knock, PI/VVT/AUX and H-bridge channels still require circuitry
and resource allocation. Independent actuator permission circuitry is not supplied
by these core sheets. Neither a no-connect marker nor a global net name completes
a missing interface. Harness aliases must be reviewed before joining connector nets.

## Source provenance

| Source | Applied evidence |
|---|---|
| [ST DS11532 Rev 9, July 2025](https://www.st.com/resource/en/datasheet/stm32f767zi.pdf) | LQFP176 Fig14 and Table11; power Fig25; VCAP Table19; HSE bypass section6.3.9; PC13 restrictions |
| [ST AN4661 Rev5](https://www.st.com/resource/en/application_note/an4661-getting-started-with-stm32f7-series-mcu-hardware-development-stmicroelectronics.pdf) | F7 minimum supply, boot, reset and debug recommendations |
| [TI TLV1117LV SBVS160C](https://www.ti.com/lit/ds/symlink/tlv1117lv.pdf) | SOT223 pins, ceramic stability and operating limits |
| [TI TCAN1042H-Q1 SLLSES9D](https://www.ti.com/lit/ds/symlink/tcan1042h-q1.pdf) | HGV pinout, VIO, standby and supply application |
| [TI TLIN1029A-Q1 SLLSFK8A](https://www.ti.com/lit/ds/symlink/tlin1029a-q1.pdf) | Pinout, operating/absolute limits and responder application |
| [TI duty-cycle erratum guidance](https://e2e.ti.com/support/interface-group/interface/f/interface-forum/1342824/tlin1029-q1-figure-9-1-of-the-datasheet) | Manufacturer recommendation to use A variant |
| [Nexperia PESD2CAN Rev2](https://assets.nexperia.com/documents/data-sheet/PESD2CAN.pdf) | SOT23 pin map and CAN application |
| [Microchip DS20006202A](https://www.microchip.com/content/dam/mchp/documents/OTH/ProductDocuments/DataSheets/MIC4426-7-8-Dual-1-5A-Peak-Low-Side-MOSFET-DRivers-DS20006202A.pdf) | MIC4427 pin map, non-inverting function and input load |
| [Abracon ASEM RevP, January 2025](https://abracon.com/Oscillators/ASEM.pdf) | Oscillator ordering code, electrical limits and package land pattern |

Official KiCad 9.0.9 libraries were extracted from `kicad/kicad:9.0`, image digest
`sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.
Input library hashes are in `core_sources/kicad_provenance.json`. The selected
MCU symbol is flattened from its official parent; VCAP electrical types are
changed from `power_in` to `power_out` because ST Fig25 identifies the internal
regulator outputs. Geometry and physical pad numbers are retained. No other pin
type is changed to hide an ERC error. KiCad library attribution and the applicable
CC BY-SA 4.0 library exception are retained in `core_sources/KICAD_LICENSE.md`.
Proteus was inspected as circuit context; no Proteus library or sheet was copied.

## Reproducible checks

Run from the repository root after integration of the source-owned external leaves:

```text
py -3.12 Power8GDI/hardware/design/build_core_schematic.py
kicad-cli sch export netlist --format kicadxml -o Power8GDI/hardware/design/core.net Power8GDI/hardware/design/Power8GDI_Core.kicad_sch
kicad-cli sch erc --format json -o Power8GDI/hardware/design/core_erc.json Power8GDI/hardware/design/Power8GDI_Core.kicad_sch
py -3.12 Power8GDI/hardware/design/verify_core.py --erc Power8GDI/hardware/design/core_erc.json --output Power8GDI/hardware/design/core_checks.json
py -3.12 -m unittest discover -s Power8GDI/hardware/design/core_tests -v
```

The commands were executed using KiCad 9.0.9 in Docker and Python 3.12. Export
passed; 373 physical components and all 176 MCU pads were present. Five tests
passed, including deliberate VCAP loading, supply-pin reversal, fitted ignition
output and incompatible upstream TVS mutations. The verifier checks every owned
manifest pad, footprint and DNP attribute against the actual KiCad XML export.
`--release` deliberately returns exit2 while qualification is blocked.

Current combined ERC: **38 findings: 27 dangling global labels and 11 undriven
power inputs**. No library mismatch or off-grid violations were suppressed.
Several undriven power findings are expected from passive supply paths, but require
review rather than automatic dismissal. The report is committed verbatim and the
CLI's zero process exit is not interpreted as zero findings. Schematic PDFs were
rendered and reviewed; label directions and text placement were corrected.

No manufacturing, engine, thermal, EMC, timing or fault-tolerance qualification
is established by this checkpoint. Production release remains blocked.
