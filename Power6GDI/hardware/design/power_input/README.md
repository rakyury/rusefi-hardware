# Logic input supply: electrical candidate

The sheet contains 19 connected parts and can be opened in KiCad 9. The project root is `../Power8GDI_Core.kicad_sch`. This branch is for logic only; GDI boost, injectors, pumps and motor stages must not be powered through D501.

## Connections and component decisions

`VBAT_MAIN_FUSED` is an externally fused supply. D502 is a Littelfuse SMBJ24CA bidirectional 24 V TVS candidate, specified for38.9V clamping at its rated pulse current at25C. Hot clamping and parasitic overshoot remain unqualified. D501 is ST's automotive STPS2H100UY, SMB, 100 V / 2 A. Its cathode (pad1) feeds `VBAT_LOGIC_PROTECTED`; anode (pad2) connects to the fused supply. An automotive part designation does not qualify this assembled ECU for vehicle transients.

U501 is LM5164QDDARQ1 with an exposed ground pad. It supplies `+5V_CORE`; U102 on the core sheet supplies the shared 3.3 V domain. Separate GDI regulators provide `+5V_GDI_A/B`. PGOOD is pulled to 3.3 V and is currently a diagnostic provision, not a hardware actuator interlock.

The selected buck divider gives an ideal 4.9996 V and RON gives approximately 303.37 kHz. A 47 uH Coilcraft MSS1246T-473MLC and Type-3 ripple injection are populated. The injection network is SW--110k--RIPPLE, RIPPLE--3.3nF--VOUT and RIPPLE--220pF--FB. Bootstrap capacitance is 2.2 nF, 5%.

R501/R502 give nominal 8.295 V rising UVLO **after** the series diode. The diode adds input headroom: this candidate does not maintain operation through a deep cold crank. Resistor and comparator tolerances give a conservative rising threshold near 8.713 V and a minimum falling threshold near 7.344 V at the protected rail. These are threshold estimates, not startup test results.

The output design target is 0.8 A. At 53.3 V input and -20% inductance, the calculated peak is approximately 0.999 A, below the IC's minimum 1.25 A peak limit. This calculation does not establish the complete ECU current budget, thermal limits, or transient behavior. PT2001 VCCIO maxima are unavailable in the public short datasheet; their current remains an explicit unknown. The output's injection-related DC offset and actual effective capacitor values require measurement.

## Layout requirements

- Keep U501 VIN/GND and C501/C502 loop short. Put C504 beside BST/SW. Connect the exposed pad to ground with thermal vias.
- Minimize SW area; keep FB/RON and their ground returns away from the switching loop. Kelvin-sense VOUT after L501.
- Locate D502 near the input contact and return path. Verify fuse/TVS coordination before applying surge tests.
- C503's 8x10 mm footprint is provisional. Select an actual 63 V capacitor with suitable ESR, ripple current, temperature life and cold impedance before footprint release.

No transient test, thermal test, line/load response test or EMC test has been run. Input source inductance, bulk damping, TVS pulse energy and capacitor DC-bias derating remain open. Current-limit arithmetic is not a substitute for those checks.

## Reproducibility and provenance

Run `python build_power_input.py` from any directory after the core helper is present. The generated manifest records every reference, pad, net and footprint plus calculated assumptions. `check_power_input.py` verifies the exported XML against critical electrical connectivity and recomputes the design margins independently.

The selected symbols were extracted from the official KiCad 9.0.9 library in Docker image `kicad/kicad:9.0`, digest `sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`. KiCad libraries are distributed under CC-BY-SA 4.0 with the KiCad library exception; retain the upstream attribution and exception when distributing extracted library material. Source symbols: Device R/C/C_Polarized/L/D_Schottky/D_TVS and Regulator_Switching LM5164DDA. No downstream symbol pin type was weakened to hide ERC findings.

Primary sources, consulted 2026-10-21:

- [TI LM5164-Q1 datasheet, SNVSB51C](https://www.ti.com/lit/gpn/LM5164-Q1), pin table, design equations and Type-3 network. This 5 V circuit is a calculated adaptation, not the datasheet's 12 V example.
- [ST STPS2H100-Y datasheet, DS6949 Rev2](https://www.st.com/resource/en/datasheet/stps2h100-y.pdf), electrical ratings, SMB package and order code.
- [Coilcraft MSS1246T-473](https://www.coilcraft.com/en-us/products/power/shielded-inductors/ferrite-drum/mss-mos/mss1246t/mss1246t-473/), inductance, DCR and current ratings.
- [Littelfuse SMBJ series](https://www.littelfuse.com/assetdocs/littelfuse_tvs_diode_smbj_datasheet.pdf?assetguid=09a6ae9a-73cb-4ac4-acac-e6dab92ab953), TVS family candidate; final automotive grade and surge envelope are not frozen.
- [KiCad library license](https://www.kicad.org/libraries/license/).

The standalone ERC reports undriven external power pins. The integrated ERC must be reviewed independently; no exclusions are authorized to convert unresolved supplies into a pass.
