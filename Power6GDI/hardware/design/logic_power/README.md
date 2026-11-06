# Logic power replacement, 2026-10-23

Two actual KiCad sheets and 32 populated parts replace the complete old LM5164 input sheet and the TLV1117 3.3 V sheet. This is an electrically connected engineering design, not a measured or released supply. No PCB routing or DRC claim is made here.

## Integration contract

Read `interface.json` for deterministic sheet UUIDs. Add `logic_power/logic_5v` and `logic_power/logic_3v3`. Remove root instances of **both** `power_input/power_input` and `core_power`, their manifests and placement entries; keep historical source files for traceability. U102/TLV1117, U501/LM5164 and their old source circuits must not remain on the live netlist. Run `check_logic_power.py FULL_ROOT_NETLIST.xml` after integration: it rejects the old regulator refs. Add this directory's symbol library to root sym-lib-table. All footprints are standard KiCad9 libraries, checked in `footprint_check.json`.

Input is VBAT_MAIN_FUSED and GND. Outputs preserve **VBAT_LOGIC_PROTECTED**, +5V_CORE and +3V3. VBAT_LOGIC_PROTECTED feeds LIN VSUP and, through their existing branch diodes, the two TPS7B4253 trackers. The sensor trackers use +5V_CORE only as their ADJ reference; sensor load must not be counted as a 5V buck load. Existing GDI local 5V regulators and motor battery protection remain independent.

LP5_PG_RAW links the two new sheets. It is a 5V-domain net and must not connect directly to an MCU pin. PGOOD_3V3_CORE is an optional 3.3V open-drain diagnostic with local pullup, not a new safety permission. Unused historical PGOOD_5V_CORE disappears. No MCU GPIO change is required.

## Manufacturer-reviewed circuit

* U5200 LM76003QRNPRQ1 is the 3.5A silicon variant, operated here at a 2A design target. TI SNVSAU3B p4 defines all 30 pins and grounded DAP. NC pads7/19/23/27..30 are deliberately connected to ground copper as TI recommends. RT is deliberately open for500kHz; MODE is grounded for auto PFM/PWM. BOOT has470nF toSW, internal VCC2.2uF toGND and no external load; BIAS is5V with1uF. Neither VCC nor SW is an external logic rail. [TI LM76003-Q1](https://www.ti.com/lit/ds/symlink/lm76003-q1.pdf)
* L5200 is XAL7070-682MEC,6.8uH/20%. The nominal 25C manufacturer values are12.8A at30% inductance reduction and19.62mOhm maxDCR. At60V,440kHz and initial Lminus20%,2Aload gives2.963A computed peak, below the LM76003 minimum HS current limit4.35A. Hot saturation and core losses still require evaluation; typical Isat is not a guaranteed hot rating. Land pads1.92x6.50mm at4.82mm centres agree with manufacturer drawing and installed KiCad footprint. [Coilcraft XAL7070](https://www.coilcraft.com/getmedia/1ba55433-bcc8-4838-9b21-382f497e12e0/xal7070.pdf)
* U5300 TPS62130AQRGTRQ1 is adjustable, not the fixed5V TPS62133A. FSW tied HIGH selects1.25MHz; DEF low. All three SW pads feed L5300; VOS senses3V3 directly and FB has100k/32k. AVIN100nF and PVIN10uF are separate local placements on the same5V supply. C5303=3.3nF sets nominal1.65ms ramp. RGT0016C has1.68x1.68mm grounded exposed pad17, matched to the installed KiCad footprint. [TI TPS62130A-Q1](https://www.ti.com/lit/ds/symlink/tps62130a-q1.pdf)
* L5300 XAL5030-222MEC is2.2uH/20%,9.2A typical30% Isat at25C and14.5mOhm maxDCR. It gives more fault-current margin than the smaller XFL4020 recommendation. Computed peak at5.12Vin,1Aload,Lminus20%,assumed1MHz is1.333A. DCS switching frequency is load/input dependent;1MHz is an analysis assumption, not a guaranteed oscillator minimum. [Coilcraft XAL5030-222](https://www.coilcraft.com/en-us/products/power/high-voltage-inductors/xal/xal50xx/xal5030-222/)
* D5200 STPS5H100BY-TR is the automotive5A/100V DPAK rectifier: pin1NC,2/tabK,3A, consistent with the sibling WBO heater feed. Its5A rating is conditional on case temperature; estimated dissipation at the2.60A combined protected-battery envelope is1.46W using ST's loss equation. Provide real tab copper and thermal verification. D5201 retains the existing SMBJ24CA candidate,38.9V rated clamp. There is no qualified load-dump envelope and no independent overvoltage disconnect for the sensor/LIN battery rail. [ST DS6906 Rev3](https://www.st.com/resource/en/datasheet/stps5h100-y.pdf)

The RNP0030B LM footprint EP is1.8x4.5mm. Grounded EPs need thermal vias in PCB integration, not a thermal rating inferred from library geometry. Avoid high-current return flow through AGND/FB. Keep PVIN-cap-PGND loops short, SW area small, feedback Kelvin-routed away from SW and coils. Do not route LP5_PG_RAW alongside switch nodes. Connect the marked short winding end of each inductor to SW per vendor orientation guidance when the chosen placement is reviewed.

## Budget and operating assumptions

`calculate.py` produces `power_budget.json`; all entries are **engineering allocations**, not measurements or guaranteed sum-of-maxima for unspecified loads. Main3V3 allocation is0.700A with a1.000A target. For the upstream calculation the entire1A target is charged at3.3V/(4.9V*0.85)=0.792A, assuming an85% efficiency floor that must be measured. Direct5V allocation1.050A gives total1.842A and0.158A headroom under2A. This supports the requested targets provisionally;5V spare capacity is modest, so further5V accessories require budget review.

|5V direct load group|Allocated current|
|---|---:|
|Two WBO controllers including local3V3 LDOs|0.400A|
|Two main TCAN1042 transceivers incl specified fault condition|0.240A|
|Eight ignition gate drivers, static and dynamic allowance|0.100A|
|Six TLE9104 logic supplies|0.180A|
|VR/knock/level conversion|0.080A|
|Hall/pullups/sensor references/other|0.050A|

Per WBO node the200mA envelope is110mA for the TJA1051's documented dominant bus-short condition,50mA local MCU allocation,10mA analog/reference allocation,10mA LEDs and20mA gate/other allowance. This budget uses the actual root WBO parts (XC6206,F042,MCP6004,AD8628,REF3033,TJA1051,AHCT gate), not the removed CJ125 design. TJA1051 normal dominant max is70mA; its stated fault110mA is not every conceivable bus fault. TCAN1042 similarly specifies up to110mA in its stated dominant fault condition;120mA each is allocated. Main STM32F767 gets350mA including analog/clocks; ST tables show269mA at200MHz/105C for the quoted all-peripheral workload, with analog additions. Firmware clocks and hot temperature limits must obey its selected speed grade. [TJA1051](https://www.nxp.com/docs/en/data-sheet/TJA1051.pdf), [TCAN1042](https://www.ti.com/lit/ds/symlink/tcan1042h-q1.pdf), [STM32F767](https://www.st.com/resource/en/datasheet/stm32f767ii.pdf)

Four H bridges, two heater currents, injector/PI/ignition primary currents and GDI local supplies use their own battery feeds and are excluded from5V/3V3 load sums. Four bridge logic interfaces receive20mA in the3V3 allocation. Two sensor outputs are separately allocated0.600A and LIN0.150A on protected battery. With2A5V load at6.4V protected input and assumed85% buck efficiency, this gives2.60A input-diode current. Sensor tracker dissipation at high battery may limit those outputs well below300mA each; no300mA board rating is asserted.

## Default, startup and faults

EN470k/100k gives nominal6.863V rising threshold on the protected side of the diode; conservative static resistor/comparator/leakage bounds6.393..7.231V. Battery must exceed the selected diode drop in addition. This is not a cold-crank ride-through design. Nominal normal-operation study range is8..18V battery; verify threshold corners and minimum5V headroom at actual current.

LM starts5V first. Its open-drain PG is pulled up from5V, never3V3, avoiding a circular startup dependency. PG low disables the downstream TPS. A1M fallback pulls this enable low when its pullup source disappears. LM PG deglitch and its validity at very low input do not constitute an independent safety circuit. Existing TPS3808 supervisor and hardware actuator latch remain required. Loss of5V PG removes3V3 regulation; residual capacitance and external backfeed can keep voltages present. The10k3V3 bleed does not guarantee a safe discharge time. No PG is tied into an actuator fault bus in these sheets.

Both bucks have their documented current-limit/thermal behavior, but a failed output is not isolated from the other rail. A3V3 overload may propagate into5V. Reverse input is blocked by the front diode; this does not solve backfeed from programmer, USB, sensor clamps or IO. Test power-up/down, slow ramps, brownout, output short, external powered peripherals and reset/dwell disable using current-limited supplies before actuator connection.

## Remaining release gates and verification

Feedback tolerances plus specified reference/leakage produce static5V4.921..5.099V and3V3 PSM3.209..3.408V, excluding ripple/transients. Output5V has4x47uF25V X7R, nominal188uF with a required effective minimum100uF. Input2x10uF100V requires combined effective>=10uF across the qualified voltage range. The180pF feedforward value follows TI's estimate for156uF effective capacitance. Exact capacitor order codes/DC-bias/temperature curves must be selected, then re-evaluate all parallel board capacitance and measure loop/load-step response. These capacitor and thermal gates are unresolved; nominal capacitance alone is not a validated filter.

Reproduction: run `build_logic_power.py`, `calculate.py`, then KiCad9.0.9 XML-netlist/ERC exports of both sheets to ignored `work/`; run `check_footprints.py` inside the pinned KiCad Docker image and `check_logic_power.py`. `validation.json` records results. The tests independently assert manufacturer pin wiring and reject reversed input diode, bootstrap-to-ground, circular3V3 PG pullup, wrong TPS frequency strap and a retained old LDO. Standalone ERC source warnings are kept visible; no suppression or synthetic power flags are inserted.

GDI is still blocked on authoritative PT2001 full electrical thresholds/shutdown semantics and verification that the loaded microcode maps HPFP commands to START6 and disables those outputs under DRVEN/fault. Shared high-side scheduling also prevents a blanket arbitrary-overlap promise. The real GDI input protection and gates do not remove those firmware/device qualification gates.

## Explicit unresolved loads

The 0.700 A allocation excludes neither the SD card nor PT2001 VCCIO by
assumption: those loads are now separately listed as unresolved in power_budget.json.
The remaining 0.300 A envelope must cover their measured/qualified peaks and
margin; it is not proven spare capacity. No selected SD-card or full PT VCCIO
maximum is available. The 5 V calculation already reserves a full 1 A of 3.3 V
conversion load. The allocation_complete flag stays false until these rows close.
