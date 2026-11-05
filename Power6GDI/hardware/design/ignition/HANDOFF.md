# Historical ignition checkpoint — superseded by README.md

This file preserves research and the interrupted checkpoint. Current implementation
and actual validation are in README.md and reports/. MIC4427YM has since been
replaced by automotive UCC27524AQDRQ1; LIMIT is now E96 4.99k (9.93A nominal).
The statements below about not running generation/tests describe the old checkpoint.

Work paused for user-requested transfer to WIN-V7K2CF64NGO on 2026-10-23.
`build_ignition.py` has been written but NOT run, syntax-tested, ERC-checked,
rendered, integrated or routed. Do not treat this checkpoint as a validated design.
No generated sheets or manifest exist yet. No background processes started.

Parent owns shared core, MCU, harness and PCB. This branch owns ignition only.
Assigned reference range 5400–5599. Generator API:
`make_ignition(syms, root_id, variant="passive")` returns nine leaf sheets.
Parent removes old core_ignition and connects IGN_OC_OK to HW_KILL_N with R6500;
existing supervisor then latches the global safety permission off. Local bank
also directly gates all eight channels on any overcurrent alert.

External aliases: IGN1..IGN8, HW_ACTUATOR_ENABLE, +3V3, +5V_CORE, GND,
HARNESS_IGN1..HARNESS_IGN8, and open-drain active-low-fault IGN_OC_OK.
No extra MCU pin required. Passive HARNESS_IGN outputs are primary collectors,
potentially 420 V: never connect them to a smart-coil logic input.

## Decisions already researched

BMW service bulletin SIB01 01 26 identifies G42 M240i MY2023–25 and M240i xDrive
MY2022–25 as B58D. Bosch lists 0986221124 for BMW12138643360/12138678438,
three terminals and 14 V. This is candidate identification, not an exact VIN match.
Nexsys's own bench research explicitly uses an external IGBT with its tested
Bosch/Eldor B58 coils, supporting passive-coil architecture for these parts.
BMW's newer 740i announcement explicitly describes integrated coil electronics,
so “all B58 coils are passive” would be false.

- BMW: https://static.nhtsa.gov/odi/tsbs/2026/MC-11032729-0001.pdf
- Bosch: https://www.boschautoparts.com/p/ignition-coils-0986221124-
- Original bench research: https://nexsysmotorsport.com/blogs/technical-information/ignition-coil-secondary-spark-energy-comparison
- Generation exception: https://www.press.bmwgroup.com/usa/article/detail/T0382613EN_US/the-new-bmw-7-series

OEM harness pinout was NOT retrieved. Community conversion documentation gives
candidate coil pin1 +12V, pin2 ground, pin3 switched primary; TE1-1718644-1
housing and7-1452671-3 terminals. It is NOT sufficient to release a harness.
Verify exact coil part and pin numbering on actual stock harness before energizing.
Do not infer passive architecture solely from three pins.
Community lead: https://www.ms4x.net/index.php?title=B58_Ignition_Coil_Conversion

## Implemented intent, requiring review

Each command triggers LTC6993-1, ANDed with its non-retriggerable window and
bank hardware permission. Four MIC4427YM drivers feed eight clamped IGBTs.
Each emitter has a 10mOhm shunt and continuously enabled INA300-Q1 comparator.
LATCH stays high; faults persist until power cycle. All ALERT pins form the
IGN_OC_OK open-drain bus, with Schmitt cleanup before the bank permission AND.
DELAY/HYS intentionally float for 10us typical response and 2mV hysteresis.
Never disable/re-enable comparator every dwell (300us typical wakeup blind time).

Conservative initial threshold: 5.05k LIMIT / 10mOhm gives 10.05 A nominal.
Earlier discussion of 8.06k /16.07A is superseded: unknown coil inductance could
exceed the chosen IGBT's hot energy rating. The generator calculates a tolerance
budget using ILIMIT19.85..20.15uA, 1%+25ppm/100C resistor, 1%+75ppm/100C shunt,
and conservative offset/drift/PSR/CMR budget865uV. The result is a threshold
budget, NOT a maximum dynamic short-circuit current. INA response and IGBT
turnoff times are typical, not worst-case bounds; bench short tests remain required.

Timer: LTC6993-1 is NON-retriggerable rising-edge; -2 is retriggerable.
147k SET, N4096, DIV100k/39.2k gives12.04224ms nominal. Include IC2.3% and
R1% plus temperature budget; resistor temperature term not yet included in script.
Window is fault containment, not dwell calibration. A second edge during an
active window does not extend it. Retrigger/multi-spark and high-RPM behavior
must be modeled; no engine RPM support has been qualified.

Hard fault turnoff can cause unintended spark; soft shutdown is NOT implemented.
Parent must cut fuel/GDI permission and remove coil +12V feed on latched fault.
Shunt low terminals need dedicated power return copper to connector/star,
with separate Kelvin sense returns; logical GND net alone does not prove layout.
IGBT collector/tab cooling copper is HV, not chassis/ground. No flyback diode
or low-voltage TVS across primary. Repetitive avalanche and thermal margin remain
unqualified. ST hot single-pulse rating180mJ cannot be used as repetitive license.

Logic assembly is separately generated, with no IGBT and no HV bypass jumper.
It is an alternative netlist/PCB assembly, not a software selector. Default is
passive for the requested stock coils. Logic variant remains untested too.

## Datasheet pin review already done

| Part | Explicit pin mapping | Source |
|---|---|---|
| STGB18N40LZT4 |1 G,2 collector/tab,3 E; clamp360..420V;180mJ at150C|https://www.st.com/resource/en/datasheet/stgb18n40lzt4.pdf |
| LTC6993HS6-1#WTRPBF |S6:1 TRIG,2 GND,3 SET,4 DIV,5 V+,6 OUT; automotive W ordering|https://www.analog.com/media/en/technical-documentation/data-sheets/ltc6993-6993-1-6993-2-6993-3-6993-4.pdf |
| SN74LVC1G11BDCKRQ1 |1 A,2 GND,3 B,4 Y,5 VCC,6 C; B revision automotive125C|https://www.ti.com/lit/ds/symlink/sn74lvc1g11b-q1.pdf |
| SN74LVC1G17QDBVRQ1 |1 NC,2 A,3 GND,4 Y,5 VCC|https://www.ti.com/lit/ds/symlink/sn74lvc1g17-q1.pdf |
| MIC4427YM |1 NC,2 INA,3 GND,4 INB,5 OUTB,6 VS,7 OUTA,8 NC|https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/MIC4426-7-8-Dual-1-5A-Peak-Low-Side-MOSFET-DRivers-DS20006202A.pdf |
| INA300AQDGSRQ1 |1 IN+,2 IN-,3 LIMIT,4 ENABLE,5 ALERT,6 LATCH,7 DELAY,8 GND,9 VS,10 HYS|https://www.ti.com/lit/ds/symlink/ina300-q1.pdf |
| WSLP2512R0100FEA |10mOhm,1%,3W2512,75ppm/C; Kelvin traces required|https://www.vishay.com/docs/30122/wslp.pdf |

MIC4427YM full temperature grade remains to verify; do NOT claim125C/AEC-Q100.
Its1.5A rating is gate-drive peak, not coil current. Supply minimum4.5V requires
regulated5V headroom/rail-failure qualification. Pin mapping verified; current
KiCad footprint existence and pad mapping for ALL chosen packages remain to check.
Rejected obsolete options: NXP MC33810 EOL, onsemi FGBS3040 obsolete; ST VBG08H-E
active but its8A range was not blindly assumed adequate for stock coil power.

## Resume checklist

1. Review generator logic and actual datasheets again where uncertainties marked;
   calculate actual tolerance report and add timer resistor temperature budget.
2. Verify all standard footprints and pad mappings (TO-263-2, TSOT-23-6,
   SC70-6, VSSOP10, SOIC8) against package drawings; verify MIC temperature grade.
3. Run generator, build standalone validation root with real rail source symbols,
   export ERC/netlist; inspect rendered sheets for overlaps and legibility.
4. Add meaningful safety tests: stuck-high timeout, unarmed/rail loss, OC latch
   persistence, bank inhibit, no raw-command bypass, no mixed HV/logic assembly.
5. Write final HW_IGNITION_B58.md with calculations, wiring and release limits.
6. Parent integrates leaves and fault alias; parent checks complete-netlist ERC,
   real return geometry, HV clearance, heatsinking, thermal and short tests.

No manufacturing/engine approval, DRC success or full B58 compatibility is claimed.
