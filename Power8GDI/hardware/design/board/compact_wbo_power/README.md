# Compact WBO power tile — integration candidate

This is a **20 × 18 mm local power tile**, not the full WBO circuit, compact ECU
PCB, or a manufactured daughterboard. It contains the ten existing LT3042 and
REF3033 supply components copied from the real baseline PCB, with unchanged
values, lands and pad/net assignments. The old full PCB and its generator remain
unchanged. The standalone outline is a fixture boundary for DRC and must not be
copied into a full-board Edge.Cuts outline.

## Completed local connections

- IN1/2, EN3 and PGFB6 share +5V_CORE, with Cin and the REF input bypass.
- REF3033 output drives SET through the existing 220 Ω resistor; the 30 kΩ
  bleed and 100 nF SET capacitor are connected.
- OUT10 feeds Cout and the output bleed. OUTS9 reaches Cout1 through a separate
  Kelvin branch. SET capacitor/resistor grounds reach Cout2 through a separate
  quiet branch, without a via or early power-ground connection.
- REF ground and its bypass returns use a separate branch to Cout2. They do
  not return through the loaded EP ground path or the SET quiet branch.
- GND8 and ILIM5 reach EP11. One EP via contacts the In1 ground plane. This is
  a connectivity result, **not** a demonstrated thermal solution.
- PG4 retains its original unconnected net. No schematic functionality changed.

The implementation follows the Kelvin topology in the
[LT3042 Rev. C datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/lt3042.pdf),
pin functions and Output Sensing and Stability discussion. Exact effective
Cin/Cout capacitance, ESR/ESL, loop stability, load response, thermal dissipation
and noise remain hardware qualification gates.

## Integration API and interfaces

`build_tile.build(output, origin=(0,0), rotation=0)` creates a standalone fixture.
`--origin X Y --rotation DEG` applies a rigid translation/rotation to footprints,
copper, outline and rule areas. Manifest geometry includes both canonical and
transformed world coordinates. Generated footprint-library paths are relative
to the chosen output directory; they reference the repository libraries.

Electrical ports are existing lands, not new connectors:

| Port | Land | Meaning |
|---|---|---|
| +5V_CORE | C5661.1 | Input from the future main +5 V distribution |
| GND | C5662.2 | Load return / Kelvin star |
| WBO1_3V3 | C5662.1 | Output to WBO load distribution |

**The main +5 V regulator is not connected in this standalone tile.** WBO MCU,
analog loads, CAN, heater control and their distribution are outside its scope.
No complete WBO, full compact-board DRC, enclosure fit or engine release is claimed.

Reserve the tile polygon on both outer layers. Retain its actual B.Cu copper-pour
keepout: a same-net fill would otherwise bypass the Kelvin star without a normal
short-circuit DRC error. Do not insert foreign copper, vias or loaded returns in
the reserved area without rerunning geometry, connectivity and DRC checks. Keep
boost/ignition/motor switching paths outside the quiet supply region. The final
floorplan must review return partitioning, source impedance, proximity to the
load, Cin/Cout loop length and case heat transfer. No EMI spacing or thermal
qualification is inferred solely from this bounding box.

## Reproduce and verify

Use KiCad 9.0.9 Python and CLI (pinned image
`kicad/kicad@sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`).
From this directory, with repository libraries accessible:

```text
python3 build_tile.py
kicad-cli pcb drc --format json --all-track-errors --severity-all --exit-code-violations -o candidate/drc.json candidate/WBO_Power.kicad_pcb
python3 test_tile.py
```

The frozen candidate has native DRC **0 violations / 0 unconnected items**.
`test_tile.py` passed one test containing four placements (0°, 90°, 180°, 270°),
checking every transformed route endpoint, ports, retained keepout, EP plane
contact, unchanged source PCB, and real CLI DRC in temporary output directories.
All four DRC runs returned success. Independent electrical/Kelvin audit and
fault-injection tests are maintained separately by the integrating reviewer.

Independent verification on the frozen candidate also passed: all 30 electrical
lands match `core.net`, component values and land sizes match the source PCB,
all local nets connect through actual tracks/pads, and polygon intersections
confirm no early merge for SET ground, OUTS, or the REF ground branch. Seven
independent tests passed, including injected SET/REF ground shortcuts, an
OUT–OUTS shortcut, a disconnected reference, a wrong net, and a shrunken land.
Reports are `candidate/independent_audit.json`, `independent_tests.log`, and
`drc.provenance.json`. The final native DRC was rerun independently with the
original project and rule files byte-for-byte unchanged. The source full PCB
still has SHA-256 `638900cd40914d65b20f752ccf2698f53bb84e6ac96d56a0a211c24fb287576f`.

```text
python3 independent_audit.py candidate/WBO_Power.kicad_pcb candidate/manifest.json ../../core.net
python3 -m unittest discover -s . -p test_independent_audit.py -v
```

Frozen candidate SHA-256:
`1be7af6e1ee1b9cbaa83a82b546397d794df142d0f1f54570ecd72bf63d6c80c`.
Build logs include KiCad SWIG teardown warnings; successful process exits and
the actual DRC JSON are the reported verification results.
