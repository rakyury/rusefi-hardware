# Connected GDI schematic checkpoint — 2026-10-21

Two actual KiCad 9 sheets now contain 268 components: each has the 129-component
GDI4 rev.d power section, one unpopulated enable boundary, and four local 5 V
regulator components. This is a reference-derived engineering draft. **Do not
energize or manufacture it.** A connected schematic and pin parity do not qualify
the inherited circuit for this engine or establish a safe hardware inhibit.

The editable sheets, local symbol/footprint libraries, CSV BOM, exported XML
netlists, SVG drawings, ERC reports and scripts are in
`Power8GDI/hardware/design/gdi/`. `pcb_handoff.json` records every retained source
reference/net rename and every excluded reference. `source_pin_nets.json` is a
reviewed connectivity snapshot, not a synthetic netlist pretending to be an
EDA export. The verification command re-exports the original source and compares it.

## Source and device resolution

The source schematic and PCB both identify U1 as MC33PT2001AE, dated 2023-05-14,
rev.d. The rev.d manufacturing BOM instead says MC33816. The historical assembled
device is therefore **unresolved**. The new design explicitly selects MC33PT2001AE
and removes the unverified inherited LCSC identifier; it does not retroactively
correct or certify the historical BOM.

The [NXP PT2001 short datasheet](https://www.nxp.com/docs/en/data-sheet/MC33PT2001_SDS.pdf),
Rev10.1, identifies pin20 as VCC1P5, not the inherited symbol's VCC2P5.
The new symbol corrects this name, MISO's three-state output, flag bidirectional
types and supply/ground types. AE is the 72 V variant without EOI. These are
part-identification facts, not a selected operating boost voltage. The exact
active polarities, detailed timing, VCC5/VCCIO current consumption and configured
FLAG fault semantics remain unknown without the full documentation.

The [Nexperia BUK9230-100B datasheet](https://assets.nexperia.com/documents/data-sheet/BUK9230-100B.pdf)
confirms gate1, source3 and drain at the mounting base (represented by pad2).
Every exported electrical pin has a corresponding physical footprint pad.
This check does not establish MOSFET SOA, cooling or a complete diode/inductor
procurement audit.

The 130 local footprints are extracted from the source PCB with `pcbnew`, with
placement and nets removed. They retain source geometry. In particular, the
source PT footprint has a 5 mm exposed-pad name and an ADV7611 description;
NXP specifies a 4.9 mm package exposed pad. Land pattern, solder mask, paste and
thermal vias require a separate review. No assertion of correct NXP land pattern
follows from preserved geometry or matching pad numbers.

`provenance.json` carries source Git blobs, normalized SHA256 and manufacturer
references. No applicable GDI4 board license was found. The power topology,
symbols and footprint geometry are **derived from that source**, not independently
authored. The NXP evaluation schematic SPF-29357 was read only: its explicit use
restriction prevented copying its power circuit into this design. No upstream
source edit or physical hardware action occurred in this task. Derived review
artifacts are integrated into the existing project fork; that integration does
not resolve the source board's redistribution/license uncertainty.

## Interfaces and local supplies

U201/U301 have separate CS, RESET, FLAG and device DRVEN nets. Only GND, +3V3 and
the three SPI bus wires are shared. Each stage has its own VBAT_GDI_A/B feed,
boost rail and +5V_GDI_A/B supply. VBAT feeds still require independently reviewed
fusing, reverse-battery/load-dump protection and power-discharge design.

R299/R399 are DNP links between the MCU DRVEN request and the actual device net.
They **must remain DNP** until a real hardware inhibit circuit and PT electrical
truth table are reviewed. An open assembly boundary is not a watchdog or
single-fault-tolerant safety architecture. The source 1 kOhm pulldowns are retained
as source values; they do not prove an active-low/active-high safety contract.

DI1–4 and DI5–8 are proposed START1–4 wiring assignments for each stage. Firing
semantics require verified PT microcode. HPFP1/2 are deliberately not assigned
to START5/6. Source high-side labels H1/H2/H5 are physically one bank, and
H3/H4/H6 a second bank; the sheet now gives each bank one name. Connector and
actuator mapping must respect this topology. Source H5PUMP/L6PUMP are preserved
descriptive names, not proof of an approved HPFP configuration.

Each U249/U349 is a provisional NCV78M05ABDTRKG local regulator, with input
330 nF/50 V, output 100 nF/25 V and 910 Ohm/1% minimum load. Its pin mapping and
variant follow [onsemi MC78M00/D Rev29](https://www.onsemi.com/pdf/datasheet/mc78m00-d.pdf).
The family is rated to 500 mA only with adequate heatsinking. The selected AB
variant is specified over -40 to125 C, with a 7–20 V regulation test range and
4.80–5.20 V output over the stated load conditions. Input35 V is an absolute
maximum, not a transient rating. Typical dropout is2 V. Approximate dissipation
is `(Vin - 5)*Iload + Vin*Iquiescent`: at12 V and100 mA, the pass term alone is
0.7 W; at500 mA it is3.5 W. Minimum-load power is about27.5 mW at5 V;
4.8 V across the maximum919.1 Ohm still draws over5 mA. These examples are not
PT2001 current estimates. Actual VCC5 and shared3V3 VCCIO budgets are UNKNOWN;
PCB temperature and crank-voltage behavior remain release blockers.

## Actual validation

Environment: Windows Python3.12.10, Docker KiCad9.0.9, image
`kicad/kicad:9.0`, digest
`sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`.

```text
python Power8GDI/hardware/design/gdi/generate.py
python Power8GDI/hardware/design/gdi/verify.py --kicad
Ran 11 tests ... OK
Fresh source XML: 94 nets / 343 retained component pins per stage, exact parity PASS
Both stage XML exports: 134 components, all pin-to-pad checks PASS
Stage A ERC: 19 violations, 8 errors + 11 warnings; native exit5
Stage B ERC: 19 violations, 8 errors + 11 warnings; native exit5
```

ERC is **not clean**. Each standalone sheet reports3 undriven SPI/CS inputs,
5 power nets without a recognized power-output driver (including passive boost
and VCCIO paths), and11 single-use global interface/optional diagnostic labels.
The raw reports are retained; no issue is excluded or globally disabled. The
full hierarchy must resolve real drivers and any justified power-source markers.
The structural checker returning0 does not override the ERC failures.
`verify.py --require-ready` returns2 while the release remains blocked.

The tests also detect deliberate broken/shorted source nets, independent stage
controls/rails, DNP enable isolation, corrected PT pin metadata, BOM/export
consistency, regulator wiring and missing HPFP assignment. An SVG was rendered
and visually inspected. No MCU build, physical measurement, thermal/EMC test,
fault injection or engine test was performed here. PCB routing/DRC belongs to
the separately integrated board checkpoint; this report makes no board claim.
