# Four Huge-style motor bridges — engineering candidate

Four TLE9201SG channels replace the two old DRV8871 sheets. Seven connected KiCad leaves, 106 fitted components, actual exported netlists, local symbol/footprint libraries and 587 passing checks are included. The overall PCB, firmware and hardware qualification are separate integration tasks. No load, engine, thermal, EMC or production approval is implied.

## Integration contract

Register `Power8GDI_Motor4.kicad_sym` under library **Power8GDI_Motor4**, and the same-name `.pretty` footprint directory. Add the seven sheets using the UUIDs and paths in `interface.json`; remove `motor/dbw_driver` and `motor/ewg_driver`. Do not register these symbols under Aux/Core or alter their net aliases.

| Channel | IC | PWM / TIM3 AF2 | DIR | DIS | Output nets | Raw feed |
|---|---|---|---|---|---|---|
| DBW | U6000 | PC6 / CH1 | PI2 | PD13 | DBW_MOTOR_A/B | VBAT_DBW_FUSED |
| EWG | U6050 | PC8 / CH3 | PD14 | PD15 | EWG_MOTOR_A/B | VBAT_EWG_FUSED |
| Motor3 | U6100 | PC7 / CH2 | PI3 | PI10 | MOTOR3_MOTOR_A/B | VBAT_DBW_FUSED |
| Motor4 | U6150 | PC9 / CH4 | PI4 | PI11 | MOTOR4_MOTOR_A/B | VBAT_EWG_FUSED |

The raw feeds are existing harness VBAT_MAIN_2 and VBAT_MAIN_3. This circuitry does not draw motor power through the electronics/WBO feed or the logic regulator. Motor13 and Motor24 each have an independent LM74800 plus two common-drain 100V MOSFETs. Output rails are `MOTOR13_VS` and `MOTOR24_VS`. Both input and power returns require a combined two-motor current budget at their connector contacts.

**VSO is +3V3**, while VS is protected motor battery. TLE pin13 in our symbol represents the exposed **ground** slug. It is not a thirteenth lead. LM74800 pin13 is an entirely different **floating** exposed pad and must not be grounded.

## Disable behavior

Each TLE DIS input receives `HW_ACTUATOR_ENABLE_N OR <channel>_DISABLE` through an automotive OR gate. Channel disable and resulting DIS have 10k pull-ups; DIR/PWM have 10k pull-downs. An independent positive hardware enable controls both supply controllers, with 10k default-off EN resistors. Loss of the global latch both commands DIS and removes supply; residual bulk energy is still present. With 3V3 absent, TLE VSO sleep and unpowered logic behavior require bench verification, including mixed power/backfeed cases.

DIS high disconnects both outputs. **PWM=0 is not a substitute:** it selects a high-side freewheel state. Software must never use zero PWM alone as emergency shutdown. Disable/enable propagation is up to80us by the TLE electrical table, in addition to upstream gate/latch delays. This is not independent SIL certification or protection against an internally shorted power transistor.

## SPI contract

PB4 `MOTOR_CS_N` selects all four devices. SCK/MOSI/MISO share the existing `GDI_SPI2_*` bus. Physical order: MOSI -> DBW -> EWG -> Motor3 -> Motor4 -> SN74LVC1G125 buffer -> MISO. Buffer OE is the same CS_N; it cannot drive the shared return when deselected. TLE's own SO is high impedance with CS_N high; its asynchronous fault flag exists after CS_N falls and before the first clock edge (datasheet4.12.1). The added buffer makes board-level isolation explicit.

Use SPI **mode1**, MSB first, initially <=1MHz, 32 clocks per transaction. Send and receive byte order Motor4, Motor3, EWG, DBW. Replies correspond to the previous frame; the first reply after power-up is revision information. CS high time >=2us; meet lead/lag timing, conservatively use1us before/after clocks. Never let CS glitch: there is no hardware frame-length check. Serialize against PT2001 access and change mode/rate only while all selects are high.

Normal output control stays on PWM/DIR: keep control register SIN bit3 zero. Reads RD_DIA=0x00, RD_REV=0x20, RD_CTRL=0x60; RES_DIA=0x80 clears latched faults only after the system has disabled the actuator and established a safe retry policy. Check diagnosis TV bit5 is zero, valid coding, stale frames and communication failures. Open-load reports require suitable current/PWM state; repeat a disabled diagnostic after current settles. Do not classify low-duty and direction-change false positives as confirmed wiring faults.

All PWM pins use the same TIM3 period. Datasheet maximum20kHz; start bench work at2kHz then validate the final shared frequency, switching loss and EMC. No closed-loop current ADC exists in this implementation. Position sensors, plausibility, scheduling, stall timeout, watchdog and diagnostic handling are firmware integration requirements, not implemented firmware in this directory.

## Power and thermal budget

The LM74800 OV divider140k/10k gives nominal18.465V cutoff, conservative static17.864..19.075V including specified comparator/divider/bias/SW terms. This provides a normal-input limit below TLE's28V operating maximum. It is an actual disconnect, not a claim that a TVS alone guarantees normal supply voltage. Local SMCJ18CA devices nominally clamp29.2V at their rated25C pulse current; this is a **transient** region above normal operation and must be measured below40V absolute maximum, including wiring inductance and temperature. Input SMCJ33CA nominally clamps53.3V below the controller65V limit under its specified pulse conditions. Do not infer ISO pulse compliance from those numbers.

Per-channel **2A continuous is a design target, not a qualified rating or firmware-enforced current limit**. This implies4A continuous sum per feed and8A across all bridges. At hot TLE maximum0.2ohm per switch, conduction loss is1.6W per channel,6.4W across four, excluding switching. At3A it is3.6W per channel; at6A14.4W. The6A headline is therefore not a four-channel continuous board rating. Using the datasheet's reference30C/W PCB solely as an illustration gives48C rise at2A before switching and adjacent-channel heating; actual245x165 board copper/airflow/case conditions differ. At125C ambient the2A target is not established. Throttling or derating may be necessary.

The built-in chopper threshold spans6..10A and short detection is higher still. It does not replace an external fuse or protect an arbitrary small motor. The two100V supply MOSFETs have6.7mohm max each at25C/VGS10V: at4A this is about0.214W per pair before hot resistance. Their startup SOA and repeated OV retries need measurement with actual bulk capacitance.

The ideal-diode front end blocks energy return to the battery. Each feed has two100uF capacitors plus local TVS, but200uF stores only58.8mJ between14V and28V. Actual motor electrical/mechanical energy, braking duty and harness impedance are unknown. Neither TVS pulse power nor that small capacitor margin establishes safe regenerative braking. Qualify hot TVS pulse energy, disconnected-battery shutdown and simultaneous motors before operation. No24V jump-start operation is approved. Fuse time-current coordination, wire gauge, contact heating and permissible simultaneous peaks remain open.

## Footprint evidence and placement

Infineon TLE9201SG datasheetp25 PG-DSO-12-17 was visually inspected (`reports/tle9201_package.png`). Body7.5x6.4mm, pitch1mm, lead span10.3±0.3mm, slug4.2±0.1 by7.8±0.1mm. KiCad9.0.9 `Infineon_PG-DSO-12-11_ThermalVias` was selected by these dimensions, not its name: lead lands at x±4.8mm, y±2.5/1.5/0.5mm, size2x0.65mm, EP4.5x8.1mm. Lead1 corner, all12 positions, EP coverage and18 ground thermal vias are checked. The land pattern is a geometrically compatible candidate; assembly yield/paste/wicking and package STEP height still need manufacturing review.

Put each VS ceramic directly between pins4 and6 with the smallest loop, bulk/TVS beside it, output EMI capacitors near the chip, and use solid EP ground with multiple copper layers. The two small logic capacitors belong at VSO and OR-gate VCC. Keep power return away from sensor-ground necks. Do not route noisy motor copper beneath either WBO analog cluster. The18 thermal via holes are part of the selected footprint; ensure the global via-fill/tenting fabrication process supports it.

LM74800 DRR0012E custom footprint is copied from this project's GDI protection commit `22d5fffdca7bd3d0293909fcd0f317672701b837`. The source drawing4224874/C11/2023 uses1.3x2.5mm isolated EP; no ground vias. Its topology is independently checked again here. Supply/IC pin checks and fault mutations detect flipped inputFET, grounded LM EP, incorrect charge-pump capacitor return, ungated DIS, broken chain and forced-active MISO buffer.

Bulk `100uF50V` currently reserves `CP_Elec_10x10.5` with pin1 positive. Exact MPN, hot ripple/cold ESR and height are pending measured load demand. Passive voltage/temperature grades and TVS automotive-grade sourcing are also release gates. The symbols are connected and fitted; provisional choices are not hidden as DNP or ERC exclusions.

## Evidence and reproducibility

`checks.json` contains587 PASS checks after actual KiCad XML export, including8 deliberately injected faults that were detected. Isolated bridge leaves each have14 ERC findings, power leaves3 each, SPI leaf8: only external/cross-sheet driver and power-driver/global-label findings. There are no library mismatch findings. These isolated results do not substitute for root ERC or PCB DRC. Rendered DBW/power pages were visually inspected; allseven SVG previews are included.

From the dedicated worktree root:

```powershell
py -3.12 Power8GDI/hardware/design/motor4/build_motor4.py
docker run --rm -v "${PWD}:/work" kicad/kicad:9.0 sh -c 'for f in /work/Power8GDI/hardware/design/motor4/*.kicad_sch; do kicad-cli sch export netlist --format kicadxml -o "${f%.kicad_sch}.xml" "$f"; kicad-cli sch erc --format json -o "${f%.kicad_sch}.erc.json" "$f"; done; python3 /work/Power8GDI/hardware/design/motor4/verify_motor4.py'
```

Primary sources and local hashes are in `sources.json`. Manufacturer PDFs are reference evidence with their own copyright; they do not license manufacturer artwork or guarantee this design. No original Huge circuit asset was modified or imported here. Huge-inspired TLE driver choice, new circuitry with explicit source checks:

- [Infineon TLE9201SG datasheet Rev1.0,2014-02-25](https://www.infineon.com/dgdl/Infineon-TLE9201SG-DS-v01_00-en.pdf?fileId=db3a304345087709014518190f481cec): pins, timing, protection and package.
- [TI LM7480-Q1 SNOSD95C](https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf): common-drain protection, floating EP and OV limits.
- [Infineon IPD90N10S4-06 Rev1.1,2023-01-30](https://www.infineon.com/assets/row/public/documents/10/49/infineon-ipd90n10s4-06-datasheet-en.pdf):100V FET pinout and resistance.
- [TI SN74LVC1G32-Q1](https://www.ti.com/lit/ds/symlink/sn74lvc1g32-q1.pdf) and [SN74LVC1G125-Q1](https://www.ti.com/lit/ds/symlink/sn74lvc1g125-q1.pdf): DBV pin maps and partial-power behavior.
- [Littelfuse SMCJ series,2025-02-27](https://www.littelfuse.com/~/media/electronics/datasheets/tvs_diodes/littelfuse_tvs_diode_smcj_datasheet.pdf.pdf): clamp/current table inspected through web; direct file download denied, no local PDF claimed.
