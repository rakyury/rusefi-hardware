# Power8GDI Rev A — preliminary design package

**Status: interface definition / floorplan only; NOT an electrically completed PCB or a fabrication deliverable.**

## Connector decision

Requested **four 34-contact connectors**, A-D, for 136 total contacts. This differs from rusEFI Huge's actual A=34, B=26, C=34, D=26 arrangement (120 total). Huge harness housing part numbers are:
- A 4-1437290-0 (34-contact, key 1)
- B 3-1437290-7 (26-contact, key 1)
- C 4-1437290-1 (34-contact, key 2)
- D 3-1437290-8 (26-contact, key 2)

Candidate 34-contact PCB headers: TE 6437288-1 (34 key1, upper), 6437288-2 (34 key2, upper), 2-6437285-5 (34 key1, lower), 2-6437285-6 (34 key2, lower), per TE Superseal catalog. Confirm mechanics and footprint drawings before PCB layout; the four coding/positions do not guarantee unique harness interchange protection.

**DO NOT use any provisional schematic wire labels to connect to PT2001 output until polarity/peak voltage/return currents and connector pin ratings are validated.**

## Interface partition
A (J1): 8 DI high/low =16 contacts; 2 HPFP high/low =4; GDI fused feeds 4; power returns 8; main power 2. Verify contact current-rating and heat before design freeze.
B (J2): 8 ignition logic, 8 PI low sides, 4 VVT low-side/PWM, 8 AUX PWM (channel 1: oil pressure control B58), 4 low-side AUX, power/return.
C (J3): VR crank, 4 cam, 4 Hall, 2 analog Knock channels, 4 throttle/pedal, MAP/baro/CLT/IAT/oil/rail/LPFP/EMAP/EWG, 5V and sensor ground.
D (J4): dual H-bridges, 4 SENT, 2 LIN (second reserved), dual CAN, 4 digital, 2 spare analog, 2 WB LSU4.9 harness placeholders, chassis/sensor return.

## Current sources
- [Power4GDI schematic Rev A](https://wiki.rusefi.com/Hardware-files/Hellen/alphax-4K-GDI-a-schematic.pdf)
- [rusEFI Huge](https://wiki.rusefi.com/rusEFI-Huge/)
- [TE 34-position header 6437288-1](https://www.te.com/en/product-6437288-1.html)
- [TE Superseal connector catalogue](https://www.te.com/content/dam/te-com/custom/documents/ts-ict-t-c-cat-2018/docs/TS-ICT-T-C-CAT-2018.pdf)
- [Proteus schematic + PCB](https://github.com/mck1117/proteus)
- [GDI4 KiCad hardware + firmware](https://github.com/rusefi/rusefi-hardware/tree/main/GDI-4ch)

## Major blockers to electrical design signoff
1. Verify four actual TE board headers, assembly/footprints and mated housings, board edge dimensions, connector lock clearance, and any mixup risk.
2. Confirm whether 136 contacts fit enclosure; mechanical target and four connector overlap along board edge must be set.
3. Select precise STM32F7 (pin count, MCU revision), flash/RAM, loader and reset/debug pins; complete every GPIO/ADC/DMA/interrupt conflict check.
4. Two GDI power sections require proven PT2001 layout with measured current loops, isolated fault control and flyback/boost voltage handling; compare PCB stack-up and copper weight against real waveforms and stress.
5. Current/contact budget: 1 mm Superseal contacts require derating with temperature and pin-adjacency; provide alternate power feed if continuous current is too high.
6. Confirm actuator type/current for BMW B58 oil-pressure solenoid; assign appropriate smart low-side/PWM and feedback sensor.
7. Expand rusEFI high pressure pump model to two independently timed outputs and implement safety validation for shared or split rails.
8. 2x LSU4.9 WBO and 2x Knock front-ends need verified individual analog filters and routing isolation.
9. LIN2, SENT2-4 and auxiliary PWM channels reserve only harness positions at this stage; map to real MCU peripheral pins after selecting MCU package.
10. KiCad ERC/DRC, impedance, safety fault injection, EMC and high-voltage clearance verification required before production.

## What is included
- `hardware/Power8GDI_RevA.kicad_sch`: actual KiCad source connector interface diagram with 136 pins and net names. No actual GDI power circuitry yet. No assigned connector footprint.
- `hardware/Power8GDI_RevA.kicad_pcb`: actual KiCad board floorplan, outline 245 x 165mm as a **temporary working envelope**, no footprints, no traces. These rectangles are planning graphics, not copper clearances.
- `pinout/power8gdi_revA_pinout.csv`: full contact map for all 136 contacts.
- `tests/test_pinout.py`: automated pinout uniqueness and requested-function checks.

## NEXT
Obtain source boards and identify validated modules. Create real electrical sheets: (1) MCU/clock/flash/debug (2) power input/protection and grounds (3) GDI1 PT2001 (4) GDI2 PT2001 (5) 8 IGN + PI and PWM (6) analog/knock/SENT (7) dual WBO (8) two DC bridges, LIN/CAN. Once schematics pass ERC, replace mechanical board placeholder with exact TE footprints and begin layout.
