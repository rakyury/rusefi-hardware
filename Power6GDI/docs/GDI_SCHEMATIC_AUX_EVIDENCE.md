# Auxiliary knock and wideband schematic evidence

Review date: 2026-10-21. Base: `daf7c81`. Scope: `hardware/design/interfaces_aux/` only. No original rusEFI board source was edited; no hardware was connected or energized. This is an engineering increment, not a complete working wideband controller or production release.

Four connected KiCad 9 sheets contain 106 components: TPIC8101 dual knock (23), two CJ125 analogue networks (29 each), and four-channel ADC/control (25). XML exports, BOM, pin-level parts manifest, source hashes, SVGs and unfiltered ERC JSON are included. Project `Power8GDI_Core`, root and leaf instance UUIDs are recorded in `interface.json`. The new symbols encode actual manufacturer pin numbers. The CJ125 ICs are DNP; their generic LQFP32 geometry is explicitly unconfirmed.

## Implemented circuitry

The TI TPIC8101 receives two AC-coupled sensor inputs with unity external input gain, Vref decoupling and a dedicated 8 MHz oscillator. Digital SPI readout avoids an MCU ADC allocation. Sensor channels are multiplexed, not simultaneous. An AHCT244 translates 3.3 V controller outputs to 5 V; a CS-controlled LVC125 returns SDO to the 3.3 V shared bus. MCU oscillator loading is unchanged. The TPIC clock mode, digital-readout initialization, integration windows and channel scheduling still require firmware and bench qualification. Source: [TI TPIC8101](https://www.ti.com/lit/ds/symlink/tpic8101.pdf), [TI AHCT244-Q1](https://www.ti.com/lit/ds/symlink/sn74ahct244-q1.pdf), [TI LVC125-Q1](https://www.ti.com/lit/ds/symlink/sn74lvc1g125-q1.pdf), [Abracon ASEM](https://abracon.com/Oscillators/ASEM.pdf).

The two CJ125 networks use Bosch's public 32-pin drawing and LSU4.9 application values, with independent virtual grounds. The Nernst prefilter's 2.2 nF returns to GND, not VM; a 100 kOhm leakage-detection resistor connects UN_RAW to UP. The drawing's unvalued series resistor and post-filter capacitor use explicitly provisional 100 Ohm/100 nF values. Unknown VCCSS pin18 stays on an unresolved net. UB and heater feeds remain external. Heater gate and drain diagnosis nodes are visible boundaries. No heater MOSFET is represented. Source: [Bosch CJ125 public proposal](https://www.bosch-semiconductors.com/media/automotive_systems_ics/pdf_1/ic_engine_management/cj125_product_info_2019-02.pdf).

The four UA/UR signals drive TLV9004-Q1 unity buffers, then 10 kOhm/15 kOhm dividers with 100 nF ADC reservoirs. Direct dividers were rejected: Bosch specifies UA swing under a 10 microampere output-load condition, while a 25 kOhm divider would draw about 200 microamperes. The buffer removes that resistive load; its bias, offset, leakage and startup behavior still enter the error budget. Divider worst-case ratio with 0.1% resistors gives 3.1525 V from 5.25 V. This is not proof against a missing 3.3 V rail, which requires sequencing/backfeed evaluation. The 10 kOhm resistor isolates the amplifier from the reservoir. Source: [TI TLV9004-Q1](https://www.ti.com/lit/gpn/TLV9004-Q1).

MCP3204 reads all four channels on the shared SPI bus at a candidate clock no greater than 500 kHz; conversion clocks must also respect the datasheet minimum. Four low-rate measurements, settling delay and dummy-conversion policy need validation. The amplifier, resistor ratio, ADC reference, acquisition and leakage errors are not yet a calibrated lambda measurement. MCP3204 and the selected oscillator have an 85 degree C operating ceiling. Source: [Microchip DS21298E](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/21298e.pdf).

Seven control GPIOs are required: KNOCK_CS_N, KNOCK_INT_HOLD, WBO1_CS_N, WBO2_CS_N, WBO1_HEATER_PWM, WBO2_HEATER_PWM, WBO_ADC_CS_N. Shared nets are GDI_SPI2_SCK/MOSI/MISO. SAFETY_CLEAR_N drives a 5 V translated common CJ125 reset. HW_ACTUATOR_ENABLE_N disables both heater-request buffer banks; output pull-downs are present. Those are logic signals, not heater power outputs. The shared SPI bus requires proven CS exclusivity, mode/clock switching and timing with PT2001/TLE devices.

## Harness boundaries

Knock uses HARNESS_KNOCK1_SIG/RETURN and HARNESS_KNOCK2_SIG/RETURN. Sensor-return links enter GND through distinct 0 Ohm links, requiring an analogue-ground placement/EMC review. The two WBO groups use HARNESS_WBOi_CONTACT1..6 with manufacturer sensor roles IP, VM, H-, H+, IA trim, UN. These are sensor contact names, not an assignment to the project's TE connector. Both H- and H+ adaptation links stay DNP. VM must never be merged into board ground or the other sensor VM. Source: [Bosch LSU4.9](https://www.bosch-motorsport.com/content/downloads/Raceparts/en-GB/51865867208058251.html).

## Source comparison and provenance

`sources.json` records seven primary-document SHA256 values, revisions and original URLs, plus four exact git blob/SHA256 references from the inherited rusEFI hardware tree. Downloaded PDFs are ignored and not part of this commit. Application topology is derived from the cited manufacturer publications, not claimed as independently invented. Standard KiCad footprint references retain the [KiCad library license and exception](https://www.kicad.org/libraries/license/). The parent fork's upstream license question is not resolved by this increment.

- `lambda-x2` is a different MCU-based analogue design. Its own readme documents cross-channel ESR coupling and LSU4.9 component changes; copying its shared switching arrangement would not prove two independent CJ125 channels.
- `wideband-F103` reports unknown/abandoned hardware/firmware matching. It is not used as a validated design.
- Legacy `CJ125_board_rev00.20` uses the historical SOIC24 representation and records past footprint/MOSFET defects. It cannot establish the current public LQFP32 pin mapping.
- The examined ArtElectro knock board uses MAX9939 circuitry; a TPIC symbol in its library is not evidence that its PCB implements TPIC8101. No upstream schematic or PCB was copied into this increment.

## Verification and remaining release gates

`python hardware/design/interfaces_aux/verify_aux.py --kicad` exports using KiCad 9.0.9 and runs twelve offline checks. `--require-ready` runs the same checks and exits 2 because release remains blocked. Source tests verify actual exported net connectivity, DNP preservation, primary pin maps, virtual-ground isolation, CS-controlled return buffers, four independently buffered ADC channels, heater inhibit, footprint pad coverage, references and provenance. They do not establish analogue performance or SPI firmware operation.

Standalone ERC, native exit 5 for each sheet:

| Sheet | Errors | Warnings | Findings |
|---|---:|---:|---|
| knock_dual | 6 | 11 | external power/input drivers and dangling integration labels |
| wbo1_analog | 10 | 14 | external drivers/power, unknown VCCSS, heater/harness boundaries |
| wbo2_analog | 10 | 14 | same independent channel boundaries |
| wbo_adc_control | 9 | 7 | external power/control and analogue inputs from other sheets |

No ERC exclusions, fake power flags or driven-pin type changes conceal these findings. Integrated ERC must be rerun by the integration owner; cross-sheet findings may disappear, but the real unresolved boundaries must remain visible.

Release blockers are: CJ125 full VCCSS/variant/package/SPI specification; exact component ordering/footprint qualification; real independent heater MOSFET/current/protection circuits; protected UB and heater feeds; +5V_CORE current and thermal budget including both CJ125 loads; ADC power-sequence/backfeed and analogue error/settling proof; sensor calibration and heater condensation/startup control; SPI timing; temperature grades; harness qualification; sensor EMC/fault injection and all physical testing. The public CJ125 table gives up to 76 mA VCC plus 4 mA VCCS per controller before other loads, so two fitted controllers alone reserve 160 mA on the 5 V supply. No full-board DRC or routed-board completeness claim is made here.
