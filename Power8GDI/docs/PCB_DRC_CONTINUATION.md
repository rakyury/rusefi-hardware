# PCB correction checkpoint, 2026-10-21

This is an engineering checkpoint, not a manufacturing release. The current
full design is still changing; the comparison below uses the 631-part board at
integration `daf7c81`, not the later 775/987-part schematic.

## Actual corrections

- Derived `HSOP8_EP_ThermalVia0p3` preserves every non-hole package land and
  changes only six EP holes from 0.2 to 0.3 mm, with 0.6 mm annular lands. Parent
  schematic now selects it for U501/U901/U951. Reflow/fabrication qualification
  remains open. Generator and source hash accompany the footprint.
- Connector silk ends 0.3 mm before the board edge; physical Fab/courtyard and
  all 34 contact coordinates remain unchanged.
- References remain visible at 0.8 mm height, are moved clear of actual pad and
  graphic bounds, and retain unresolved local placement conflicts in the report.
- KiCad's own endpoint predicate removes donor dead tails after zone filling.
  A deletion is rejected if the unconnected count increases. The regression
  removed 60 segments, retained two DI tails, and kept the count at 999 (CLI
  unconnected-item count 499). Vias are not automatically discarded.
- The previous builder wrote the project rules before its final `SaveBoard`.
  The in-process KiCad project cache then overwrote the intended minimum track
  width with **0.0 mm**. Rules now have current schema metadata and priorities,
  are written **after the final board save**, and are tested in a separate
  KiCad process. Explicit equivalent power/HV rules also travel with the board;
  `run_drc.py` now copies and hashes `.kicad_dru`.
- The provisional limits remain 0.2 mm minimum track/clearance, 0.3 mm drill,
  0.3 mm supply clearance and 0.6 mm named GDI boost/drive clearance. No DRC
  exclusions or reduced limits were added.

## Regression evidence

Nine tests pass under the pinned KiCad 9.0.9 image, including preservation of
package lands, connector pad count, rule persistence across process boundaries,
and the pre-existing pin/net/DNP contract tests.

The corrected-rule 631-part comparison (before installing the new thermal
footprint into that old snapshot) reports:

| DRC category | Earlier snapshot | Correction comparison |
|---|---:|---:|
| Clearance | 511 | 509 |
| Track width | 0 checked under the intended limit | 199 newly exposed |
| Drill range | 18 | 18, old footprint still in this regression snapshot |
| Dangling track | 17 | 2 |
| Dangling via | 7 | 12 |
| Silk over copper | 54 | 6 |
| Silk overlap | 109 | 33 |
| Silk at edge | 12 | 0 |
| Text height | 24 | 0 |

The corrected run is **779 violations plus 499 missing connections**, not a
passing DRC. Of the clearance reports, 413 use the 0.2 mm default, 53 explicitly
use the 0.3 mm power rule, and 43 explicitly use the 0.6 mm HV rule. This proves
that the full rule set is actually being evaluated. The increase in dangling
vias follows removal of formerly attached dead branches and remains visible.

## Placement and routing work still open

The strict grouped-output experiment found no position for its first 24-part
four-channel group in the proposed B.Cu region x156–239/y95–141 mm with existing
GDI copper/vias. This disproves that particular placement template, not every
possible 245×165 mm layout. `--grouped-outputs` fails explicitly on the conflict.
Without that option the existing diagnostic staging mode is still marked
`staged_unreviewed_placements`; it is not a functional layout approval.

An enlarged outline is now authorized by the integration lead; it will need a
new enclosure/connector fit review. No drop-in mechanical compatibility is
claimed.

`route_logic.py` is an experimental offline DSN/SES adapter. It protects existing
copper and imports only an explicit list of logic nets. The export proxy reserves
both GDI domains and the inner ground plane. A generic router is not allowed to
redesign GDI boost, gate or Kelvin paths. No automatic routing result is accepted
by this checkpoint; every candidate still requires the full native DRC and
pin/net consistency verification. Freerouting 2.5.0 native CLI failed in its
serialization layer; the isolated Java runs have not yet yielded a verified
session. Tools run with `--network none`; no board data is uploaded.

## Commands

From the repository root, inside `kicad/kicad:9.0`:

```text
python3 -m unittest discover -s Power8GDI/hardware/design/board/tests -v
python3 Power8GDI/hardware/design/board/build_board.py --output-dir build/board
python3 Power8GDI/hardware/design/board/run_drc.py build/board/Power8GDI_Review.kicad_pcb --output build/board/drc.json
```

The DRC wrapper returns nonzero when violations remain. Do not interpret a
successfully parsed/generated file as a successful DRC or qualification.
