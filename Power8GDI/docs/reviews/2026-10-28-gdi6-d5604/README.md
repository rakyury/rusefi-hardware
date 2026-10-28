# D5604 silk correction — 2026-10-28

Baseline: 98208688a45204fe52cf7921d42b3367e5539ce5.
PCB SHA-256: 0ab109350b42bd0286b5aaaa88ac83b4ddd04a17f6802320568667b6ebe970c4.

J5600 mask clipped two D5604 outline strokes. A local `Power8GDI_Board:SOT-23_D5604_J5600_Clearance` footprint shortens the upper outline and relocates its 0.05 mm stub to the new endpoint. Both remain silk; all object UUIDs and the pin-1 triangle are preserved. The original standard library is unchanged. The source copy alongside this report is from pinned KiCad image `sha256:e638b79b0321f29395a5b783e94bb9f3c73303e8da15da27b8f5cb4b67a37729`, `/usr/share/kicad/footprints/Package_TO_SOT_SMD.pretty/SOT-23.kicad_mod`.

The schematic generator, selection binding exception for D5604 only, netlists, BOM and PCB use the same variant. Electrical connectivity, all 1092 component MPNs, quantities and pad/copper/mask/paste geometry are unchanged; see independent parsed comparison. WBO verification now resolves the project library explicitly. Board generation loads this custom library and verifies its mask clearance after placement.

## Verification

- Native KiCad 9.0.9 full DRC: silk-over-mask **2 -> 0**, library mismatch **0**; no exclusions or relaxed rules.
- Full connectivity remains **2099**; dangling via 14 and dangling track 4 remain. Clearance and width reports are capped and not a completeness/progress metric.
- Pad/net verification: 1092 positions, 3464 assignments, no errors; twenty shunt apertures intact.
- 19 board tests, 36 core tests, 18 strict costing freshness tests passed. Full schematic review passed its structural checks; the existing 12 dangling-global-label ERC findings remain.
- Complete review commands and outputs: `hardware/design/review_validation.json`. Full DRC and hash provenance: `hardware/design/board/gdi6_candidate/`.
- Assembly remains 1047 fitted positions, 3210 SMT lands, 162 THT lands; cost totals unchanged. PDF has 49 pages; contact sheet and page 41 inspected after export.

Board remains an incomplete engineering candidate, not ready for fabrication. The integration owner will refresh delivery PDF/Excel provenance after accepting this commit.
