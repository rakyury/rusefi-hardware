# Additional interface electrical candidates

This subtree adds **six connected electrical leaf sheets, 106 physical components and 288 connected pins**. It is an engineering candidate, with no release, engine, automotive pulse, EMC, thermal or environmental approval. The root MCU sheet, pin CSV, connector aliases and PCB are owned by the integration lead; this subtree does not silently change those contracts.

| Leaf | Circuit | Main references |
|---|---|---|
| `comms2` | Second CAN and LIN physical layers, reset defaults, optional termination/commander bias | U1501/U1502 |
| `usb_fs` | Micro-B USB FS device, ESD, transistor VBUS detector, shield network | J1501/D1510/Q1510 |
| `sd_spi` | microSD SPI3 socket, detect, pullups, damping and ESD | J1502/D1520/D1521 |
| `sensor_power` | Two battery-fed tracking supplies and three sensor return links | U1530/U1531/D1530/D1531/R1530..1532 |
| `digital_aux_1/2` | Nine filtered, clamped, inverting 5 V logic input candidates | U1600/U1601 |

## Integration contract

`interfaces_manifest.json` supplies the exact root UUID, flat leaf `name`, `uuid` and `sheet_id`, component/pin maps, GPIO contract, harness aliases and blockers. The project name remains `Power8GDI_Core`; root UUID is `f4d21065-0a5b-5086-a08e-1af9469f04bd`. Add the six leaves directly to the root. Merge the **bare** definitions in `interfaces.kicad_sym` into the root `Power8GDI_Core` library, deduplicating existing common symbols only when identical. Add `Power8GDI_Interfaces` pointing at `interfaces/Power8GDI_Interfaces.pretty` to the root footprint table. No hidden global-library install is required.

Critical mapping change: **SENT3 moves from PB6 to PE11, LQFP176 pad 74, AF1 TIM1_CH2**. CAN2 needs PB5/PB6 AF9. SENT1 and SENT3 then share TIM1 and require a reviewed capture timebase; the former TIM4 assignment must not remain in firmware or resource reports. LIN2 uses PB10/PB11 USART3 AF7. USB uses PA11/PA12 AF10 with PA9 as an ordinary GPIO. SD uses PC10/11/12 SPI3 AF6 and PA8 chip select. PG11 is polled card detect; PG12 CAN standby and PG13 LIN enable.

HALL1..4 use PH14/PH15/PI0/PI7 and FLEX_FREQ uses PI8, with EXTI14/15/0/7/8 respectively. DIN5..8 on PI2/PI3/PI4/PI11 are **polled**, avoiding existing EXTI3/4 and avoiding an implicit EXTI11 reservation. The existing PTA_FLAG/PG10 and PTB_FLAG/PG9 do not conflict with these EXTI choices. All nine inputs invert. Actual edge latency, cable loading and frequency limits remain unmeasured.

Harness aliases include `HARNESS_LIN2_BUS`, not `HARNESS_LIN2`. Sensor ground A/B/C each passes through its own fitted 0 Ω 0805 link to GND; these are neither fuses nor galvanic isolation. Route them to the quiet local ground star and verify fault current and ground offsets. `HARNESS_CHASSIS_GND` maps to `USB_SHIELD`, providing a separate enclosure bond when the harness/enclosure implements it. The shield-to-logic 0 Ω link stays DNP; the fitted 1 nF/2 kV capacitor is a provisional HF return, not a certified isolation barrier. This does not invent an enclosure bond that the wiring lacks.

## Circuit-specific limits

CAN2 defaults to standby. The optional 120 Ω terminator is DNP. The MCU supports classic CAN; the transceiver's FD capability does not add an FD controller. Shared bxCAN filters/clock, bit timing and bus-end topology need firmware review. LIN2 defaults to sleep with RXD pulled to 3.3 V. Both optional commander bias parts remain DNP, giving responder operation when enabled. TLIN1029A is used; the older TLIN1029 duty-cycle erratum is not silently accepted. The root's nominal 38.9 V TVS clamp leaves a candidate margin below LIN's 45 V absolute limit, but overshoot, temperature, pulse energy and operation during transients remain unqualified.

USB host VBUS is isolated from +5V_CORE and +3V3. PA9 reads an **active-low** MOSFET detector; firmware must disable native OTG VBUS sensing and implement attach/detach only with VBUS present. Internal FS PHY matching/pullup functions are used. Verify the 48 MHz clock, descriptors and unpowered attachment. The service connector is not sealed or automotive qualified.

The microSD socket is an internal service part, not a selected memory card. Pins 1..8 follow the manufacturer's DAT2/DAT3/CMD/VDD/CLK/VSS/DAT0/DAT1 drawing; the official KiCad footprint assigns the separate switch terminals to 9/10 and four shell pads to 11. The switch is electrically symmetric and closes on card insertion. Final connector dimensional/assembly review must compare the actual part drawing and board. SPI mode at 3.3 V only; no UHS/1.8 V or SDMMC claim. Card current spikes, inrush and power-fail data integrity remain unknown. The proposed 22 Ω clock/data damping values need SI review. ESD arrays do not establish board-level ESD immunity or eliminate injection into the supply rail.

Sensor supplies track +5V_CORE but take load power from protected battery. Individual input Schottky diodes isolate the common rail during short-to-battery detection. Each FB joins its own OUT, with no divider. Effective output capacitance must remain at least 10 µF after bias, tolerance and temperature; the listed 22 µF/50 V value is not a frozen capacitor MPN. No fault pin exists on the selected DDA tracker. Its 300 mA capability is not a permissible harness-load rating. The custom land pattern follows the current DDA0008J-C02 drawing: pins 1..8 plus exposed pad 9/GND, 2.95×4.9 mm central copper and 2.6×3.2 mm mask/paste aperture. Thermal vias and copper area must be designed on the actual PCB.

The Hall/flex/digital circuits accept provisional 5 V logic, not VR sensors or raw battery inputs. Clamp current can backpower +5V_CORE; simultaneous faults with ECU off, maximum clamp voltage and hot leakage explicitly block release. Optional open-drain pullups remain DNP until the sensor models are selected.

## Incremental power budget

| Load | Rail | Evidence or unresolved requirement |
|---|---|---|
| CAN2 | +5V_CORE | Datasheet normal dominant maximum 70 mA at 60 Ω, 80 mA at 50 Ω; listed bus-fault case reaches 110 mA. Do not budget average recessive current as the peak. |
| CAN2 I/O | +3V3 | Datasheet maximum 300 µA with RXD unloaded; external switching loads add current. |
| Two tracker references | +5V_CORE | At most 2×5.5 µA in the stated 5 V tracking condition, plus local capacitor charging. Sensor output load is supplied from battery. |
| Tracker bank A/B | protected battery | 100 mA at 14→5 V is about 0.9 W per tracker before diode loss; 300 mA is about 2.7 W. Neither is thermally approved. Include quiescent current, both banks, cold crank dropout and faults. |
| SD card | +3V3 through existing LDO | Unknown until a card is selected and write/inrush current measured; LDO input also loads +5V_CORE. This blocks closing the 0.8 A buck and LDO thermal budgets. |
| Digital inputs, USB and LIN I/O | +3V3 / +5V_CORE | Static pullups and dynamic Schmitt/PHY currents must be summed with MCU, existing inputs, GDI VCCIO, safety, six TLE supplies and auxiliary circuits. No aggregate budget is declared closed. |

## Primary evidence

Accessed 2026-10-21. Manufacturer documents establish component facts; the candidate choices and calculated budgets above remain engineering decisions.

| Source | Used evidence |
|---|---|
| [ST DS11532 Rev 9](https://www.st.com/resource/en/datasheet/stm32f767zi.pdf), pin/AF tables and USB electrical section | STM32F767IIT6 package/alternate functions; USB FS has embedded driver matching. Official KiCad 9.0.9 symbol independently supplies the 176 pad names. |
| [TI TCAN1042 SLLSES9D](https://www.ti.com/lit/ds/symlink/tcan1042h-q1.pdf), Tables 6-1 and 7.5 | HGV pinout, 3.3 V VIO, standby, supply current. |
| [TI TLIN1029A SLLSFK8A](https://www.ti.com/lit/ds/symlink/tlin1029a-q1.pdf) and [TI variant recommendation](https://e2e.ti.com/support/interface-group/interface/f/interface-forum/1342824/tlin1029-q1-figure-9-1-of-the-datasheet) | A variant, pinout, RXD, sleep and supply limits. |
| [Nexperia PESD2CAN](https://assets.nexperia.com/documents/data-sheet/PESD2CAN.pdf) and [BAS21](https://assets.nexperia.com/documents/data-sheet/BAS21.pdf) | CAN suppressor and optional commander diode pin polarity. |
| [ST USBLC6-2 DS4260 Rev 7](https://www.st.com/resource/en/datasheet/usblc6-2.pdf) | Two feedthrough I/O pairs and VBUS/GND pins; specified component-level ESD characteristics only. |
| [ST AN4879 VBUS guidance](https://www.st.com/content/st_com/en/technical-documents/an4879-introduction-to-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics_asset/chunk-003-topic-an4879-vbus-sensing-detection.html), Rev 12 | GPIO/native-detect distinction and transistor VBUS detector. |
| [Nexperia 2N7002](https://assets.nexperia.com/documents/data-sheet/2N7002.pdf) | Pin1 gate,2 source,3 drain; gate-voltage limits. |
| [Molex USB SD-105017-001 drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/105/105017/1050170001_sd.pdf) and [part data](https://www.molex.com/en-us/products/part-detail/1050170001?display=pdf) | Micro-B part identity and mechanical reference. Official KiCad connector footprint supplies numbered PCB pads1..6. |
| [Molex SD-104031-001 drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/104/104031/1040310811_sd.pdf), sheet1, and [PS-104031-001](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/104/104031/PS-104031-001-001.pdf) | Eight card contacts, separate detect switch, shell and environmental limits. |
| [TI TPS7B4253 SLVSCP3D](https://www.ti.com/lit/ds/symlink/tps7b4253-q1.pdf), Table4-1, §§5.3/5.5/6.3.3 and pp24–26 | Tracker pinout, FB, capacitance, reverse-current latency, reference current and current DDA land pattern. |
| [ST STPS2H100-Y DS6949 Rev 2](https://www.st.com/resource/en/datasheet/stps2h100-y.pdf) | STPS2H100UY 100 V automotive Schottky, SMB polarity. |
| [TI SN74LVC14A-Q1 SCAS705B](https://www.ti.com/lit/ds/symlink/sn74lvc14a-q1.pdf) and [Nexperia BAT54S](https://assets.nexperia.com/documents/data-sheet/BAT54S.pdf) | Inverter pinout, supply/input tolerance and clamp polarity. |

The Molex PDFs were readable through the web source service; direct downloads on this host timed out. This is recorded rather than claiming a local drawing-overlay check. The official KiCad footprint pad sets were loaded and checked with `pcbnew` for **all 106 components**, including the custom tracker footprint. That verifies CAD pad presence, not manufacturer mechanical tolerances or assembly success.

## Reproduction and checks

From repository root, generate with `py -3.12 Power8GDI/hardware/design/interfaces/build_interfaces.py`. Export each leaf with KiCad 9.0.9 `kicad-cli sch export netlist --format kicadxml`, then run `kicad-cli sch erc --format json`; perform these sequentially for a project. The container used is `kicad/kicad:9.0` (9.0.9), digest `sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.

```
py -3.12 -m unittest discover -s Power8GDI/hardware/design/interfaces -p test_interfaces.py -v
py -3.12 Power8GDI/hardware/design/interfaces/check_interfaces.py
# In the official KiCad container, with the repository mounted:
python3 Power8GDI/hardware/design/interfaces/check_interfaces.py --footprints --report Power8GDI/hardware/design/interfaces/interfaces_checks.json
```

Eleven tests exercise exported connectivity and deliberate failures: USB backfeed/FET swap, SD switch/shell substitution, tracker diode/FB/EP faults, premature commander population, clamp reversal and missing ground return. `--release` deliberately exits **2** while release blockers exist. Structural check exits0; failure exits1. The six standalone ERC reports retain **31 findings: 19 dangling global boundaries, 11 undriven power inputs, 1 undriven CAN TX input**. No flags, exclusions or disabled rules hide them. Integration must rerun root ERC: standalone boundaries cannot prove the full assembly is connected. Generated PDFs were visually inspected; source exports/PDFs are not production schematics.
