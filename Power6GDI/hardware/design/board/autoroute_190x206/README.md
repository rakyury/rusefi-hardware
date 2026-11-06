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
  Settings: `router.autorouter.max_passes = 10`, 6 optimizer threads.
- The job stopped at its 12 h wall-clock limit during pass 4 and saved that state:
  pass 1 left 840 unrouted (4.1 h), pass 2 1135, pass 3 1078 — the ripup passes
  oscillated rather than converged.
- Import: `autoroute_candidate.py import` into a copy, zones refilled, title set to
  "AUTOROUTED CANDIDATE". Nothing was removed on HARNESS_IGN* because the router
  could not route those nets at all (2.5 mm rule against the 3 mm TE34 pitch).

## Result

| | before | after |
|---|---|---|
| unconnected items (KiCad) | 1553 | **878** |
| router copper | – | 9164 tracks, 1572 vias |

DRC (capped report, KiCad 9.0.9): clearance 502, track_width 199, via_dangling 11,
track_dangling 4, **copper_edge_clearance 4** (new: the router kept 0.25 mm to the
edge where the project rule is 0.5 mm). 3413 pre-existing violations in the donor
copper were reported by the router before it started and are unchanged.

Visible review items in `front.png` / `back.png` / `in2.png`: wide GDI_HV / boost
class traces routed on In2 under the donor power stages; long 45° runs across the
analog and MCU regions; via count. These are reasons this is a candidate for
reading, not a layout.

Reproduce: `build/p6/autoroute/run_freerouting_nofanout.sh` then
`review_autoroute.sh` (scripts in the ignored build directory of the working tree
that produced this; the Python steps are in `../autoroute_candidate.py`).
