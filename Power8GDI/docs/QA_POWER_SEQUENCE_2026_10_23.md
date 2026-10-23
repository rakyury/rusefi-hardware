# Independent power sequencing / default-off review — 2026-10-23

## Reviewed snapshot and limits

Read-only review of the main checkout, including the newly integrated U806 5 V monitor. Main HEAD observed: `dd4d300d59df13d5a8ac25f7cdd3c437600614b4`. No main file, schematic, PCB, firmware or UI was changed by this review. This report is authored separately in the GDI worktree.

Evidence inspected: exported `hardware/design/core.net`, `core_erc.json`, safety/logic_power/GDI/motor4/WBO parts and generators, and manufacturer documents linked below. The root netlist has real paths for all 21 power-input ERC warnings; that finding does **not** establish startup/fault safety or PCB current capability.

Snapshot SHA-256:

| Artifact | SHA-256 |
|---|---|
| `hardware/design/core.net` | `171a2d234b448750f7baa44831ddb6fb832127faa1dc90f3db1f43f0cffcfbe0` |
| `hardware/design/core_erc.json` | `d6bace11489c1173a4092fea7673bd3a4e44708575549fec7a37c8cf3b2cd4a7` |
| `hardware/design/safety/parts.json` | `b4accfb821731e48ce09aa96adf001e78f0b63829d5c78bbbfcc194d7ed53af5` |

No scope, DRC, thermal or engine qualification was inferred from connectivity. Findings below distinguish a circuit weakness from missing manufacturer evidence and required physical validation.

## Actionable findings

### P1 — WBO global inhibit does not retain its disabled polarity when main 3.3 V disappears

**Observed circuit:** U5611/U5811 SN74AHCT1G125 are powered by `+5V_CORE`; their active-low OE pins share `HW_ACTUATOR_ENABLE_N`. R5642/R5842, R805 and R6194 pull that signal toward **main +3V3**, not the local buffer supply. U804 also runs from main +3V3. The WBO controllers and U5610/U5810 AND gates run from separate XC6206 local 3.3 V rails fed by +5V_CORE.

**Reproducible state:** hold +5V_CORE at 5 V, force main +3V3 to 0 V. U804 is unpowered; the common OE pullups become pulldowns to zero. OE is therefore enabled while both WBO local controllers may remain powered. TI specifies OE-high for high impedance and recommends its pullup to the buffer's own VCC for power sequencing. [TI SN74AHCT1G125-Q1, sections 7.1–7.3](https://www.ti.com/lit/ds/symlink/sn74ahct1g125-q1.pdf).

This is **loss of the independent global inhibit**, not proof that the heaters inevitably turn on. R5640/R5840 still pull main permission low; U5610/U5810 require both that permission and local PWM, and output/gate pulldowns remain. The AND gate has partial-power-down protection. [TI SN74LVC1G08-Q1](https://www.ti.com/lit/ds/symlink/sn74lvc1g08-q1.pdf).

**Required correction:** local default-disabled OE generation with a validated crossing from main permission/latch into the live 5 V domain. Preserve the independent MCU-permission AND path. Do not simply pull U804's push-pull output to 5 V: its live 3.3 V output limits also need checking. U804 Ioff protects the powered-off case, not every partially powered output state. [TI SN74LVC2G74-Q1, electrical characteristics](https://www.ti.com/lit/ds/symlink/sn74lvc2g74-q1.pdf).

Acceptance: with battery and local WBO rails live, main +3V3=0 must force both OE pins HIGH even if the local PWM and permission test inputs are driven HIGH. Then sweep startup/shutdown ramps and measure heater-gate voltage/current. This fault stimulus deliberately checks independence; it is not a claim about normal MCU behavior.

### P2 — Logic-rail budget omits explicit SD-card and PT2001 VCCIO allocations

`logic_power/power_budget.json` totals 0.700 A at 3.3 V against a 1 A target. The SD socket J1502.4 is powered from main +3V3 through R1520; there is no explicit SD-card allocation or qualified card current. R221/R321 also power PT2001 VCCIO from main +3V3. The exclusion text “GDI ... incl local PT supplies” must not be read as excluding these VCCIO loads.

The 0.300 A remaining allocation may accommodate them, but no selected-card peak limit or PT VCCIO maximum closes that calculation. At 5 V the declared 1.842317 A already charges a full 1 A of 3.3 V load at the assumed 85% conversion efficiency; this is a reasonable provisional envelope, not a guaranteed operating maximum. Two WBO nodes have 0.200 A each; the four motor **power** loads and WBO **heaters** correctly remain outside logic-rail current.

Required closure: separate SD and PT VCCIO rows, explicit selected-part maxima/peak durations, actual WBO node load, and regulator thermal/load-step validation. No evidence here proves a regulator overload; the defect is incomplete budget attribution.

## Existing release gates confirmed by this audit

### GDI partial power and retained boost energy

U201/U301 VCCIO pin 17 is fed from main +3V3 through four-terminal R221/R321 (power pads 1 and 4). It is **not** connected to local GDI 5 V. VCC5 pin 21 comes from U249/U349 NCV78M05 on the switched battery rail. Consequently main logic and PT digital pins can be live before bank power is enabled and after it is disconnected. CLK, START, SPI and MISO connections make this a real electrical condition, not an abstract fault.

NXP's short datasheet permits 3.3 V VCCIO and describes separate VCC5/VCC1P5 supplies, direct DRVEN inhibition, and reset-state MISO high impedance. It does not provide the electrical sequencing, unpowered leakage or worst-case shutdown timing needed to extend those claims to VCCIO-live/VCC5-off, or to VCCIO-off/VBOOST-retained operation. The reset-state table is not an Ioff specification. [NXP MC33PT2001 SDS Rev.10.1, sections 7–8](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf).

R228/R328 are real 1 kΩ RESET-to-ground defaults. The permission AND and device-side pulldowns are implemented; R299/R399 remain explicit DNP enable boundaries. **Do not fit those links on the strength of this audit.** Full manufacturer electrical evidence or an approved qualification plan must resolve DRVEN/RESET/MISO behavior with all rail-order permutations, followed by dummy-load tests. We did not establish that the chip fails those conditions; we established that the available document does not prove them.

Battery cutoff through LM74800 and two common-drain MOSFETs disconnects new input energy; it does not discharge the downstream capacitors instantaneously. The LM74800 supplies real input blocking and load-disconnect functions. [TI LM7480-Q1](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf).

Each exported GDI bank has 2×470 µF boost capacitors and nine fitted 56 kΩ resistors across boost/boost-return. At an **illustrative** 65 V (not an approved injector setting): energy is 1.986 J/bank, equivalent resistance 6.222 kΩ, nominal RC 5.849 s, and ideal decay to 10 V takes 10.95 s. The 75 kΩ LED branch and PT consumption shorten that nominal decay; component tolerances, residual input energy and faults are not included. The return is through R203/R303's power terminals. Confirm actual voltage-rated capacitor MPNs and measured decay before defining discharge time. Power cutoff cannot substitute for a verified gate-off path during this interval.

### U806 correctly closes the static 5 V-loss detection gap, with limited margins

Exported pins verified: U806.6 VDD and .3 MR → +3V3; .2 → GND; .5 SENSE → R807/R808/C808 divider; .1 RESET → SAFETY_FAULT_N; .4 CT intentionally open. There is no direct 5 V connection to SENSE.

Independent calculation with 102 kΩ/9.76 kΩ, ±0.35% each resistor, ±2% threshold and ±25 nA sense current gives falling bounds **4.513337–4.763219 V**, conservative maximum hysteretic release **4.906116 V**, and nominal divider RC **8.90766 µs**. These agree with `safety/RAIL_MONITOR.md`.

TI specifies CT-open release at 12–28 ms, SENSE normally no higher than VDD, and 20 µs nominal SENSE-to-RESET delay at the stated 5% overdrive. Thus no arbitrary-fast-collapse interception guarantee follows. When +5V remains live and VDD=0, divided SENSE is about 0.44 V: within absolute limits but outside normal SENSE≤VDD operation; do not credit U806 as an active supervisor in that state. [TI TPS3808-Q1 SBVS085J, sections 7.1–7.6](https://www.ti.com/lit/ds/symlink/tps3808-q1.pdf).

The independent static 5 V minimum is 4.92111 V, only about **15 mV above maximum release**. Ripple, load steps and board drop need measurement. The lowest falling threshold is only 13 mV above 4.5 V, so delay/filtering can let a fast fall pass below that operating boundary before inhibit. These are validation limits already acknowledged by the integration note, not grounds to remove the new monitor.

### Ignition, PI and motor default-off paths

Ignition has real gate-emitter resistors and R5401=1 kΩ on the eight shared driver EN inputs. With 200 kΩ **typical** internal pullups, the nominal off-domain voltage is approximately 0.19 V at 5 V. Do not turn that typical resistance into a guaranteed worst-case current bound. UCC27524A holds outputs low in UVLO and accepts input/EN levels independent of VDD, but its normal supply range starts at 4.5 V; falling UVLO ranges 3.5–4.1 V. Test collapse/ramp waveforms and stored gate charge rather than treating U806 plus UVLO as a zero-delay cutoff. [TI UCC27524A-Q1, sections 6.3/6.5 and 7](https://www.ti.com/lit/ds/symlink/ucc27524a-q1.pdf).

The six TLE9104 have VIO from +3V3, VDD from +5V_CORE, EN from the hardware permit with ground defaults, and a separate buffered RESN release with a strong 1 kΩ default. MCU commands have pulldowns before inversion. The device's specified VIO/VDD ranges are 3–5.5 V / 4.5–5.5 V; reset sequencing remains necessary before enabling outputs. Current or thermal protection does not qualify arbitrary supply faults. [Infineon TLE9104SH Rev.1.31](https://www.infineon.com/assets/row/public/documents/10/49/infineon-tle9104sh-datasheet-en.pdf).

All four TLE9201 VSO pins are directly on +3V3. Infineon explicitly documents pulling VSO to ground as a sleep/output-off path (threshold range 0.5–2 V), so a fully absent main 3.3 V rail has a documented motor shutdown mechanism despite retained VS energy. SO must not exceed VSO+0.3 V. The daisy-chain SO nodes stay inside that common domain, with U6190 buffering the shared MCU MISO boundary. Slow ramps through undefined/intermediate domains and regenerative energy still require testing. [Infineon TLE9201SG Rev.1.0, sections 4.1–4.2 and table 4](https://www.infineon.com/dgdl/Infineon-TLE9201SG-DS-v01_00-en.pdf?fileId=db3a304345087709014518190f481cec).

### Power feed, backfeed and returns

`VBAT_LOGIC_PROTECTED` has a real source through D5200 and continues to feed both LIN VSUP paths and the sensor trackers. U5300 EN is pulled from 5 V through LM76003 PG with a ground default, avoiding circular 3.3 V startup dependence. Removed U102 LDO/U501 buck do not exist in this live netlist. TPS62130 shutdown stops switching; it must not be treated as galvanic output isolation. Its PG also ceases to hold LOW when input is removed. The hardware safety path correctly uses separate rail monitors. [TI TPS62130A-Q1, sections 9.3.4/9.3.7/9.4.3](https://www.ti.com/lit/ds/symlink/tps62130a-q1.pdf).

Sensor tracker outputs draw from protected battery rather than the 5 V buck. D1530/D1531 isolate their input paths. TI documents a finite reverse-fault response and recommends a diode where short-to-battery could otherwise charge other input loads; the fitted diode direction is consistent with that purpose. [TI TPS7B4253-Q1, section 6.3.3](https://www.ti.com/lit/ds/symlink/tps7b4253-q1.pdf).

External digital/Hall clamp paths can inject into +5V_CORE while the ECU is off; debugger power can reach +3V3; neither rail has established off-state sink/isolation guarantees for arbitrary external excitation. These are explicit fault-injection cases, not proof that the newly selected converters alone create a backfeed defect. Measure off-state rail voltage/current with representative live sensors, LIN/CAN peers, SD and programmer. Verify that no source bypasses the intended enable state.

GND is one schematic net. Harness returns are J601.25–32 plus J602.34; sensor return branches join through R1530–R1532. This proves connection, not Kelvin routing or capacity. Primary ignition/PI/motor/GDI switching loops must not share sensor-reference necks. J602.33 supplies main logic **and both WBO heaters**, so its contact, wire, upstream fuse and return allocation must be sized for their combined load. No contact-current rating or harness assembly signoff was established in this review.

## Complete disposition of 21 `power_pin_not_driven` warnings

The table enumerates each root ERC item; several represent additional pins on the same rail. “Path present” means the exported pins form the listed electrical path. Passive, nonlinear and switching elements do not propagate a KiCad `power_out` type. It does not mean the rail is energized while disarmed. No PWR_FLAG or suppression was added.

| # | ERC pin / rail | Physical source or return path | Disposition |
|---|---|---|---|
| 1 | U101.6 VBAT / +3V3 | U5300 SW.1–3 → L5300.1–2 → +3V3 | Path present; buck output through inductor |
| 2 | U101.39 VDDA / +3V3_A | +3V3 → fitted R101 0Ω → +3V3_A | Path present; same source as #1 |
| 3 | U101.14 VSS / GND | GND → J601.25–32 and J602.34 → harness battery return | External return present; layout/harness capacity unqualified |
| 4 | U103.3 VCC / +5V_CORE | U5200 SW.1–5 → L5200.1–2 → +5V_CORE | Path present; buck output through inductor |
| 5 | U104.7 VSUP / LIN1_VSUP | J602.33 VBAT_MAIN_FUSED → D5200.3(A)→.2(K) → protected battery → R111 0Ω | Path present |
| 6 | U201.48 VBOOST / PTA_VBOOST | VBAT_GDI_A → L201 → L202 → D212.1/3(A)→.2(K); Q202 boost switch, C207/C209 storage | Boost/passive path present; GDI release gate remains |
| 7 | U201.39 VBATT / VBAT_GDI_A | J601.21/22 → Q5001 source→drain → Q5002 drain→source, controlled by U5001 | Switched path present; intentionally absent when disabled |
| 8 | U201.17 VCCIO | +3V3 → R221.1→.4 (10mΩ power terminals) | Path present; partial-power qualification open |
| 9 | U301.48 VBOOST / PTB_VBOOST | VBAT_GDI_B → L301 → L302 → D312.1/3(A)→.2(K); Q302, C307/C309 | Same disposition as #6 |
| 10 | U301.39 VBATT / VBAT_GDI_B | J601.23/24 → Q5051 → common drain → Q5052 → VBAT_GDI_B, U5051 control | Switched path present |
| 11 | U301.17 VCCIO | +3V3 → R321.1→.4 | Same disposition as #8 |
| 12 | U1502.7 VSUP / LIN2_VSUP | Protected battery from #5 → fitted R1506 0Ω | Path present |
| 13 | U1530.8 IN / SENSOR_A_IN | Protected battery → D1530.2(A)→.1(K) | Path present; sensor current uses battery feed |
| 14 | U1531.8 IN / SENSOR_B_IN | Protected battery → D1531.2(A)→.1(K) | Path present |
| 15 | U5001.10 VS / GDI_A_MID | J601.21/22 → Q5001 body diode/channel → common-drain midpoint | Controller startup supply path present |
| 16 | U5051.10 VS / GDI_B_MID | J601.23/24 → Q5051 body diode/channel → midpoint | Controller startup supply path present |
| 17 | U5200.20 PVIN1 / VBAT_LOGIC_PROTECTED | J602.33 → D5200 anode3→cathode2 | Path present; also feeds PVIN21/22 |
| 18 | U6000.4 VS / MOTOR13_VS | J601.33 → Q6200 → common drain → Q6201 → MOTOR13_VS | Switched path present; also feeds U6100 |
| 19 | U6050.4 VS / MOTOR24_VS | J601.34 → Q6250 → common drain → Q6251 → MOTOR24_VS | Switched path present; also feeds U6150 |
| 20 | U6200.10 VS / MOTOR13_MID | J601.33 → Q6200 body diode/channel → midpoint | Controller startup supply path present |
| 21 | U6250.10 VS / MOTOR24_MID | J601.34 → Q6250 body diode/channel → midpoint | Controller startup supply path present |

The remaining 12 root ERC items are dangling optional PT labels (IRQ/OA1/OA2/FLAG1/FLAG2/DBG in each bank), a separate category. This audit does not convert those into functional telemetry.

## Handoff

Fix the WBO OE domain issue in its owned module and add a real partial-power acceptance test. Close the two missing budget allocations. Preserve the explicit GDI inhibit boundary pending manufacturer sequencing evidence. Before power-load release, perform controlled supply-order/collapse, residual-energy, external-backfeed and ground-bounce tests with dummy loads; record actual current and voltage waveforms. PCB completion and DRC remain separate work.

## Follow-up: other 5 V buffer domains

Read-only follow-up after the initial checkpoint checked all exported AHCT and LVC buffer instances. The 24 low-side channels use 3.3 V LVC14 inverters with ground-default MCU commands, plus separate EN/RESN ground defaults; they do not duplicate the WBO 5 V OE topology.

Knock U1702 AHCT244 runs from +5V_CORE with both OE pins grounded. With main +3V3 absent, R1701 pulls KNOCK_CS_N toward zero, so the live knock peripheral can be selected. U1703, however, buffers its return onto shared MISO from the main 3.3 V domain with partial-power-down behavior; TPIC8101 analog OUT is NC. Thus this is not a second actuator-inhibit defect. SCK/MOSI and the oscillator input still need checks for undefined levels and supply current while their source domain is off. AHCT244 specifies input leakage for VCC from 0 to 5.5 V and input range independent of VCC, so direct MCU-to-AHCT inputs are not inherently a forward-diode backfeed path. [TI SN74AHCT244-Q1, sections 5.1/5.5](https://www.ti.com/lit/ds/symlink/sn74ahct244-q1.pdf).
