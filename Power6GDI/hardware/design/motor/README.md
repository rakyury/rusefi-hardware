# DBW/EWG motor interface candidates

Two editable sheets contain 50 connected components. They implement a provisional current-limited H-bridge for each motor, independent hardware permission, MCU disable, PWM/direction encoding, input defaults and separate reverse-protected feeds. **The user has not selected either motor. These are bounded engineering candidates, not approved DBW/EWG power stages.** A motor requiring higher start/stall current can require a different driver, diode, connector allocation and cooling design.

Each DRV8871DDAR receives its own externally fused raw supply (`VBAT_DBW_FUSED` or `VBAT_EWG_FUSED`) through STPS2H100UY. It does not draw motor current through the logic regulator. SMBJ24CA is connected **after** this blocking diode, across the driver VM rail, so its path includes regenerative motor energy. The capacitance and TVS energy rating cannot be finalized without motor inductance, maximum speed, cable impedance and braking energy. The 100uF/50V bulk footprint is provisional; a specific capacitor has not been qualified.

The 36.5kOhm/1% ILIM resistor gives a calculated nominal 1.753A chop threshold, with approximately1.600–1.909A from the datasheet's current constant and resistor tolerance. It is not a continuous output rating, and current can overshoot during blanking. The diode's2A rating also depends on lead temperature. Driver silicon has 3.6A peak capability, but that does not establish either continuous motor current or a permissible stall duration on this PCB. The DRV8871 is an industrial candidate; no AEC-Q100 claim applies to it.

For each channel the physical gates implement:

`IN1 = PWM AND HW_ACTUATOR_ENABLE AND NOT DISABLE AND NOT DIR`

`IN2 = PWM AND HW_ACTUATOR_ENABLE AND NOT DISABLE AND DIR`

Either hardware permission low or the MCU's active-high disable forces both driver inputs low. This selects coast/sleep. PWM-low uses fast decay; firmware must account for the driver's sleep/restart timing. Direction polarity at the mechanism remains unknown until motor wiring and position feedback are checked. The static truth table does not qualify dynamic gate glitches or power sequencing.

DISABLE has a10k pullup; PWM and DIR have100k pulldowns. Each driver's input has an external10k pulldown. The latter keeps the estimated steady power-off voltage below the driver's0.5V low limit even using11uA combined leakage without relying on its internal pulldown. Power-up/brownout timing still needs measured fault tests. Gate power and the hardware latch are common dependencies: this is not a redundant or single-fault-tolerant actuator shutdown design.

DRV8871 has automatic fault retry and no external fault output or motor-current telemetry. Those are explicit limitations for the eventual ECU. Redundant throttle/pedal checking, actuator plausibility, current monitoring, independent power isolation and latched fault handling are unfinished system requirements. The two motor sheets do not complete those functions.

## Verification

`build_motor.py` generates both sheets, symbols, manifest and BOM. Export each with KiCad9 `sch export netlist --format kicadxml` to `dbw_driver.xml` and `ewg_driver.xml`, then run `check_motor.py`. The checker evaluates all16 input combinations for each channel directly from the exported gate netlist, checks the independent disable paths, catches a deliberately bypassed hardware inhibit, verifies diode/TVS placement and checks supply/ground/ILIM pins. It is a static electrical-connectivity check, not a motor simulation or hardware validation.

## Primary sources

- [TI DRV8871 datasheet SLVSCY9B](https://www.ti.com/lit/gpn/DRV8871): pin table, PWM truth table, current regulation, thermal/automatic retry limitations.
- [TI SN74LVC1G08-Q1 SCES556H](https://www.ti.com/lit/gpn/SN74LVC1G08-Q1): SOT23-5 AND gate and partial-power behavior.
- [TI SN74LVC1G04-Q1 SCES482F](https://www.ti.com/lit/gpn/SN74LVC1G04-Q1): inverter pinning and partial-power behavior.
- [ST STPS2H100-Y DS6949 Rev2](https://www.st.com/resource/en/datasheet/stps2h100-y.pdf): automotive diode limits and SMB package.
- [Littelfuse SMBJ family](https://www.littelfuse.com/~/media/electronics/datasheets/tvs_diodes/littelfuse_tvs_diode_smbj_datasheet.pdf.pdf):24V standoff/38.9V rated pulse clamp forSMBJ24CA at25C from the indexed primary datasheet. The live vendor asset link was unavailable during review; procurement must obtain the current datasheet.

The active-device symbol pin maps were authored against these sources. Passives are extracted official KiCad symbols with attribution in `../core_sources/KICAD_LICENSE.md`. Standard KiCad footprints are used; motor driver thermal-pad assembly review remains open.
