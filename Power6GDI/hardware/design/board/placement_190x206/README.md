# Placement candidate 190 x 206 (donor GDI copper)

**Incomplete engineering placement. Do not fabricate, energize or claim qualification.**

Built on 2026-11-05 with the pinned KiCad 9.0.9 image from
`layout_profiles/190x206_donor.json` (owner decision: option b, keep the GDI-4ch
donor copper on a single 190 mm wide board):

```text
python3 Power6GDI/hardware/design/board/build_board.py \
  --layout-profile Power6GDI/hardware/design/board/layout_profiles/190x206_donor.json \
  --output-dir Power6GDI/hardware/design/board/placement_190x206
kicad-cli pcb drc --format json --all-track-errors --severity-all -o drc.json Power8GDI_Review.kicad_pcb
```

- 1092 positions, 3464 pins, no pad/net mismatch; every reviewed local route
  group (ignition 24, shunt returns 2, WBO CAN/VIO/reset/grounds/supply/regulator)
  applied in the translated stage B / WBO frame.
- 2088 unconnected items. DRC (capped report): clearance 502, track_width 199,
  via_dangling 14, track_dangling 5 — the same categories as the 245 x 165
  baseline; no copper-to-edge or new categories.
- No courtyard bounding-box overlap involves a fixed part (connectors, MCU,
  ignition cells); the 16 overlaps inside the donor blocks match the baseline.

## Ground stitching (2026-11-05)

`ground_stitch.py` adds one 0.65/0.3 mm via and a 0.3 mm stub beside one pad of
every GND island (pads that tracks and fills do not join to the In1 plane),
after checking the candidate against other-net copper on F/In2/B with the
voltage-domain clearances, every drill, every mask opening and the board edge:

```text
python3 Power6GDI/hardware/design/board/ground_stitch.py   Power6GDI/hardware/design/board/placement_190x206/Power8GDI_Review.kicad_pcb   --layout-profile Power6GDI/hardware/design/board/layout_profiles/190x206_donor.json
```

- 652 GND islands found; **534 stitched**, 118 reported as having no admissible
  position within 6 mm of the pad body (dense 0402 fields of the donor blocks
  and the packed cells, and pads inside PT2001 switching-net / ignition
  clearance zones). They stay in `ground_stitch.json`, not forced.
- Unconnected items **2088 → 1553**. Stub length median 1.26 mm, max 7.4 mm.
- DRC after refill (capped report): clearance 502, track_width 199,
  via_dangling 14, track_dangling 5; no violation lists a stitched via or stub.
- The plane, its return paths, the stitch density and the 118 islands remain
  review items; this is connectivity for a placement candidate only.

`gdi6_candidate/` remains the sealed 245 x 165 review candidate that the BOM and
cost report are bound to. File names keep the historical `Power8GDI_` prefix.
Context: `docs/PCB_LAYOUT_PROFILE_2026_11_05.md`.
