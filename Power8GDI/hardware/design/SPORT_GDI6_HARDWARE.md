# Power6GDI: six-cylinder electrical candidate

Active scope approved on 2026-10-25: **6 DI + optional 6 high-impedance PI,
2 HPFP, 6 ignition channels, DBW + EWG, one onboard LSU4.9 controller,
two knock inputs, two external CAN buses, SENT and LIN**. The `Power8GDI/`
directory and KiCad library identifiers are retained for compatibility. The
eight-cylinder version remains recoverable from Git before this change.

Open **Power8GDI_Core.kicad_sch** in this directory. `core.net` is the
authoritative KiCad XML export. The old `hardware/Power8GDI_RevA.*` files are
historical interface-only placeholders, not the active electrical design.
Unreferenced historical leaves must not be assembled as additional channels.

## Physical changes

| Function | Current hardware |
|---|---|
| Direct injection | Two MC33PT2001AE banks, three injector branches per bank |
| HPFP | One valve branch on each bank, START6 |
| PI / auxiliary low sides | Six TLE9104SH ICs; 6 PI + 4 VVT + 8 AUX PWM + 4 service = 22 outputs |
| Unused TLE9104 channels | Last two inputs tied to 3V3 (OFF); outputs NC; unused inverter inputs grounded |
| Ignition | Six guarded IGBT channels, three dual UCC27524A gate drivers |
| Motors | Two TLE9201SG bridges; two independent protected feeds |
| Wideband | One Hellen-derived F042/analog node with hardware heater permission |
| Communications | Two external CAN, two LIN, four SENT inputs |
| Knock | Two inputs into one TPIC8101 front end |
| Harness | Four 34-way headers; 18 deleted-function contacts explicitly NC |

Four VVT channels are retained as the existing working allocation until the
engine/bank requirements are frozen. One external CAN EGT channel remains the
working assumption; no thermocouple converter is silently added onboard.
Peak/hold DI uses PT2001 power stages. The PI option currently supports
high-impedance injectors; low-impedance PI peak/hold is a separate circuit change.

The user selected **B58B30 Gen2 DI injectors** and **IDX1050 PI injectors**. These names are preserved verbatim; no guessed Bosch/OE number or ID1050x substitution is implied. DI current waveform/Vboost and the exact PI variant remain to be checked against manufacturer data. This selection is not bench qualification.

## PT2001 mapping and source provenance

| Main-MCU function | Main-MCU pin | PT device input | Physical injector output |
|---|---|---|---|
| DI1 | PG7 | PTA START1, pin4 | PTA H1 / L1 |
| DI2 | PG8 | PTA START2, pin5 | PTA H1 / L2 |
| DI3 | PD11 | PTA START3, pin6 | PTA H3 / L3 |
| DI4 | PD9 | PTB START1, pin4 | PTB H1 / L1 |
| DI5 | PF12 | PTB START2, pin5 | PTB H1 / L2 |
| DI6 | PF13 | PTB START3, pin6 | PTB H3 / L3 |
| HPFP1 | PD8 | PTA START6, pin9 | PTA H5PUMP / L6PUMP |
| HPFP2 | PD12 | PTB START6, pin9 | PTB H5PUMP / L6PUMP |

The reference-derived GDI4 rev.d schematic and PCB are revision-matched and
unchanged. Each generated bank removes source **Q10, D14, C50, C61, R18, S4**,
including the associated fourth low-side/gate wiring. U1 D_LS4 pin35 and G_LS4
pin44 become NC; START4 pin7 has a 10k pull-down (R297/R397) on a separate unexposed net; firmware must leave it as an unused input. Other retained pin connectivity
is checked against the pinned original source partition, not against generator
labels. Per bank: 123 source components + 5 regulator/isolation parts + the new START4 pull-down.

[NXP MC33PT2001 SDS Rev10.1, Table2 note2](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf)
permits unused nonsupply pins to remain open. A pull-down biases unused START4 while avoiding a hard short if this bidirectional pin is accidentally configured as an output.
This does not qualify the loaded microcode or the current waveform: the
three-injector active mask, simultaneous scheduling and HPFP events require
firmware/hardware verification. Fuel-rail assignment is independent of PT bank.

The donor copper importer excludes removed parts and unused IC nets before
its connectivity/endpoint audit. It does not copy floating fourth-channel
copper merely because an unused PT package pad still exists.

## Motor and wideband interface changes

The diagnostic chain is now MOSI → DBW → EWG → gated MISO, **16 clocks per
CS pulse**, wire byte order EWG then DBW. PWM remains TIM3 CH1/CH3 with a shared
frequency. U6190 receives EWG_SPI_SO. Old MOTOR3/4 bridge assemblies and main-MCU
controls are absent from the root export. The existing 2 A/channel figure is
an unqualified design target, not an actuator rating.

Only WBO1 remains, with data/diagnostic CAN IDs 400/401 in the source-derived
working profile. F042 local PWM, main-MCU heater permission and global hardware
permission remain separate. The extra CAN transceiver inside the lambda node
shares CAN2; it is not a third external CAN bus.

## Verification and manufacturing boundary

`python Power8GDI/hardware/design/run_review.py --schematic-only` regenerates
the hierarchy, exports in pinned KiCad 9.0.9 and runs electrical, footprint,
resource and fault-mutation regressions. The latest run is recorded in
`review_validation.json`. `check_sport_profile.py` independently checks the
six-cylinder scope directly in the XML export.

The current root contains **1092 physical positions: 1047 installed components, 11 bare PCB features and 34 DNP**.
The 21 power-source errors were resolved by explicit documented PWR_FLAG assertions for real supply paths through inductors, diodes, fitted resistors and protected MOSFETs. `power_sources.py` independently checks those paths and rejects removed or DNP source components. Native ERC retains **12 unused PT diagnostic-label warnings**, without exclusions. Static connectivity checks pass. That is not a fabrication or engine-use release.
PT enable-boundary resistors remain DNP pending qualification.

`integrated_bom.csv` is generated from this exact root export and carries its
SHA-256 on every row. `integrated_bom_manifest.json` records counts and gaps.
Source LCSC fields and reference MPNs are kept separately; generic passives and
source inductors without an order code are explicitly unresolved. A price quote
must name the final BOM hash and must not reuse the historical eight-channel BOM.

The matching placement/routing candidate is generated in `board/gdi6_candidate/`
using the existing **245 × 165 mm, four-layer, 1.6 mm** working outline. Its own
netlist/PCB comparison and native DRC are required; the old eight-channel PCB
reports are not evidence for this candidate. The board remains incomplete until
routing, high-energy clearances, power/thermal calculations, device loads,
startup/fault behavior, EMC and physical measurements are closed.
