# Power8GDI high-level hardware architecture

## MCU and firmware

- STM32F7 MCU, precise part number / package / clock reviewed against pin resource sheet.
- rusEFI core maintained as upstream submodule/reference, Power8GDI board target separate.
- Custom Hellen-like board HAL and two-PT2001 SPI configuration, with independent CS,
  DRVEN, RESET and fault logic.
- ECU-to-PC transport via confirmed rusEFI TunerStudio pages/INI definition;
  no serial writes until target firmware and calibration signature are pinned.

## Power distribution

12 V car supply => reverse polarity / surge protection / filtered 12V raw =>
quiet sensors 5V regulators / MCU 3V3 + 5V analog, plus separate 12V high-power
supply branches for EWG, DBW and 2x GDI boost / injector circuits.

HV boost circuits use separate copper islands and intentionally planned
return current paths. This includes attention to isolation and creepage from
logic and analog sensors. Layout rules must come from parts data and real stackup.

## Channels

8 DI = 2x PT2001 (4 injectors per) => 8 x injector +/- terminals.
2 HPFP = 2x independent PT2001 command and power path, two feedback sensors.
8 coil smart logic outputs; 8 PI outputs separately timed by ECU engine scheduler.
4 VVT and 8 spare AUX PWM (one B58 oil pump pressure solenoid), plus 4 service low-side.
2 knock analog channels, DBW dual TPS, EWG position, CAN x2 planned,
LIN x1 (x2 desirable), SENT target 4 inputs.

**Existing Power4GDI MCU lines used for PT2001 reset/enable/HPFP MUST be
reallocated before choosing new DI 5-8 wires.**

## Safety

No single software fault may leave an uncontrolled injector energized.
Independent physical disable of each GDI stage and dual motor H-bridges.
ECU restart/brownout must default all injector channels and HPFP commands OFF.
Faults on either GDI section inhibit engine operation; power re-arming
requires validated synchronized engine and supply state.
