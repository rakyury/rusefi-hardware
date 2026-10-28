# PCB checkpoint, 23 October 2026

Engineering checkpoint only. Fabrication gate remains FAIL.

The actual KiCad9.0.9 board is `hardware/design/board/layout_candidate/Power8GDI_Review.kicad_pcb`, with front/back SVG and PNG exports from that board. Original 245 × 165 mm outline, four copper layers and four TE34 connector positions are retained. Both images omit the drawing sheet; the back image uses the same top-view coordinate convention as the front.

Source is the 1236-component / 3873-pin integrated netlist, SHA256 `171a2d234b448750f7baa44831ddb6fb832127faa1dc90f3db1f43f0cffcfbe0`. Independent saved-board verification reports zero pad-net, footprint, value or assembly-flag mismatches. Updated WBO supply components are not yet in this snapshot.

New components are placed in functional regions with actual package/pad obstacles. All copper layers are checked for through-hole/thermal pads, not merely the component assembly side. Correcting that check eliminated the first candidate's 82 reported shorts, 77 hole-clearance conflicts and 54 mask bridges. The current DRC has zero reported errors in those categories. Placement is still a review candidate: generic net-neighbour attraction does not certify buck hot loops, WBO feedback, grounding or EMC.

Eight ignition cells have 32 explicit connections: series gate resistor to gate, gate-emitter pulldown branches and emitter to shunt. Actual endpoint nets are verified before adding copper. Emitter necks are provisionally 1.0 mm; there is no current/thermal qualification. Collector harness routes, shared high-current returns and shunt Kelvin routes remain unfinished. The saved board contains 2602 tracks/vias; its full KiCad connectivity residual is 2535 missing connections.

## DRC report limits

The recorded report contains 926 violations, including 501 clearance and 199 track-width entries, plus 499 unconnected entries. These are **capped samples, not complete totals**. KiCad9.0.9 [DRC engine source](https://raw.githubusercontent.com/KiCad/kicad-source-mirror/9.0.9/pcbnew/drc/drc_engine.cpp), lines47–48 and571–578, sets per-category limits of199, extended to499 for clearance/unconnected; concurrent providers can slightly overshoot a cap. `--all-track-errors` does not remove these limits. `net_coverage.json` records the cap flag and separate full connectivity count. A net missing from the capped report must not be labelled fully routed.

The current explicit rules were not relaxed to obtain a pass. Remaining issues include donor GDI copper designed with smaller signal/sense dimensions, provisional boost/ignition clearances, and the broad 0.3 mm low-voltage supply rule conflicting with 0.5 mm-pitch packages. These require a targeted engineering rules review and/or geometry changes, not exclusions. The TE connector repetitive-ignition qualification gate is documented separately in `PCB_IGNITION_INSULATION.md`.

## Reproduction

In the pinned KiCad9 Docker environment, invoke `build_board.py --functional-layout --output-dir .../layout_candidate`; the builder includes local ignition routing. `verify_board.py <board> <core.net>` independently checks the saved pins. `run_drc.py <board> --output <drc.json>` records source hashes and intentionally returns nonzero while violations remain. `summarize_drc.py <board> <drc.json> <net_coverage.json>` exposes report caps. SVG exports use `--mode-single --exclude-drawing-sheet --page-size-mode 2` with F.Cu/F.Silkscreen/Edge.Cuts or B.Cu/B.Silkscreen/Edge.Cuts.

The final full rebuild was interrupted before save; the saved all-layer-checked placement was incrementally updated by `route_ignition_local.py <board>`, then independently reverified and rerun through DRC. That command refuses a duplicate application. Subsequent root WBO updates require a fresh build.
