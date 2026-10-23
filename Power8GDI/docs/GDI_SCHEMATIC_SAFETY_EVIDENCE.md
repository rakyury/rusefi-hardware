# Hardware inhibit and ignition gate candidate — 2026-10-21

`hardware/design/safety/safety_gate.kicad_sch` is a connected, project-authored
33-component circuit with an actual KiCad XML export, BOM, symbols and pin/pad
checks. It adds an independent watchdog and power monitor, a latched enable,
and eight ignition logic gates. **It remains an unqualified engineering candidate.**
The downstream MIC output links and GDI DRVEN links must remain unpopulated until
the load, power-sequence and failure tests below are completed.

## Electrical implementation and primary evidence

| Ref | Selected part | Connections and evidence |
| --- | --- | --- |
| U801 | TPS3431SQDRBRQ1 | External falling-edge watchdog; EN/SET1 tied +3V3 so firmware cannot disable it. WDO and ENOUT join SAFETY_FAULT_N as explicitly allowed by TI. Thermal pad 9 goes to GND. [TI Rev A](https://www.ti.com/lit/ds/symlink/tps3431-q1.pdf), pin table p3, timing p14, package drawings. |
| U802 | TPS3808G33QDBVRQ1 | +3V3 power-on/brownout monitor; nominal threshold 3.07 V. RESET joins the open-drain fault bus. CT intentionally NC gives nominal 20 ms reset delay. MR is HW_KILL_N. [TI Rev J](https://www.ti.com/lit/ds/symlink/tps3808-q1.pdf), pin table and timing characteristics. |
| U803 | SN74LVC1G17QDBVRQ1 | Noninverting Schmitt buffer turns the resistor-released fault bus into a clean latch-clear input. DBV pins 2 input, 4 output, 3 GND, 5 supply, 1 NC. [TI Rev E](https://www.ti.com/lit/ds/symlink/sn74lvc1g17-q1.pdf), p3. |
| U804 | SN74LVC2G74QDCURQ1 | D=1, /PRE=1, /CLR from U803; ARM is CLK. **Pin5 is Q; pin3 is Qbar.** Q exports active-high HW_ACTUATOR_ENABLE; Qbar drives both U805 /OE. [TI Rev C](https://www.ti.com/lit/ds/symlink/sn74lvc2g74-q1.pdf), pp1–2. |
| U805 | SN74LVC244AQPWRQ1 | Eight noninverting channels; /OE pins 1/19 high disable both banks. R805 pulls /OE up; R821–828 pull disabled outputs down. [TI Rev D](https://www.ti.com/lit/ds/symlink/sn74lvc244a-q1.pdf), pp3–4,11–12 and PW0020A package. |

Fault assertion asynchronously clears the latch. Recovery of voltage, heartbeat
or kill contact leaves it cleared. A **new rising edge** on SAFETY_ARM_REQUEST
after fault release is needed to enable. An ARM edge during a fault is discarded;
holding ARM high does not re-enable after the fault. This follows the DFF truth
table within its specified supply, clock/clear timing and transition limits.
The logic tests demonstrate this interpretation; they are not analogue tests.

The single fault bus has a 10 kOhm pull-up shared by compatible open-drain outputs.
HW_KILL_N also has a 10 kOhm pull-up and is a **local 3.3 V open-drain/contact-to-GND
boundary**, not a protected external 12 V or harness input. C801–C805 are 100 nF
local bypass capacitors for U801–U805. The layout must keep their returns short.

U801 CWD uses 120 pF C0G, 1%, rather than 100 pF: its lower tolerance bound remains
above the datasheet's 100 pF characterized minimum. The datasheet equation gives
64.288 ms nominal, 58.181–70.395 ms with the ideal capacitor timing factors,
or 58.097–70.497 ms after including nominal capacitance tolerance. Parasitic
capacitance, temperature drift and actual board measurements are not covered by
that final arithmetic. This timer is a **backup processor monitor, not an
independent maximum coil dwell or injector pulse limiter**. Required fault
reaction time and the firmware heartbeat policy remain unqualified.

## Connected interfaces

All parts use +3V3 and GND. MCU raw IGN1–IGN8 feed U805 inputs; IGN1_GATED–
IGN8_GATED must feed the MIC logic inputs. The input/output pin pairs are
2→18, 4→16, 6→14, 8→12, 11→9, 13→7, 15→5 and 17→3. Each raw input also has a
10 kOhm pull-down. U805 is logic only and does not drive a coil directly.

The coordinated MCU nets are PH4/pad45 SAFETY_HEARTBEAT, PH5/pad46
SAFETY_ARM_REQUEST, and PH6/pad83 SAFETY_FAULT_N. Root integration is responsible
for connecting those pins and the MIC gates; this standalone sheet does not
alter the MCU sheet. HW_ACTUATOR_ENABLE also supplies the root motor-domain gate.
PT2001 DRVEN is deliberately absent: its exact truth, thresholds and fault
behavior still need full NXP documentation and measurements.

## Power-up and partial power limitations

TI specifies the U805 OE pull-up for high-impedance outputs during power-up/down,
and specifies Ioff at VCC=0. U804 also has Ioff. R805 follows that OE recommendation,
and the eight output resistors define the low state when U805 is high impedance.
Using the U805 maximum 20 uA leakage over the full listed temperature range alone,
10 kOhm ±1% contributes at most 0.202 V. **This is not a complete low-level budget:**
MIC input leakage, routing and transient coupling must be included and measured.

These facts do not establish guaranteed behaviour throughout arbitrary supply
ramps between 0 V and the logic's valid supply range. The POR's low-voltage reset
guarantees have specified sink current and ramp-rate conditions; they cannot be
generalized to all ramp shapes. Required tests include slow/fast rise/fall,
partial-power backfeed, brownout, contact bounce, ARM/clear timing, and recovery
while raw IGN is high. The positive-edge latch does not prove synchronous recovery
or eliminate metastability near asynchronous clear release.

## Verification, provenance and blockers

Run from the repository root:

```
python Power8GDI/hardware/design/safety/generate.py
python Power8GDI/hardware/design/safety/verify.py --kicad
python Power8GDI/hardware/design/safety/verify.py --require-ready
```

KiCad 9.0.9 standalone ERC reports **2 errors**, both power-pin-not-driven for
the external +3V3 and GND rails; native ERC exit code is 5. No power flags,
severity suppression or ERC exclusions were introduced. The normal verification
command passes source-level checks while recording that ERC result; the explicit
readiness command exits **2**. Ten tests check actual XML connectivity, exact IC
pin numbers, all physical pad identifiers, gate/clear polarity, missing pull-down
and swapped-OE regressions, fault recovery, and watchdog tolerance arithmetic.
The exported SVG was visually reviewed. There has been no physical hardware test,
analogue simulation, PCB signal-integrity check or manufacturing release.

`provenance.json` contains primary source hashes and revisions; downloaded PDFs
stay in ignored work files. `footprint_manifest.json` hashes seven installed
KiCad library footprints and their pin numbers; matching pad numbers alone does
not sign off land pattern, stencil, assembly or thermal details. Symbol pin maps
and this interconnect are project-authored; the writer is adapted from this
project's core schematic helper. This increment does not copy the restricted
NXP evaluation circuit or modify upstream GDI4 files.

Remaining release blockers include the preceding power sequence tests; independent
maximum-dwell/current limitation; stuck individual IGN while heartbeat continues;
watchdog stuck output, latch or buffer internal faults; common supply failures;
unprotected HW_KILL_N connector interface; MCU fault policy; simultaneous load and
thermal/EMC review. This architecture is **not claimed single-fault tolerant**.
No engine or actuator model has yet qualified the raw-output polarity or timing.
