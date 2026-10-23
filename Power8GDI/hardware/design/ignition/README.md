# Eight passive-coil ignition channels

Engineering candidate for retaining the requested stock B58 coils. Nine real
KiCad sheets, 146 components, references5400–5599. No PCB layout or engine
qualification is claimed. Exact G42 coil part and harness pinout remain open;
BMW/Bosch and original bench evidence is recorded in [HANDOFF.md](HANDOFF.md).

## Integration contract

Call `make_ignition(syms, root_id)` from `ignition.build_ignition`. Add its nine
returned sheets to the parent root, write them using the design directory, and
include their `parts` in the integrated manifest/BOM. Remove the previous
`core_ignition` leaf and its drivers. Do not add `ignition_validation` or X5599
to production: they are an explicit external-interface verification fixture.

| Alias | Direction and requirement |
|---|---|
| IGN1..IGN8 | MCU3.3V command, HIGH charges coil; rising-edge window trigger |
| HW_ACTUATOR_ENABLE | Parent latched permission; must stay LOW through startup, reset, invalid rails and fault |
| +3V3 | Timer, gates, continuous current comparators; supervised by parent |
| +5V_CORE | Regulated gate-driver supply; >=4.5V operating supply at driver pins |
| GND | Logical common net; physical coil-current returns and Kelvin paths must be designed separately |
| HARNESS_IGN1..HARNESS_IGN8 | IGBT collector/tab, switched primary; up to420V clamp envelope, never logic output |
| IGN_OC_OK | Wired open drain; LOW means fault. Local10k pullup to3V3. Parent connects through R6500=0R to HW_KILL_N |

The eight INA300 ALERT outputs directly inhibit the entire ignition bank through
U5400/U5401, independently of software. The parent HW_KILL_N connection must
also force the supervisor and global safety latch off, inhibiting fuel/GDI/other
actuators. No new MCU GPIO is required. Existing parent10k pullup in parallel
with local10k presents approximately0.66mA total sink current at3.3V.

Parent must provide external switched/fused coil+12V feed and a fault strategy
that removes it. This module does not contain that relay/high-side switch.
Latch clearing requires power-cycle; verify parent does not automatically re-arm
after transient3V3 loss. Startup software delay is not a substitute for hardware
rail supervision. Hold permission low until rails and timers/comparators settle.

PC13/IGN1 only drives the timer input, one CMOS gate and100k pulldown; it never
drives the IGBT or 1k enable pulldown. Nominal resistor load33uA at3.3V, plus
input leakage. Configure slow GPIO edges and keep total loading <=30pF, operation
<=2MHz; input capacitances are partly typical, so routing/probing needs budget.
ST warns these backup-domain pins must not act as power/current-source outputs.
The logic-load use still needs parent pinmux/firmware review; do not hang LEDs,
another harness output or a heavy pull-down on PC13.
[STM32F767 datasheet](https://www.st.com/resource/en/datasheet/stm32f767ii.pdf).

## Circuit and calculations

Four **UCC27524AQDRQ1** devices replace MIC4427YM. The D SOIC-8 package has
ENA1, INA2, GND3, INB4, OUTB5, VDD6, OUTA7, ENB8. Both enables join
IGN_SAFE_EN;1k holds the shared enable low against internal pullups, and each
input also has100k pull-down. UVLO holds driver outputs low. The driver is
automotive grade1; recommended junction range in RevC is−40..140°C, despite
the150°C feature/absolute limit. This does not set the whole ECU temperature
rating. No PowerPAD DGN substitution is allowed without a footprint change.
[TI primary datasheet](https://www.ti.com/lit/gpn/ucc27524a-q1).

Each channel uses a non-retriggerable rising-edge LTC6993-1 and three-input AND.
The command must be HIGH, its window active and hardware permission present.
SET147k1%/25ppm, DIV100k/39.2k selects N4096. Nominal window12.04224ms;
conservative IC/resistor/100°C drift budget11.6182..12.4732ms. This is not a
dwell map. A new edge during the window cannot extend it; a new edge after
expiration can start another window. Multi-spark/maximum-RPM use requires review.
An open SET resistor is not covered by a fail-safe timer claim.
[ADI primary datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf).

STGB18N40LZT4 gate1, collector/tab2 and emitter3 are mapped to TO-263-2. The
gate has10R series and10k gate/emitter pull-down. Each emitter returns through
WSLP2512R0100FEA10mOhm shunt. Each INA300-Q1 is always enabled, with LATCH
HIGH, DELAY/HYS intentionally floating. The alert persists after current falls.
See [ST](https://www.st.com/resource/en/datasheet/stgb18n40lzt4.pdf),
[TI](https://www.ti.com/lit/ds/symlink/ina300-q1.pdf), and
[Vishay](https://www.vishay.com/docs/30122/wslp.pdf) primary datasheets.

LIMIT4.99k is an available E96 value, superseding the earlier5.05k discussion.
Nominal trip `(20uA * 4990 - 500uV) / 10mOhm = 9.93A`.
The script applies ILIMIT19.85..20.15uA, resistor1%+25ppm*100°C,
shunt1%+75ppm*100°C, and a conservative865uV offset/drift/PSR/CMR allowance.
Computed threshold budget: **9.479..10.399A**. Board offsets, transient noise,
thermal gradients and response overshoot are not included.

**This is not a guaranteed10.4A short-circuit peak limit.** Comparator response
10us is typical, and IGBT turnoff adds delay. A low-inductance short can rise
much faster. At3mH and the upper threshold, stored energy is162.2mJ; that is
already near the IGBT180mJ hot single-pulse rating, before overshoot/tolerances.
Do not use this calculation as repetitive-avalanche, thermal or full-power B58
approval. Exact coil L/R/current and useful spark energy need measurement.

Fault cut-off can create an unintended spark. No soft shutdown is implemented.
Ground/shunt faults, shorted IGBT and hard low-inductance short survival remain
unqualified. Global coil power removal is necessary even with local gate disable.

## Layout constraints for integration

- Keep IGBT collector/tab copper and HARNESS_IGN in a420V transient net class;
  determine actual clearances from board/process/environment requirements.
- Place shunt at emitter return; run IN+/IN− as a short Kelvin pair to its pads.
  Separate high-current return copper to power connector/star from logic/sensor
  return. Sharing the name GND does not establish a correct physical return.
- Driver, gate resistor and gate/emitter return loop should be compact. Put100n
  and1u at each driver's supply. Avoid ignition/GDI switching loops near SENT,
  analog, lambda or timer SET/DIV traces. Keep SET capacitance low.
- Collector tab is high voltage. A chassis heatsink needs verified electrical
  isolation; do not pour ground into the tab. Check repetitive thermal losses.
- Do not add a freewheel diode or low-voltage TVS across the coil primary.
- Alternative `variant="logic"` is a separate generated assembly with no IGBT
  or comparator; it is not routed/released or selectable in firmware. There is
  no DNP jumper spanning the passive assembly's high-voltage collector net.

## Actual validation

KiCad9.0.9 isolated fixture ERC: **0 errors,0 warnings,0 exclusions**.
Actual KiCad XML export audited:146 production components,442 mapped pins,
104 nets. Additional independent assertions check IGBT G/C/E, comparator
LATCH/ENABLE/ALERT, timer/AND pin mapping, guarded driver inputs and enables,
and that each collector reaches only its harness terminal. Standard footprint
pad inventories and hashes are in `reports/net_and_footprint_audit.json`.
TO-263 pad2 broad tab and1/3 pitch are explicitly checked. Package-family and
pin-number review is not solder-joint/process qualification.

Ten tests pass for the event-level timing contract, stuck HIGH, non-extension,
latched fault, permission/supply-valid inhibition and variant separation. Supply
validity in the ideal model is an assumption; it does not simulate analogue
brownout. The XML audit checks generated wires, not just the generator manifest.
No whole-board ERC/DRC, SPICE transient, real short or thermal test was performed
in this workstream. SVGs and rendered channel/common/fixture previews were
visually inspected. All eight channel sheets share one generator template.

From repository root on Windows PowerShell:

```powershell
py -3.12 Power8GDI/hardware/design/ignition/validate_ignition.py prepare
py -3.12 Power8GDI/hardware/design/ignition/test_ignition.py
$ign = '/work/Power8GDI/hardware/design/ignition'
docker run --rm -v "${PWD}:/work" -w $ign kicad/kicad:9.0 kicad-cli sch export netlist --format kicadxml -o reports/ignition.net.xml ignition_validation.kicad_sch
docker run --rm -v "${PWD}:/work" -w $ign kicad/kicad:9.0 kicad-cli sch erc --format json --severity-all --exit-code-violations -o reports/erc.json ignition_validation.kicad_sch
docker run --rm -v "${PWD}:/work" -w $ign kicad/kicad:9.0 python3 validate_ignition.py audit
docker run --rm -v "${PWD}:/work" -w $ign kicad/kicad:9.0 kicad-cli sch export svg -o reports/svg/ ignition_validation.kicad_sch
```

`node render_ignition.cjs` inside this directory uses the installed `sharp`
package via NODE_PATH to normalize SVG filenames and render PNG previews.
The XML export is force-tracked because repository-wide ignore rules match XML.
Production integration must rerun parent ERC and replace the external fixture
with the actual supplies, MCU, connectors and safety latch before routing.
