# Autorouted candidate 190 x 206 — machine copper, NOT reviewed

**Do not fabricate, energize or treat any track here as designed.** This directory
is the hand-checked placement candidate (`../placement_190x206/`, after GND
stitching) plus whatever Freerouting produced on it. Nobody has reviewed return
paths, loop areas, current capacity, thermal or EMC behaviour of the added copper.
The placement candidate itself is unchanged.

## How it was produced (2026-11-06)

- Export: `autoroute_candidate.py export` → Specctra DSN of the stitched candidate
  (sha256 in `autoroute_report.json`); net classes GDI_HV / Ignition_HV / Power /
  LogicSupply with their widths and clearances went into the DSN.
- Router: Freerouting 2.5.0 (jar from the GitHub release; the native CLI binary of
  the same release crashes in its routing thread on this board) on Temurin 25 in a
  container without network. Fanout pre-pass disabled: with it enabled the router
  spent all ten passes on fanout (about 1050 extra vias) and never reached routing.
  Settings: `router.autorouter.max_passes = 1`, 6 optimizer threads.
- Why one pass: a ten-pass run hit its 12 h job limit during pass 4 with pass 1 at
  840 unrouted (4.1 h), pass 2 at 1135 and pass 3 at 1078 — the ripup passes
  oscillated rather than converged, and its saved mid-pass-4 state imported to
  878 unconnected with 4 copper-to-edge violations. The single pass reproduced
  the 840 / score 602.66 result exactly (4 h 19 min) and imports better.
- Import: `autoroute_candidate.py import` into a copy, zones refilled, title set to
  "AUTOROUTED CANDIDATE". Nothing was removed on HARNESS_IGN* because the router
  could not route those nets at all (2.5 mm rule against the 3 mm TE34 pitch).

## Result

| | before | after |
|---|---|---|
| unconnected items (KiCad) | 1553 | **675** |
| router copper | – | 7890 tracks, 1397 vias |

DRC (capped report, KiCad 9.0.9): clearance 500, track_width 199, via_dangling 10,
track_dangling 5 — the same categories as the placement candidate, no new ones. 3413 pre-existing violations in the donor
copper were reported by the router before it started and are unchanged.

Visible review items in `front.png` / `back.png` / `in2.png`: wide GDI_HV / boost
class traces routed on In2 under the donor power stages; long 45° runs across the
analog and MCU regions; via count. These are reasons this is a candidate for
reading, not a layout.

## Measured on 2026-11-10

`../review_autoroute.py` measured this copper block by block
(`docs/reviews/2026-11-10-autoroute-review/autoroute_review.json`, verdicts in
`docs/PCB_AUTOROUTE_REVIEW_2026_11_10.md`). Headline: the router treated In1.Cu
(the GND plane) as a signal layer — 626 tracks, 3 026 mm, main plane polygon
36 624 → 33 557 mm² and five fragments — and the project's own clearance rule is
violated by 2 328 of its 9 287 items (the DRC report is capped at 500 and cannot
show this). `in1.png` shows the In1 tracks and holes; the export does not draw
the fill. No block's copper is accepted as is.

Reproduce: `build/p6/autoroute/run_freerouting_1pass.sh` then
`review_autoroute.sh` (scripts in the ignored build directory of the working tree
that produced this; the Python steps are in `../autoroute_candidate.py`).
