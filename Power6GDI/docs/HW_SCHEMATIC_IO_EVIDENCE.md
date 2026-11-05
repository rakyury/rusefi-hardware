# Input frontends — engineering review, 2026-10-21

The integrated hierarchy adds eight sheets and 171 components: 17 analog
channels, eight Hall/SENT receivers and one differential crank receiver.
All are provisional circuits. Sensor models, fault pulses and physical tests
have not been supplied or performed.

- The five TLV9004QPWRQ1 devices use PW/TSSOP14 pinning from
  [TI SBOS980G, table 5-3](https://www.ti.com/lit/gpn/TLV9004-Q1).
  Each active channel has a 100k/100k divider, 1nF filter, BAT54S clamp,
  unity-gain buffer and 1k/10nF ADC filter. Spare amplifiers have closed
  feedback and grounded positive inputs. Nominal divider gain is 0.5;
  input and output filter poles are approximately 3.18kHz and 15.9kHz.
  This is an arithmetic starting point, not a sensor accuracy specification.
- Two SN74LVC14AQPWRQ1 receivers follow
  [TI SCAS705B](https://www.ti.com/lit/gpn/SN74LVC14A-Q1).
  All eight channels invert. The input network is 10k series, 47k to ground
  and 47pF, with clamps to ground/5V. Open-drain sensor pull-ups are DNP.
  CAM1..4 are presently Hall/push-pull candidates; they do not implement
  differential VR cam inputs. SENT thresholds, cable loading, tick duration
  and firmware polarity need measurement and timing allocation.
- The MAX9924UAUB/V+ uses Mode A2 (BIAS, ZERO_EN and INT_THRS grounded;
  EXT unused), per [Analog Devices Rev5 table1 and figure3](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX9924-MAX9927.pdf).
  A 10k pull-up takes its open-drain output to 3V3. Input resistors and
  differential filter are initial reference values, not a qualified
  maximum sensor voltage or transient protection envelope.

STM32F767 LQFP176 draft pins are recorded in `mcu_gpio_draft.csv` and
`resource_contract.json`: CAM3/4 on PI5/PI6 (TIM8 CH1/CH2), SENT3/4 on
PB6/PB7 (TIM4 CH1/CH2), PTA/PTB flag on PG10/PG9. HPFP2 PD12 remains a
GPIO-timed request; enabling its TIM4 alternate function would conflict.
CRANK PB1, CAM1 PF3 and CAM2 PF4 require reviewed EXTI timestamp handling.
ADC pin facts and these assignments do not qualify DMA, timer sharing,
interrupt latency or the rusEFI board target.

Blocking issues: clamp leakage over temperature at the 50k divider source
impedance; ADC settling and calibration; power-off rail injection; simultaneous
short-to-battery faults; pulse ratings of resistors; sensor supplies and return
connections; NTC curves; connector current and EMC. Three NTC bias resistors
and eight sensor pull-ups remain DNP. The sensor 5V and sensor ground harness
terminals are still isolated pending their dedicated protection/return design.

The XML integration tests detect direct harness-to-MCU bypasses, wrong VR mode,
missing components and changed DNP flags. They do not simulate analog behavior.
