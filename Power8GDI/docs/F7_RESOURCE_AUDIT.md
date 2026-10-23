# STM32F7 MCU resource budget — Rev A

**Provisional MCU candidate:** [STM32F767IIT6](https://www.st.com/en/microcontrollers-microprocessors/stm32f767ii.html), LQFP176, 216 MHz Cortex-M7, 2 MB Flash, 512 KB SRAM family. The industrial-grade part is listed as active by ST. **Not yet selected for CAD symbol/footprint**: final GPIO and peripheral connectivity requires reviewing the package's actual datasheet pinout and STM32CubeMX AF/DMA allocation.

## Current logical assignment gaps

The source of truth is `hardware/mcu_gpio_draft.csv`; the parser/consistency checker is `hardware/audit_resources.py`.

```bash
python Power8GDI/hardware/audit_resources.py --gate structure # exits 0 for coherent audit inputs
python Power8GDI/hardware/audit_resources.py                  # exits 2 while release evidence is missing
```

See [the reproducible audit](HW_RESOURCE_AUDIT.md) and
`hardware/resource_audit_report.json`: 104 required functions, 26 absent rows,
32 UNASSIGNED, five conditional interface conflicts and 13 missing evidence
groups. A passing structure gate does not qualify the MCU allocation.


The existing draft assigns all 8 DI trigger signals and all 8 IGN by naming Hellen macros, but that is **not evidence that the actual Power8GDI PCB traces or all STM32 alternate functions are correct**. The expanded reproducible audit above supersedes the earlier 32-signal minimum list. This is a minimum count: an electrical design will need to allocate additional ADCs, clocks, oscillator, USB and safety control, as well as I/O expanders, if used.

## Specific verified or visible conflicts

1. `H144_LS_6` (PF12) in Power4GDI is HPFP control; `LS_7` (PF13) is PT2001 DRVEN; `LS_8` (PF14) is PT2001 RESETB. Rev A's provisional use of those as DI6/7/8 requires **explicit relocation** and independent per-chip control.
2. `PA15` is the Hellen `H_SPI3_CS` alias and is used in at least one Hellen CAN-terminator implementation. The tentative assignment to PT2001-B CS is **not reserved until all board SPI/terminator resources are resolved**.
3. `PC6=TIM3_CH1` and `PC8=TIM3_CH3` for DBW/EWG PWM share a timer period. They can have independent duties but **not independent base frequencies** without reassigning one signal.
4. `PF5` is among Hellen multi-function sensor inputs. Tentative knock2 must not share ADC and digital cam inputs; protection and filtering require an actual analog schematic.
5. Eight PI outputs demand deterministic injection timing with a suitable high-current low-side stage. A SPI-expander/TLE9104 output used as a relay must not be assumed suitable for microsecond injection timing; test driver update latency and event jitter.
6. Four VVT and eight AUX PWM channels require explicit scheduling/hardware PWM architecture; simply multiplying 4-channel low-side ICs does not ensure twelve independent safe PWM channels or current limits.
7. `SENT1..4` need four robust input-capture instances / callbacks, timers and DMA/IRQ audits; current rusEFI config may expose fewer channels than the hardware could sample.
8. Dual LIN buses require separate automotive LIN transceivers with bus protection; UART-only GPIO does not constitute an automotive LIN physical layer.
9. Two wideband oxygen sensors consume twelve harness contacts but also need dedicated heater/measurement frontends and bus/ADC resources. They are **not raw MCU ADC inputs**.
10. Four 34-way TE connector contacts must be checked for injector peak current, pump current, return-path copper/EMI, keying and mechanical envelope; the provisional signal groups are not an approved pinout.

## F7 vs H7

H7 remains deferred. Do not change target MCU family merely to work around incomplete pin mapping. A 176-pin F7 candidate provides more I/O than the 144-pin board reference; confirm its power domain, flash layout and DMA scheduling instead of assuming the previous H144 GPIO map is valid without porting.

## Release policy

`hardware/audit_resources.py` intentionally fails until complete allocation. Other static tests check only structural consistency and cannot be interpreted as ERC/DRC or product acceptance.
