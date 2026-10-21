# Review PCB builder

**Incomplete engineering PCB. Do not fabricate, energize or claim qualification.**
The original placeholder PCB is untouched. This folder builds real footprints,
pad nets and routed subdomains from the current electrical hierarchy.

Use the pinned official `kicad/kicad:9.0` image, KiCad9.0.9; digest is recorded
in `source_provenance.json`. No network is needed during generation. Mount the
repository at`/src`, set working directory`/src`, and run:

```text
python3 Power8GDI/hardware/design/board/build_connector_schematic.py
kicad-cli sch export netlist --format kicadxml -o Power8GDI/hardware/design/board/connectors.xml Power8GDI/hardware/design/board/connectors.kicad_sch
python3 Power8GDI/hardware/design/board/build_board.py
python3 Power8GDI/hardware/design/board/verify_board.py Power8GDI/hardware/design/board/review/Power8GDI_Review.kicad_pcb Power8GDI/hardware/design/core.net
kicad-cli pcb drc --format json --all-track-errors --severity-all --exit-code-violations -o Power8GDI/hardware/design/board/review/drc.json Power8GDI/hardware/design/board/review/Power8GDI_Review.kicad_pcb
```

The authoritative integrated root XML is `design/core.net`. It includes
J601..604, so the current verifier uses only this XML. Duplicate refs
and conflicting pad assignments are errors. Before root integration the
builder also accepts whole separate GDI/power XML sheets; a partially duplicate
hierarchy is rejected. `--design-root`, `--source-board`, `--pinout` and
`--output-dir` support isolated build snapshots without editing source designs.

Source electrical flags includingDNP and BOM exclusion are carried to the
physical board and independently compared on reload. A source off-board
component fails instead of silently becoming a physical pad.

The copper transfer uses KiCad's actual source connectivity graph, exact
oldref→newref mapping and sourcepad→targetnet mapping. It rejects any source
net that would join two distinct target nets. Branches terminating at removed
logic/connectors and open physical endpoints are removed. Ground vias count
as real plane endpoints only with a retained pad. Groundplane fill and DRC are
run on the resulting board. Reference power/sense-zone shapes remain visible;
source clearances are **not** automatically accepted as new design rules.

The stageB reference3V3/5V supply buses cross the provisional edge when rotated;
they are explicitly omitted for rerouting to the new regulators. Remaining
unrouted connections are reported, not represented by invented tracks.

The provisional outline245×165mm,4-layer1.6mm stackup and clearances are design
inputs, not a manufacturer's approved stackup. Outer copper70µm, inner35µm,
dielectrics120/1130/120µm, soldermask10µm each side are an engineering proposal.
Current, thermal, impedance, transient, dielectric and assembly budgets remain
open. PCB pads/trace exports alone do not demonstrate electrical qualification.

Run portable contract tests with:

```text
python -m unittest discover -s Power8GDI/hardware/design/board/tests -v
```

`render_preview.py` optionally converts actual KiCad SVG plots toPNG using
PyQt6/QtSvg. It does not infer or invent copper. Rendered exports and full DRC
reports belong in the chosen build/output directory; no manufacturing Gerber
release is produced while the DRC and functional gates fail.
