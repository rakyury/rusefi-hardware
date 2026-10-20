# STM32F7 resource allocation — unresolved design ledger

**Draft only — not an MCU schematic or validated netlist.**
Do not start PCB routing from this document. Actual STM32F767 package choice, pin multiplexing, DMA streams and all dedicated ADC/clock pins are still to be verified.

## Working requirements

- 8 DI engine-timed digital commands to 2x PT2001, not high-voltage outputs driven directly by MCU.
- 2 independent HPFP engine-timed commands, one to each GDI section.
- 8 smart coil logic commands, and 8 *optional* low-side port injectors.
- 4 VVT PWM, 8 additional auxiliary PWM, 4 service low-side.
- Two independent H-bridge motor controllers (DBW/EWG), analog feedback, 2 knock, 4 SENT, 2 LIN, 2 CAN, USB, SD, crank and cam.
- PWM hardware channels vs CPU-scheduled PWM vs smart external drivers MUST be distinguished. No promise of 12 independent hardware PWM channels.
- UART for LIN needs a dedicated automotive LIN transceiver; 2 LIN buses require 2 transceivers.

## Existing F7/Hellen signal mapping (reference, NOT free-pin list)

| Hellen macro | STM32 signal | Existing Power4GDI use | Power8GDI action |
|---|---|---|---|
| H144_LS_1..4 | PG7/PG8/PD11/PD10 | DI1..4 commands | Keep as candidates, confirm drive circuitry |
| H144_LS_5 | PD9 | Not assigned to GDI in default | Candidate DI5 |
| H144_LS_6 | PF12 | HPFP1 command | Must relocate if reassigned to DI6 |
| H144_LS_7 | PF13 | PT2001 DRVEN | Must relocate if reassigned to DI7 |
| H144_LS_8 | PF14 | PT2001 RESETB | Must relocate if reassigned to DI8 |
| H144_IGN_1..8 | PC13/PE5/PE4/PE3/PE2/PB8/PB9/PE6 | IGN1..4 default | 8 logic output candidates, full pin review needed |
| H_SPI2_CS | PB12 | PT2001 SPI2 CS | PT2001 A CS candidate |
| H_SPI2_SCK/MISO/MOSI | PB13/PB14/PB15 | PT2001 + other SPI2 devices | Bus load/driver arbitration, separate CS for B |
| H144_IN_RES3 | PF8 | PT2001 FLAG0 | PT2001 A fault candidate |
| H144_IN_SENS1/2 | PF3/PF4 | Cam1/Cam2 | Preserve trigger sensing, avoid ADC conflicts |
| KNOCK_PIN_CH1 | PF7 | ADC3 knock channel 1 | Preserve and add second analog knock path |
| H144_CAN_RX/TX | PD0/PD1 | CAN | Protect and retain |
| H144_UART2_TX/RX | PD5/PD6 | UART candidate | LIN1 candidate (must check multiplexing) |
| H144_IN_AUX2_DIGITAL | PE9 | SENT candidate, TIM1 CH1 | SENT1 candidate, verify ICU allocation |

## Critical conflicts and work items

- The prior provisional assumption that `H144_LS_1..8` are free is **incorrect for Power4GDI defaults**: LS6/7/8 are already HPFP/DRVEN/RESET. Moving them requires schematic + firmware changes.
- A second PT2001 needs independent chip-select, reset, enable, diagnostic input, and a verified power/fault-disable design. Candidate MCU pins are **unassigned**, not promised.
- Shared SPI2 also carries TLE9104 transactions; inspect driver mutual exclusion, chip selects and priority under high-load conditions.
- 4 SENT inputs need ICU timer allocation, callback instances, filters and queue-overflow protection; the current count in base configuration is 1.
- Two knock front-ends must be independently conditioned and mapped to ADC3 sampling groups; avoid collisions with cam and GDI control wiring.
- Reserve TIM5 precise event scheduler, TIM6 ADC scheduler; inspect actual board configurations before assigning PWM or capture channels.
- Define startup/default-state safety for each GDI enable, HPFP, motor H-bridge and auxiliary output.
- Validate voltage, current, thermal and connector packing; a 34-way interface cannot be accepted solely based on contact count.
- B58 oil valve: reserve AUX_PWM1 and feedback pressure sensor, but leave duty polarity, switching frequency and actual driver choice open until measured.

**Gate for electrical schematic:** no PCB footprints or routing approval until full resource/multiplex collision review is signed off.
