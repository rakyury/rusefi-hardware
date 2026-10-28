# B58B30 Gen2 / IDX1050: hardware review, 27 October 2026

Status: engineering candidate, updated 28 October. No engine, thermal, EMC or manufacturing release.
The requested names are retained exactly: six B58B30 Gen2 DI injectors and optional
six IDX1050 PI injectors. Exact OEM DI part number and exact PI suffix remain
unverified. Two HPFP loads also require their electrical profiles.

## Evidence and electrical boundary

[Bosch HDEV6 family datasheet](https://www.bosch-motorsport.com/media/catalog_content/downloads_catalog/pdf_catalog/datasheet_420215179_hp_injection_valve_hdev_6.pdf)
describes a solenoid injector family with approximate, design-dependent electrical
values: 65 V boost, 12–13 A opening current, 5.3 A pickup for 600 us and 2.6–3.6 A
hold at 12 V; ambient winding resistance is about 1.83 ohm. These are a design
envelope for investigation, not a measured B58 injector calibration. In particular,
600 us is pickup duration, not a documented 65 V boost duration. Inductance,
demagnetization time and the exact OEM waveform are unknown.

[Injector Dynamics states that its injectors are high impedance](https://help.injectordynamics.com/support/solutions/articles/4000002161-resistor-box-removal-with-any-id-injector-).
This supports the retained saturated PI architecture, conditional on verifying
what the user's name IDX1050 identifies and its flow/voltage/pressure data.

[NXP MC33PT2001 short datasheet, Rev 10.1](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf),
Table 1, gives **VBOOST max 72 V** for AE and 80 V for HAE. The short document does
not provide a full recommended-operating/absolute-maximum table; neither category
is inferred here. The internal gate supply is nominally 7 V, not the 3.3 V logic
supply. Consequently MOSFET selection must consider low gate voltage. The HAE
variant is a possible route to greater voltage allowance, but replacing AE requires
full electrical, configuration, microcode and sourcing review first.

65 to 72 V is an arithmetic difference of only 7 V, not an approved transient
margin. Internal boost control, reported errors and the MCU-controlled DRVEN
boundary do not independently prove overvoltage protection. R299/R399 remain DNP.
Release requires qualified ripple/overshoot limits, returned-energy handling and
an independent shutdown/OVP design supported by the full PT specification.

## Replaced obsolete MOSFET

The 24 BUK9230-100B positions become **Infineon IPD60N10S4L12ATMA1**, an engineering
candidate with an explicit conditional qualification field. Old LCSC sourcing is
retained only as source provenance, not as a purchase identifier for the new part.

| Parameter | Original BUK9230-100B | Selected IPD60N10S4L-12 |
|---|---:|---:|
| VDS rating | 100 V | 100 V |
| RDS(on) maximum, VGS=4.5 V | 33 milliohm | 15 milliohm |
| Gate charge | 33 nC typical at 5 V | 38 typical / 49 maximum nC at 10 V |
| Miller charge | 13 nC typical | 9 typical / 18 maximum nC |
| Junction limit | 185 C | 175 C |
| Junction-to-case thermal resistance | 0.95 K/W | 1.6 K/W |
| Single-pulse avalanche example | 150 mJ at 47 A | 120 mJ at 30 A |
| Body diode recovery charge | 196 nC typical | 150 nC typical |

Sources: [Nexperia original datasheet](https://assets.nexperia.com/documents/data-sheet/BUK9230-100B.pdf),
[Infineon selected-device datasheet](https://www.infineon.com/assets/row/public/documents/10/49/infineon-ipd60n10s4l-12-ds-en.pdf),
[manufacturer product/order page](https://www.infineon.com/cms/en/product/power/mosfet/automotive-mosfet/ipd60n10s4l-12/).
Charge, avalanche and diode figures have different test conditions; they are not
direct comparative robustness scores. Lower conduction resistance does not cancel
the worse thermal resistance, lower temperature limit, switching loss or SOA
constraints. Repetitive avalanche and the actual 65 V/current trajectory remain
unqualified. Stock observed for one board does not establish stock for 240 devices.

The [PG-TO252-3-313 package drawing](https://www.infineon.com/assets/row/public/packages/73/package_download/pg-to252-3-313-package-overview.pdf)
confirms G=1, D=2/tab, S=3. The existing rotated DPAK geometry has a 6.4 by 5.8 mm
drain land, 2.2 by 1.2 mm leads and 10.6 mm overall land extent, matching the
recommended pattern. `test_gdi_load_review.py` checks the actual library pads.
That dimensional check does not establish solder quality or heat spreading.

## Shared paths and current sensing

Each PT bank retains three DI channels and one pump. DI1/DI2 share PTA_H1 and
R212; DI3 uses PTA_H3/R213. Bank B repeats this as DI4/DI5 with R312 and DI6 with
R313. Fuel rail assignment is independent of this electrical grouping.

`hardware/design/gdi/scheduling_contract.json` reserves a shared path throughout
boost, pickup, hold and demagnetization. Commands for the paired injectors cannot
overlap. A qualified guard is required after demagnetization; it remains null and
therefore denies engine admission. A conservative one-boost-phase-per-bank rule
also applies until converter recharge and peak current are proven. Independent
paths alone do not qualify simultaneous supply power or PT microcode execution.
The check follows actual netlist shunt/driver pins and includes fault mutations.

The inherited shunt footprint declared all four pins one net-tie group. That could
hide a cross-terminal short in PCB checks. The corrected derived footprints and
board generator allow only pairs **1/2** and **3/4**, matching the copper tap at
each end of the physical two-terminal resistor. Upstream source files are unchanged.

The inherited LCSC shunt is not treated as a qualified 13 A device. A 10 milliohm
resistor dissipates 1.69 W instantaneously at 13 A; pulse duration, repetition,
temperature coefficient and cooling decide suitability. Eight power-path shunts
and the two separate VCCIO shunts must not be confused. Metal-element candidates
still require pulse/thermal and Kelvin-layout review.

The selected [Vishay WSLP1206R0100FEA](https://www.vishay.com/docs/30122/wslp.pdf)
is a 1 W at 70 C metal-strip candidate with 75 ppm/C component TCR at 10 milliohm.
Its two solder lands are changed to the manufacturer's 1.65 by 1.93 mm with
1.80 mm gap, retaining the same-terminal Kelvin taps. This does not prove the
repetitive waveform or cooling. The [SiTime SiT8924B](https://www.sitime.com/datasheet/SiT8924)
7 by 5 mm oscillator candidate likewise receives its actual 5.08 by 3.81 mm land
spacing and 2.2 by 2.0 mm pads, rotated to preserve the circuit pin ordering.
OE floating behavior, clock loading and timing remain conditional.

## Power budget: explicit calculations, remaining design work

Per bank, L201 is the 6.8 uH input filter; **L202 is the 10 uH boost inductor**.
D212 is the dual-common-cathode boost rectifier (anodes 1/3, cathode 2), in the
actual source-derived TO-263/D2PAK footprint REF_D34.
C207/C209 provide 940 uF nominal boost storage. The machine report
`gdi/load_review.json` records arithmetic examples, with no permitted operating
current implied:

- At 65 V, 940 uF stores about 1.99 J. Discharge to 60 V releases about 0.294 J.
- A 13 A load for 100 us without recharge drops that nominal capacitance about
  1.38 V. ESR, tolerance, ripple, temperature and capacitor lifetime are additional.
- Ideal conversion from 12 to 65 V gives duty 0.815; a 10 uH inductor at 100 kHz
  has about 9.78 A ripple. Neither DC current nor saturation rating follows from
  this calculation. The actual profile must determine peak and RMS current.
- A conservative charge budget of 49 nC for twelve gates at 100 kHz is 58.8 mA
  per PT bank, before driver losses. Actual simultaneous switching and the PT
  regulator capability remain to be checked against full electrical data.
- At 13 A and the selected 25 C resistance limit, one conducting MOSFET dissipates
  2.54 W instantaneously. Average and hot-junction losses require the real waveform.

Input capacitors C205/206/305/306 change from 1200 to 1300 uF, 50 V candidate
UBY1H132MHL6 in the existing 16 mm diameter, 25 mm height, 7.5 mm pitch geometry.
The 8.3% nominal capacitance increase requires inrush/input-filter review.
MCU bulk C114 becomes a 10 uF, 16 V X7R 1206 candidate; 4.7 uF minimum effective
capacitance is a test/design criterion, not a guarantee from its nominal value.

SDURB1020CT remains a sourcing gate if only an 800-piece reel can be bought. Its
unit catalogue price cannot be multiplied by two and called cash purchase cost.
No unrelated single diode, smaller DPAK or reversed pinout is accepted as a substitute.
The final selection table must identify capacitor voltage/ripple, inductor
saturation/RMS, diode switching limits, and unresolved evidence explicitly.

The [Nichicon UBY catalogue](https://www.nichicon.com/getmedia/640b351d-ceef-400c-b016-39f8657ea779/e-uby-DB.pdf)
provides 80 V UBY1K471MHL candidates for the four boost capacitors. Their nominal
rating does not establish PT voltage margin or returned-energy tolerance. Per-part
ripple and temperature limits are stored in the selection data; current sharing,
frequency correction and lifetime calculation still require validation.

The final nominal MLCC candidates require C1511 to change to 1812, C1533/C1538 to
2220, and C5208–C5211 to 47 uF/16 V X7R in 1210 on the 5 V output. Effective
capacitance and regulator stability remain open gates, explicitly stored in the
schematic sourcing fields. `apply_selection.py` checks original value/package or
an explicit hardware-approved deviation before adding MPNs, then independently
checks those fields and every mapped pin in the exported KiCad netlist. Sourcing
data cannot silently change the electrical values or fit a DNP boundary.

The PCB remains an incomplete routing candidate. ERC, netlist equivalence and
these tests do not supply thermal, transient, engine or manufacturing approval.

Verification on 2026-10-28: the complete schematic review pipeline passed,
including 34 core tests and 11 selection tests. Native ERC reports zero errors
and twelve dangling diagnostic-label warnings. The exported schematic has 49
pages. The actual board matches 1,092 physical positions and 3,464 pad/net
assignments. Its full connectivity graph still has 2,101 missing connections;
native DRC reports 740 violations in a potentially truncated report. No DRC
exclusions were added. Package updates require further placement and routing.

The exported BOM binds all 1,047 installed positions to selected order codes,
with 261 positions retaining explicit review gaps. It distinguishes 34 DNP
positions and eleven bare PCB features. Actual fitted footprints provide 3,210
SMT solder lands and 162 through-hole solder lands. The binding proof is
`hardware/design/selection_validation.json`; current board, schematic, BOM and
review hashes are sealed in `board/gdi6_candidate/artifact_manifest.json`.
