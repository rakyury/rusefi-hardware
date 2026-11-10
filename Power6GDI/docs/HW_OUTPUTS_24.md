# Twenty-four direct low-side output circuits

The electrical candidate now implements PI1–8, VVT1–4, AUX_PWM1–8 and
LS_AUX1–4 with six **TLE9104SHXUMA1** devices. Seven new sheets contain 144
components. Each output connects to its named harness terminal; these are
low-side switches for externally fused battery-fed loads, not power supplies.

The implementation follows [Infineon TLE9104SH Rev 1.31](https://www.infineon.com/assets/row/public/documents/10/49/infineon-tle9104sh-datasheet-en.pdf)
and the [PG-DSO-20-88 package drawing](https://www.infineon.com/package/PG-DSO-20-88).
The custom footprint follows the manufacturer's land pattern, including the
cross-shaped floating heat slug. Its ground connection is explicit. The
0.3 mm thermal holes require a reviewed filled/capped via process and stencil.
No generic SOIC footprint or old upstream design was substituted.

## Command and shutdown behavior

The driver inputs are **active low**. Six SN74LVC14AQPWRQ1 inverters preserve
an active-high MCU command. MCU-side 100k pull-downs, driver-side 10k pull-ups
and 100-ohm series resistors establish an off command during reset. Each
driver's EN pin separately receives `HW_ACTUATOR_ENABLE` through 100 ohms,
with a local 10k pull-down. A low EN overrides the direct command. Each
device also requires its SPI output-enable bit, which resets disabled.

Individual chip selects share SPI2 with the two PT2001 devices. SPI performs
configuration and diagnostics; it does not generate injection edges. Every
PI channel has a dedicated timed GPIO. VVT and AUX channels have dedicated
GPIO but require scheduled PWM in firmware; twelve independent hardware
PWM timers are not claimed. SPI mode changes, arbitration, driver latency,
watchdog servicing and the MCU event scheduler remain to be implemented and
measured together. The TLE datasheet's 15-us switching figures are **typical**,
not guaranteed maximum delays.

The shared reset buffer uses a 1k 1% pull-down. Six maximum 100-uA internal
reset pull-ups plus 10-uA buffer off-state leakage give 0.6161 V at maximum
resistance, below the driver's 1-V reset-low limit. Firmware holds reset
low for at least 10 us after 5-V supply stabilization, verifies configuration
with all commands off, then permits explicit arming. Loss of either supply
requires resetting and reinitializing the drivers. Partial-power behavior
still needs bench verification.

## Electrical limits still require loads and measurements

Six drivers add a maximum 60 mA to the 5-V logic load using the stated
per-device supply maximum. EN fanout additionally loads the safety flip-flop.
Neither the chip's nominal current nor its protection threshold is an approved
continuous board output rating.

For an initial bounded calculation, a 1.4-A switch-off current, 16-V battery,
50-V clamp and 7-mJ allowed driver energy imply **L <= 4.86 mH**, using
`E_driver = 0.5 * L * I^2 * Vclamp / (Vclamp - Vbattery)`.
This explicitly includes battery energy during demagnetization. The 7-mJ
choice is an engineering margin against the manufacturer's specified
14-mJ repetitive test condition, not evidence that this board meets it.
At 1.4 A and 0.35 ohm, four simultaneous continuous channels already dissipate
2.744 W in one device before switching losses. Load resistance, inductance,
duty cycle, frequency, copper temperature, enclosure cooling and connector
return current must be established. Low-impedance peak-and-hold port injectors
are outside this candidate's scope.

There is no qualified maximum-pulse hardware limiter per port injector.
The common watchdog cannot detect a stuck command while firmware still
services its heartbeat. The fuse and turn-off tests must include that fault.

## Reproduced checks

`outputs/check_outputs.py` reads KiCad's actual integrated XML. It checks
every IN/OUT, physical ground/heat slug, supply, reset and hardware-enable
path. Seven tests include injected output swaps, wrong active-low command
paths, bypassed enables, removed heat-slug ground and a reset-bias fault.
These checks pass; they are not a power, thermal or functional ECU test.

The seven new sheets were exported with KiCad 9.0.9. The first bank PDF was
visually inspected. No ERC exclusions, fabricated power flags or reduced DRC
rules were introduced by this increment.
